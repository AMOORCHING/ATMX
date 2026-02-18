"""Async webhook dispatcher — fires settlement events to registered callbacks.

Each delivery includes:
- JSON body matching the WebhookEvent schema
- X-ATMX-Event header with the event type
- X-ATMX-Signature header with HMAC-SHA256 if a shared secret was provided
- X-ATMX-Delivery header with the event_id for idempotency

Retries on transient failures (5xx, timeouts) with exponential backoff.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timezone

import httpx

from app.core.config import settings
from app.models.schemas import (
    RiskType,
    WebhookEvent,
    WebhookEventType,
    WebhookRegistration,
)
from app.services import webhook_store

logger = logging.getLogger(__name__)


def _sign_payload(payload_bytes: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()


async def _deliver(
    reg: WebhookRegistration,
    event: WebhookEvent,
    payload_bytes: bytes,
) -> bool:
    """Attempt delivery with retries.  Returns True on success."""
    headers = {
        "Content-Type": "application/json",
        "X-ATMX-Event": event.event_type.value,
        "X-ATMX-Delivery": event.event_id,
    }

    secret = webhook_store.get_secret(reg.id)
    if secret:
        headers["X-ATMX-Signature"] = f"sha256={_sign_payload(payload_bytes, secret)}"

    backoff = 1.0
    for attempt in range(1, settings.webhook_max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=settings.webhook_timeout_seconds) as client:
                resp = await client.post(
                    reg.callback_url,
                    content=payload_bytes,
                    headers=headers,
                )
            if resp.status_code < 300:
                logger.info(
                    "Webhook delivered: hook=%s event=%s attempt=%d status=%d",
                    reg.id, event.event_type.value, attempt, resp.status_code,
                )
                return True
            if resp.status_code < 500:
                logger.warning(
                    "Webhook rejected (non-retryable): hook=%s status=%d body=%s",
                    reg.id, resp.status_code, resp.text[:200],
                )
                return False
            logger.warning(
                "Webhook server error: hook=%s status=%d attempt=%d",
                reg.id, resp.status_code, attempt,
            )
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            logger.warning(
                "Webhook delivery failed: hook=%s attempt=%d error=%s",
                reg.id, attempt, exc,
            )

        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 30.0)

    logger.error("Webhook delivery exhausted retries: hook=%s event=%s", reg.id, event.event_id)
    return False


async def dispatch(
    event_type: WebhookEventType,
    contract_id: str,
    h3_index: str,
    risk_type: RiskType,
    outcome: str,
    observed_value: float | None = None,
    settled_at: datetime | None = None,
    record_hash: str | None = None,
) -> int:
    """Fan out a settlement event to all registered webhooks.

    Returns the number of successful deliveries.
    """
    registrations = webhook_store.list_for_event(event_type)
    if not registrations:
        return 0

    event = WebhookEvent(
        event_id=uuid.uuid4().hex,
        event_type=event_type,
        timestamp=datetime.now(timezone.utc),
        contract_id=contract_id,
        h3_index=h3_index,
        risk_type=risk_type,
        outcome=outcome,
        observed_value=observed_value,
        settled_at=settled_at,
        record_hash=record_hash,
    )

    payload_bytes = json.dumps(event.model_dump(mode="json"), default=str).encode()

    tasks = [_deliver(reg, event, payload_bytes) for reg in registrations]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    return sum(1 for r in results if r is True)
