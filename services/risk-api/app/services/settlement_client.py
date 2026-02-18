"""HTTP client for the Python settlement oracle service.

Wraps the settlement-oracle API behind a clean async interface for
contract creation, settlement status checks, and hash-chain verification.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_BASE = settings.settlement_oracle_url.rstrip("/")


class SettlementOracleError(Exception):
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(f"SettlementOracle {status}: {detail}")


def _wrap_connection_error(exc: httpx.ConnectError | httpx.TimeoutException) -> SettlementOracleError:
    return SettlementOracleError(0, f"Cannot reach settlement oracle at {_BASE}: {exc}")


async def create_contract(
    h3_cell: str,
    metric: str,
    threshold: float,
    unit: str,
    window_hours: int,
    expiry_utc: str,
    description: str | None = None,
) -> dict[str, Any]:
    """POST /api/v1/contracts — register a settlement contract spec."""
    payload: dict[str, Any] = {
        "h3_cell": h3_cell,
        "metric": metric,
        "threshold": threshold,
        "unit": unit,
        "window_hours": window_hours,
        "expiry_utc": expiry_utc,
    }
    if description:
        payload["description"] = description

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{_BASE}/api/v1/contracts", json=payload)
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        raise _wrap_connection_error(exc) from exc

    if resp.status_code >= 400:
        raise SettlementOracleError(resp.status_code, resp.text)
    return resp.json()


async def get_contract(contract_id: str) -> dict[str, Any] | None:
    """GET /api/v1/contracts/{id} — retrieve contract details."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{_BASE}/api/v1/contracts/{contract_id}")
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        raise _wrap_connection_error(exc) from exc

    if resp.status_code == 404:
        return None
    if resp.status_code >= 400:
        raise SettlementOracleError(resp.status_code, resp.text)
    return resp.json()


async def get_settlement(contract_id: str) -> dict[str, Any] | None:
    """GET /api/v1/settlements/{contract_id} — retrieve the settlement record."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{_BASE}/api/v1/settlements/{contract_id}")
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        raise _wrap_connection_error(exc) from exc

    if resp.status_code == 404:
        return None
    if resp.status_code >= 400:
        raise SettlementOracleError(resp.status_code, resp.text)
    return resp.json()


async def list_contracts(status: str | None = None) -> list[dict[str, Any]]:
    """GET /api/v1/contracts — list contracts, optionally filtered by status."""
    params: dict[str, str] = {}
    if status:
        params["status"] = status

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{_BASE}/api/v1/contracts", params=params)
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        raise _wrap_connection_error(exc) from exc

    if resp.status_code >= 400:
        raise SettlementOracleError(resp.status_code, resp.text)
    data = resp.json()
    return data if isinstance(data, list) else data.get("contracts", data.get("items", []))


async def trigger_settlement(contract_id: str) -> dict[str, Any]:
    """POST /api/v1/settle/{contract_id} — trigger settlement."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{_BASE}/api/v1/settle/{contract_id}")
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        raise _wrap_connection_error(exc) from exc

    if resp.status_code >= 400:
        raise SettlementOracleError(resp.status_code, resp.text)
    return resp.json()
