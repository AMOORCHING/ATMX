"""Request logging middleware with per-key attribution and rate-limit headers."""

from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("atmx.access")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = uuid.uuid4().hex[:12]
        request.state.request_id = request_id

        start = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - start) * 1000, 1)

        response.headers["X-Request-ID"] = request_id

        if hasattr(request.state, "rate_limit"):
            response.headers["X-RateLimit-Limit"] = str(request.state.rate_limit)
            response.headers["X-RateLimit-Remaining"] = str(
                getattr(request.state, "rate_limit_remaining", 0)
            )

        key_id = getattr(getattr(request.state, "api_key", None), "id", "-")

        logger.info(
            "%s %s %d %.1fms key=%s req=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            key_id,
            request_id,
        )

        return response
