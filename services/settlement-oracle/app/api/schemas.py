"""Pydantic schemas for the REST API request/response models."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.contract import ContractMetric
from app.models.settlement import SettlementOutcome


# ── Contract ──────────────────────────────────────────────────────────────────


class ContractCreate(BaseModel):
    """Request body for creating a new contract."""

    h3_cell: str = Field(
        ...,
        description="H3 cell index at resolution 7",
        examples=["872a1070bffffff"],
    )
    metric: ContractMetric
    threshold: float = Field(..., gt=0, description="Threshold value for the metric")
    unit: str = Field(..., description="Unit of measurement (mm, m/s)")
    window_hours: int = Field(default=24, gt=0, le=168)
    expiry_utc: datetime
    description: str | None = None


class ContractResponse(BaseModel):
    id: uuid.UUID
    h3_cell: str
    metric: ContractMetric
    threshold: float
    unit: str
    window_hours: int
    expiry_utc: datetime
    description: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Settlement ────────────────────────────────────────────────────────────────


class SettlementResponse(BaseModel):
    """Response from POST /settle/{contract_id}."""

    id: uuid.UUID
    contract_id: uuid.UUID
    outcome: SettlementOutcome
    observed_value: float | None
    threshold: float
    unit: str
    stations_used: int
    station_readings: dict[str, Any] | None
    dispute_reason: str | None
    record_hash: str
    previous_hash: str | None
    evidence_payload: dict[str, Any] | None
    settled_at: datetime

    model_config = {"from_attributes": True}


class ErrorResponse(BaseModel):
    detail: str
