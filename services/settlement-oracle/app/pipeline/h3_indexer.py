"""Map GRIB2 grid points to H3 hexagonal cells and aggregate values per cell.

Resolution 7 → average hexagon area ≈ 5.16 km², edge length ≈ 1.22 km.
This is an appropriate resolution for mesoscale weather phenomena.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass

import h3

from dataclasses import dataclass


@dataclass
class GridPoint:
    """A single grid point extracted from a GRIB2 field."""

    latitude: float
    longitude: float
    value: float

logger = logging.getLogger(__name__)

H3_RESOLUTION = 7


@dataclass
class CellAggregate:
    """Aggregated value for a single H3 cell."""

    h3_cell: str
    mean_value: float
    max_value: float
    min_value: float
    point_count: int


def index_points_to_h3(points: list[GridPoint], resolution: int = H3_RESOLUTION) -> list[CellAggregate]:
    """Map a list of GridPoints to H3 cells and compute per-cell aggregates.

    Args:
        points: Extracted grid points from GRIB2 data.
        resolution: H3 resolution (default 7).

    Returns:
        List of CellAggregate, one per H3 cell that contains at least one point.
    """
    cell_values: dict[str, list[float]] = defaultdict(list)

    for pt in points:
        cell = h3.latlng_to_cell(pt.latitude, pt.longitude, resolution)
        cell_values[cell].append(pt.value)

    aggregates: list[CellAggregate] = []
    for cell, values in cell_values.items():
        aggregates.append(
            CellAggregate(
                h3_cell=cell,
                mean_value=sum(values) / len(values),
                max_value=max(values),
                min_value=min(values),
                point_count=len(values),
            )
        )

    logger.info(
        "Indexed %d points into %d H3 cells (res %d)",
        len(points),
        len(aggregates),
        resolution,
    )
    return aggregates
