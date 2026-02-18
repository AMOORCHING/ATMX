"""Background settlement pipeline — watches contract expiries and auto-settles.

Replaces the manual /settle endpoint flow with a cron-triggered loop:
1. Poll the settlement oracle for active contracts
2. For any whose expiry_utc has passed, trigger settlement
3. On settlement result, dispatch webhooks to registered platforms

Runs as an asyncio background task managed by FastAPI's lifespan.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.core.config import settings
from app.models.schemas import RiskType, WebhookEventType
from app.services import settlement_client, webhook_dispatcher

logger = logging.getLogger(__name__)

_running = False


def _map_metric_to_risk_type(metric: str, threshold: float) -> RiskType:
    m = metric.lower()
    if "precip" in m:
        return RiskType.PRECIP_HEAVY if threshold > 10 else RiskType.PRECIP_MODERATE
    if "wind" in m:
        return RiskType.WIND_HIGH if threshold < 25 else RiskType.WIND_EXTREME
    if "temp" in m:
        return RiskType.TEMP_FREEZE if threshold < 20 else RiskType.TEMP_HEAT
    if "snow" in m:
        return RiskType.SNOW_HEAVY
    return RiskType.PRECIP_HEAVY


async def _settle_contract(contract: dict) -> None:
    """Trigger settlement for a single expired contract and dispatch webhooks."""
    contract_id = contract["id"]
    h3_index = contract.get("h3_cell", "")
    metric = contract.get("metric", "")
    threshold = contract.get("threshold", 0.0)
    risk_type = _map_metric_to_risk_type(metric, threshold)

    logger.info("Auto-settling contract %s (expired: %s)", contract_id, contract.get("expiry_utc"))

    try:
        result = await settlement_client.trigger_settlement(contract_id)
    except settlement_client.SettlementOracleError as exc:
        logger.error("Settlement failed for %s: %s", contract_id, exc)
        return

    outcome = result.get("outcome", "UNKNOWN")
    observed_value = result.get("observed_value")
    settled_at_str = result.get("settled_at")
    settled_at = (
        datetime.fromisoformat(settled_at_str) if settled_at_str else datetime.now(timezone.utc)
    )
    record_hash = result.get("record_hash")

    if outcome in ("YES", "NO"):
        event_type = WebhookEventType.CONTRACT_SETTLED
    elif outcome == "DISPUTED":
        event_type = WebhookEventType.CONTRACT_DISPUTED
    else:
        event_type = WebhookEventType.CONTRACT_EXPIRED

    delivered = await webhook_dispatcher.dispatch(
        event_type=event_type,
        contract_id=contract_id,
        h3_index=h3_index,
        risk_type=risk_type,
        outcome=outcome,
        observed_value=observed_value,
        settled_at=settled_at,
        record_hash=record_hash,
    )
    logger.info(
        "Contract %s settled: outcome=%s, webhooks_delivered=%d",
        contract_id, outcome, delivered,
    )


async def run_settlement_loop() -> None:
    """Main cron loop — runs until cancelled."""
    global _running
    _running = True
    interval = settings.settlement_cron_interval_seconds
    logger.info("Settlement cron started (interval=%ds)", interval)

    while _running:
        try:
            await _tick()
        except asyncio.CancelledError:
            break
        except settlement_client.SettlementOracleError as exc:
            logger.debug("Settlement oracle unreachable: %s", exc)
        except Exception:
            logger.exception("Settlement cron tick failed unexpectedly")

        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            break

    logger.info("Settlement cron stopped")


async def _tick() -> None:
    """Single cron tick: find expired contracts, settle them."""
    now = datetime.now(timezone.utc)

    try:
        contracts = await settlement_client.list_contracts(status="active")
    except settlement_client.SettlementOracleError as exc:
        logger.warning("Could not list contracts: %s", exc)
        return

    expired = []
    for c in contracts:
        expiry_str = c.get("expiry_utc")
        if not expiry_str:
            continue
        try:
            expiry = datetime.fromisoformat(expiry_str)
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue

        if expiry <= now:
            expired.append(c)

    if not expired:
        return

    logger.info("Found %d expired contracts to settle", len(expired))
    for contract in expired:
        await _settle_contract(contract)


def stop() -> None:
    global _running
    _running = False
