"""Settlement engine — the core resolution logic for weather derivative contracts.

This module:
1. Loads the contract specification.
2. Fetches official ASOS observations for the contract's H3 cell and time window.
3. Aggregates station readings, detects conflicts, and determines outcome.
4. Writes an immutable, hash-chained settlement record.

Edge cases handled:
- No stations in the H3 cell → DISPUTED (no data).
- Sensor outage / all readings missing → DISPUTED (sensor outage).
- Partial data (some hours missing) → settles on available data with a flag.
- Conflicting station readings within the cell → DISPUTED if spread exceeds threshold.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.hashing import compute_record_hash
from app.models.contract import Contract, ContractMetric
from app.models.settlement import SettlementOutcome, SettlementRecord
from app.services.asos_client import (
    CellObservationBundle,
    StationObservation,
    get_cell_observations,
)

logger = logging.getLogger(__name__)


class SettlementError(Exception):
    """Raised when a settlement cannot be performed due to system errors."""


async def settle_contract(
    session: AsyncSession,
    contract_id: uuid.UUID,
    observation_bundle: CellObservationBundle | None = None,
) -> SettlementRecord:
    """Settle a contract and return the immutable settlement record.

    Args:
        session: Async database session.
        contract_id: UUID of the contract to settle.
        observation_bundle: Pre-fetched observations (for testing). If None,
                            observations are fetched live from ASOS.

    Returns:
        The persisted SettlementRecord.

    Raises:
        SettlementError: If the contract doesn't exist or is already settled.
    """
    # 1. Load contract
    contract = await _load_contract(session, contract_id)

    # 2. Check for existing settlement (idempotency)
    existing = await _get_existing_settlement(session, contract_id)
    if existing is not None:
        logger.info("Contract %s already settled: %s", contract_id, existing.outcome.value)
        return existing

    # 3. Fetch observations
    window_end = contract.expiry_utc
    window_start = window_end - timedelta(hours=contract.window_hours)

    if observation_bundle is None:
        observation_bundle = await get_cell_observations(
            contract.h3_cell, window_start, window_end
        )

    # 4. Determine outcome
    outcome, observed_value, station_readings, dispute_reason = _resolve(
        contract, observation_bundle
    )

    # 5. Build evidence payload
    evidence = _build_evidence(contract, observation_bundle, outcome, observed_value)

    # 6. Get previous hash for chain
    previous_hash = await _get_latest_hash(session)

    # 7. Compute record hash
    hash_payload = {
        "contract_id": str(contract_id),
        "outcome": outcome.value,
        "observed_value": observed_value,
        "threshold": contract.threshold,
        "settled_at": datetime.now(timezone.utc).isoformat(),
        "station_readings": station_readings,
    }
    record_hash = compute_record_hash(hash_payload, previous_hash)

    # 8. Persist settlement record
    record = SettlementRecord(
        contract_id=contract_id,
        outcome=outcome,
        observed_value=observed_value,
        threshold=contract.threshold,
        unit=contract.unit,
        stations_used=observation_bundle.station_count,
        station_readings=station_readings,
        evidence_payload=evidence,
        dispute_reason=dispute_reason,
        previous_hash=previous_hash,
        record_hash=record_hash,
    )
    session.add(record)
    await session.flush()

    logger.info(
        "Settled contract %s → %s (observed=%.2f vs threshold=%.2f)",
        contract_id,
        outcome.value,
        observed_value if observed_value is not None else -1,
        contract.threshold,
    )
    return record


async def _load_contract(session: AsyncSession, contract_id: uuid.UUID) -> Contract:
    """Load and validate a contract exists."""
    stmt = select(Contract).where(Contract.id == contract_id)
    result = await session.execute(stmt)
    contract = result.scalar_one_or_none()
    if contract is None:
        raise SettlementError(f"Contract {contract_id} not found")
    return contract


async def _get_existing_settlement(
    session: AsyncSession, contract_id: uuid.UUID
) -> SettlementRecord | None:
    """Return an existing settlement if the contract has already been settled."""
    stmt = select(SettlementRecord).where(SettlementRecord.contract_id == contract_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _get_latest_hash(session: AsyncSession) -> str | None:
    """Get the hash of the most recent settlement record for chain linking."""
    stmt = (
        select(SettlementRecord.record_hash)
        .order_by(SettlementRecord.settled_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    return row


def _resolve(
    contract: Contract,
    bundle: CellObservationBundle,
) -> tuple[SettlementOutcome, float | None, dict[str, Any], str | None]:
    """Core resolution logic.

    Returns:
        (outcome, observed_value, station_readings_dict, dispute_reason)
    """
    # Edge case 1: No stations in cell
    if bundle.station_count == 0:
        return (
            SettlementOutcome.DISPUTED,
            None,
            {},
            "No ASOS/AWOS stations found in H3 cell",
        )

    # Extract per-station aggregated readings
    station_agg = _aggregate_by_station(contract.metric, bundle.observations)

    # Edge case 2: All readings are None (sensor outage)
    valid_readings = {sid: val for sid, val in station_agg.items() if val is not None}
    if not valid_readings:
        return (
            SettlementOutcome.DISPUTED,
            None,
            {sid: None for sid in station_agg},
            "All station readings missing or flagged (sensor outage)",
        )

    # Edge case 3: Insufficient stations with valid data
    if len(valid_readings) < settings.min_stations_for_settlement:
        return (
            SettlementOutcome.DISPUTED,
            None,
            station_agg,
            f"Only {len(valid_readings)} valid station(s), "
            f"minimum {settings.min_stations_for_settlement} required",
        )

    # Edge case 4: Conflicting station readings
    values = list(valid_readings.values())
    if len(values) > 1:
        spread = max(values) - min(values)
        mean_val = sum(values) / len(values)
        if mean_val > 0 and (spread / mean_val) > settings.disputed_threshold_ratio:
            return (
                SettlementOutcome.DISPUTED,
                mean_val,
                station_agg,
                f"Station readings conflict: spread={spread:.2f}, "
                f"mean={mean_val:.2f}, ratio={spread / mean_val:.2%}",
            )

    # Normal case: compute mean observed value
    observed_value = sum(values) / len(values)

    # Compare against threshold
    if observed_value > contract.threshold:
        outcome = SettlementOutcome.YES
    else:
        outcome = SettlementOutcome.NO

    return outcome, observed_value, station_agg, None


def _aggregate_by_station(
    metric: ContractMetric,
    observations: list[StationObservation],
) -> dict[str, float | None]:
    """Aggregate observations per station based on the contract metric.

    For precipitation: sum all hourly readings (total accumulation).
    For wind speed: take the maximum reading (peak sustained wind).
    """
    station_values: dict[str, list[float]] = {}

    for obs in observations:
        if metric == ContractMetric.PRECIPITATION:
            val = obs.precipitation_mm
        elif metric == ContractMetric.WIND_SPEED:
            val = obs.wind_speed_ms
        else:
            continue

        if val is None:
            continue

        station_values.setdefault(obs.station_id, []).append(val)

    result: dict[str, float | None] = {}
    all_stations = {obs.station_id for obs in observations}

    for sid in all_stations:
        vals = station_values.get(sid)
        if vals is None or len(vals) == 0:
            result[sid] = None
        elif metric == ContractMetric.PRECIPITATION:
            result[sid] = sum(vals)  # total accumulation
        elif metric == ContractMetric.WIND_SPEED:
            result[sid] = max(vals)  # peak wind
        else:
            result[sid] = None

    return result


def _build_evidence(
    contract: Contract,
    bundle: CellObservationBundle,
    outcome: SettlementOutcome,
    observed_value: float | None,
) -> dict[str, Any]:
    """Build a comprehensive evidence payload for the settlement record."""
    return {
        "contract": {
            "id": str(contract.id),
            "h3_cell": contract.h3_cell,
            "metric": contract.metric.value,
            "threshold": contract.threshold,
            "unit": contract.unit,
            "window_hours": contract.window_hours,
            "expiry_utc": contract.expiry_utc.isoformat(),
        },
        "observation_summary": {
            "h3_cell": bundle.h3_cell,
            "window_start": bundle.window_start.isoformat(),
            "window_end": bundle.window_end.isoformat(),
            "total_observations": len(bundle.observations),
            "stations_reporting": bundle.station_count,
        },
        "determination": {
            "outcome": outcome.value,
            "observed_value": observed_value,
            "threshold": contract.threshold,
            "exceeded": (
                observed_value > contract.threshold
                if observed_value is not None
                else None
            ),
        },
        "raw_observations": [
            {
                "station_id": obs.station_id,
                "observed_at": obs.observed_at.isoformat(),
                "precipitation_mm": obs.precipitation_mm,
                "wind_speed_ms": obs.wind_speed_ms,
                "quality_flag": obs.quality_flag,
            }
            for obs in bundle.observations
        ],
    }
