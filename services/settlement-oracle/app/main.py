"""FastAPI application entry point for the Weather Contract Settlement Service."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

app = FastAPI(
    title="Settlement Oracle",
    description=(
        "NOAA ingestion and weather contract resolution oracle. Settles weather "
        "derivative contracts against official ASOS/AWOS observations. Part of the "
        "atmx weather derivative trading platform."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1", tags=["settlement"])


@app.get("/health", tags=["ops"])
async def health_check() -> dict:
    return {"status": "ok", "service": "settlement-oracle"}
