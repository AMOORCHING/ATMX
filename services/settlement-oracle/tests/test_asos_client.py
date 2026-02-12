"""Tests for the ASOS client: station mapping, data parsing, edge cases."""

from datetime import datetime, timezone

import pytest

from app.services.asos_client import (
    StationObservation,
    _knots_to_ms,
    _safe_float,
    get_stations_in_cell,
)


class TestKnotsConversion:
    """Test wind speed unit conversion."""

    def test_standard_conversion(self):
        assert _knots_to_ms(10.0) == pytest.approx(5.14444)

    def test_zero(self):
        assert _knots_to_ms(0.0) == 0.0

    def test_high_wind(self):
        assert _knots_to_ms(100.0) == pytest.approx(51.4444)


class TestSafeFloat:
    """Test robust float parsing from ASOS CSV data."""

    def test_valid_number(self):
        assert _safe_float("12.5") == 12.5

    def test_integer_string(self):
        assert _safe_float("42") == 42.0

    def test_missing_marker_m(self):
        """ASOS uses 'M' to indicate missing data."""
        assert _safe_float("M") is None

    def test_trace_marker_t(self):
        """ASOS uses 'T' to indicate trace amounts (< 0.01)."""
        assert _safe_float("T") is None

    def test_empty_string(self):
        assert _safe_float("") is None

    def test_none_input(self):
        assert _safe_float(None) is None

    def test_whitespace(self):
        assert _safe_float("  ") is None

    def test_invalid_string(self):
        assert _safe_float("abc") is None

    def test_negative_value(self):
        assert _safe_float("-3.5") == -3.5

    def test_zero(self):
        assert _safe_float("0.0") == 0.0


class TestStationCellMapping:
    """Test H3 cell ↔ station mapping."""

    def test_known_station_returns_match(self):
        """Verify we can find at least one station when querying the correct cell."""
        import h3

        # Get the actual cell for JFK
        cell = h3.latlng_to_cell(40.6413, -73.7781, 7)
        stations = get_stations_in_cell(cell)
        assert len(stations) >= 1
        station_ids = [s[0] for s in stations]
        assert "KJFK" in station_ids

    def test_empty_cell_returns_no_stations(self):
        """A cell in the middle of the ocean has no stations."""
        # Middle of the Atlantic
        import h3

        cell = h3.latlng_to_cell(35.0, -45.0, 7)
        stations = get_stations_in_cell(cell)
        assert len(stations) == 0


class TestStationObservation:
    """Test the StationObservation dataclass."""

    def test_creation(self):
        obs = StationObservation(
            station_id="KJFK",
            observed_at=datetime(2025, 8, 14, 12, 0, tzinfo=timezone.utc),
            latitude=40.6413,
            longitude=-73.7781,
            h3_cell="872a1070bffffff",
            precipitation_mm=5.0,
            wind_speed_ms=10.0,
        )
        assert obs.station_id == "KJFK"
        assert obs.precipitation_mm == 5.0
        assert obs.wind_speed_ms == 10.0

    def test_optional_fields_default_none(self):
        obs = StationObservation(
            station_id="KJFK",
            observed_at=datetime(2025, 8, 14, 12, 0, tzinfo=timezone.utc),
            latitude=40.6413,
            longitude=-73.7781,
            h3_cell="872a1070bffffff",
        )
        assert obs.precipitation_mm is None
        assert obs.wind_speed_ms is None
        assert obs.quality_flag is None
