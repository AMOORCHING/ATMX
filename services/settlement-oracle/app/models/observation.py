"""Observation model — stores official ASOS/AWOS sensor readings.

Each row represents one station's reading mapped to its H3 cell.
Multiple stations may exist inside one H3 cell; the settlement engine
aggregates them and detects conflicts.
"""

import enum
import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Enum, Float, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ObservationSource(str, enum.Enum):
    ASOS = "ASOS"
    AWOS = "AWOS"
    MANUAL = "MANUAL"  # fallback / manual override for testing


class Observation(Base):
    __tablename__ = "observations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    station_id: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    source: Mapped[ObservationSource] = mapped_column(
        Enum(ObservationSource, name="observation_source"), nullable=False
    )

    h3_cell: Mapped[str] = mapped_column(String(16), nullable=False, index=True)

    # PostGIS point for the station
    location: Mapped[str | None] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326), nullable=True
    )

    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Measured values — only relevant fields are populated per observation type
    precipitation_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_speed_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Quality flags from the source network
    quality_flag: Mapped[str | None] = mapped_column(String(8), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    def __repr__(self) -> str:
        return (
            f"<Observation {self.station_id} @ {self.observed_at} "
            f"precip={self.precipitation_mm}mm wind={self.wind_speed_ms}m/s>"
        )
