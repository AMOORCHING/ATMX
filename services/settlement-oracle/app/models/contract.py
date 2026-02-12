"""Contract specification model.

A contract defines a weather derivative question:
  "Will <metric> in H3 cell <h3_cell> exceed <threshold> <unit>
   during the <window_hours>-hour window ending at <expiry_utc>?"
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ContractMetric(str, enum.Enum):
    PRECIPITATION = "precipitation"  # total accumulated, mm
    WIND_SPEED = "wind_speed"        # sustained, m/s


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # H3 cell at resolution 7 (~5.16 km²)
    h3_cell: Mapped[str] = mapped_column(String(16), nullable=False, index=True)

    metric: Mapped[ContractMetric] = mapped_column(
        Enum(
            ContractMetric,
            name="contract_metric",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)  # "mm", "m/s"

    window_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    expiry_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    def __repr__(self) -> str:
        return (
            f"<Contract {self.id} | {self.metric.value} > {self.threshold}{self.unit} "
            f"in {self.h3_cell} by {self.expiry_utc}>"
        )
