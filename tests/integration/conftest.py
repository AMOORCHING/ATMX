"""Shared fixtures for end-to-end integration tests.

These tests exercise the full pipeline: ingest → trade → settle.
They require running services (use docker compose up first).
"""

import os

import httpx
import pytest


MARKET_ENGINE_URL = os.getenv("MARKET_ENGINE_URL", "http://localhost:8080")
SETTLEMENT_ORACLE_URL = os.getenv("SETTLEMENT_ORACLE_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def market_client():
    """HTTP client pointed at the market-engine service."""
    with httpx.Client(base_url=MARKET_ENGINE_URL, timeout=10.0) as client:
        yield client


@pytest.fixture(scope="session")
def oracle_client():
    """HTTP client pointed at the settlement-oracle service."""
    with httpx.Client(base_url=SETTLEMENT_ORACLE_URL, timeout=10.0) as client:
        yield client


@pytest.fixture(scope="session", autouse=True)
def _check_services(market_client, oracle_client):
    """Verify both services are healthy before running integration tests."""
    resp = market_client.get("/health")
    assert resp.status_code == 200, "market-engine is not running"

    resp = oracle_client.get("/health")
    assert resp.status_code == 200, "settlement-oracle is not running"
