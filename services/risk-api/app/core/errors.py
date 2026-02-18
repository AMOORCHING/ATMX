"""Structured error response handlers.

Every error — validation, auth, upstream, or unexpected — returns:

    {
      "error": {
        "code": "DESCRIPTIVE_CODE",
        "message": "Human-readable explanation of what went wrong.",
        "request_id": "abc123...",
        ...extra fields when relevant
      }
    }
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

_STATUS_CODE_MAP: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMIT_EXCEEDED",
    502: "UPSTREAM_ERROR",
    503: "SERVICE_UNAVAILABLE",
}


def register_error_handlers(app: FastAPI) -> None:

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)

        if isinstance(exc.detail, dict):
            body = {"error": {**exc.detail, "request_id": request_id}}
        else:
            body = {
                "error": {
                    "code": _STATUS_CODE_MAP.get(exc.status_code, "ERROR"),
                    "message": str(exc.detail),
                    "request_id": request_id,
                }
            }

        return JSONResponse(
            status_code=exc.status_code,
            content=body,
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)

        fields = []
        for err in exc.errors():
            loc = " -> ".join(str(part) for part in err["loc"])
            fields.append({"field": loc, "message": err["msg"], "type": err["type"]})

        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": f"{len(fields)} validation error(s) in your request.",
                    "details": fields,
                    "request_id": request_id,
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        logger.exception("Unhandled error (request_id=%s)", request_id)

        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": (
                        "An unexpected error occurred. "
                        "If this persists, contact support with the request_id."
                    ),
                    "request_id": request_id,
                }
            },
        )
