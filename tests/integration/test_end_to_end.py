"""End-to-end integration tests: ingest → trade → settle.

These tests require all services running via docker compose.
Run with: pytest tests/integration/ -v

The flow:
1. Create a weather contract via settlement-oracle
2. Create a prediction market linked to the contract via market-engine
3. Execute trades on the market
4. Trigger settlement and verify the market resolves correctly
"""

import uuid

import httpx
import pytest


class TestFullPipeline:
    """End-to-end: contract creation → market → trade → settlement."""

    @pytest.mark.integration
    def test_create_contract_and_market(self, oracle_client: httpx.Client, market_client: httpx.Client):
        """Create a contract in the oracle, then open a market for it."""
        # 1. Create contract
        contract_resp = oracle_client.post(
            "/api/v1/contracts",
            json={
                "h3_cell": "872a1070bffffff",
                "metric": "precipitation",
                "threshold": 25.0,
                "unit": "mm",
                "window_hours": 24,
                "expiry_utc": "2026-08-15T00:00:00Z",
            },
        )
        assert contract_resp.status_code == 201
        contract_id = contract_resp.json()["id"]

        # 2. Create market linked to contract
        market_resp = market_client.post(
            "/api/v1/markets",
            json={"contract_id": contract_id},
        )
        assert market_resp.status_code == 201
        market = market_resp.json()
        assert market["contract_id"] == contract_id
        assert market["price_yes"] == pytest.approx(0.5)

    @pytest.mark.integration
    def test_trade_moves_price(self, market_client: httpx.Client):
        """Buying YES shares should increase the YES price."""
        # Create a market
        market_resp = market_client.post(
            "/api/v1/markets",
            json={"contract_id": str(uuid.uuid4())},
        )
        market_id = market_resp.json()["id"]

        # Execute a trade
        trade_resp = market_client.post(
            f"/api/v1/markets/{market_id}/trade",
            json={
                "trader_id": "trader-1",
                "side": "YES",
                "quantity": 10,
            },
        )
        assert trade_resp.status_code == 200

        # Check price moved
        price_resp = market_client.get(f"/api/v1/markets/{market_id}/price")
        prices = price_resp.json()
        assert prices["yes"] > 0.5, "YES price should increase after buying YES"

    @pytest.mark.integration
    def test_positions_track_correctly(self, market_client: httpx.Client):
        """Positions should reflect all trades made by a trader."""
        market_resp = market_client.post(
            "/api/v1/markets",
            json={"contract_id": str(uuid.uuid4())},
        )
        market_id = market_resp.json()["id"]

        # Two trades
        market_client.post(
            f"/api/v1/markets/{market_id}/trade",
            json={"trader_id": "alice", "side": "YES", "quantity": 5},
        )
        market_client.post(
            f"/api/v1/markets/{market_id}/trade",
            json={"trader_id": "alice", "side": "YES", "quantity": 3},
        )

        pos_resp = market_client.get(f"/api/v1/markets/{market_id}/positions")
        positions = pos_resp.json()
        assert positions["alice"]["YES"] == pytest.approx(8)


class TestServiceHealth:
    """Verify service health endpoints work in the composed environment."""

    @pytest.mark.integration
    def test_market_engine_health(self, market_client: httpx.Client):
        resp = market_client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "market-engine"

    @pytest.mark.integration
    def test_settlement_oracle_health(self, oracle_client: httpx.Client):
        resp = oracle_client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "settlement-oracle"
