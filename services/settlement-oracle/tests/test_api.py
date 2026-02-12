"""Tests for the REST API endpoints.

These tests use FastAPI's TestClient with mocked database sessions
to verify request/response contracts without requiring a live database.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.contract import Contract, ContractMetric
from app.models.settlement import SettlementOutcome, SettlementRecord


# ── Helpers ───────────────────────────────────────────────────────────────────


def _override_session(mock_session: AsyncMock):
    """Override the FastAPI get_session dependency."""
    from app.core.database import get_session

    async def _mock_get_session():
        yield mock_session

    app.dependency_overrides[get_session] = _mock_get_session


def _clear_overrides():
    app.dependency_overrides.clear()


# ── Contract Endpoint Tests ───────────────────────────────────────────────────


class TestCreateContract:
    """Test POST /api/v1/contracts."""

    def setup_method(self):
        self.client = TestClient(app)

    def teardown_method(self):
        _clear_overrides()

    def test_create_contract_success(self):
        """Valid contract creation returns 201 with contract data."""
        mock_session = AsyncMock()

        contract_id = uuid.uuid4()

        async def mock_flush():
            pass

        async def mock_refresh(obj):
            obj.id = contract_id
            obj.created_at = datetime.now(timezone.utc)

        mock_session.flush = mock_flush
        mock_session.refresh = mock_refresh
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.close = AsyncMock()

        _override_session(mock_session)

        response = self.client.post(
            "/api/v1/contracts",
            json={
                "h3_cell": "872a1070bffffff",
                "metric": "precipitation",
                "threshold": 25.0,
                "unit": "mm",
                "window_hours": 24,
                "expiry_utc": "2025-08-15T00:00:00Z",
                "description": "Test contract",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["h3_cell"] == "872a1070bffffff"
        assert data["metric"] == "precipitation"
        assert data["threshold"] == 25.0

    def test_create_contract_invalid_threshold(self):
        """Threshold must be positive."""
        mock_session = AsyncMock()
        _override_session(mock_session)

        response = self.client.post(
            "/api/v1/contracts",
            json={
                "h3_cell": "872a1070bffffff",
                "metric": "precipitation",
                "threshold": -5.0,
                "unit": "mm",
                "expiry_utc": "2025-08-15T00:00:00Z",
            },
        )
        assert response.status_code == 422  # validation error

    def test_create_contract_missing_required_fields(self):
        """Missing required fields return 422."""
        mock_session = AsyncMock()
        _override_session(mock_session)

        response = self.client.post(
            "/api/v1/contracts",
            json={"h3_cell": "872a1070bffffff"},
        )
        assert response.status_code == 422


# ── Settlement Endpoint Tests ─────────────────────────────────────────────────


class TestSettleEndpoint:
    """Test POST /api/v1/settle/{contract_id}."""

    def setup_method(self):
        self.client = TestClient(app)

    def teardown_method(self):
        _clear_overrides()

    @patch("app.api.routes.settle_contract")
    def test_settle_returns_yes(self, mock_settle):
        """Successful settlement returns the outcome."""
        contract_id = uuid.uuid4()
        mock_record = SettlementRecord(
            id=uuid.uuid4(),
            contract_id=contract_id,
            outcome=SettlementOutcome.YES,
            observed_value=30.0,
            threshold=25.0,
            unit="mm",
            stations_used=1,
            station_readings={"KJFK": 30.0},
            record_hash="a" * 64,
            previous_hash=None,
            evidence_payload={"test": True},
            settled_at=datetime.now(timezone.utc),
        )
        mock_settle.return_value = mock_record

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.close = AsyncMock()
        _override_session(mock_session)

        response = self.client.post(f"/api/v1/settle/{contract_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["outcome"] == "YES"
        assert data["observed_value"] == 30.0
        assert data["record_hash"] == "a" * 64

    @patch("app.api.routes.settle_contract")
    def test_settle_returns_disputed(self, mock_settle):
        """DISPUTED outcome includes dispute_reason."""
        contract_id = uuid.uuid4()
        mock_record = SettlementRecord(
            id=uuid.uuid4(),
            contract_id=contract_id,
            outcome=SettlementOutcome.DISPUTED,
            observed_value=None,
            threshold=25.0,
            unit="mm",
            stations_used=0,
            station_readings={},
            dispute_reason="No ASOS/AWOS stations found in H3 cell",
            record_hash="b" * 64,
            previous_hash=None,
            evidence_payload={},
            settled_at=datetime.now(timezone.utc),
        )
        mock_settle.return_value = mock_record

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.close = AsyncMock()
        _override_session(mock_session)

        response = self.client.post(f"/api/v1/settle/{contract_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["outcome"] == "DISPUTED"
        assert data["dispute_reason"] is not None

    @patch("app.api.routes.settle_contract")
    def test_settle_contract_not_found(self, mock_settle):
        """Non-existent contract returns 404."""
        from app.services.settlement_engine import SettlementError

        mock_settle.side_effect = SettlementError("Contract not found")

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.close = AsyncMock()
        _override_session(mock_session)

        response = self.client.post(f"/api/v1/settle/{uuid.uuid4()}")
        assert response.status_code == 404

    def test_settle_invalid_uuid(self):
        """Invalid UUID format returns 422."""
        mock_session = AsyncMock()
        _override_session(mock_session)

        response = self.client.post("/api/v1/settle/not-a-uuid")
        assert response.status_code == 422


# ── Health Check ──────────────────────────────────────────────────────────────


class TestHealthCheck:
    def test_health(self):
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
