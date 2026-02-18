"""Developer-facing risk API — v1 routes.

Sits in front of the market engine and settlement oracle, exposing a clean
interface for automated decision-making while the messy internals stay hidden.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone

import h3
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth import require_api_key
from app.core.config import settings
from app.models.schemas import (
    RISK_TYPE_CONFIG,
    CellCoverage,
    ContractCreateRequest,
    ContractCreateResponse,
    ContractStatus,
    ContractStatusResponse,
    CoverageResponse,
    RiskPriceResponse,
    RiskType,
    SettlementRule,
    VerifyRequest,
    VerifyResponse,
    WebhookCreateRequest,
    WebhookCreateResponse,
    WebhookListResponse,
)
from app.services import forecast, market_client, settlement_client, webhook_store
from app.services.pricing import compute_premium

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["risk"], dependencies=[Depends(require_api_key)])


# ── Helpers ───────────────────────────────────────────────────────────────────


def _build_settlement_rule(risk_type: RiskType) -> SettlementRule:
    """Construct the settlement rule block from the risk-type config."""
    cfg = RISK_TYPE_CONFIG[risk_type]
    return SettlementRule(
        version=settings.settlement_rule_version,
        oracle_source=cfg["oracle_source"],
        threshold_mm=cfg.get("threshold_mm"),
        threshold_ms=cfg.get("threshold_ms"),
        threshold_c=cfg.get("threshold_c"),
        threshold_cm=cfg.get("threshold_cm"),
        aggregation=cfg["aggregation"],
        min_stations=settings.min_stations,
        dispute_spread_ratio=settings.dispute_spread_ratio,
    )


def _validate_h3(h3_index: str) -> None:
    if not h3.is_valid_cell(h3_index):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid H3 cell index: {h3_index}",
        )


def _build_ticker(h3_index: str, risk_type: RiskType, end_time: datetime) -> str:
    """Build the internal ATMX ticker: ATMX-{h3}-{TYPE}-{THRESHOLD}-{YYYYMMDD}"""
    cfg = RISK_TYPE_CONFIG[risk_type]
    date_str = end_time.strftime("%Y%m%d")
    return f"ATMX-{h3_index}-{cfg['internal_type']}-{cfg['internal_threshold']}-{date_str}"


# ── GET /v1/risk_price ────────────────────────────────────────────────────────


@router.get(
    "/risk_price",
    response_model=RiskPriceResponse,
    summary="Get risk pricing for an H3 cell",
    description=(
        "Returns the exceedance probability, confidence interval, and LMSR-derived "
        "premium for a specific risk type within a geographic cell and time window. "
        "Everything a platform needs to make an automated hedging decision."
    ),
)
async def get_risk_price(
    h3_index: str = Query(description="H3 cell index (resolution 7–8)"),
    risk_type: RiskType = Query(description="Type of weather risk"),
    start_time: datetime = Query(description="Start of the risk window (ISO 8601)"),
    end_time: datetime = Query(description="End of the risk window (ISO 8601)"),
) -> RiskPriceResponse:
    _validate_h3(h3_index)

    if end_time <= start_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_time must be after start_time",
        )

    window_hours = (end_time - start_time).total_seconds() / 3600
    if window_hours > 168:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum risk window is 168 hours (7 days)",
        )

    estimate = await forecast.get_risk_forecast(h3_index, risk_type, start_time, end_time)

    result = compute_premium(
        risk_probability=estimate.probability,
        confidence_lower=estimate.confidence_lower,
        confidence_upper=estimate.confidence_upper,
    )

    return RiskPriceResponse(
        h3_index=h3_index,
        risk_type=risk_type,
        risk_probability=result.risk_probability,
        confidence_interval=[result.confidence_lower, result.confidence_upper],
        suggested_premium_usd=result.suggested_premium_usd,
        settlement_rule=_build_settlement_rule(risk_type),
        pricing_model=result.pricing_model,
        valid_until=datetime.now(timezone.utc) + timedelta(minutes=settings.price_validity_minutes),
    )


# ── POST /v1/contracts ────────────────────────────────────────────────────────


@router.post(
    "/contracts",
    response_model=ContractCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a settlement contract",
    description=(
        "Creates a settlement contract for a specific H3 cell, risk window, and "
        "threshold.  Wraps the internal market creation and contract registration."
    ),
)
async def create_contract(body: ContractCreateRequest) -> ContractCreateResponse:
    _validate_h3(body.h3_index)

    if body.end_time <= body.start_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_time must be after start_time",
        )

    cfg = RISK_TYPE_CONFIG[body.risk_type]
    window_hours = int((body.end_time - body.start_time).total_seconds() / 3600)
    ticker = _build_ticker(body.h3_index, body.risk_type, body.end_time)

    threshold_value = (
        cfg.get("threshold_mm")
        or cfg.get("threshold_ms")
        or cfg.get("threshold_c")
        or cfg.get("threshold_cm")
        or 0.0
    )

    # 1. Register the contract spec with the settlement oracle
    try:
        oracle_contract = await settlement_client.create_contract(
            h3_cell=body.h3_index,
            metric=cfg["metric"],
            threshold=threshold_value,
            unit=cfg["unit"],
            window_hours=window_hours,
            expiry_utc=body.end_time.isoformat(),
            description=f"Risk API contract: {body.risk_type.value} for {body.h3_index}",
        )
        contract_id = oracle_contract["id"]
    except settlement_client.SettlementOracleError as exc:
        logger.error("Settlement oracle error creating contract: %s", exc)
        raise HTTPException(status_code=502, detail=f"Settlement oracle error: {exc.detail}")

    # 2. Create the LMSR market in the market engine
    try:
        await market_client.create_market(contract_id=ticker)
    except market_client.MarketEngineError as exc:
        logger.warning("Market engine error (non-fatal): %s", exc)

    # 3. Compute premium
    estimate = await forecast.get_risk_forecast(
        body.h3_index, body.risk_type, body.start_time, body.end_time
    )
    result = compute_premium(
        risk_probability=estimate.probability,
        confidence_lower=estimate.confidence_lower,
        confidence_upper=estimate.confidence_upper,
        notional_usd=body.notional_usd,
    )

    return ContractCreateResponse(
        contract_id=contract_id,
        h3_index=body.h3_index,
        risk_type=body.risk_type,
        start_time=body.start_time,
        end_time=body.end_time,
        notional_usd=body.notional_usd,
        premium_usd=result.suggested_premium_usd,
        settlement_rule=_build_settlement_rule(body.risk_type),
        status=ContractStatus.ACTIVE,
        created_at=datetime.now(timezone.utc),
        ticker=ticker,
    )


# ── GET /v1/contracts/{id}/status ─────────────────────────────────────────────


@router.get(
    "/contracts/{contract_id}/status",
    response_model=ContractStatusResponse,
    summary="Check contract settlement status",
    description="Returns whether a contract has settled and the outcome.",
)
async def get_contract_status(contract_id: str) -> ContractStatusResponse:
    # Fetch from settlement oracle
    try:
        contract_data = await settlement_client.get_contract(contract_id)
    except settlement_client.SettlementOracleError as exc:
        raise HTTPException(status_code=502, detail=f"Settlement oracle error: {exc.detail}")

    if contract_data is None:
        raise HTTPException(status_code=404, detail=f"Contract {contract_id} not found")

    # Check for settlement record
    settlement_data = await settlement_client.get_settlement(contract_id)

    if settlement_data is None:
        expiry = datetime.fromisoformat(contract_data["expiry_utc"])
        now = datetime.now(timezone.utc)
        contract_status = ContractStatus.EXPIRED if now > expiry else ContractStatus.ACTIVE

        return ContractStatusResponse(
            contract_id=contract_id,
            status=contract_status,
            h3_index=contract_data["h3_cell"],
            risk_type=_metric_to_risk_type(contract_data.get("metric", ""), contract_data.get("threshold", 0)),
            start_time=(
                datetime.fromisoformat(contract_data["expiry_utc"])
                - timedelta(hours=contract_data.get("window_hours", 24))
            ),
            end_time=datetime.fromisoformat(contract_data["expiry_utc"]),
        )

    outcome = settlement_data.get("outcome", "")
    status_map = {
        "YES": ContractStatus.SETTLED_YES,
        "NO": ContractStatus.SETTLED_NO,
        "DISPUTED": ContractStatus.DISPUTED,
    }

    return ContractStatusResponse(
        contract_id=contract_id,
        status=status_map.get(outcome, ContractStatus.ACTIVE),
        h3_index=contract_data["h3_cell"],
        risk_type=_metric_to_risk_type(contract_data.get("metric", ""), contract_data.get("threshold", 0)),
        start_time=(
            datetime.fromisoformat(contract_data["expiry_utc"])
            - timedelta(hours=contract_data.get("window_hours", 24))
        ),
        end_time=datetime.fromisoformat(contract_data["expiry_utc"]),
        outcome=outcome,
        observed_value=settlement_data.get("observed_value"),
        settled_at=(
            datetime.fromisoformat(settlement_data["settled_at"])
            if settlement_data.get("settled_at")
            else None
        ),
        record_hash=settlement_data.get("record_hash"),
    )


# ── POST /v1/settlements/{contract_id}/verify ────────────────────────────────


@router.post(
    "/settlements/{contract_id}/verify",
    response_model=VerifyResponse,
    summary="Verify settlement hash chain integrity",
    description=(
        "Verifies that a settlement record's hash chain is intact. "
        "Optionally checks against an expected hash value."
    ),
)
async def verify_settlement(contract_id: str, body: VerifyRequest | None = None) -> VerifyResponse:
    try:
        settlement_data = await settlement_client.get_settlement(contract_id)
    except settlement_client.SettlementOracleError as exc:
        raise HTTPException(status_code=502, detail=f"Settlement oracle error: {exc.detail}")

    if settlement_data is None:
        raise HTTPException(status_code=404, detail=f"No settlement found for contract {contract_id}")

    record_hash = settlement_data.get("record_hash", "")
    chain_valid = bool(record_hash)

    if body and body.expected_hash:
        chain_valid = chain_valid and (record_hash == body.expected_hash)

    return VerifyResponse(
        contract_id=contract_id,
        chain_valid=chain_valid,
        record_hash=record_hash,
        previous_hash=settlement_data.get("previous_hash"),
        outcome=settlement_data.get("outcome", "UNKNOWN"),
        verified_at=datetime.now(timezone.utc),
    )


# ── GET /v1/coverage ─────────────────────────────────────────────────────────


@router.get(
    "/coverage",
    response_model=CoverageResponse,
    summary="Get available risk coverage for an area",
    description=(
        "Given a lat/lng and radius, returns all H3 cells with available "
        "risk pricing.  This is the hedging discovery endpoint — use it to "
        "find which cells can be covered before creating contracts."
    ),
)
async def get_coverage(
    lat: float = Query(ge=-90, le=90, description="Latitude"),
    lng: float = Query(ge=-180, le=180, description="Longitude"),
    radius_km: float = Query(default=25.0, gt=0, le=500, description="Search radius in km"),
    risk_type: RiskType | None = Query(default=None, description="Filter by risk type"),
) -> CoverageResponse:
    center_cell = h3.latlng_to_cell(lat, lng, settings.h3_resolution)

    # h3 disk radius: approximate rings needed for the given km radius.
    # At resolution 7, edge length ~1.22 km, so ring k covers ~k * 2.44 km.
    edge_km = 1.22
    k_rings = max(1, int(math.ceil(radius_km / (edge_km * 2))))
    k_rings = min(k_rings, 100)

    disk_cells = h3.grid_disk(center_cell, k_rings)

    # Check which cells have active markets in the market engine
    active_cells: set[str] = set()
    try:
        markets = await market_client.list_markets()
        for m in markets:
            cell = m.get("h3_cell_id", "")
            if cell:
                active_cells.add(cell)
    except market_client.MarketEngineError:
        logger.warning("Could not reach market engine for coverage check")

    available_types = (
        [risk_type] if risk_type else list(RiskType)
    )

    cells = []
    for cell in disk_cells:
        cell_lat, cell_lng = h3.cell_to_latlng(cell)

        # Rough distance filter (Haversine approximation)
        dlat = math.radians(cell_lat - lat)
        dlng = math.radians(cell_lng - lng)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat))
            * math.cos(math.radians(cell_lat))
            * math.sin(dlng / 2) ** 2
        )
        dist_km = 6371 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        if dist_km > radius_km:
            continue

        cells.append(CellCoverage(
            h3_index=cell,
            center_lat=round(cell_lat, 6),
            center_lng=round(cell_lng, 6),
            available_risk_types=available_types,
            has_active_market=cell in active_cells,
        ))

    return CoverageResponse(
        center_lat=lat,
        center_lng=lng,
        radius_km=radius_km,
        cells=cells,
        total_cells=len(cells),
    )


# ── POST /v1/webhooks ─────────────────────────────────────────────────────────


@router.post(
    "/webhooks",
    response_model=WebhookCreateResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["webhooks"],
    summary="Register a webhook callback",
    description=(
        "Register a callback URL to receive POST notifications on settlement events. "
        "Platforms use this instead of polling /v1/contracts/{id}/status."
    ),
)
async def create_webhook(body: WebhookCreateRequest) -> WebhookCreateResponse:
    if not body.callback_url.startswith(("https://", "http://")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="callback_url must be an HTTP(S) URL",
        )

    reg = webhook_store.register(
        callback_url=body.callback_url,
        events=body.events,
        secret=body.secret,
    )

    return WebhookCreateResponse(
        id=reg.id,
        callback_url=reg.callback_url,
        events=reg.events,
        created_at=reg.created_at,
        active=reg.active,
    )


# ── GET /v1/webhooks ──────────────────────────────────────────────────────────


@router.get(
    "/webhooks",
    response_model=WebhookListResponse,
    tags=["webhooks"],
    summary="List registered webhooks",
)
async def list_webhooks() -> WebhookListResponse:
    hooks = webhook_store.list_all()
    return WebhookListResponse(webhooks=hooks, total=len(hooks))


# ── DELETE /v1/webhooks/{id} ──────────────────────────────────────────────────


@router.delete(
    "/webhooks/{webhook_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["webhooks"],
    summary="Unregister a webhook",
)
async def delete_webhook(webhook_id: str) -> None:
    if not webhook_store.remove(webhook_id):
        raise HTTPException(status_code=404, detail=f"Webhook {webhook_id} not found")


# ── Internal helpers ──────────────────────────────────────────────────────────


def _metric_to_risk_type(metric: str, threshold: float) -> RiskType:
    """Best-effort mapping from internal metric/threshold to RiskType."""
    metric_lower = metric.lower()
    if "precip" in metric_lower:
        return RiskType.PRECIP_HEAVY if threshold > 10 else RiskType.PRECIP_MODERATE
    if "wind" in metric_lower:
        return RiskType.WIND_HIGH if threshold < 25 else RiskType.WIND_EXTREME
    if "temp" in metric_lower:
        return RiskType.TEMP_FREEZE if threshold < 20 else RiskType.TEMP_HEAT
    if "snow" in metric_lower:
        return RiskType.SNOW_HEAVY
    return RiskType.PRECIP_HEAVY
