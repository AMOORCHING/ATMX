#!/usr/bin/env python3
"""Seed the database with sample weather contracts for development/testing.

Usage:
    python scripts/seed_contracts.py
"""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "settlement-oracle"))

from app.core.database import async_session_factory
from app.models.contract import Contract, ContractMetric


SAMPLE_CONTRACTS = [
    {
        "h3_cell": "872a1070bffffff",
        "metric": ContractMetric.PRECIPITATION,
        "threshold": 25.0,
        "unit": "mm",
        "window_hours": 24,
        "description": "NYC area precipitation > 25mm in 24h",
    },
    {
        "h3_cell": "872a1070bffffff",
        "metric": ContractMetric.WIND_SPEED,
        "threshold": 15.0,
        "unit": "m/s",
        "window_hours": 12,
        "description": "NYC area wind > 15 m/s in 12h",
    },
    {
        "h3_cell": "8729a5649ffffff",
        "metric": ContractMetric.PRECIPITATION,
        "threshold": 50.0,
        "unit": "mm",
        "window_hours": 48,
        "description": "LA area heavy rainfall > 50mm in 48h",
    },
]


async def seed():
    async with async_session_factory() as session:
        for spec in SAMPLE_CONTRACTS:
            contract = Contract(
                **spec,
                expiry_utc=datetime.now(timezone.utc) + timedelta(days=7),
            )
            session.add(contract)
            print(f"  Created: {contract.description}")
        await session.commit()
    print(f"\nSeeded {len(SAMPLE_CONTRACTS)} contracts.")


if __name__ == "__main__":
    asyncio.run(seed())
