#!/usr/bin/env python3
"""Seed the database with sample weather contracts AND corresponding markets.

Creates contracts in the settlement oracle (via DB) and markets in the
market engine (via REST API) so the demo flow is complete end-to-end.

Usage:
    # With services running:
    python scripts/seed_contracts.py

    # Custom market-engine URL:
    MARKET_ENGINE_URL=http://localhost:8080 python scripts/seed_contracts.py
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "settlement-oracle"))

from app.core.database import async_session_factory
from app.models.contract import Contract, ContractMetric

MARKET_ENGINE_URL = os.getenv("MARKET_ENGINE_URL", "http://localhost:8080")

# Each entry seeds both a settlement-oracle contract AND a market-engine market.
# The `ticker` field is the ATMX ticker used by the market engine.
SAMPLE_CONTRACTS = [
    {
        "h3_cell": "872a1070bffffff",
        "metric": ContractMetric.PRECIPITATION,
        "threshold": 25.0,
        "unit": "mm",
        "window_hours": 24,
        "description": "NYC area precipitation > 25mm in 24h",
        "ticker": "ATMX-872a1070b-PRECIP-25MM-{date}",
    },
    {
        "h3_cell": "872a1070bffffff",
        "metric": ContractMetric.WIND_SPEED,
        "threshold": 15.0,
        "unit": "m/s",
        "window_hours": 12,
        "description": "NYC area wind > 15 m/s in 12h",
        "ticker": "ATMX-872a1070b-WIND-15MS-{date}",
    },
    {
        "h3_cell": "8729a5649ffffff",
        "metric": ContractMetric.PRECIPITATION,
        "threshold": 50.0,
        "unit": "mm",
        "window_hours": 48,
        "description": "LA area heavy rainfall > 50mm in 48h",
        "ticker": "ATMX-8729a5649-PRECIP-50MM-{date}",
    },
    {
        "h3_cell": "872a100d1ffffff",
        "metric": ContractMetric.WIND_SPEED,
        "threshold": 20.0,
        "unit": "m/s",
        "window_hours": 24,
        "description": "Miami area wind > 20 m/s in 24h",
        "ticker": "ATMX-872a100d1-WIND-20MS-{date}",
    },
    {
        "h3_cell": "87283082effffff",
        "metric": ContractMetric.PRECIPITATION,
        "threshold": 30.0,
        "unit": "mm",
        "window_hours": 24,
        "description": "Houston area precipitation > 30mm in 24h",
        "ticker": "ATMX-87283082e-PRECIP-30MM-{date}",
    },
]


async def seed():
    expiry = datetime.now(timezone.utc) + timedelta(days=7)
    date_str = expiry.strftime("%Y%m%d")

    # ── Step 1: Seed contracts in settlement oracle DB ──────────────────
    print("Seeding contracts in settlement oracle...")
    async with async_session_factory() as session:
        for spec in SAMPLE_CONTRACTS:
            contract = Contract(
                h3_cell=spec["h3_cell"],
                metric=spec["metric"],
                threshold=spec["threshold"],
                unit=spec["unit"],
                window_hours=spec["window_hours"],
                description=spec["description"],
                expiry_utc=expiry,
            )
            session.add(contract)
            print(f"  [oracle] Created: {spec['description']}")
        await session.commit()
    print(f"  Seeded {len(SAMPLE_CONTRACTS)} contracts in oracle.\n")

    # ── Step 2: Create corresponding markets in market engine ───────────
    print("Creating markets in market engine...")
    async with httpx.AsyncClient(base_url=MARKET_ENGINE_URL, timeout=10.0) as client:
        # Check market engine is reachable.
        try:
            health = await client.get("/health")
            health.raise_for_status()
        except httpx.HTTPError as exc:
            print(f"  [WARNING] Market engine not reachable at {MARKET_ENGINE_URL}: {exc}")
            print("  Skipping market creation. Start the market engine and re-run.")
            return

        created = 0
        for spec in SAMPLE_CONTRACTS:
            ticker = spec["ticker"].format(date=date_str)
            resp = await client.post(
                "/api/v1/markets",
                json={"contract_id": ticker},
            )
            if resp.status_code == 201:
                market = resp.json()
                print(f"  [market] Created: {ticker} → market_id={market['id']}")
                created += 1
            elif resp.status_code == 409:
                print(f"  [market] Already exists: {ticker}")
            else:
                print(f"  [market] Failed ({resp.status_code}): {ticker} — {resp.text}")

    print(f"\n  Created {created} markets in market engine.")
    print("\nDone! Demo pipeline is ready.")


if __name__ == "__main__":
    asyncio.run(seed())
