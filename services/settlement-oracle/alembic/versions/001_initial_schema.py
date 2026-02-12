"""Initial schema: contracts, observations, settlement_records.

Revision ID: 001
Revises:
Create Date: 2025-01-15
"""
from typing import Sequence, Union

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable PostGIS extension
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "contracts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("h3_cell", sa.String(16), nullable=False, index=True),
        sa.Column(
            "metric",
            sa.Enum("precipitation", "wind_speed", name="contract_metric"),
            nullable=False,
        ),
        sa.Column("threshold", sa.Float, nullable=False),
        sa.Column("unit", sa.String(16), nullable=False),
        sa.Column("window_hours", sa.Integer, nullable=False, server_default="24"),
        sa.Column("expiry_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("station_id", sa.String(10), nullable=False, index=True),
        sa.Column(
            "source",
            sa.Enum("ASOS", "AWOS", "MANUAL", name="observation_source"),
            nullable=False,
        ),
        sa.Column("h3_cell", sa.String(16), nullable=False, index=True),
        sa.Column(
            "location",
            geoalchemy2.Geometry(geometry_type="POINT", srid=4326),
            nullable=True,
        ),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("precipitation_mm", sa.Float, nullable=True),
        sa.Column("wind_speed_ms", sa.Float, nullable=True),
        sa.Column("quality_flag", sa.String(8), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "settlement_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "contract_id", postgresql.UUID(as_uuid=True), nullable=False, index=True
        ),
        sa.Column(
            "outcome",
            sa.Enum("YES", "NO", "DISPUTED", name="settlement_outcome"),
            nullable=False,
        ),
        sa.Column("observed_value", sa.Float, nullable=True),
        sa.Column("threshold", sa.Float, nullable=False),
        sa.Column("unit", sa.String(16), nullable=False),
        sa.Column("stations_used", sa.Integer, nullable=False, server_default="0"),
        sa.Column("station_readings", postgresql.JSON, nullable=True),
        sa.Column("evidence_payload", postgresql.JSON, nullable=True),
        sa.Column("dispute_reason", sa.Text, nullable=True),
        sa.Column("previous_hash", sa.String(128), nullable=True),
        sa.Column(
            "record_hash", sa.String(128), nullable=False, unique=True
        ),
        sa.Column(
            "settled_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # Composite index for efficient observation queries
    op.create_index(
        "ix_observations_cell_time",
        "observations",
        ["h3_cell", "observed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_observations_cell_time", table_name="observations")
    op.drop_table("settlement_records")
    op.drop_table("observations")
    op.drop_table("contracts")
    op.execute("DROP TYPE IF EXISTS settlement_outcome")
    op.execute("DROP TYPE IF EXISTS observation_source")
    op.execute("DROP TYPE IF EXISTS contract_metric")
