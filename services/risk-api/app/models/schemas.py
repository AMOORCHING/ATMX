"""Pydantic schemas for the developer-facing risk API."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────────


class RiskType(str, Enum):
    PRECIP_HEAVY = "precip_heavy"
    PRECIP_MODERATE = "precip_moderate"
    WIND_HIGH = "wind_high"
    WIND_EXTREME = "wind_extreme"
    TEMP_FREEZE = "temp_freeze"
    TEMP_HEAT = "temp_heat"
    SNOW_HEAVY = "snow_heavy"


class ContractStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    SETTLED_YES = "settled_yes"
    SETTLED_NO = "settled_no"
    DISPUTED = "disputed"
    EXPIRED = "expired"


RISK_TYPE_CONFIG: dict[RiskType, dict[str, Any]] = {
    RiskType.PRECIP_HEAVY: {
        "oracle_source": "NOAA_ASOS",
        "threshold_mm": 12.7,
        "unit": "mm",
        "aggregation": "sum",
        "internal_type": "PRECIP",
        "internal_threshold": "13MM",
        "metric": "precipitation",
    },
    RiskType.PRECIP_MODERATE: {
        "oracle_source": "NOAA_ASOS",
        "threshold_mm": 6.35,
        "unit": "mm",
        "aggregation": "sum",
        "internal_type": "PRECIP",
        "internal_threshold": "6MM",
        "metric": "precipitation",
    },
    RiskType.WIND_HIGH: {
        "oracle_source": "NOAA_ASOS",
        "threshold_ms": 20.0,
        "unit": "m/s",
        "aggregation": "max",
        "internal_type": "WIND",
        "internal_threshold": "20MS",
        "metric": "wind_speed",
    },
    RiskType.WIND_EXTREME: {
        "oracle_source": "NOAA_ASOS",
        "threshold_ms": 30.0,
        "unit": "m/s",
        "aggregation": "max",
        "internal_type": "WIND",
        "internal_threshold": "30MS",
        "metric": "wind_speed",
    },
    RiskType.TEMP_FREEZE: {
        "oracle_source": "NOAA_ASOS",
        "threshold_c": 0.0,
        "unit": "°C",
        "aggregation": "min",
        "internal_type": "TEMP",
        "internal_threshold": "0C",
        "metric": "temperature",
    },
    RiskType.TEMP_HEAT: {
        "oracle_source": "NOAA_ASOS",
        "threshold_c": 40.0,
        "unit": "°C",
        "aggregation": "max",
        "internal_type": "TEMP",
        "internal_threshold": "40C",
        "metric": "temperature",
    },
    RiskType.SNOW_HEAVY: {
        "oracle_source": "NOAA_ASOS",
        "threshold_cm": 15.0,
        "unit": "cm",
        "aggregation": "sum",
        "internal_type": "SNOW",
        "internal_threshold": "15CM",
        "metric": "snowfall",
    },
}


# ── Settlement Rule ───────────────────────────────────────────────────────────


class SettlementRule(BaseModel):
    version: str = Field(description="Settlement rule version")
    oracle_source: str = Field(description="Official data source used for settlement")
    threshold_mm: float | None = Field(default=None, description="Precipitation threshold in mm")
    threshold_ms: float | None = Field(default=None, description="Wind speed threshold in m/s")
    threshold_c: float | None = Field(default=None, description="Temperature threshold in °C")
    threshold_cm: float | None = Field(default=None, description="Snow threshold in cm")
    aggregation: str = Field(description="Aggregation method (sum, max, min)")
    min_stations: int = Field(description="Minimum ASOS stations required")
    dispute_spread_ratio: float = Field(
        description="Station disagreement ratio that triggers DISPUTED"
    )

    model_config = {"json_schema_extra": {"example": {
        "version": "v1.3",
        "oracle_source": "NOAA_ASOS",
        "threshold_mm": 12.7,
        "aggregation": "sum",
        "min_stations": 1,
        "dispute_spread_ratio": 0.2,
    }}}


# ── Risk Price Response ───────────────────────────────────────────────────────


class RiskPriceResponse(BaseModel):
    h3_index: str = Field(description="H3 cell index")
    risk_type: RiskType
    risk_probability: float = Field(ge=0, le=1, description="Exceedance probability [0, 1]")
    confidence_interval: list[float] = Field(
        min_length=2, max_length=2, description="[lower, upper] bounds on the probability"
    )
    suggested_premium_usd: float = Field(ge=0, description="LMSR-derived premium in USD")
    settlement_rule: SettlementRule
    pricing_model: str = Field(description="Identifier for the pricing model used")
    valid_until: datetime = Field(description="ISO 8601 timestamp after which to re-query")


# ── Contract Creation ─────────────────────────────────────────────────────────


class ContractCreateRequest(BaseModel):
    h3_index: str = Field(
        description="H3 cell index at resolution 7-8",
        examples=["882a100d25fffff"],
    )
    risk_type: RiskType
    start_time: datetime
    end_time: datetime
    notional_usd: float = Field(default=10.0, gt=0, description="Payout if threshold is exceeded")


class ContractCreateResponse(BaseModel):
    contract_id: str = Field(description="Unique contract identifier")
    h3_index: str
    risk_type: RiskType
    start_time: datetime
    end_time: datetime
    notional_usd: float
    premium_usd: float = Field(description="Premium charged for this contract")
    settlement_rule: SettlementRule
    status: ContractStatus
    created_at: datetime
    ticker: str = Field(description="Internal market ticker (ATMX-{h3}-{type}-{threshold}-{date})")


# ── Contract Status ───────────────────────────────────────────────────────────


class ContractStatusResponse(BaseModel):
    contract_id: str
    status: ContractStatus
    h3_index: str
    risk_type: RiskType
    start_time: datetime
    end_time: datetime
    outcome: str | None = Field(
        default=None, description="Settlement outcome: YES, NO, or DISPUTED"
    )
    observed_value: float | None = Field(
        default=None, description="Observed metric value at settlement"
    )
    settled_at: datetime | None = None
    record_hash: str | None = Field(
        default=None, description="SHA-256 hash of the settlement record"
    )


# ── Settlement Verification ──────────────────────────────────────────────────


class VerifyRequest(BaseModel):
    expected_hash: str | None = Field(
        default=None,
        description="If provided, verify the record hash matches this value",
    )


class VerifyResponse(BaseModel):
    contract_id: str
    chain_valid: bool = Field(description="Whether the hash chain is intact")
    record_hash: str
    previous_hash: str | None
    outcome: str
    verified_at: datetime


# ── Coverage ──────────────────────────────────────────────────────────────────


class CoverageRequest(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    radius_km: float = Field(gt=0, le=500, default=25.0)
    risk_type: RiskType | None = None


class CellCoverage(BaseModel):
    h3_index: str
    center_lat: float
    center_lng: float
    available_risk_types: list[RiskType]
    has_active_market: bool


class CoverageResponse(BaseModel):
    center_lat: float
    center_lng: float
    radius_km: float
    cells: list[CellCoverage]
    total_cells: int


# ── Webhooks ─────────────────────────────────────────────────────────────────


class WebhookEventType(str, Enum):
    CONTRACT_SETTLED = "contract.settled"
    CONTRACT_DISPUTED = "contract.disputed"
    CONTRACT_EXPIRED = "contract.expired"


ALL_SETTLEMENT_EVENTS: list[WebhookEventType] = [
    WebhookEventType.CONTRACT_SETTLED,
    WebhookEventType.CONTRACT_DISPUTED,
    WebhookEventType.CONTRACT_EXPIRED,
]


class WebhookCreateRequest(BaseModel):
    callback_url: str = Field(
        description="HTTPS URL that will receive POST notifications",
        examples=["https://platform.example.com/hooks/atmx"],
    )
    events: list[WebhookEventType] = Field(
        default_factory=lambda: list(ALL_SETTLEMENT_EVENTS),
        description="Event types to subscribe to (defaults to all settlement events)",
    )
    secret: str | None = Field(
        default=None,
        description="Shared secret for HMAC-SHA256 signature verification on payloads",
    )


class WebhookRegistration(BaseModel):
    id: str = Field(description="Unique webhook registration ID")
    callback_url: str
    events: list[WebhookEventType]
    created_at: datetime
    active: bool = True


class WebhookCreateResponse(BaseModel):
    id: str
    callback_url: str
    events: list[WebhookEventType]
    created_at: datetime
    active: bool = True


class WebhookListResponse(BaseModel):
    webhooks: list[WebhookRegistration]
    total: int


class WebhookEvent(BaseModel):
    """Payload delivered to the platform's callback URL."""
    event_id: str = Field(description="Unique event ID for idempotency")
    event_type: WebhookEventType
    timestamp: datetime
    contract_id: str
    h3_index: str
    risk_type: RiskType
    outcome: str = Field(description="YES, NO, or DISPUTED")
    observed_value: float | None = None
    settled_at: datetime | None = None
    record_hash: str | None = None


# ── Errors ────────────────────────────────────────────────────────────────────


class ErrorResponse(BaseModel):
    detail: str
    code: str | None = None
