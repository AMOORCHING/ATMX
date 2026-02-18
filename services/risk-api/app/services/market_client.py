"""HTTP client for the Go market engine service.

Wraps the internal market-engine API (/api/v1/markets, /api/v1/trade) behind
a clean async interface.  All upstream errors are translated into typed
exceptions so the route layer can return proper HTTP status codes.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_BASE = settings.market_engine_url.rstrip("/")


class MarketEngineError(Exception):
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(f"MarketEngine {status}: {detail}")


def _wrap_connection_error(exc: httpx.ConnectError | httpx.TimeoutException) -> MarketEngineError:
    return MarketEngineError(0, f"Cannot reach market engine at {_BASE}: {exc}")


async def create_market(contract_id: str, liquidity_b: float | None = None) -> dict[str, Any]:
    """POST /api/v1/markets — create a new LMSR market for a contract.

    Returns the market object from the engine.
    """
    payload: dict[str, Any] = {"contract_id": contract_id}
    if liquidity_b is not None:
        payload["b"] = liquidity_b

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{_BASE}/api/v1/markets", json=payload)
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        raise _wrap_connection_error(exc) from exc

    if resp.status_code >= 400:
        raise MarketEngineError(resp.status_code, resp.text)
    return resp.json()


async def get_market(market_id: str) -> dict[str, Any] | None:
    """GET /api/v1/markets/{id} — retrieve a market by ID."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{_BASE}/api/v1/markets/{market_id}")
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        raise _wrap_connection_error(exc) from exc

    if resp.status_code == 404:
        return None
    if resp.status_code >= 400:
        raise MarketEngineError(resp.status_code, resp.text)
    return resp.json()


async def list_markets(h3_cell: str | None = None) -> list[dict[str, Any]]:
    """GET /api/v1/markets — list markets, optionally filtered by H3 cell."""
    params: dict[str, str] = {}
    if h3_cell:
        params["h3_cell"] = h3_cell

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{_BASE}/api/v1/markets", params=params)
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        raise _wrap_connection_error(exc) from exc

    if resp.status_code >= 400:
        raise MarketEngineError(resp.status_code, resp.text)
    return resp.json()


async def get_market_price(market_id: str) -> dict[str, Any] | None:
    """GET /api/v1/markets/{id}/price — current LMSR prices."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{_BASE}/api/v1/markets/{market_id}/price")
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        raise _wrap_connection_error(exc) from exc

    if resp.status_code == 404:
        return None
    if resp.status_code >= 400:
        raise MarketEngineError(resp.status_code, resp.text)
    return resp.json()
