"""NWS forecast service — pulls ensemble percentiles and derives exceedance probabilities.

For week-1 "naive" pricing this service:
1. Converts the H3 cell to a centroid lat/lng.
2. Calls the NWS API (api.weather.gov) to fetch the probabilistic forecast grid.
3. Extracts the probability-of-precipitation (PoP) and QPF percentiles.
4. Derives an exceedance probability relative to the risk-type threshold.

If the NWS API is unreachable, falls back to a latitude/season-based
climatological baseline — good enough for week-1 while the full HRRR
ingestion pipeline is wired in.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone

import h3
import httpx

from app.core.config import settings
from app.models.schemas import RiskType

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ForecastEstimate:
    """Exceedance probability + confidence bounds for a risk type."""

    probability: float
    confidence_lower: float
    confidence_upper: float
    source: str  # "nws_api" or "climatological_baseline"


async def get_risk_forecast(
    h3_index: str,
    risk_type: RiskType,
    start_time: datetime,
    end_time: datetime,
) -> ForecastEstimate:
    """Return an exceedance-probability estimate for the given cell and risk window."""
    lat, lng = h3.cell_to_latlng(h3_index)

    try:
        estimate = await _fetch_nws_forecast(lat, lng, risk_type, start_time, end_time)
        if estimate is not None:
            return estimate
    except Exception:
        logger.warning("NWS API call failed for (%s, %s), falling back", lat, lng, exc_info=True)

    return _climatological_baseline(lat, lng, risk_type, start_time, end_time)


async def _fetch_nws_forecast(
    lat: float,
    lng: float,
    risk_type: RiskType,
    start_time: datetime,
    end_time: datetime,
) -> ForecastEstimate | None:
    """Try to pull a real forecast from the NWS API."""
    async with httpx.AsyncClient(
        timeout=settings.nws_request_timeout,
        headers={"User-Agent": "(atmx-risk-api, contact@atmx.dev)", "Accept": "application/geo+json"},
    ) as client:
        points_resp = await client.get(f"{settings.nws_api_base}/points/{lat:.4f},{lng:.4f}")
        if points_resp.status_code != 200:
            return None

        props = points_resp.json().get("properties", {})
        grid_url = props.get("forecastGridData")
        if not grid_url:
            return None

        grid_resp = await client.get(grid_url)
        if grid_resp.status_code != 200:
            return None

        grid_data = grid_resp.json().get("properties", {})
        return _extract_probability(grid_data, risk_type, start_time, end_time)


def _extract_probability(
    grid_data: dict,
    risk_type: RiskType,
    start_time: datetime,
    end_time: datetime,
) -> ForecastEstimate | None:
    """Extract exceedance probability from NWS gridpoint data.

    The NWS gridpoint JSON exposes time-series arrays keyed by metric name.
    Each value has {"validTime": "ISO/duration", "value": ...}.
    """
    if risk_type in (RiskType.PRECIP_HEAVY, RiskType.PRECIP_MODERATE):
        pop_values = _get_values_in_window(
            grid_data.get("probabilityOfPrecipitation", {}), start_time, end_time
        )
        qpf_values = _get_values_in_window(
            grid_data.get("quantitativePrecipitation", {}), start_time, end_time
        )

        if pop_values:
            max_pop = max(pop_values) / 100.0
            threshold = 12.7 if risk_type == RiskType.PRECIP_HEAVY else 6.35
            max_qpf = max(qpf_values) if qpf_values else 0.0

            if max_qpf > 0:
                exceedance = max_pop * min(1.0, max_qpf / threshold)
            else:
                exceedance = max_pop * 0.3

            spread = max(0.02, exceedance * 0.3)
            return ForecastEstimate(
                probability=_clamp(exceedance, 0.001, 0.999),
                confidence_lower=_clamp(exceedance - spread, 0.001, 0.999),
                confidence_upper=_clamp(exceedance + spread, 0.001, 0.999),
                source="nws_api",
            )

    elif risk_type in (RiskType.WIND_HIGH, RiskType.WIND_EXTREME):
        wind_values = _get_values_in_window(
            grid_data.get("windSpeed", {}), start_time, end_time
        )
        if wind_values:
            max_wind_kmh = max(wind_values)
            max_wind_ms = max_wind_kmh / 3.6
            threshold = 20.0 if risk_type == RiskType.WIND_HIGH else 30.0
            ratio = max_wind_ms / threshold
            exceedance = _clamp(1.0 / (1.0 + math.exp(-4.0 * (ratio - 0.8))), 0.001, 0.999)
            spread = max(0.02, exceedance * 0.25)
            return ForecastEstimate(
                probability=exceedance,
                confidence_lower=_clamp(exceedance - spread, 0.001, 0.999),
                confidence_upper=_clamp(exceedance + spread, 0.001, 0.999),
                source="nws_api",
            )

    elif risk_type in (RiskType.TEMP_FREEZE, RiskType.TEMP_HEAT):
        temp_values = _get_values_in_window(
            grid_data.get("temperature", {}), start_time, end_time
        )
        if temp_values:
            if risk_type == RiskType.TEMP_FREEZE:
                min_temp = min(temp_values)
                exceedance = _clamp(1.0 / (1.0 + math.exp(2.0 * min_temp)), 0.001, 0.999)
            else:
                max_temp = max(temp_values)
                exceedance = _clamp(1.0 / (1.0 + math.exp(-0.5 * (max_temp - 38))), 0.001, 0.999)
            spread = max(0.02, exceedance * 0.2)
            return ForecastEstimate(
                probability=exceedance,
                confidence_lower=_clamp(exceedance - spread, 0.001, 0.999),
                confidence_upper=_clamp(exceedance + spread, 0.001, 0.999),
                source="nws_api",
            )

    return None


def _get_values_in_window(
    series: dict, start_time: datetime, end_time: datetime
) -> list[float]:
    """Extract numeric values from a NWS time-series that overlap the window."""
    values_list = series.get("values", [])
    results: list[float] = []

    for entry in values_list:
        val = entry.get("value")
        if val is None:
            continue

        valid_time = entry.get("validTime", "")
        try:
            iso_part = valid_time.split("/")[0]
            ts = datetime.fromisoformat(iso_part.replace("Z", "+00:00"))
        except (ValueError, IndexError):
            continue

        start_aware = start_time if start_time.tzinfo else start_time.replace(tzinfo=timezone.utc)
        end_aware = end_time if end_time.tzinfo else end_time.replace(tzinfo=timezone.utc)

        if start_aware <= ts <= end_aware:
            results.append(float(val))

    return results


def _climatological_baseline(
    lat: float,
    lng: float,
    risk_type: RiskType,
    start_time: datetime,
    end_time: datetime,
) -> ForecastEstimate:
    """Latitude/season heuristic when the NWS API is unavailable.

    Uses broad climatological patterns:
    - Tropics (|lat| < 25): higher precip probability
    - Mid-latitudes (25-50): seasonal variation
    - High latitudes (>50): higher freeze/snow probability
    """
    abs_lat = abs(lat)
    month = start_time.month if start_time else 6
    is_winter = month in (11, 12, 1, 2, 3)

    base_probs: dict[RiskType, float] = {
        RiskType.PRECIP_HEAVY: 0.12 if abs_lat < 25 else (0.08 if is_winter else 0.15),
        RiskType.PRECIP_MODERATE: 0.25 if abs_lat < 25 else (0.18 if is_winter else 0.30),
        RiskType.WIND_HIGH: 0.06 if abs_lat < 30 else 0.10,
        RiskType.WIND_EXTREME: 0.02,
        RiskType.TEMP_FREEZE: 0.01 if abs_lat < 25 else (0.40 if is_winter else 0.05),
        RiskType.TEMP_HEAT: 0.30 if abs_lat < 30 else 0.08,
        RiskType.SNOW_HEAVY: 0.01 if abs_lat < 30 else (0.15 if is_winter else 0.02),
    }

    p = base_probs.get(risk_type, 0.10)
    spread = max(0.02, p * 0.3)

    return ForecastEstimate(
        probability=_clamp(p, 0.001, 0.999),
        confidence_lower=_clamp(p - spread, 0.001, 0.999),
        confidence_upper=_clamp(p + spread, 0.001, 0.999),
        source="climatological_baseline",
    )


def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))
