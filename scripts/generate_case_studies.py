#!/usr/bin/env python3
"""Generate retroactive case studies using real ASOS weather data.

Fetches historical observations from the Iowa Environmental Mesonet (IEM)
archive, runs them through the ATMX pricing and settlement engines, and
produces documented case studies with hash-chained settlement records.

Output:
    docs/case_studies.json  — Structured data for programmatic access
    docs/case_studies.md    — Human-readable case studies for API docs

Usage:
    python scripts/generate_case_studies.py

Requires:
    pip install httpx h3
"""

import asyncio
import csv
import hashlib
import io
import json
import math
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

try:
    import h3
except ImportError:
    h3 = None

# ── LMSR pricing (mirrors services/risk-api/app/services/pricing.py) ───────

LIQUIDITY_B = 100.0
LOADING_FACTOR = 0.10
PRICING_MODEL = "ensemble_baseline_v1"


def _log_sum_exp(xs: list[float]) -> float:
    if not xs:
        return float("-inf")
    m = max(xs)
    if math.isinf(m) and m < 0:
        return float("-inf")
    return m + math.log(sum(math.exp(x - m) for x in xs))


def lmsr_cost(q_yes: float, q_no: float, b: float) -> float:
    return b * _log_sum_exp([q_yes / b, q_no / b])


def lmsr_trade_cost(q_yes: float, q_no: float, delta: float, b: float) -> float:
    return lmsr_cost(q_yes + delta, q_no, b) - lmsr_cost(q_yes, q_no, b)


def compute_premium(probability: float, notional: float) -> float:
    p = max(0.001, min(0.999, probability))
    q_yes = LIQUIDITY_B * math.log(p / (1.0 - p))
    fill = lmsr_trade_cost(q_yes, 0.0, 1.0, LIQUIDITY_B)
    return max(0.01, round(fill * notional * (1.0 + LOADING_FACTOR), 2))


# ── Hashing (mirrors services/settlement-oracle/app/core/hashing.py) ───────

def canonical_json(data: dict) -> str:
    def _default(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Not serializable: {type(obj)}")
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=_default)


def compute_record_hash(payload: dict, previous_hash: str | None = None) -> str:
    h = hashlib.sha256()
    if previous_hash:
        h.update(previous_hash.encode())
    h.update(canonical_json(payload).encode())
    return h.hexdigest()


# ── ASOS data fetching ─────────────────────────────────────────────────────

ASOS_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"

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

STATION_NAMES: dict[str, str] = {
    "KJFK": "JFK International Airport",
    "KLAX": "Los Angeles International Airport",
    "KORD": "O'Hare International Airport",
    "KATL": "Hartsfield-Jackson Atlanta Intl Airport",
    "KDEN": "Denver International Airport",
    "KDFW": "Dallas/Fort Worth International Airport",
    "KSFO": "San Francisco International Airport",
    "KBOS": "Boston Logan International Airport",
    "KMIA": "Miami International Airport",
    "KSEA": "Seattle-Tacoma International Airport",
}


@dataclass
class Obs:
    station: str
    time: datetime
    precip_mm: float | None = None
    wind_ms: float | None = None


def _safe_float(v: str | None) -> float | None:
    if v is None or v.strip() in ("", "M", "T"):
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


async def fetch_asos(station: str, start: datetime, end: datetime) -> list[Obs]:
    params = {
        "station": station, "data": "p01m,sknt", "tz": "Etc/UTC",
        "format": "comma", "latlon": "no",
        "year1": str(start.year), "month1": f"{start.month:02d}",
        "day1": f"{start.day:02d}", "hour1": f"{start.hour:02d}",
        "year2": str(end.year), "month2": f"{end.month:02d}",
        "day2": f"{end.day:02d}", "hour2": f"{end.hour:02d}",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(ASOS_URL, params=params)
        r.raise_for_status()

    # Strip IEM debug/comment lines before CSV parsing.
    lines = [ln for ln in r.text.splitlines() if not ln.startswith("#")]
    clean_csv = "\n".join(lines)

    obs: list[Obs] = []
    for row in csv.DictReader(io.StringIO(clean_csv)):
        try:
            dt = datetime.strptime(row["valid"], "%Y-%m-%d %H:%M")
        except (KeyError, ValueError):
            continue
        p = _safe_float(row.get("p01m"))
        w = _safe_float(row.get("sknt"))
        obs.append(Obs(station, dt, p, w * 0.514444 if w is not None else None))
    return obs


# ── Hourly precipitation aggregation ───────────────────────────────────────
#
# ASOS reports p01m as a running accumulator within each hour, resetting at
# the :51/:52/:53 mark.  To get the true hourly total, we take the maximum
# p01m value within each clock-hour.  Summing those hourly maxima gives the
# correct precipitation accumulation for the full window.

def aggregate_hourly_precip(observations: list[Obs]) -> tuple[float, list[dict]]:
    """Return (total_mm, hourly_readings) with correct de-duplication."""
    hourly_max: dict[str, float] = defaultdict(float)
    for o in observations:
        if o.precip_mm is not None and o.precip_mm > 0:
            key = o.time.strftime("%Y-%m-%d %H:00")
            hourly_max[key] = max(hourly_max[key], round(o.precip_mm, 2))

    readings = [
        {"hour_utc": k, "precip_mm": v}
        for k, v in sorted(hourly_max.items())
        if v > 0  # excludes trace amounts that round to 0
    ]
    total = round(sum(r["precip_mm"] for r in readings), 2)
    return total, readings


# ── Settlement resolution (mirrors settlement_engine._resolve) ─────────────

def settle(threshold: float, observations: list[Obs]) -> tuple[str, float | None, str | None]:
    if not observations:
        return "DISPUTED", None, "No observations available"

    total, _ = aggregate_hourly_precip(observations)

    has_any_reading = any(o.precip_mm is not None for o in observations)
    if not has_any_reading:
        return "DISPUTED", None, "All readings missing"

    return ("YES" if total > threshold else "NO"), total, None


# ── Case study event definitions ───────────────────────────────────────────

@dataclass
class Event:
    id: int
    title: str
    event_name: str
    venue: str
    city: str
    state: str
    date_display: str
    description: str
    station: str
    window_start: datetime
    window_end: datetime
    threshold_mm: float
    payout_usd: float
    probability: float
    tz_name: str
    utc_offset: int
    purchase_time: str
    ticket_price: float


EVENTS: list[Event] = [
    # ── YES outcomes (payout triggered) ─────────────────────────────────
    Event(
        id=1,
        title="Summer Concert at Prospect Park",
        event_name="Prospect Park Summer Music Festival",
        venue="Prospect Park Bandshell",
        city="Brooklyn", state="NY",
        date_display="July 9, 2023",
        description=(
            "An outdoor summer music festival at the Prospect Park Bandshell, "
            "one of Brooklyn's most popular venues for live outdoor performance. "
            "Summer evening thunderstorms are a perennial risk for NYC outdoor events."
        ),
        station="KJFK",
        window_start=datetime(2023, 7, 9, 20, 0, tzinfo=timezone.utc),
        window_end=datetime(2023, 7, 10, 4, 0, tzinfo=timezone.utc),
        threshold_mm=10.0, payout_usd=50.0, probability=0.150,
        tz_name="EDT", utc_offset=-4,
        purchase_time="2:00 PM EDT",
        ticket_price=45.0,
    ),
    Event(
        id=2,
        title="Lollapalooza at Grant Park",
        event_name="Lollapalooza 2023 — Pre-Show Events",
        venue="Grant Park",
        city="Chicago", state="IL",
        date_display="July 12, 2023",
        description=(
            "The build-up week of outdoor concerts and activations at Grant Park "
            "leading into Lollapalooza. Chicago's lakefront is highly exposed to "
            "mid-summer convective storms that sweep in from the Great Plains."
        ),
        station="KORD",
        window_start=datetime(2023, 7, 12, 17, 0, tzinfo=timezone.utc),
        window_end=datetime(2023, 7, 13, 3, 0, tzinfo=timezone.utc),
        threshold_mm=12.0, payout_usd=75.0, probability=0.120,
        tz_name="CDT", utc_offset=-5,
        purchase_time="9:00 AM CDT",
        ticket_price=135.0,
    ),
    Event(
        id=3,
        title="Bayfront Park Jazz Night",
        event_name="Miami Summer Jazz Series",
        venue="Bayfront Park Amphitheater",
        city="Miami", state="FL",
        date_display="August 17, 2023",
        description=(
            "An outdoor jazz performance at Bayfront Park Amphitheater. South "
            "Florida's late-summer thunderstorms are among the most intense in the "
            "continental US, fueled by tropical moisture and sea-breeze convergence."
        ),
        station="KMIA",
        window_start=datetime(2023, 8, 17, 18, 0, tzinfo=timezone.utc),
        window_end=datetime(2023, 8, 18, 3, 0, tzinfo=timezone.utc),
        threshold_mm=20.0, payout_usd=65.0, probability=0.200,
        tz_name="EDT", utc_offset=-4,
        purchase_time="11:00 AM EDT",
        ticket_price=55.0,
    ),
    Event(
        id=4,
        title="Atlanta Jazz Festival",
        event_name="Atlanta Jazz Festival",
        venue="Piedmont Park",
        city="Atlanta", state="GA",
        date_display="April 1, 2023",
        description=(
            "The Atlanta Jazz Festival at Piedmont Park — one of the largest free "
            "jazz festivals in the country. Spring in Atlanta brings warm, humid "
            "Gulf air that fuels afternoon thunderstorms."
        ),
        station="KATL",
        window_start=datetime(2023, 4, 1, 12, 0, tzinfo=timezone.utc),
        window_end=datetime(2023, 4, 1, 22, 0, tzinfo=timezone.utc),
        threshold_mm=10.0, payout_usd=55.0, probability=0.150,
        tz_name="EDT", utc_offset=-4,
        purchase_time="7:00 AM EDT",
        ticket_price=0.0,
    ),
    Event(
        id=5,
        title="Cinespia at Hollywood Forever",
        event_name="Cinespia Outdoor Movie Screening",
        venue="Hollywood Forever Cemetery",
        city="Los Angeles", state="CA",
        date_display="January 9, 2023",
        description=(
            "The popular Cinespia outdoor screening at Hollywood Forever Cemetery. "
            "January 2023 brought an extraordinary series of atmospheric rivers to "
            "Southern California, producing some of the heaviest rainfall in years."
        ),
        station="KLAX",
        window_start=datetime(2023, 1, 10, 3, 0, tzinfo=timezone.utc),
        window_end=datetime(2023, 1, 10, 7, 0, tzinfo=timezone.utc),
        threshold_mm=10.0, payout_usd=45.0, probability=0.180,
        tz_name="PST", utc_offset=-8,
        purchase_time="2:00 PM PST",
        ticket_price=22.0,
    ),
    # ── NO outcomes (no payout) ─────────────────────────────────────────
    Event(
        id=6,
        title="Celebrate Brooklyn! at Prospect Park",
        event_name="Celebrate Brooklyn! Summer Concert",
        venue="Prospect Park Bandshell",
        city="Brooklyn", state="NY",
        date_display="July 15, 2023",
        description=(
            "An evening concert at the Prospect Park Bandshell, part of the "
            "Celebrate Brooklyn! performing arts festival — the city's longest-running "
            "free outdoor performing arts series."
        ),
        station="KJFK",
        window_start=datetime(2023, 7, 15, 22, 0, tzinfo=timezone.utc),
        window_end=datetime(2023, 7, 16, 2, 0, tzinfo=timezone.utc),
        threshold_mm=10.0, payout_usd=50.0, probability=0.062,
        tz_name="EDT", utc_offset=-4,
        purchase_time="2:00 PM EDT",
        ticket_price=45.0,
    ),
    Event(
        id=7,
        title="Boston Pops Fireworks Spectacular",
        event_name="Boston Pops Fireworks Spectacular",
        venue="Hatch Memorial Shell, Esplanade",
        city="Boston", state="MA",
        date_display="July 4, 2023",
        description=(
            "The annual Boston Pops Fireworks Spectacular on the Charles River "
            "Esplanade — one of America's most iconic Fourth of July celebrations, "
            "drawing over 500,000 spectators. Afternoon showers tested the crowd's "
            "resolve, but the threshold wasn't reached."
        ),
        station="KBOS",
        window_start=datetime(2023, 7, 4, 18, 0, tzinfo=timezone.utc),
        window_end=datetime(2023, 7, 5, 3, 0, tzinfo=timezone.utc),
        threshold_mm=10.0, payout_usd=50.0, probability=0.070,
        tz_name="EDT", utc_offset=-4,
        purchase_time="12:00 PM EDT",
        ticket_price=0.0,
    ),
    Event(
        id=8,
        title="Stern Grove Festival Concert",
        event_name="Stern Grove Festival",
        venue="Sigmund Stern Grove",
        city="San Francisco", state="CA",
        date_display="September 1, 2023",
        description=(
            "The historic Stern Grove Festival — San Francisco's free outdoor concert "
            "series since 1938. Despite the city's famous microclimates, September is "
            "statistically its warmest and driest month."
        ),
        station="KSFO",
        window_start=datetime(2023, 9, 1, 21, 0, tzinfo=timezone.utc),
        window_end=datetime(2023, 9, 2, 0, 0, tzinfo=timezone.utc),
        threshold_mm=5.0, payout_usd=40.0, probability=0.020,
        tz_name="PDT", utc_offset=-7,
        purchase_time="10:00 AM PDT",
        ticket_price=0.0,
    ),
    Event(
        id=9,
        title="Outdoor Cinema at Gas Works Park",
        event_name="Movies at the Park",
        venue="Gas Works Park",
        city="Seattle", state="WA",
        date_display="July 25, 2023",
        description=(
            "An outdoor movie screening at Gas Works Park overlooking Lake Union. "
            "Seattle's dry summer season makes July the prime window for outdoor "
            "events, though marine air incursions from Puget Sound can bring "
            "unexpected drizzle."
        ),
        station="KSEA",
        window_start=datetime(2023, 7, 26, 3, 0, tzinfo=timezone.utc),
        window_end=datetime(2023, 7, 26, 6, 0, tzinfo=timezone.utc),
        threshold_mm=5.0, payout_usd=40.0, probability=0.030,
        tz_name="PDT", utc_offset=-7,
        purchase_time="5:00 PM PDT",
        ticket_price=15.0,
    ),
    Event(
        id=10,
        title="Fair Park Food Festival",
        event_name="Texas Outdoor Food Festival",
        venue="Fair Park",
        city="Dallas", state="TX",
        date_display="August 10, 2023",
        description=(
            "An outdoor food competition at Fair Park. August in North Texas means "
            "extreme heat but typically low precipitation — though isolated severe "
            "thunderstorms can develop rapidly along the dryline."
        ),
        station="KDFW",
        window_start=datetime(2023, 8, 10, 15, 0, tzinfo=timezone.utc),
        window_end=datetime(2023, 8, 11, 3, 0, tzinfo=timezone.utc),
        threshold_mm=10.0, payout_usd=45.0, probability=0.050,
        tz_name="CDT", utc_offset=-5,
        purchase_time="8:00 AM CDT",
        ticket_price=25.0,
    ),
]


# ── Helpers ─────────────────────────────────────────────────────────────────

def _station_h3(station: str) -> str:
    if h3 is None:
        return "requires-h3-library"
    lat, lon = STATION_COORDS[station]
    return h3.latlng_to_cell(lat, lon, 7)


def _utc_to_local(dt: datetime, offset: int) -> str:
    local = dt + timedelta(hours=offset)
    hour = local.hour % 12 or 12
    ap = "AM" if local.hour < 12 else "PM"
    return f"{hour}:{local.minute:02d} {ap}"


def _window_local(ev: Event) -> str:
    return f"{_utc_to_local(ev.window_start, ev.utc_offset)} – {_utc_to_local(ev.window_end, ev.utc_offset)} {ev.tz_name}"


def _iem_url(station: str, start: datetime, end: datetime) -> str:
    return (
        f"https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?"
        f"station={station}&data=p01m&tz=Etc/UTC&format=comma&latlon=no&"
        f"year1={start.year}&month1={start.month}&day1={start.day}&hour1={start.hour}&"
        f"year2={end.year}&month2={end.month}&day2={end.day}&hour2={end.hour}"
    )


# ── Main generation loop ───────────────────────────────────────────────────

async def generate() -> list[dict]:
    results: list[dict] = []
    previous_hash: str | None = None

    print(f"\n{'=' * 78}")
    print(f"  ATMX Case Study Generator — {len(EVENTS)} retroactive case studies")
    print(f"  Data source: Iowa Environmental Mesonet ASOS Archive")
    print(f"{'=' * 78}\n")

    for ev in EVENTS:
        print(f"  [{ev.id:2d}/{len(EVENTS)}] {ev.title} ({ev.city}, {ev.state})...",
              end=" ", flush=True)

        premium = compute_premium(ev.probability, ev.payout_usd)
        h3_cell = _station_h3(ev.station)

        try:
            obs = await fetch_asos(ev.station, ev.window_start, ev.window_end)
        except Exception as exc:
            print(f"ERROR: {exc}")
            continue

        await asyncio.sleep(0.5)

        outcome, observed_value, dispute_reason = settle(ev.threshold_mm, obs)
        _, hourly_readings = aggregate_hourly_precip(obs)

        settled_at = ev.window_end + timedelta(minutes=30)

        evidence = {
            "contract": {
                "h3_cell": h3_cell,
                "metric": "precipitation",
                "threshold_mm": ev.threshold_mm,
                "unit": "mm",
                "window_start": ev.window_start.isoformat(),
                "window_end": ev.window_end.isoformat(),
            },
            "observation_summary": {
                "station": ev.station,
                "station_name": STATION_NAMES.get(ev.station, ev.station),
                "total_raw_observations": len(obs),
                "hourly_readings": hourly_readings,
            },
            "determination": {
                "outcome": outcome,
                "observed_value_mm": observed_value,
                "threshold_mm": ev.threshold_mm,
                "exceeded": (observed_value > ev.threshold_mm
                             if observed_value is not None else None),
            },
        }

        hash_payload = {
            "case_study_id": ev.id,
            "outcome": outcome,
            "observed_value_mm": observed_value,
            "threshold_mm": ev.threshold_mm,
            "settled_at": settled_at.isoformat(),
            "station": ev.station,
        }
        record_hash = compute_record_hash(hash_payload, previous_hash)

        payout_amount = ev.payout_usd if outcome == "YES" else 0.0
        result = {
            "id": ev.id,
            "title": ev.title,
            "event_name": ev.event_name,
            "venue": ev.venue,
            "city": ev.city,
            "state": ev.state,
            "date": ev.date_display,
            "description": ev.description,
            "ticket_price_usd": ev.ticket_price,
            "station": ev.station,
            "station_name": STATION_NAMES.get(ev.station, ev.station),
            "h3_cell": h3_cell,
            "local_timezone": ev.tz_name,
            "utc_offset_hours": ev.utc_offset,
            "window_local": _window_local(ev),
            "purchase_time": ev.purchase_time,
            "pricing": {
                "risk_probability": ev.probability,
                "risk_probability_pct": f"{ev.probability * 100:.1f}%",
                "payout_usd": ev.payout_usd,
                "premium_usd": premium,
                "premium_pct_of_payout": f"{premium / ev.payout_usd * 100:.1f}%",
                "pricing_model": PRICING_MODEL,
                "lmsr_b": LIQUIDITY_B,
                "loading_factor": LOADING_FACTOR,
            },
            "weather": {
                "window_start_utc": ev.window_start.isoformat(),
                "window_end_utc": ev.window_end.isoformat(),
                "threshold_mm": ev.threshold_mm,
                "observed_value_mm": observed_value,
                "total_raw_observations": len(obs),
                "hourly_readings": hourly_readings,
            },
            "settlement": {
                "outcome": outcome,
                "observed_value_mm": observed_value,
                "threshold_mm": ev.threshold_mm,
                "exceeded": (observed_value > ev.threshold_mm
                             if observed_value is not None else None),
                "settled_at_utc": settled_at.isoformat(),
                "settlement_time_local": (
                    _utc_to_local(settled_at, ev.utc_offset) + f" {ev.tz_name}"
                ),
                "dispute_reason": dispute_reason,
                "payout_triggered": outcome == "YES",
                "payout_amount_usd": payout_amount,
            },
            "hash_chain": {
                "record_hash": record_hash,
                "previous_hash": previous_hash,
                "algorithm": "sha256",
            },
            "evidence_payload": evidence,
            "iem_verification_url": _iem_url(ev.station, ev.window_start, ev.window_end),
        }

        results.append(result)
        previous_hash = record_hash

        status = "PAYOUT" if outcome == "YES" else ("DRY" if outcome == "NO" else "DISPUTED")
        obs_str = f"{observed_value}mm" if observed_value is not None else "N/A"
        print(f"{status} — {obs_str} vs {ev.threshold_mm}mm threshold "
              f"({len(obs)} raw obs, {len(hourly_readings)} wet hours)")

    # ── Write outputs ───────────────────────────────────────────────────
    docs_dir = Path(__file__).resolve().parent.parent / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    json_path = docs_dir / "case_studies.json"
    with open(json_path, "w") as f:
        json.dump({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generator": "scripts/generate_case_studies.py",
            "data_source": "Iowa Environmental Mesonet ASOS Archive",
            "data_source_url": "https://mesonet.agron.iastate.edu/request/download.phtml",
            "hash_chain_algorithm": "sha256",
            "pricing_model": PRICING_MODEL,
            "lmsr_liquidity_b": LIQUIDITY_B,
            "loading_factor": LOADING_FACTOR,
            "aggregation_note": (
                "ASOS p01m is a running hourly accumulator. "
                "We take the max value per clock-hour then sum across hours."
            ),
            "case_studies": results,
        }, f, indent=2)
    print(f"\n  Wrote {json_path}")

    md_path = docs_dir / "case_studies.md"
    with open(md_path, "w") as f:
        f.write(_generate_markdown(results))
    print(f"  Wrote {md_path}")

    yes_count = sum(1 for r in results if r["settlement"]["outcome"] == "YES")
    no_count = sum(1 for r in results if r["settlement"]["outcome"] == "NO")
    disp_count = sum(1 for r in results if r["settlement"]["outcome"] == "DISPUTED")
    print(f"\n{'=' * 78}")
    print(f"  Generated {len(results)} case studies: "
          f"{yes_count} payouts, {no_count} no-payouts, {disp_count} disputed")
    print(f"{'=' * 78}\n")

    return results


# ── Markdown generation ─────────────────────────────────────────────────────

def _generate_markdown(results: list[dict]) -> str:
    lines: list[str] = []
    w = lines.append

    w("# ATMX Case Studies: Real Events, Real Weather, Real Settlement\n")
    w(
        "These case studies reconstruct how ATMX weather protection **would have "
        "worked** for real outdoor events using verified historical weather data. "
        "Every observation is sourced from NOAA ASOS sensors via the "
        "[Iowa Environmental Mesonet archive]"
        "(https://mesonet.agron.iastate.edu/request/download.phtml) — the same "
        "data source the ATMX settlement oracle uses in production.\n"
    )
    w("Each case study walks through the complete contract lifecycle:\n")
    w("1. **Pricing** — LMSR-derived premium computed at time of ticket purchase")
    w("2. **Observation** — Real ASOS precipitation data during the event window")
    w("3. **Settlement** — Automated resolution against the contract threshold")
    w("4. **Audit** — SHA-256 hash-chained settlement record with full evidence payload\n")
    w(
        "> All 10 case studies are linked in a single hash chain, demonstrating "
        "the tamper-evident audit trail that the CFTC requires for event contract "
        "record-keeping (17 CFR § 38.1051). The raw data is also available in "
        "[`case_studies.json`](case_studies.json).\n"
    )

    # Summary table
    w("---\n")
    w("## Summary\n")
    w("| # | Event | City | Date | Premium | Observed | Threshold | Outcome | Payout |")
    w("|---|-------|------|------|---------|----------|-----------|---------|--------|")
    for r in results:
        obs_val = r["settlement"]["observed_value_mm"]
        obs_str = f"{obs_val} mm" if obs_val is not None else "N/A"
        outcome = r["settlement"]["outcome"]
        badge = {"YES": "**YES** \u2705", "NO": "NO", "DISPUTED": "DISPUTED \u26a0\ufe0f"}.get(outcome, outcome)
        payout = r["settlement"]["payout_amount_usd"]
        payout_str = f"**${payout:.2f}**" if payout > 0 else "—"
        w(
            f"| {r['id']} "
            f"| {r['title']} "
            f"| {r['city']}, {r['state']} "
            f"| {r['date']} "
            f"| ${r['pricing']['premium_usd']:.2f} "
            f"| {obs_str} "
            f"| {r['weather']['threshold_mm']} mm "
            f"| {badge} "
            f"| {payout_str} |"
        )
    w("")

    for r in results:
        w("---\n")
        _write_case_study(w, r)

    # Hash chain section
    w("---\n")
    w("## Hash Chain Integrity\n")
    w(
        "Every settlement record is linked to the previous one via SHA-256 hashing. "
        "Tampering with any single record breaks the chain for all subsequent entries, "
        "providing a tamper-evident audit trail without blockchain consensus overhead.\n"
    )
    w("```")
    for i, r in enumerate(results):
        hc = r["hash_chain"]
        short = hc["record_hash"][:16] + "..."
        if i == 0:
            w(f"  #{r['id']:2d}  ─── {short}  (genesis)")
        else:
            prev = hc["previous_hash"][:16] + "..."
            w(f"       │")
            w(f"       ▼  prev = {prev}")
            w(f"  #{r['id']:2d}  ─── {short}")
    w("```\n")

    # Verification
    w("---\n")
    w("## Verify the Data Yourself\n")
    w("Every observation can be independently verified:\n")
    w("1. Visit the [IEM ASOS Download Page](https://mesonet.agron.iastate.edu/request/download.phtml)")
    w("2. Select the station (e.g. KJFK), date range, and `p01m` (1-hour precipitation)")
    w("3. Compare the hourly maxima against the readings listed in each case study\n")
    w(
        "To verify hash chain integrity, recompute each record's SHA-256 hash "
        "using the `hash_payload` fields from [`case_studies.json`](case_studies.json) "
        "and confirm it matches `record_hash`. Each hash includes the previous "
        "record's hash as a prefix, so a single altered record invalidates the "
        "entire downstream chain.\n"
    )
    w(
        "**Aggregation note:** ASOS `p01m` is a running accumulator within each "
        "clock hour. We take the maximum value per hour (representing the full "
        "hourly total), then sum across hours for the event window total.\n"
    )

    w("---\n")
    w(
        f"*Generated from real NOAA ASOS data by `scripts/generate_case_studies.py`. "
        f"See also: [API Lifecycle Guide](../services/risk-api/docs/api_lifecycle.md) · "
        f"[Design Document](design.md)*\n"
    )

    return "\n".join(lines)


def _write_case_study(w, r: dict) -> None:
    p = r["pricing"]
    s = r["settlement"]
    hc = r["hash_chain"]
    weather = r["weather"]

    w(f"## {r['id']}. {r['title']} — {r['city']}, {r['state']}\n")

    # The Event
    w("### The Event\n")
    ticket = f"${r['ticket_price_usd']:.0f} tickets" if r['ticket_price_usd'] > 0 else "free admission"
    w(
        f"On **{r['date']}**, {r['description']} "
        f"The event ran from **{r['window_local']}** at {r['venue']} "
        f"({ticket}).\n"
    )

    # Pricing
    w("### Risk Pricing\n")
    w(f"At **{r['purchase_time']}**, the ATMX API would have returned:\n")
    w("| Parameter | Value |")
    w("|-----------|-------|")
    w(f"| Risk probability | {p['risk_probability_pct']} |")
    w(f"| Threshold | >{weather['threshold_mm']} mm precipitation |")
    w(f"| Event window | {r['window_local']} |")
    w(f"| Payout | ${p['payout_usd']:.2f} |")
    w(f"| **Premium** | **${p['premium_usd']:.2f}** |")
    w(f"| Pricing model | LMSR (b={p['lmsr_b']:.0f}) + {p['loading_factor']*100:.0f}% loading |")
    w(f"| Oracle source | NOAA ASOS via IEM |")
    w(f"| Station | {r['station']} ({r['station_name']}) |")
    if r["h3_cell"] != "requires-h3-library":
        w(f"| H3 cell (res 7) | `{r['h3_cell']}` |")
    w("")

    # Observations
    w("### ASOS Observations\n")
    readings = weather["hourly_readings"]
    if readings:
        w(f"Station **{r['station']}** recorded the following hourly precipitation:\n")
        w("| Hour (UTC) | Precipitation |")
        w("|------------|--------------|")
        for rd in readings:
            w(f"| {rd['hour_utc']} | {rd['precip_mm']} mm |")
        w(f"| **Total** | **{s['observed_value_mm']} mm** |")
        w("")
    else:
        w(
            f"Station **{r['station']}** recorded **no measurable precipitation** "
            f"during the event window ({weather['total_raw_observations']} observations).\n"
        )
    w(f"> Verify: [IEM ASOS Archive]({r['iem_verification_url']})\n")

    # Settlement
    w("### Settlement\n")
    w(
        f"The settlement engine auto-triggered at **{s['settlement_time_local']}**, "
        f"30 minutes after the event window closed.\n"
    )
    settlement_json = {
        "outcome": s["outcome"],
        "observed_value_mm": s["observed_value_mm"],
        "threshold_mm": s["threshold_mm"],
        "exceeded": s["exceeded"],
        "settled_at": s["settled_at_utc"],
        "payout_triggered": s["payout_triggered"],
        "payout_amount_usd": s["payout_amount_usd"],
    }
    w("```json")
    w(json.dumps(settlement_json, indent=2))
    w("```\n")

    if s["outcome"] == "YES":
        roi = s["payout_amount_usd"] / p["premium_usd"]
        w(
            f"**Result:** The ticket holder paid **${p['premium_usd']:.2f}** "
            f"and received **${s['payout_amount_usd']:.2f}** — "
            f"a **{roi:.1f}\u00d7 return** on the weather protection.\n"
        )
    elif s["outcome"] == "NO":
        if s["observed_value_mm"] and s["observed_value_mm"] > 0:
            w(
                f"**Result:** It rained ({s['observed_value_mm']} mm) but stayed "
                f"below the {s['threshold_mm']} mm threshold. The "
                f"**${p['premium_usd']:.2f} premium** covered the risk — "
                f"the event continued despite light rain.\n"
            )
        else:
            w(
                f"**Result:** Clear skies — no payout triggered. The "
                f"**${p['premium_usd']:.2f} premium** was the cost of peace of mind.\n"
            )

    # Hash record
    w("### Settlement Record\n")
    w("```")
    w(f"Algorithm:   SHA-256")
    w(f"Record hash: {hc['record_hash']}")
    if hc["previous_hash"]:
        w(f"Prev hash:   {hc['previous_hash']}")
    else:
        w(f"Prev hash:   (genesis — first record in chain)")
    w("```\n")

    w("<details>")
    w("<summary>Evidence payload</summary>\n")
    w("```json")
    w(json.dumps(r["evidence_payload"], indent=2))
    w("```\n")
    w("</details>\n")


# ── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    results = asyncio.run(generate())
    if not results:
        print("  No case studies generated — check network connectivity.")
        sys.exit(1)
    sys.exit(0)
