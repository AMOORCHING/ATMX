"""Shared test fixtures for the contract-settler test suite.

These fixtures provide an in-memory-style test harness using SQLite for fast
unit tests that don't require a live PostgreSQL + PostGIS instance.  Integration
tests that need PostGIS should be marked with @pytest.mark.integration.

For the settlement engine tests, we mock the database layer entirely and inject
pre-built observation bundles so the core logic is tested in isolation.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.contract import Contract, ContractMetric
from app.models.settlement import SettlementOutcome, SettlementRecord
from app.services.asos_client import CellObservationBundle, StationObservation


# ── Factory helpers ───────────────────────────────────────────────────────────


def make_contract(
    h3_cell: str = "872a1070bffffff",
    metric: ContractMetric = ContractMetric.PRECIPITATION,
    threshold: float = 25.0,
    unit: str = "mm",
    window_hours: int = 24,
    expiry_utc: datetime | None = None,
    contract_id: uuid.UUID | None = None,
) -> Contract:
    """Create a Contract instance for testing."""
    c = Contract(
        id=contract_id or uuid.uuid4(),
        h3_cell=h3_cell,
        metric=metric,
        threshold=threshold,
        unit=unit,
        window_hours=window_hours,
        expiry_utc=expiry_utc or datetime(2025, 8, 15, 0, 0, tzinfo=timezone.utc),
        description=f"Test contract: {metric.value} > {threshold}{unit}",
        created_at=datetime.now(timezone.utc),
    )
    return c


def make_observation(
    station_id: str = "KJFK",
    h3_cell: str = "872a1070bffffff",
    observed_at: datetime | None = None,
    precipitation_mm: float | None = None,
    wind_speed_ms: float | None = None,
    quality_flag: str | None = None,
) -> StationObservation:
    """Create a StationObservation for testing."""
    return StationObservation(
        station_id=station_id,
        observed_at=observed_at or datetime(2025, 8, 14, 12, 0, tzinfo=timezone.utc),
        latitude=40.6413,
        longitude=-73.7781,
        h3_cell=h3_cell,
        precipitation_mm=precipitation_mm,
        wind_speed_ms=wind_speed_ms,
        quality_flag=quality_flag,
    )


def make_bundle(
    h3_cell: str = "872a1070bffffff",
    observations: list[StationObservation] | None = None,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> CellObservationBundle:
    """Create a CellObservationBundle for testing."""
    end = window_end or datetime(2025, 8, 15, 0, 0, tzinfo=timezone.utc)
    start = window_start or (end - timedelta(hours=24))
    return CellObservationBundle(
        h3_cell=h3_cell,
        window_start=start,
        window_end=end,
        observations=observations or [],
    )


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_contract() -> Contract:
    """A standard precipitation contract for testing."""
    return make_contract()


@pytest.fixture
def wind_contract() -> Contract:
    """A wind speed contract for testing."""
    return make_contract(
        metric=ContractMetric.WIND_SPEED,
        threshold=15.0,
        unit="m/s",
    )


@pytest.fixture
def mock_session() -> AsyncMock:
    """A mocked AsyncSession that returns no existing settlement by default."""
    session = AsyncMock()

    # Default: no existing settlement
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = None
    session.execute.return_value = execute_result

    return session
