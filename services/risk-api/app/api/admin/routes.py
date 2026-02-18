"""Admin endpoints for API key management.

Protected by ADMIN_SECRET — these are for the ATMX operator, not end-user
platforms.  Platforms receive their keys from the operator and use the
``Authorization: Bearer atmx_sk_...`` header on /v1/* endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth import (
    create_key,
    get_key,
    get_usage,
    list_keys,
    require_admin,
    revoke_key,
)

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.post(
    "/api_keys",
    status_code=status.HTTP_201_CREATED,
    summary="Issue a new API key",
    description=(
        "Creates a new API key for a platform.  The raw key is returned **only once** — "
        "store it securely.  Subsequent list calls show only the key prefix."
    ),
)
async def create_api_key(
    name: str = Query(description="Human-readable label for this key (e.g. 'acme-staging')"),
    rate_limit: int | None = Query(
        default=None,
        description="Custom rate limit (requests/min).  Omit to use the server default.",
    ),
) -> dict:
    api_key, raw_key = create_key(name=name, rate_limit=rate_limit)
    return {
        "id": api_key.id,
        "name": api_key.name,
        "key": raw_key,
        "prefix": api_key.prefix,
        "created_at": api_key.created_at.isoformat(),
        "rate_limit": api_key.rate_limit or "default",
        "message": "Store this key securely — it will not be shown again.",
    }


@router.get(
    "/api_keys",
    summary="List all API keys",
    description="Returns metadata for every issued key (no secrets exposed).",
)
async def list_api_keys() -> dict:
    keys = list_keys()
    return {
        "keys": [
            {
                "id": k.id,
                "name": k.name,
                "prefix": k.prefix,
                "active": k.active,
                "created_at": k.created_at.isoformat(),
                "rate_limit": k.rate_limit or "default",
                "total_requests": get_usage(k.id).total_requests,
            }
            for k in keys
        ],
        "total": len(keys),
    }


@router.get(
    "/api_keys/{key_id}/usage",
    summary="Get usage metrics for an API key",
    description=(
        "Returns per-endpoint request counts, error count, and last activity "
        "timestamp — the data you need for a usage dashboard."
    ),
)
async def get_key_usage(key_id: str) -> dict:
    api_key = get_key(key_id)
    if api_key is None:
        raise HTTPException(status_code=404, detail="API key not found")

    usage = get_usage(key_id)
    return {
        "key_id": key_id,
        "name": api_key.name,
        "active": api_key.active,
        "total_requests": usage.total_requests,
        "error_count": usage.error_count,
        "last_request_at": usage.last_request_at.isoformat() if usage.last_request_at else None,
        "endpoints": usage.requests_by_endpoint,
    }


@router.delete(
    "/api_keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke an API key",
    description="Immediately deactivates the key.  In-flight requests may still complete.",
)
async def revoke_api_key(key_id: str) -> None:
    if not revoke_key(key_id):
        raise HTTPException(status_code=404, detail="API key not found")
