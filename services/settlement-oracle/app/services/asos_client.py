"""Client for the Iowa Environmental Mesonet (IEM) ASOS/AWOS data service.

The IEM provides a free, REST-accessible archive of US ASOS/AWOS observations.
We query this service to get official sensor readings for settlement.

Docs: https://mesonet.agron.iastate.edu/request/download.phtml
"""

import csv
import io
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import h3
import httpx

from app.core.config import settings
H3_RESOLUTION = 7  # Must match app.pipeline.h3_indexer.H3_RESOLUTION

logger = logging.getLogger(__name__)

# Known ASOS stations and their coordinates.
# In production, this would be a database table populated from FAA/NOAA station lists.
# For the MVP we include a representative sample.
STATION_COORDS: dict[str, tuple[float, float]] = {
    "KJFK": (40.6413, -73.7781),
    "KLAX": (33.9425, -118.4081),
    "KORD": (41.9742, -87.9073),
    "KATL": (33.6407, -84.4277),
    "KDEN": (39.8561, -104.6737),
    "KDFW": (32.8998, -97.0403),
    "KSFO": (37.6213, -122.3790),
    "KBOS": (42.3656, -71.0096),
    "KMIA": (25.7959, -80.2870),
    "KSEA": (47.4502, -122.3088),
}


@dataclass
class StationObservation:
    """A single observation from one ASOS/AWOS station."""

    station_id: str
    observed_at: datetime
    latitude: float
    longitude: float
    h3_cell: str
    precipitation_mm: float | None = None
    wind_speed_ms: float | None = None
    quality_flag: str | None = None


@dataclass
class CellObservationBundle:
    """All station observations within a single H3 cell for a time window."""

    h3_cell: str
    window_start: datetime
    window_end: datetime
    observations: list[StationObservation] = field(default_factory=list)

    @property
    def station_count(self) -> int:
        return len({obs.station_id for obs in self.observations})


def get_stations_in_cell(h3_cell: str) -> list[tuple[str, float, float]]:
    """Return known ASOS stations whose coordinates fall inside the given H3 cell.

    Returns:
        List of (station_id, lat, lon) tuples.
    """
    matches = []
    for station_id, (lat, lon) in STATION_COORDS.items():
        cell = h3.latlng_to_cell(lat, lon, H3_RESOLUTION)
        if cell == h3_cell:
            matches.append((station_id, lat, lon))
    return matches


async def fetch_asos_observations(
    station_id: str,
    start: datetime,
    end: datetime,
) -> list[dict]:
    """Fetch ASOS observations from IEM for a given station and time range.

    Returns raw observation dicts parsed from CSV.
    """
    params = {
        "station": station_id,
        "data": "p01m,sknt",  # precip 1-hr (mm) and wind speed (knots)
        "tz": "Etc/UTC",
        "format": "comma",
        "latlon": "yes",
        "year1": start.strftime("%Y"),
        "month1": start.strftime("%m"),
        "day1": start.strftime("%d"),
        "hour1": start.strftime("%H"),
        "year2": end.strftime("%Y"),
        "month2": end.strftime("%m"),
        "day2": end.strftime("%d"),
        "hour2": end.strftime("%H"),
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(settings.asos_base_url, params=params)
        resp.raise_for_status()

    rows: list[dict] = []
    reader = csv.DictReader(io.StringIO(resp.text))
    for row in reader:
        # Skip comment / header rows
        if row.get("station", "").startswith("#"):
            continue
        rows.append(row)

    logger.info("Fetched %d ASOS observations for %s (%s – %s)", len(rows), station_id, start, end)
    return rows


def _knots_to_ms(knots: float) -> float:
    """Convert knots to meters per second."""
    return knots * 0.514444


def _safe_float(val: str | None) -> float | None:
    """Parse a float, returning None for missing or 'M' (missing) markers."""
    if val is None or val.strip() in ("", "M", "T"):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


async def get_cell_observations(
    h3_cell: str,
    window_start: datetime,
    window_end: datetime,
) -> CellObservationBundle:
    """Fetch all ASOS observations for stations inside an H3 cell over a time window.

    This is the primary function used by the settlement engine.
    """
    stations = get_stations_in_cell(h3_cell)
    bundle = CellObservationBundle(
        h3_cell=h3_cell,
        window_start=window_start,
        window_end=window_end,
    )

    for station_id, lat, lon in stations:
        try:
            raw_obs = await fetch_asos_observations(station_id, window_start, window_end)
        except httpx.HTTPError as exc:
            logger.warning("Failed to fetch ASOS data for %s: %s", station_id, exc)
            continue

        for row in raw_obs:
            precip = _safe_float(row.get("p01m"))
            wind_knots = _safe_float(row.get("sknt"))
            wind_ms = _knots_to_ms(wind_knots) if wind_knots is not None else None

            try:
                observed_at = datetime.strptime(row["valid"], "%Y-%m-%d %H:%M")
            except (KeyError, ValueError):
                continue

            bundle.observations.append(
                StationObservation(
                    station_id=station_id,
                    observed_at=observed_at,
                    latitude=lat,
                    longitude=lon,
                    h3_cell=h3_cell,
                    precipitation_mm=precip,
                    wind_speed_ms=wind_ms,
                    quality_flag=row.get("metar", None),
                )
            )

    logger.info(
        "Cell %s: %d observations from %d stations",
        h3_cell, len(bundle.observations), bundle.station_count,
    )
    return bundle
