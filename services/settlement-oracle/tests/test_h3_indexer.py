"""Tests for the H3 spatial indexer."""

import pytest

from app.pipeline.grib_parser import GridPoint
from app.pipeline.h3_indexer import CellAggregate, H3_RESOLUTION, index_points_to_h3


class TestH3Indexer:
    """Test H3 cell mapping and aggregation."""

    def test_single_point_maps_to_one_cell(self):
        """A single grid point produces one CellAggregate."""
        points = [GridPoint(latitude=40.7128, longitude=-74.0060, value=15.0)]
        result = index_points_to_h3(points)
        assert len(result) == 1
        assert result[0].point_count == 1
        assert result[0].mean_value == 15.0
        assert result[0].max_value == 15.0
        assert result[0].min_value == 15.0

    def test_colocated_points_aggregate(self):
        """Points at the same location (same cell) are aggregated."""
        points = [
            GridPoint(latitude=40.7128, longitude=-74.0060, value=10.0),
            GridPoint(latitude=40.7129, longitude=-74.0061, value=20.0),
            GridPoint(latitude=40.7127, longitude=-74.0059, value=30.0),
        ]
        result = index_points_to_h3(points)
        assert len(result) == 1
        assert result[0].point_count == 3
        assert result[0].mean_value == pytest.approx(20.0)
        assert result[0].max_value == 30.0
        assert result[0].min_value == 10.0

    def test_distant_points_map_to_different_cells(self):
        """Points far apart end up in different H3 cells."""
        points = [
            GridPoint(latitude=40.7128, longitude=-74.0060, value=10.0),   # NYC
            GridPoint(latitude=34.0522, longitude=-118.2437, value=5.0),   # LA
        ]
        result = index_points_to_h3(points)
        assert len(result) == 2
        cells = {agg.h3_cell for agg in result}
        assert len(cells) == 2  # different cells

    def test_empty_input_returns_empty(self):
        """No points → no aggregates."""
        result = index_points_to_h3([])
        assert result == []

    def test_cell_format_is_valid_h3(self):
        """H3 cell strings have the expected format."""
        import h3

        points = [GridPoint(latitude=40.7128, longitude=-74.0060, value=1.0)]
        result = index_points_to_h3(points)
        assert len(result) == 1
        cell = result[0].h3_cell
        assert h3.is_valid_cell(cell)
        assert h3.get_resolution(cell) == H3_RESOLUTION

    def test_custom_resolution(self):
        """Custom resolution parameter is respected."""
        import h3

        points = [GridPoint(latitude=40.7128, longitude=-74.0060, value=1.0)]
        result = index_points_to_h3(points, resolution=5)
        assert len(result) == 1
        assert h3.get_resolution(result[0].h3_cell) == 5
