"""Extensive tests for the settlement engine — the core logic interviewers will probe.

Test categories:
1. Happy path: clear YES and NO determinations.
2. Edge cases: sensor outages, partial data, missing stations.
3. Dispute scenarios: conflicting readings, threshold boundary.
4. Aggregation logic: precipitation summing, wind speed max.
5. Hash chain integrity.
6. Idempotency: re-settlement returns same result.
7. Multi-station scenarios.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.hashing import compute_record_hash
from app.models.contract import Contract, ContractMetric
from app.models.settlement import SettlementOutcome, SettlementRecord
from app.services.settlement_engine import (
    SettlementError,
    _aggregate_by_station,
    _resolve,
    settle_contract,
)
from tests.conftest import make_bundle, make_contract, make_observation


# ═══════════════════════════════════════════════════════════════════════════════
# 1. HAPPY PATH — CLEAR DETERMINATIONS
# ═══════════════════════════════════════════════════════════════════════════════


class TestHappyPath:
    """Test clear YES/NO outcomes with unambiguous data."""

    def test_precipitation_exceeds_threshold_returns_yes(self):
        """Single station reports 30mm total > 25mm threshold → YES."""
        contract = make_contract(threshold=25.0, metric=ContractMetric.PRECIPITATION)
        bundle = make_bundle(
            observations=[
                make_observation(precipitation_mm=10.0, observed_at=datetime(2025, 8, 14, 6, 0, tzinfo=timezone.utc)),
                make_observation(precipitation_mm=12.0, observed_at=datetime(2025, 8, 14, 12, 0, tzinfo=timezone.utc)),
                make_observation(precipitation_mm=8.0, observed_at=datetime(2025, 8, 14, 18, 0, tzinfo=timezone.utc)),
            ]
        )
        # Total = 10 + 12 + 8 = 30mm > 25mm
        outcome, observed, readings, dispute = _resolve(contract, bundle)
        assert outcome == SettlementOutcome.YES
        assert observed == 30.0
        assert dispute is None

    def test_precipitation_below_threshold_returns_no(self):
        """Single station reports 20mm total < 25mm threshold → NO."""
        contract = make_contract(threshold=25.0)
        bundle = make_bundle(
            observations=[
                make_observation(precipitation_mm=8.0),
                make_observation(precipitation_mm=7.0),
                make_observation(precipitation_mm=5.0),
            ]
        )
        # Total = 20mm < 25mm
        outcome, observed, readings, dispute = _resolve(contract, bundle)
        assert outcome == SettlementOutcome.NO
        assert observed == 20.0
        assert dispute is None

    def test_wind_exceeds_threshold_returns_yes(self):
        """Peak wind speed exceeds threshold → YES."""
        contract = make_contract(
            metric=ContractMetric.WIND_SPEED, threshold=15.0, unit="m/s"
        )
        bundle = make_bundle(
            observations=[
                make_observation(wind_speed_ms=10.0),
                make_observation(wind_speed_ms=18.0),  # peak
                make_observation(wind_speed_ms=12.0),
            ]
        )
        outcome, observed, readings, dispute = _resolve(contract, bundle)
        assert outcome == SettlementOutcome.YES
        assert observed == 18.0  # max of readings

    def test_wind_below_threshold_returns_no(self):
        """Peak wind speed below threshold → NO."""
        contract = make_contract(
            metric=ContractMetric.WIND_SPEED, threshold=15.0, unit="m/s"
        )
        bundle = make_bundle(
            observations=[
                make_observation(wind_speed_ms=8.0),
                make_observation(wind_speed_ms=12.0),
                make_observation(wind_speed_ms=10.0),
            ]
        )
        outcome, observed, readings, dispute = _resolve(contract, bundle)
        assert outcome == SettlementOutcome.NO
        assert observed == 12.0


# ═══════════════════════════════════════════════════════════════════════════════
# 2. EDGE CASES — SENSOR OUTAGES, MISSING DATA
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Test sensor outages, missing data, and no-station scenarios."""

    def test_no_stations_in_cell_returns_disputed(self):
        """Empty H3 cell with no ASOS stations → DISPUTED."""
        contract = make_contract()
        bundle = make_bundle(observations=[])

        outcome, observed, readings, dispute = _resolve(contract, bundle)
        assert outcome == SettlementOutcome.DISPUTED
        assert observed is None
        assert "No ASOS/AWOS stations found" in dispute

    def test_all_readings_none_sensor_outage(self):
        """All observations have None for the relevant metric → DISPUTED."""
        contract = make_contract(metric=ContractMetric.PRECIPITATION)
        bundle = make_bundle(
            observations=[
                make_observation(station_id="KJFK", precipitation_mm=None),
                make_observation(station_id="KJFK", precipitation_mm=None),
                make_observation(station_id="KJFK", precipitation_mm=None),
            ]
        )
        outcome, observed, readings, dispute = _resolve(contract, bundle)
        assert outcome == SettlementOutcome.DISPUTED
        assert "sensor outage" in dispute.lower()

    def test_partial_data_still_settles(self):
        """Some readings are None but enough valid data exists → settles normally."""
        contract = make_contract(threshold=10.0)
        bundle = make_bundle(
            observations=[
                make_observation(precipitation_mm=5.0),
                make_observation(precipitation_mm=None),  # missing
                make_observation(precipitation_mm=8.0),
            ]
        )
        # Sum of valid readings: 5 + 8 = 13 > 10
        outcome, observed, readings, dispute = _resolve(contract, bundle)
        assert outcome == SettlementOutcome.YES
        assert observed == 13.0

    def test_wind_all_none_returns_disputed(self):
        """Wind contract with all None readings → DISPUTED."""
        contract = make_contract(metric=ContractMetric.WIND_SPEED, threshold=10.0, unit="m/s")
        bundle = make_bundle(
            observations=[
                make_observation(wind_speed_ms=None),
                make_observation(wind_speed_ms=None),
            ]
        )
        outcome, observed, readings, dispute = _resolve(contract, bundle)
        assert outcome == SettlementOutcome.DISPUTED

    def test_exactly_at_threshold_returns_no(self):
        """Observed value exactly equal to threshold → NO (must exceed, not equal)."""
        contract = make_contract(threshold=25.0)
        bundle = make_bundle(
            observations=[
                make_observation(precipitation_mm=25.0),
            ]
        )
        outcome, observed, readings, dispute = _resolve(contract, bundle)
        assert outcome == SettlementOutcome.NO
        assert observed == 25.0


# ═══════════════════════════════════════════════════════════════════════════════
# 3. DISPUTE SCENARIOS — CONFLICTING STATIONS
# ═══════════════════════════════════════════════════════════════════════════════


class TestDisputeScenarios:
    """Test scenarios where station readings conflict beyond the tolerance threshold."""

    def test_conflicting_stations_triggers_dispute(self):
        """Two stations with >20% spread in readings → DISPUTED."""
        contract = make_contract(threshold=25.0)
        # Station A: 30mm, Station B: 10mm → spread=20, mean=20, ratio=100% > 20%
        bundle = make_bundle(
            observations=[
                make_observation(station_id="KJFK", precipitation_mm=30.0),
                make_observation(station_id="KLGA", precipitation_mm=10.0),
            ]
        )
        outcome, observed, readings, dispute = _resolve(contract, bundle)
        assert outcome == SettlementOutcome.DISPUTED
        assert dispute is not None
        assert "conflict" in dispute.lower()

    def test_agreeing_stations_no_dispute(self):
        """Two stations with similar readings → normal settlement."""
        contract = make_contract(threshold=25.0)
        # Station A: 28mm, Station B: 30mm → spread=2, mean=29, ratio=6.9% < 20%
        bundle = make_bundle(
            observations=[
                make_observation(station_id="KJFK", precipitation_mm=28.0),
                make_observation(station_id="KLGA", precipitation_mm=30.0),
            ]
        )
        outcome, observed, readings, dispute = _resolve(contract, bundle)
        assert outcome == SettlementOutcome.YES
        assert observed == pytest.approx(29.0)
        assert dispute is None

    def test_three_stations_one_outlier_disputes(self):
        """Three stations where one outlier creates >20% spread → DISPUTED."""
        contract = make_contract(threshold=25.0)
        # Stations: 27, 28, 5 → spread=23, mean=20, ratio=115% > 20%
        bundle = make_bundle(
            observations=[
                make_observation(station_id="KJFK", precipitation_mm=27.0),
                make_observation(station_id="KLGA", precipitation_mm=28.0),
                make_observation(station_id="KEWR", precipitation_mm=5.0),
            ]
        )
        outcome, observed, readings, dispute = _resolve(contract, bundle)
        assert outcome == SettlementOutcome.DISPUTED

    def test_borderline_spread_below_threshold_settles(self):
        """Stations with spread just under 20% → settles normally."""
        contract = make_contract(threshold=15.0)
        # Station A: 20mm, Station B: 17mm → spread=3, mean=18.5, ratio=16.2% < 20%
        bundle = make_bundle(
            observations=[
                make_observation(station_id="KJFK", precipitation_mm=20.0),
                make_observation(station_id="KLGA", precipitation_mm=17.0),
            ]
        )
        outcome, observed, readings, dispute = _resolve(contract, bundle)
        assert outcome in (SettlementOutcome.YES, SettlementOutcome.NO)
        assert dispute is None

    def test_wind_conflicting_stations(self):
        """Wind speed disagreement beyond threshold → DISPUTED."""
        contract = make_contract(
            metric=ContractMetric.WIND_SPEED, threshold=15.0, unit="m/s"
        )
        # Station A: peak 20 m/s, Station B: peak 5 m/s → spread=15, mean=12.5, ratio=120%
        bundle = make_bundle(
            observations=[
                make_observation(station_id="KJFK", wind_speed_ms=20.0),
                make_observation(station_id="KLGA", wind_speed_ms=5.0),
            ]
        )
        outcome, observed, readings, dispute = _resolve(contract, bundle)
        assert outcome == SettlementOutcome.DISPUTED


# ═══════════════════════════════════════════════════════════════════════════════
# 4. AGGREGATION LOGIC
# ═══════════════════════════════════════════════════════════════════════════════


class TestAggregation:
    """Test per-station aggregation: precipitation=sum, wind=max."""

    def test_precipitation_sums_per_station(self):
        """Precipitation readings for one station are summed (total accumulation)."""
        observations = [
            make_observation(station_id="KJFK", precipitation_mm=5.0),
            make_observation(station_id="KJFK", precipitation_mm=10.0),
            make_observation(station_id="KJFK", precipitation_mm=3.0),
        ]
        result = _aggregate_by_station(ContractMetric.PRECIPITATION, observations)
        assert result["KJFK"] == 18.0

    def test_wind_takes_max_per_station(self):
        """Wind speed uses the peak (maximum) reading per station."""
        observations = [
            make_observation(station_id="KJFK", wind_speed_ms=8.0),
            make_observation(station_id="KJFK", wind_speed_ms=15.0),
            make_observation(station_id="KJFK", wind_speed_ms=12.0),
        ]
        result = _aggregate_by_station(ContractMetric.WIND_SPEED, observations)
        assert result["KJFK"] == 15.0

    def test_multi_station_aggregation(self):
        """Multiple stations each get their own aggregate."""
        observations = [
            make_observation(station_id="KJFK", precipitation_mm=10.0),
            make_observation(station_id="KJFK", precipitation_mm=5.0),
            make_observation(station_id="KLGA", precipitation_mm=20.0),
            make_observation(station_id="KLGA", precipitation_mm=8.0),
        ]
        result = _aggregate_by_station(ContractMetric.PRECIPITATION, observations)
        assert result["KJFK"] == 15.0
        assert result["KLGA"] == 28.0

    def test_station_with_all_none_returns_none(self):
        """A station where all readings are None should aggregate to None."""
        observations = [
            make_observation(station_id="KJFK", precipitation_mm=None),
            make_observation(station_id="KJFK", precipitation_mm=None),
        ]
        result = _aggregate_by_station(ContractMetric.PRECIPITATION, observations)
        assert result["KJFK"] is None

    def test_mixed_none_and_valid_values(self):
        """None readings are skipped; only valid values are aggregated."""
        observations = [
            make_observation(station_id="KJFK", precipitation_mm=10.0),
            make_observation(station_id="KJFK", precipitation_mm=None),
            make_observation(station_id="KJFK", precipitation_mm=5.0),
        ]
        result = _aggregate_by_station(ContractMetric.PRECIPITATION, observations)
        assert result["KJFK"] == 15.0

    def test_zero_precipitation_is_valid(self):
        """Zero is a valid reading (no rain) and should not be treated as missing."""
        observations = [
            make_observation(station_id="KJFK", precipitation_mm=0.0),
            make_observation(station_id="KJFK", precipitation_mm=0.0),
        ]
        result = _aggregate_by_station(ContractMetric.PRECIPITATION, observations)
        assert result["KJFK"] == 0.0

    def test_single_observation_per_station(self):
        """Single observation returns that value directly."""
        observations = [
            make_observation(station_id="KJFK", precipitation_mm=42.0),
        ]
        result = _aggregate_by_station(ContractMetric.PRECIPITATION, observations)
        assert result["KJFK"] == 42.0


# ═══════════════════════════════════════════════════════════════════════════════
# 5. HASH CHAIN INTEGRITY
# ═══════════════════════════════════════════════════════════════════════════════


class TestHashChain:
    """Test the tamper-evident hash chain for settlement records."""

    def test_genesis_record_has_no_previous(self):
        """First record in the chain has previous_hash=None."""
        payload = {"contract_id": "abc", "outcome": "YES"}
        h = compute_record_hash(payload, previous_hash=None)
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex digest

    def test_chained_records_are_deterministic(self):
        """Same inputs produce the same hash."""
        payload = {"contract_id": "abc", "outcome": "YES", "value": 30.0}
        h1 = compute_record_hash(payload, "prev_hash_abc")
        h2 = compute_record_hash(payload, "prev_hash_abc")
        assert h1 == h2

    def test_different_previous_hash_changes_result(self):
        """Changing the previous hash changes the record hash (chain linkage)."""
        payload = {"contract_id": "abc", "outcome": "YES"}
        h1 = compute_record_hash(payload, "chain_link_1")
        h2 = compute_record_hash(payload, "chain_link_2")
        assert h1 != h2

    def test_modified_payload_changes_hash(self):
        """Any modification to the payload changes the hash (tamper detection)."""
        payload_a = {"contract_id": "abc", "outcome": "YES", "value": 30.0}
        payload_b = {"contract_id": "abc", "outcome": "YES", "value": 30.1}
        h_a = compute_record_hash(payload_a, "prev")
        h_b = compute_record_hash(payload_b, "prev")
        assert h_a != h_b

    def test_hash_chain_simulation(self):
        """Simulate a 5-record chain and verify integrity."""
        hashes = []
        prev = None
        for i in range(5):
            payload = {"record": i, "data": f"settlement_{i}"}
            h = compute_record_hash(payload, prev)
            hashes.append(h)
            prev = h

        # Verify chain by replaying
        prev = None
        for i, expected_hash in enumerate(hashes):
            payload = {"record": i, "data": f"settlement_{i}"}
            computed = compute_record_hash(payload, prev)
            assert computed == expected_hash, f"Chain broken at record {i}"
            prev = computed

    def test_tampered_record_breaks_chain(self):
        """If a record in the middle is tampered, verification fails."""
        chain = []
        prev = None
        for i in range(3):
            payload = {"record": i, "value": i * 10}
            h = compute_record_hash(payload, prev)
            chain.append((payload, h))
            prev = h

        # "Tamper" record 1 by changing its value
        tampered_payload = {"record": 1, "value": 999}
        tampered_hash = compute_record_hash(tampered_payload, chain[0][1])

        # Record 2's hash was based on original record 1's hash
        # Re-verify record 2 with the tampered chain
        recomputed_record2 = compute_record_hash(chain[2][0], tampered_hash)
        assert recomputed_record2 != chain[2][1], "Tampering should break the chain"


# ═══════════════════════════════════════════════════════════════════════════════
# 6. IDEMPOTENCY
# ═══════════════════════════════════════════════════════════════════════════════


class TestIdempotency:
    """Test that re-settling a contract returns the same record."""

    @pytest.mark.asyncio
    async def test_already_settled_returns_existing(self):
        """If a settlement record exists, return it without re-processing."""
        contract_id = uuid.uuid4()
        existing_record = SettlementRecord(
            id=uuid.uuid4(),
            contract_id=contract_id,
            outcome=SettlementOutcome.YES,
            observed_value=30.0,
            threshold=25.0,
            unit="mm",
            stations_used=1,
            record_hash="abc123",
        )

        session = AsyncMock()

        # First call returns the contract, second returns existing settlement
        contract = make_contract(contract_id=contract_id)

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalar_one_or_none.return_value = contract
            else:
                result.scalar_one_or_none.return_value = existing_record
            return result

        session.execute = mock_execute

        result = await settle_contract(session, contract_id)
        assert result.outcome == SettlementOutcome.YES
        assert result.record_hash == "abc123"


# ═══════════════════════════════════════════════════════════════════════════════
# 7. MULTI-STATION SCENARIOS
# ═══════════════════════════════════════════════════════════════════════════════


class TestMultiStation:
    """Test complex multi-station scenarios."""

    def test_two_stations_both_above_threshold(self):
        """Both stations agree the threshold is exceeded → YES."""
        contract = make_contract(threshold=20.0)
        bundle = make_bundle(
            observations=[
                make_observation(station_id="KJFK", precipitation_mm=22.0),
                make_observation(station_id="KLGA", precipitation_mm=24.0),
            ]
        )
        outcome, observed, readings, dispute = _resolve(contract, bundle)
        assert outcome == SettlementOutcome.YES
        assert observed == pytest.approx(23.0)

    def test_two_stations_both_below_threshold(self):
        """Both stations agree the threshold is not exceeded → NO."""
        contract = make_contract(threshold=30.0)
        bundle = make_bundle(
            observations=[
                make_observation(station_id="KJFK", precipitation_mm=15.0),
                make_observation(station_id="KLGA", precipitation_mm=18.0),
            ]
        )
        outcome, observed, readings, dispute = _resolve(contract, bundle)
        assert outcome == SettlementOutcome.NO
        assert observed == pytest.approx(16.5)

    def test_one_station_valid_one_all_none(self):
        """One station has valid data, the other is all None → settles on available."""
        contract = make_contract(threshold=20.0)
        bundle = make_bundle(
            observations=[
                make_observation(station_id="KJFK", precipitation_mm=25.0),
                make_observation(station_id="KLGA", precipitation_mm=None),
                make_observation(station_id="KLGA", precipitation_mm=None),
            ]
        )
        outcome, observed, readings, dispute = _resolve(contract, bundle)
        # Only KJFK has valid data (25mm > 20mm)
        assert outcome == SettlementOutcome.YES
        assert observed == 25.0
        assert readings["KLGA"] is None

    def test_multi_hour_multi_station_precipitation(self):
        """Multiple hourly readings across stations sum correctly per station."""
        contract = make_contract(threshold=40.0)
        times = [
            datetime(2025, 8, 14, h, 0, tzinfo=timezone.utc) for h in range(6, 18)
        ]
        observations = []
        # KJFK: 2.5mm/hr for 12 hours = 30mm
        for t in times:
            observations.append(make_observation(station_id="KJFK", precipitation_mm=2.5, observed_at=t))
        # KLGA: 2.8mm/hr for 12 hours = 33.6mm (close to KJFK, within 20% spread)
        for t in times:
            observations.append(make_observation(station_id="KLGA", precipitation_mm=2.8, observed_at=t))

        bundle = make_bundle(observations=observations)
        outcome, observed, readings, dispute = _resolve(contract, bundle)

        assert readings["KJFK"] == pytest.approx(30.0)
        assert readings["KLGA"] == pytest.approx(33.6)
        # Mean = (30 + 33.6) / 2 = 31.8, spread = 3.6, ratio = 11.3% < 20% → no dispute
        # 31.8 < 40 → NO
        assert outcome == SettlementOutcome.NO
        assert observed == pytest.approx(31.8)


# ═══════════════════════════════════════════════════════════════════════════════
# 8. SETTLE_CONTRACT INTEGRATION (with mocked DB)
# ═══════════════════════════════════════════════════════════════════════════════


class TestSettleContractMocked:
    """Test the full settle_contract flow with mocked database."""

    @pytest.mark.asyncio
    async def test_contract_not_found_raises(self):
        """Attempting to settle a non-existent contract raises SettlementError."""
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute.return_value = result_mock

        with pytest.raises(SettlementError, match="not found"):
            await settle_contract(session, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_settle_with_injected_bundle(self):
        """Full settlement flow with an injected observation bundle."""
        contract_id = uuid.uuid4()
        contract = make_contract(contract_id=contract_id, threshold=25.0)

        session = AsyncMock()

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                # Load contract
                result.scalar_one_or_none.return_value = contract
            elif call_count == 2:
                # Check existing settlement
                result.scalar_one_or_none.return_value = None
            elif call_count == 3:
                # Get latest hash
                result.scalar_one_or_none.return_value = None
            else:
                result.scalar_one_or_none.return_value = None
            return result

        session.execute = mock_execute

        bundle = make_bundle(
            observations=[
                make_observation(precipitation_mm=15.0),
                make_observation(precipitation_mm=12.0),
            ]
        )

        record = await settle_contract(session, contract_id, observation_bundle=bundle)

        assert record.outcome == SettlementOutcome.YES  # 27mm > 25mm
        assert record.observed_value == 27.0
        assert record.record_hash is not None
        assert len(record.record_hash) == 64

    @pytest.mark.asyncio
    async def test_settle_disputed_no_stations(self):
        """Settlement with empty observation bundle → DISPUTED."""
        contract_id = uuid.uuid4()
        contract = make_contract(contract_id=contract_id)

        session = AsyncMock()
        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalar_one_or_none.return_value = contract
            elif call_count == 2:
                result.scalar_one_or_none.return_value = None
            elif call_count == 3:
                result.scalar_one_or_none.return_value = None
            else:
                result.scalar_one_or_none.return_value = None
            return result

        session.execute = mock_execute

        bundle = make_bundle(observations=[])
        record = await settle_contract(session, contract_id, observation_bundle=bundle)

        assert record.outcome == SettlementOutcome.DISPUTED
        assert record.dispute_reason is not None


# ═══════════════════════════════════════════════════════════════════════════════
# 9. BOUNDARY / REGRESSION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestBoundaryAndRegression:
    """Boundary conditions and regression scenarios."""

    def test_very_small_precipitation_below_threshold(self):
        """Trace amounts of precipitation (0.1mm) do not trigger a 25mm contract."""
        contract = make_contract(threshold=25.0)
        bundle = make_bundle(
            observations=[
                make_observation(precipitation_mm=0.1),
            ]
        )
        outcome, observed, readings, dispute = _resolve(contract, bundle)
        assert outcome == SettlementOutcome.NO
        assert observed == pytest.approx(0.1)

    def test_large_number_of_observations(self):
        """100 hourly observations aggregate correctly."""
        contract = make_contract(threshold=50.0)
        observations = [
            make_observation(
                precipitation_mm=1.0,
                observed_at=datetime(2025, 8, 14, 0, 0, tzinfo=timezone.utc) + timedelta(hours=i),
            )
            for i in range(100)
        ]
        bundle = make_bundle(observations=observations)
        outcome, observed, readings, dispute = _resolve(contract, bundle)
        assert observed == 100.0
        assert outcome == SettlementOutcome.YES

    def test_negative_wind_speed_treated_as_valid(self):
        """Negative wind speed (shouldn't happen but defensive) is treated as valid."""
        contract = make_contract(metric=ContractMetric.WIND_SPEED, threshold=5.0, unit="m/s")
        bundle = make_bundle(
            observations=[
                make_observation(wind_speed_ms=-1.0),
            ]
        )
        outcome, observed, readings, dispute = _resolve(contract, bundle)
        assert outcome == SettlementOutcome.NO
        assert observed == -1.0

    def test_zero_mean_avoids_division_by_zero(self):
        """When mean is zero, spread ratio check doesn't crash."""
        contract = make_contract(threshold=5.0)
        bundle = make_bundle(
            observations=[
                make_observation(station_id="KJFK", precipitation_mm=0.0),
                make_observation(station_id="KLGA", precipitation_mm=0.0),
            ]
        )
        outcome, observed, readings, dispute = _resolve(contract, bundle)
        assert outcome == SettlementOutcome.NO
        assert observed == 0.0
        assert dispute is None  # No division by zero error
