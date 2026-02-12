"""REST API routes for the contract settlement service."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    ContractCreate,
    ContractResponse,
    ErrorResponse,
    SettlementResponse,
)
from app.core.database import get_session
from app.models.contract import Contract
from app.services.settlement_engine import SettlementError, settle_contract

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/contracts",
    response_model=ContractResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new weather derivative contract",
)
async def create_contract(
    body: ContractCreate,
    session: AsyncSession = Depends(get_session),
) -> Contract:
    """Register a contract specification for future settlement."""
    contract = Contract(
        h3_cell=body.h3_cell,
        metric=body.metric,
        threshold=body.threshold,
        unit=body.unit,
        window_hours=body.window_hours,
        expiry_utc=body.expiry_utc,
        description=body.description,
    )
    session.add(contract)
    await session.flush()
    await session.refresh(contract)
    logger.info("Created contract %s", contract.id)
    return contract


@router.get(
    "/contracts/{contract_id}",
    response_model=ContractResponse,
    summary="Get contract details",
)
async def get_contract(
    contract_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Contract:
    """Retrieve a contract by its ID."""
    from sqlalchemy import select

    stmt = select(Contract).where(Contract.id == contract_id)
    result = await session.execute(stmt)
    contract = result.scalar_one_or_none()
    if contract is None:
        raise HTTPException(status_code=404, detail=f"Contract {contract_id} not found")
    return contract


@router.post(
    "/settle/{contract_id}",
    response_model=SettlementResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Contract not found"},
        409: {"model": ErrorResponse, "description": "Contract already settled"},
        500: {"model": ErrorResponse, "description": "Settlement processing error"},
    },
    summary="Settle a weather derivative contract",
    description=(
        "Triggers settlement for a contract. Pulls official ASOS observations for the "
        "contract's H3 cell, compares against the threshold, and returns YES, NO, or "
        "DISPUTED with full evidence payload. Idempotent — re-calling returns the "
        "existing settlement."
    ),
)
async def settle(
    contract_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> SettlementResponse:
    """Settle a contract and return the settlement record with full evidence.

    Returns:
        - **YES**: Threshold was exceeded.
        - **NO**: Threshold was not exceeded.
        - **DISPUTED**: Conflicting data, sensor outage, or insufficient stations.
    """
    try:
        record = await settle_contract(session, contract_id)
    except SettlementError as exc:
        logger.warning("Settlement failed for %s: %s", contract_id, exc)
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("Unexpected error settling contract %s", contract_id)
        raise HTTPException(status_code=500, detail=f"Settlement error: {exc}")

    return SettlementResponse.model_validate(record)


@router.get(
    "/settlements/{contract_id}",
    response_model=SettlementResponse,
    summary="Get existing settlement record",
)
async def get_settlement(
    contract_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> SettlementResponse:
    """Retrieve the settlement record for a contract if it exists."""
    from sqlalchemy import select
    from app.models.settlement import SettlementRecord

    stmt = select(SettlementRecord).where(SettlementRecord.contract_id == contract_id)
    result = await session.execute(stmt)
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="No settlement found for this contract")
    return SettlementResponse.model_validate(record)
