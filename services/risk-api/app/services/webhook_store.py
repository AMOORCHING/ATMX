"""In-memory webhook registration store.

Swap this for a Postgres/Redis-backed implementation in production.
The interface stays the same — register, list, get, remove — so the
route layer doesn't care about the backing store.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.models.schemas import WebhookEventType, WebhookRegistration


_webhooks: dict[str, WebhookRegistration] = {}

# Maps webhook_id -> shared secret (kept separate from the public registration)
_secrets: dict[str, str] = {}


def register(
    callback_url: str,
    events: list[WebhookEventType],
    secret: str | None = None,
) -> WebhookRegistration:
    hook_id = uuid.uuid4().hex[:16]
    reg = WebhookRegistration(
        id=hook_id,
        callback_url=callback_url,
        events=events,
        created_at=datetime.now(timezone.utc),
        active=True,
    )
    _webhooks[hook_id] = reg
    if secret:
        _secrets[hook_id] = secret
    return reg


def get(hook_id: str) -> WebhookRegistration | None:
    return _webhooks.get(hook_id)


def get_secret(hook_id: str) -> str | None:
    return _secrets.get(hook_id)


def remove(hook_id: str) -> bool:
    removed = _webhooks.pop(hook_id, None) is not None
    _secrets.pop(hook_id, None)
    return removed


def list_all() -> list[WebhookRegistration]:
    return list(_webhooks.values())


def list_for_event(event_type: WebhookEventType) -> list[WebhookRegistration]:
    """Return all active registrations subscribed to this event type."""
    return [
        reg for reg in _webhooks.values()
        if reg.active and event_type in reg.events
    ]
