"""Settlement record model — immutable, hash-chained audit trail.

Once written, a settlement record is never updated. If a dispute arises,
a new record is appended referencing the original, preserving history.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SettlementOutcome(str, enum.Enum):
    YES = "YES"            # threshold was exceeded
    NO = "NO"              # threshold was not exceeded
    DISPUTED = "DISPUTED"  # conflicting data / insufficient stations


class SettlementRecord(Base):
    __tablename__ = "settlement_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    outcome: Mapped[SettlementOutcome] = mapped_column(
        Enum(SettlementOutcome, name="settlement_outcome"), nullable=False
    )

    # Aggregated observed value used for determination
    observed_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)

    stations_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    station_readings: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Evidence and audit
    evidence_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    dispute_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Hash chain for tamper-evidence
    previous_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    record_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)

    settled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    def __repr__(self) -> str:
        return (
            f"<Settlement {self.id} | contract={self.contract_id} "
            f"outcome={self.outcome.value} hash={self.record_hash[:12]}...>"
        )
