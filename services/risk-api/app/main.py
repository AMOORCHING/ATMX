"""ATMX Risk API — developer-facing interface for weather derivative pricing.

This service sits in front of the market engine and settlement oracle,
exposing a clean API that returns everything a platform needs to make
automated hedging decisions: exceedance probabilities, LMSR-derived premiums,
settlement rules, and contract management.

The settlement cron runs as a background task, watching for expired contracts
and auto-resolving them against ASOS data via the settlement oracle.
Platforms receive outcomes via registered webhooks — no polling required.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin.routes import router as admin_router
from app.api.v1.routes import router as v1_router
from app.core import auth
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.core.middleware import RequestLoggingMiddleware
from app.services import settlement_cron

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

logger = logging.getLogger(__name__)


DESCRIPTION = """\
Developer-facing risk pricing API for **ATMX weather derivatives**.

Converts NWS ensemble forecasts into exceedance probabilities and LMSR-derived
premiums.  Includes webhook-driven settlement notifications and automatic
contract resolution via a background cron pipeline.

---

### Contract Lifecycle

| Step | Endpoint | Description |
|------|----------|-------------|
| 1 | `GET /v1/risk_price` | Get exceedance probability + premium for an H3 cell |
| 2 | `POST /v1/contracts` | Lock in a contract at the quoted price |
| 3 | *automatic* | Settlement cron resolves against ASOS at expiry |
| 4 | `POST /v1/webhooks` | Register a callback — get POSTed on settlement |
| 5 | `GET /v1/contracts/{id}/status` | Polling fallback if you prefer |

### Authentication

All `/v1/*` endpoints require a **Bearer token**:

```
Authorization: Bearer atmx_sk_...
```

Get your key from the operator via `POST /admin/api_keys` (requires admin secret).

### Rate Limits

Default: **60 requests/minute** per key.  Override per-key via the admin endpoint.
Rate limit headers (`X-RateLimit-Limit`, `X-RateLimit-Remaining`) are included
in every response.
"""


TAGS_METADATA = [
    {
        "name": "risk",
        "description": "Risk pricing, contract management, and settlement verification.",
    },
    {
        "name": "webhooks",
        "description": "Webhook registration for push-based settlement notifications.",
    },
    {
        "name": "admin",
        "description": "API key management (issue, list, revoke, usage). Requires admin secret.",
    },
    {
        "name": "ops",
        "description": "Health checks and operational endpoints.",
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    auth.bootstrap()

    cron_task = None
    if settings.settlement_cron_enabled:
        logger.info("Starting settlement cron background task")
        cron_task = asyncio.create_task(settlement_cron.run_settlement_loop())
    yield
    if cron_task is not None:
        settlement_cron.stop()
        cron_task.cancel()
        try:
            await cron_task
        except asyncio.CancelledError:
            pass
        logger.info("Settlement cron shut down")


app = FastAPI(
    title="ATMX Risk API",
    version="0.2.0",
    description=DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=TAGS_METADATA,
    lifespan=lifespan,
    swagger_ui_parameters={
        "persistAuthorization": True,
        "displayRequestDuration": True,
        "docExpansion": "list",
        "filter": True,
    },
)

register_error_handlers(app)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router)
app.include_router(admin_router)


@app.get("/health", tags=["ops"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "risk-api"}
