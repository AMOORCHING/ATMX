"""End-to-end integration tests: ingest → trade → settle.

These tests require all services running via docker compose.
Run with: pytest tests/integration/ -v

The flow:
1. Create a weather contract via settlement-oracle
2. Create a prediction market linked to the contract via market-engine
3. Execute trades on the market (POST /api/v1/trade with contract_id)
4. Query portfolio via GET /api/v1/portfolio/{userID}
"""

import httpx
import pytest


# Unique contract tickers for each test run to avoid conflicts.
_counter = 0


def _make_ticker(h3_cell: str = "872a1070b", contract_type: str = "PRECIP", threshold: str = "25MM") -> str:
    """Generate a unique ATMX ticker for testing."""
    global _counter
    _counter += 1
    # Use a unique date component to avoid contract_id collisions.
    date_str = f"2026{_counter:04d}"[:8].ljust(8, "0")
    return f"ATMX-{h3_cell}-{contract_type}-{threshold}-{date_str}"


class TestFullPipeline:
    """End-to-end: contract creation → market → trade → settlement."""

    @pytest.mark.integration
    def test_create_contract_and_market(self, oracle_client: httpx.Client, market_client: httpx.Client):
        """Create a contract in the oracle, then open a market for it."""
        # 1. Create contract in settlement oracle
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
        oracle_contract_id = contract_resp.json()["id"]

        # 2. Create market in market-engine using an ATMX ticker format.
        # The market-engine uses ticker-format contract IDs, not UUIDs.
        ticker = _make_ticker()
        market_resp = market_client.post(
            "/api/v1/markets",
            json={"contract_id": ticker},
        )
        assert market_resp.status_code == 201
        market = market_resp.json()
        assert market["contract_id"] == ticker
        # Initial price should be 0.5 (equal probability).
        assert float(market["price_yes"]) == pytest.approx(0.5, abs=0.01)

    @pytest.mark.integration
    def test_trade_moves_price(self, market_client: httpx.Client):
        """Buying YES shares should increase the YES price."""
        # Create a market with a unique ticker.
        ticker = _make_ticker()
        market_resp = market_client.post(
            "/api/v1/markets",
            json={"contract_id": ticker},
        )
        assert market_resp.status_code == 201
        market_id = market_resp.json()["id"]

        # Execute a trade via POST /api/v1/trade (the actual endpoint).
        trade_resp = market_client.post(
            "/api/v1/trade",
            json={
                "user_id": "trader-1",
                "contract_id": ticker,
                "side": "YES",
                "quantity": 10,
            },
        )
        assert trade_resp.status_code == 200
        trade_data = trade_resp.json()
        assert trade_data["side"] == "YES"
        assert float(trade_data["cost"]) > 0

        # Check price moved via the market price endpoint.
        price_resp = market_client.get(f"/api/v1/markets/{market_id}/price")
        assert price_resp.status_code == 200
        prices = price_resp.json()
        assert float(prices["yes"]) > 0.5, "YES price should increase after buying YES"

    @pytest.mark.integration
    def test_positions_track_correctly(self, market_client: httpx.Client):
        """Positions should reflect all trades made by a trader."""
        ticker = _make_ticker()
        market_resp = market_client.post(
            "/api/v1/markets",
            json={"contract_id": ticker},
        )
        assert market_resp.status_code == 201

        # Two trades via POST /api/v1/trade.
        trade1 = market_client.post(
            "/api/v1/trade",
            json={"user_id": "alice-test", "contract_id": ticker, "side": "YES", "quantity": 5},
        )
        assert trade1.status_code == 200

        trade2 = market_client.post(
            "/api/v1/trade",
            json={"user_id": "alice-test", "contract_id": ticker, "side": "YES", "quantity": 3},
        )
        assert trade2.status_code == 200

        # Query portfolio via GET /api/v1/portfolio/{userID} (the actual endpoint).
        portfolio_resp = market_client.get("/api/v1/portfolio/alice-test")
        assert portfolio_resp.status_code == 200
        portfolio = portfolio_resp.json()
        assert len(portfolio["positions"]) > 0

        # Find the position for our market.
        position = next(
            (p for p in portfolio["positions"] if p["contract_id"] == ticker),
            None,
        )
        assert position is not None, f"No position found for ticker {ticker}"
        assert float(position["yes_qty"]) == pytest.approx(8, abs=0.01)


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
