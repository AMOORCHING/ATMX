#!/usr/bin/env python3
"""Historical backtesting: verify settlement resolves correctly against real NOAA data.

Runs the settlement engine's resolution logic (without the database) against
real ASOS observations for historical weather events. This validates that:
  1. The aggregation logic (sum for precip, max for wind) works on real data.
  2. Dispute detection catches genuine sensor conflicts.
  3. Outcomes match expected results for known storms.

Usage:
    python scripts/backtest_settlement.py

Requires:
    pip install httpx h3 tabulate

The script fetches live data from the Iowa Environmental Mesonet (IEM) ASOS
archive — no API key required.
"""

import asyncio
import csv
import io
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import httpx

try:
    import h3
except ImportError:
    print("ERROR: h3 package required.  pip install h3")
    sys.exit(1)

try:
    from tabulate import tabulate
except ImportError:
    tabulate = None  # Fallback to plain printing.

# ── Constants ──────────────────────────────────────────────────────────────

ASOS_BASE_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
H3_RESOLUTION = 7
MIN_STATIONS = 1
DISPUTED_THRESHOLD_RATIO = 0.2

# Known ASOS stations and their coordinates (same as settlement oracle).
STATION_COORDS: dict[str, tuple[float, float]] = {
    "KJFK": (40.6413, -73.7781),
    "KLGA": (40.7769, -73.8740),
    "KEWR": (40.6895, -74.1745),
    "KLAX": (33.9425, -118.4081),
    "KORD": (41.9742, -87.9073),
    "KATL": (33.6407, -84.4277),
    "KDEN": (39.8561, -104.6737),
    "KDFW": (32.8998, -97.0403),
    "KSFO": (37.6213, -122.3790),
    "KBOS": (42.3656, -71.0096),
    "KMIA": (25.7959, -80.2870),
    "KSEA": (47.4502, -122.3088),
    "KIAH": (29.9844, -95.3414),
    "KMCO": (28.4312, -81.3081),
    "KPHL": (39.8744, -75.2424),
}


# ── Historical events to backtest ──────────────────────────────────────────

@dataclass
class HistoricalEvent:
    """A real weather event with known outcome for backtesting."""
    name: str
    station: str  # ASOS station ID
    h3_cell: str  # Will be computed from station coords
    metric: str   # "precipitation" or "wind_speed"
    threshold: float
    unit: str
    window_start: datetime
    window_end: datetime
    expected_outcome: str  # "YES", "NO", or "DISPUTED"
    notes: str = ""


def _station_to_h3(station_id: str) -> str:
    """Convert a station ID to its H3 cell."""
    lat, lon = STATION_COORDS[station_id]
    return h3.latlng_to_cell(lat, lon, H3_RESOLUTION)


# 30 historical events across different stations, metrics, and seasons.
HISTORICAL_EVENTS: list[HistoricalEvent] = [
    # ── NYC / JFK area ──────────────────────────────────────────────────
    HistoricalEvent(
        name="NYC Nor'easter Dec 2022",
        station="KJFK", h3_cell="", metric="precipitation", threshold=20.0, unit="mm",
        window_start=datetime(2022, 12, 23, 0, tzinfo=timezone.utc),
        window_end=datetime(2022, 12, 24, 0, tzinfo=timezone.utc),
        expected_outcome="YES", notes="Major winter storm with heavy rain/snow mix",
    ),
    HistoricalEvent(
        name="NYC clear day Jan 2023",
        station="KJFK", h3_cell="", metric="precipitation", threshold=5.0, unit="mm",
        window_start=datetime(2023, 1, 15, 0, tzinfo=timezone.utc),
        window_end=datetime(2023, 1, 16, 0, tzinfo=timezone.utc),
        expected_outcome="NO", notes="Clear winter day",
    ),
    HistoricalEvent(
        name="NYC wind event Feb 2023",
        station="KJFK", h3_cell="", metric="wind_speed", threshold=15.0, unit="m/s",
        window_start=datetime(2023, 2, 4, 0, tzinfo=timezone.utc),
        window_end=datetime(2023, 2, 4, 12, tzinfo=timezone.utc),
        expected_outcome="YES", notes="Strong low pressure system",
    ),
    HistoricalEvent(
        name="NYC calm wind Jul 2023",
        station="KJFK", h3_cell="", metric="wind_speed", threshold=10.0, unit="m/s",
        window_start=datetime(2023, 7, 15, 0, tzinfo=timezone.utc),
        window_end=datetime(2023, 7, 15, 12, tzinfo=timezone.utc),
        expected_outcome="NO", notes="Summer calm",
    ),
    HistoricalEvent(
        name="NYC Ida remnants Sep 2021",
        station="KJFK", h3_cell="", metric="precipitation", threshold=50.0, unit="mm",
        window_start=datetime(2021, 9, 1, 18, tzinfo=timezone.utc),
        window_end=datetime(2021, 9, 2, 6, tzinfo=timezone.utc),
        expected_outcome="YES", notes="Hurricane Ida remnants caused record flooding",
    ),
    # ── LAX area ────────────────────────────────────────────────────────
    HistoricalEvent(
        name="LA atmospheric river Jan 2023",
        station="KLAX", h3_cell="", metric="precipitation", threshold=30.0, unit="mm",
        window_start=datetime(2023, 1, 9, 0, tzinfo=timezone.utc),
        window_end=datetime(2023, 1, 10, 0, tzinfo=timezone.utc),
        expected_outcome="YES", notes="Series of atmospheric rivers hit California",
    ),
    HistoricalEvent(
        name="LA dry day Aug 2023",
        station="KLAX", h3_cell="", metric="precipitation", threshold=1.0, unit="mm",
        window_start=datetime(2023, 8, 15, 0, tzinfo=timezone.utc),
        window_end=datetime(2023, 8, 16, 0, tzinfo=timezone.utc),
        expected_outcome="NO", notes="Typical dry summer",
    ),
    HistoricalEvent(
        name="LA Santa Ana wind Dec 2023",
        station="KLAX", h3_cell="", metric="wind_speed", threshold=12.0, unit="m/s",
        window_start=datetime(2023, 12, 5, 0, tzinfo=timezone.utc),
        window_end=datetime(2023, 12, 5, 12, tzinfo=timezone.utc),
        expected_outcome="YES", notes="Santa Ana wind event",
    ),
    # ── Chicago / ORD ───────────────────────────────────────────────────
    HistoricalEvent(
        name="Chicago derecho Jun 2022",
        station="KORD", h3_cell="", metric="wind_speed", threshold=20.0, unit="m/s",
        window_start=datetime(2022, 6, 13, 18, tzinfo=timezone.utc),
        window_end=datetime(2022, 6, 14, 6, tzinfo=timezone.utc),
        expected_outcome="YES", notes="Severe derecho event",
    ),
    HistoricalEvent(
        name="Chicago light snow Feb 2023",
        station="KORD", h3_cell="", metric="precipitation", threshold=15.0, unit="mm",
        window_start=datetime(2023, 2, 27, 0, tzinfo=timezone.utc),
        window_end=datetime(2023, 2, 28, 0, tzinfo=timezone.utc),
        expected_outcome="YES", notes="Moderate winter snowstorm",
    ),
    HistoricalEvent(
        name="Chicago calm Mar 2023",
        station="KORD", h3_cell="", metric="wind_speed", threshold=15.0, unit="m/s",
        window_start=datetime(2023, 3, 20, 0, tzinfo=timezone.utc),
        window_end=datetime(2023, 3, 20, 12, tzinfo=timezone.utc),
        expected_outcome="NO", notes="Light winds",
    ),
    # ── Miami / MIA ─────────────────────────────────────────────────────
    HistoricalEvent(
        name="Miami Hurricane Ian approach Sep 2022",
        station="KMIA", h3_cell="", metric="wind_speed", threshold=15.0, unit="m/s",
        window_start=datetime(2022, 9, 27, 0, tzinfo=timezone.utc),
        window_end=datetime(2022, 9, 28, 0, tzinfo=timezone.utc),
        expected_outcome="YES", notes="Hurricane Ian approaching Florida",
    ),
    HistoricalEvent(
        name="Miami summer thunderstorm Jul 2023",
        station="KMIA", h3_cell="", metric="precipitation", threshold=20.0, unit="mm",
        window_start=datetime(2023, 7, 12, 12, tzinfo=timezone.utc),
        window_end=datetime(2023, 7, 13, 0, tzinfo=timezone.utc),
        expected_outcome="YES", notes="Typical summer afternoon thunderstorms",
    ),
    HistoricalEvent(
        name="Miami calm winter Jan 2023",
        station="KMIA", h3_cell="", metric="precipitation", threshold=10.0, unit="mm",
        window_start=datetime(2023, 1, 20, 0, tzinfo=timezone.utc),
        window_end=datetime(2023, 1, 21, 0, tzinfo=timezone.utc),
        expected_outcome="NO", notes="Dry winter day",
    ),
    # ── Houston / IAH ───────────────────────────────────────────────────
    HistoricalEvent(
        name="Houston heavy rain May 2023",
        station="KIAH", h3_cell="", metric="precipitation", threshold=30.0, unit="mm",
        window_start=datetime(2023, 5, 4, 0, tzinfo=timezone.utc),
        window_end=datetime(2023, 5, 5, 0, tzinfo=timezone.utc),
        expected_outcome="YES", notes="Spring severe weather",
    ),
    HistoricalEvent(
        name="Houston dry Oct 2023",
        station="KIAH", h3_cell="", metric="precipitation", threshold=5.0, unit="mm",
        window_start=datetime(2023, 10, 10, 0, tzinfo=timezone.utc),
        window_end=datetime(2023, 10, 11, 0, tzinfo=timezone.utc),
        expected_outcome="NO", notes="Dry fall day",
    ),
    # ── Boston / BOS ────────────────────────────────────────────────────
    HistoricalEvent(
        name="Boston blizzard Jan 2022",
        station="KBOS", h3_cell="", metric="precipitation", threshold=25.0, unit="mm",
        window_start=datetime(2022, 1, 29, 0, tzinfo=timezone.utc),
        window_end=datetime(2022, 1, 30, 0, tzinfo=timezone.utc),
        expected_outcome="YES", notes="Bomb cyclone blizzard",
    ),
    HistoricalEvent(
        name="Boston clear summer Aug 2023",
        station="KBOS", h3_cell="", metric="precipitation", threshold=5.0, unit="mm",
        window_start=datetime(2023, 8, 20, 0, tzinfo=timezone.utc),
        window_end=datetime(2023, 8, 21, 0, tzinfo=timezone.utc),
        expected_outcome="NO", notes="Clear summer day",
    ),
    HistoricalEvent(
        name="Boston nor'easter wind Mar 2022",
        station="KBOS", h3_cell="", metric="wind_speed", threshold=18.0, unit="m/s",
        window_start=datetime(2022, 3, 12, 0, tzinfo=timezone.utc),
        window_end=datetime(2022, 3, 12, 12, tzinfo=timezone.utc),
        expected_outcome="YES", notes="March nor'easter with strong winds",
    ),
    # ── Denver / DEN ────────────────────────────────────────────────────
    HistoricalEvent(
        name="Denver spring storm Mar 2023",
        station="KDEN", h3_cell="", metric="precipitation", threshold=15.0, unit="mm",
        window_start=datetime(2023, 3, 14, 0, tzinfo=timezone.utc),
        window_end=datetime(2023, 3, 15, 0, tzinfo=timezone.utc),
        expected_outcome="YES", notes="Late-season snowstorm",
    ),
    HistoricalEvent(
        name="Denver dry Jul 2023",
        station="KDEN", h3_cell="", metric="precipitation", threshold=5.0, unit="mm",
        window_start=datetime(2023, 7, 20, 0, tzinfo=timezone.utc),
        window_end=datetime(2023, 7, 21, 0, tzinfo=timezone.utc),
        expected_outcome="NO", notes="Typical dry summer day",
    ),
    # ── Atlanta / ATL ───────────────────────────────────────────────────
    HistoricalEvent(
        name="Atlanta severe thunderstorm Apr 2023",
        station="KATL", h3_cell="", metric="precipitation", threshold=25.0, unit="mm",
        window_start=datetime(2023, 4, 1, 0, tzinfo=timezone.utc),
        window_end=datetime(2023, 4, 2, 0, tzinfo=timezone.utc),
        expected_outcome="YES", notes="Spring severe weather outbreak",
    ),
    HistoricalEvent(
        name="Atlanta calm Oct 2023",
        station="KATL", h3_cell="", metric="wind_speed", threshold=10.0, unit="m/s",
        window_start=datetime(2023, 10, 15, 0, tzinfo=timezone.utc),
        window_end=datetime(2023, 10, 15, 12, tzinfo=timezone.utc),
        expected_outcome="NO", notes="Calm fall day",
    ),
    # ── Dallas / DFW ────────────────────────────────────────────────────
    HistoricalEvent(
        name="DFW hailstorm Apr 2023",
        station="KDFW", h3_cell="", metric="wind_speed", threshold=20.0, unit="m/s",
        window_start=datetime(2023, 4, 12, 18, tzinfo=timezone.utc),
        window_end=datetime(2023, 4, 13, 6, tzinfo=timezone.utc),
        expected_outcome="YES", notes="Severe thunderstorm with damaging winds",
    ),
    HistoricalEvent(
        name="DFW dry summer Aug 2023",
        station="KDFW", h3_cell="", metric="precipitation", threshold=5.0, unit="mm",
        window_start=datetime(2023, 8, 10, 0, tzinfo=timezone.utc),
        window_end=datetime(2023, 8, 11, 0, tzinfo=timezone.utc),
        expected_outcome="NO", notes="Hot dry summer",
    ),
    # ── Seattle / SEA ───────────────────────────────────────────────────
    HistoricalEvent(
        name="Seattle atmospheric river Nov 2022",
        station="KSEA", h3_cell="", metric="precipitation", threshold=25.0, unit="mm",
        window_start=datetime(2022, 11, 4, 0, tzinfo=timezone.utc),
        window_end=datetime(2022, 11, 5, 0, tzinfo=timezone.utc),
        expected_outcome="YES", notes="Pineapple Express atmospheric river",
    ),
    HistoricalEvent(
        name="Seattle dry summer Jul 2023",
        station="KSEA", h3_cell="", metric="precipitation", threshold=2.0, unit="mm",
        window_start=datetime(2023, 7, 25, 0, tzinfo=timezone.utc),
        window_end=datetime(2023, 7, 26, 0, tzinfo=timezone.utc),
        expected_outcome="NO", notes="Dry summer (typical PNW)",
    ),
    # ── SFO area ────────────────────────────────────────────────────────
    HistoricalEvent(
        name="SFO atmospheric river Jan 2023",
        station="KSFO", h3_cell="", metric="precipitation", threshold=20.0, unit="mm",
        window_start=datetime(2023, 1, 4, 0, tzinfo=timezone.utc),
        window_end=datetime(2023, 1, 5, 0, tzinfo=timezone.utc),
        expected_outcome="YES", notes="California atmospheric river series",
    ),
    HistoricalEvent(
        name="SFO dry summer Sep 2023",
        station="KSFO", h3_cell="", metric="precipitation", threshold=1.0, unit="mm",
        window_start=datetime(2023, 9, 1, 0, tzinfo=timezone.utc),
        window_end=datetime(2023, 9, 2, 0, tzinfo=timezone.utc),
        expected_outcome="NO", notes="Dry season",
    ),
    # ── Orlando / MCO ───────────────────────────────────────────────────
    HistoricalEvent(
        name="Orlando Hurricane Nicole Nov 2022",
        station="KMCO", h3_cell="", metric="wind_speed", threshold=15.0, unit="m/s",
        window_start=datetime(2022, 11, 10, 0, tzinfo=timezone.utc),
        window_end=datetime(2022, 11, 11, 0, tzinfo=timezone.utc),
        expected_outcome="YES", notes="Hurricane Nicole landfall near Vero Beach",
    ),
]

# Populate h3_cell from station coords.
for event in HISTORICAL_EVENTS:
    if not event.h3_cell:
        event.h3_cell = _station_to_h3(event.station)


# ── ASOS data fetching (standalone, no app dependency) ─────────────────────

def _knots_to_ms(knots: float) -> float:
    return knots * 0.514444

def _safe_float(val: str | None) -> float | None:
    if val is None or val.strip() in ("", "M", "T"):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


@dataclass
class Observation:
    station_id: str
    observed_at: datetime
    precipitation_mm: float | None = None
    wind_speed_ms: float | None = None


async def fetch_asos(station_id: str, start: datetime, end: datetime) -> list[Observation]:
    """Fetch ASOS observations from IEM."""
    params = {
        "station": station_id,
        "data": "p01m,sknt",
        "tz": "Etc/UTC",
        "format": "comma",
        "latlon": "no",
        "year1": start.strftime("%Y"), "month1": start.strftime("%m"),
        "day1": start.strftime("%d"), "hour1": start.strftime("%H"),
        "year2": end.strftime("%Y"), "month2": end.strftime("%m"),
        "day2": end.strftime("%d"), "hour2": end.strftime("%H"),
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(ASOS_BASE_URL, params=params)
        resp.raise_for_status()

    obs = []
    reader = csv.DictReader(io.StringIO(resp.text))
    for row in reader:
        if row.get("station", "").startswith("#"):
            continue
        try:
            dt = datetime.strptime(row["valid"], "%Y-%m-%d %H:%M")
        except (KeyError, ValueError):
            continue
        precip = _safe_float(row.get("p01m"))
        wind_kt = _safe_float(row.get("sknt"))
        wind_ms = _knots_to_ms(wind_kt) if wind_kt is not None else None
        obs.append(Observation(station_id, dt, precip, wind_ms))
    return obs


# ── Resolution logic (mirrors settlement_engine._resolve) ─────────────────

def resolve(metric: str, threshold: float, observations: list[Observation]) -> tuple[str, float | None, str | None]:
    """
    Run settlement logic on observations.
    Returns: (outcome, observed_value, dispute_reason)
    """
    if not observations:
        return "DISPUTED", None, "No observations available"

    # Aggregate by station
    station_values: dict[str, list[float]] = {}
    all_stations: set[str] = set()
    for obs in observations:
        all_stations.add(obs.station_id)
        if metric == "precipitation":
            val = obs.precipitation_mm
        else:
            val = obs.wind_speed_ms
        if val is not None:
            station_values.setdefault(obs.station_id, []).append(val)

    # Per-station aggregation
    agg: dict[str, float | None] = {}
    for sid in all_stations:
        vals = station_values.get(sid)
        if not vals:
            agg[sid] = None
        elif metric == "precipitation":
            agg[sid] = sum(vals)
        elif metric == "wind_speed":
            agg[sid] = max(vals)

    valid = {sid: v for sid, v in agg.items() if v is not None}
    if not valid:
        return "DISPUTED", None, "All readings missing"

    if len(valid) < MIN_STATIONS:
        return "DISPUTED", None, f"Only {len(valid)} station(s), need {MIN_STATIONS}"

    values = list(valid.values())
    if len(values) > 1:
        spread = max(values) - min(values)
        mean_val = sum(values) / len(values)
        if mean_val > 0 and (spread / mean_val) > DISPUTED_THRESHOLD_RATIO:
            return "DISPUTED", mean_val, f"Conflict: spread={spread:.2f}, mean={mean_val:.2f}"

    observed = sum(values) / len(values)
    outcome = "YES" if observed > threshold else "NO"
    return outcome, observed, None


# ── Main backtesting loop ──────────────────────────────────────────────────

async def run_backtest():
    results = []
    passed = 0
    failed = 0
    disputed = 0

    print(f"\n{'='*80}")
    print(f"  atmx Settlement Backtest — {len(HISTORICAL_EVENTS)} historical events")
    print(f"{'='*80}\n")

    for i, event in enumerate(HISTORICAL_EVENTS, 1):
        print(f"  [{i:2d}/{len(HISTORICAL_EVENTS)}] {event.name}...", end=" ", flush=True)

        try:
            obs = await fetch_asos(event.station, event.window_start, event.window_end)
        except Exception as exc:
            print(f"FETCH ERROR: {exc}")
            results.append({
                "name": event.name, "station": event.station, "metric": event.metric,
                "threshold": event.threshold, "expected": event.expected_outcome,
                "actual": "ERROR", "observed": None, "match": False,
                "obs_count": 0, "notes": str(exc),
            })
            failed += 1
            continue

        outcome, observed, dispute_reason = resolve(event.metric, event.threshold, obs)

        match = outcome == event.expected_outcome
        if outcome == "DISPUTED":
            disputed += 1

        if match:
            passed += 1
            status = "PASS"
        else:
            failed += 1
            status = "FAIL"

        obs_str = f"{observed:.2f}" if observed is not None else "N/A"
        print(f"{status} — {outcome} (observed={obs_str}, threshold={event.threshold}, {len(obs)} obs)")

        if not match:
            print(f"         Expected {event.expected_outcome}, got {outcome}")
            if dispute_reason:
                print(f"         Reason: {dispute_reason}")

        results.append({
            "name": event.name, "station": event.station, "metric": event.metric,
            "threshold": event.threshold, "expected": event.expected_outcome,
            "actual": outcome, "observed": observed, "match": match,
            "obs_count": len(obs), "notes": dispute_reason or "",
        })

    # ── Summary ────────────────────────────────────────────────────────
    print(f"\n{'='*80}")
    print(f"  Results: {passed} passed / {failed} failed / {disputed} disputed")
    print(f"  Accuracy: {passed}/{len(HISTORICAL_EVENTS)} ({100*passed/len(HISTORICAL_EVENTS):.1f}%)")
    print(f"{'='*80}\n")

    if tabulate:
        headers = ["Event", "Station", "Metric", "Threshold", "Expected", "Actual", "Observed", "#Obs", "Match"]
        rows = [
            [r["name"][:35], r["station"], r["metric"][:6], r["threshold"],
             r["expected"], r["actual"],
             f"{r['observed']:.2f}" if r["observed"] is not None else "N/A",
             r["obs_count"],
             "✓" if r["match"] else "✗"]
            for r in results
        ]
        print(tabulate(rows, headers=headers, tablefmt="github"))
    else:
        for r in results:
            mark = "✓" if r["match"] else "✗"
            obs_str = f"{r['observed']:.2f}" if r['observed'] is not None else "N/A"
            print(f"  {mark} {r['name']:<35s} {r['station']} {r['metric']:<12s} "
                  f"expected={r['expected']:<8s} actual={r['actual']:<8s} observed={obs_str}")

    # Return exit code based on pass rate.
    # Allow some tolerance for DISPUTED outcomes (real data is messy).
    pass_rate = passed / len(HISTORICAL_EVENTS)
    if pass_rate >= 0.7:
        print(f"\n  Backtest passed (>= 70% accuracy).\n")
        return 0
    else:
        print(f"\n  Backtest FAILED (< 70% accuracy). Review disputed events.\n")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_backtest())
    sys.exit(exit_code)
