"""API key authentication, per-key rate limiting, and usage tracking.

In-memory stores for development — swap for Postgres/Redis in production.
Keys use the format ``atmx_sk_<48 hex chars>`` and are stored as SHA-256 hashes.
The raw key is only returned once at creation time.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

logger = logging.getLogger(__name__)

KEY_PREFIX = "atmx_sk_"

bearer_scheme = HTTPBearer(
    scheme_name="API Key",
    description="Pass your API key as: `Authorization: Bearer atmx_sk_...`",
)

admin_scheme = HTTPBearer(
    scheme_name="Admin Secret",
    description="Pass the admin secret as: `Authorization: Bearer <ADMIN_SECRET>`",
)


# ── Data types ────────────────────────────────────────────────────────────────


@dataclass
class APIKey:
    id: str
    name: str
    key_hash: str
    prefix: str
    created_at: datetime
    active: bool = True
    rate_limit: int | None = None


@dataclass
class KeyUsage:
    total_requests: int = 0
    requests_by_endpoint: dict[str, int] = field(default_factory=dict)
    last_request_at: datetime | None = None
    error_count: int = 0


# ── Key store ─────────────────────────────────────────────────────────────────

_keys: dict[str, APIKey] = {}
_hash_index: dict[str, str] = {}


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def create_key(name: str, rate_limit: int | None = None) -> tuple[APIKey, str]:
    """Create a new API key.  Returns ``(APIKey, raw_key)``.

    The raw key is only available at creation time.
    """
    raw = KEY_PREFIX + secrets.token_hex(24)
    key_hash = _hash_key(raw)
    key_id = secrets.token_hex(8)

    api_key = APIKey(
        id=key_id,
        name=name,
        key_hash=key_hash,
        prefix=raw[:16] + "...",
        created_at=datetime.now(timezone.utc),
        active=True,
        rate_limit=rate_limit,
    )
    _keys[key_id] = api_key
    _hash_index[key_hash] = key_id
    return api_key, raw


def validate_key(raw_key: str) -> APIKey | None:
    key_hash = _hash_key(raw_key)
    key_id = _hash_index.get(key_hash)
    if key_id is None:
        return None
    api_key = _keys.get(key_id)
    if api_key is None or not api_key.active:
        return None
    return api_key


def get_key(key_id: str) -> APIKey | None:
    return _keys.get(key_id)


def list_keys() -> list[APIKey]:
    return list(_keys.values())


def revoke_key(key_id: str) -> bool:
    api_key = _keys.get(key_id)
    if api_key is None:
        return False
    api_key.active = False
    _hash_index.pop(api_key.key_hash, None)
    return True


# ── Rate limiter (sliding window) ────────────────────────────────────────────

_windows: dict[str, deque[float]] = defaultdict(deque)


def check_rate_limit(api_key: APIKey) -> tuple[bool, int, int]:
    """Returns ``(allowed, remaining, retry_after_seconds)``."""
    limit = api_key.rate_limit or settings.default_rate_limit
    window_sec = settings.rate_limit_window_seconds
    now = time.monotonic()

    dq = _windows[api_key.id]
    while dq and dq[0] < now - window_sec:
        dq.popleft()

    remaining = limit - len(dq)
    if remaining <= 0:
        retry_after = int(dq[0] + window_sec - now) + 1
        return False, 0, retry_after

    dq.append(now)
    return True, remaining - 1, 0


# ── Usage tracker ─────────────────────────────────────────────────────────────

_usage: dict[str, KeyUsage] = defaultdict(KeyUsage)


def record_request(key_id: str, endpoint: str, is_error: bool = False) -> None:
    u = _usage[key_id]
    u.total_requests += 1
    u.requests_by_endpoint[endpoint] = u.requests_by_endpoint.get(endpoint, 0) + 1
    u.last_request_at = datetime.now(timezone.utc)
    if is_error:
        u.error_count += 1


def get_usage(key_id: str) -> KeyUsage:
    return _usage[key_id]


# ── FastAPI dependencies ─────────────────────────────────────────────────────


async def require_api_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
) -> APIKey:
    """Validate the bearer token and enforce per-key rate limits."""
    api_key = validate_key(credentials.credentials)
    if api_key is None:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "INVALID_API_KEY",
                "message": (
                    "The API key is invalid, revoked, or missing. "
                    "Obtain a key via POST /admin/api_keys."
                ),
            },
        )

    allowed, remaining, retry_after = check_rate_limit(api_key)

    request.state.api_key = api_key
    request.state.rate_limit = api_key.rate_limit or settings.default_rate_limit
    request.state.rate_limit_remaining = remaining

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "RATE_LIMIT_EXCEEDED",
                "message": f"Rate limit of {request.state.rate_limit}/min exceeded. Retry in {retry_after}s.",
                "retry_after": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )

    record_request(api_key.id, request.url.path)
    return api_key


async def require_admin(
    credentials: HTTPAuthorizationCredentials = Security(admin_scheme),
) -> bool:
    """Validate the admin secret for key-management endpoints."""
    if not secrets.compare_digest(credentials.credentials, settings.admin_secret):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "FORBIDDEN",
                "message": "Invalid admin secret.",
            },
        )
    return True


# ── Bootstrap ─────────────────────────────────────────────────────────────────


def bootstrap() -> None:
    """Pre-populate a bootstrap API key from env var if set."""
    if settings.bootstrap_api_key:
        key_hash = _hash_key(settings.bootstrap_api_key)
        api_key = APIKey(
            id="bootstrap",
            name="bootstrap",
            key_hash=key_hash,
            prefix=settings.bootstrap_api_key[:16] + "...",
            created_at=datetime.now(timezone.utc),
        )
        _keys["bootstrap"] = api_key
        _hash_index[key_hash] = "bootstrap"
        logger.info("Bootstrap API key loaded (prefix=%s)", api_key.prefix)
