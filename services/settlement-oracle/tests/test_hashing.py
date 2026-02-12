"""Tests for the hashing / audit trail utilities."""

from datetime import datetime, timezone

import pytest

from app.core.hashing import canonical_json, compute_record_hash


class TestCanonicalJson:
    """Test deterministic JSON serialization."""

    def test_sorted_keys(self):
        """Keys are sorted alphabetically."""
        result = canonical_json({"z": 1, "a": 2, "m": 3})
        assert result == '{"a":2,"m":3,"z":1}'

    def test_no_whitespace(self):
        """No extraneous whitespace in output."""
        result = canonical_json({"key": "value"})
        assert " " not in result

    def test_datetime_serialization(self):
        """Datetime objects are serialized as ISO format strings."""
        dt = datetime(2025, 8, 15, 0, 0, tzinfo=timezone.utc)
        result = canonical_json({"time": dt})
        assert "2025-08-15" in result

    def test_nested_objects(self):
        """Nested dicts are also sorted."""
        result = canonical_json({"outer": {"z": 1, "a": 2}})
        assert result == '{"outer":{"a":2,"z":1}}'

    def test_deterministic_across_calls(self):
        """Same input always produces the same output."""
        data = {"x": 1, "y": [1, 2, 3], "z": {"nested": True}}
        assert canonical_json(data) == canonical_json(data)


class TestComputeRecordHash:
    """Test hash computation for settlement records."""

    def test_returns_hex_string(self):
        h = compute_record_hash({"test": True})
        assert all(c in "0123456789abcdef" for c in h)

    def test_sha256_length(self):
        h = compute_record_hash({"test": True})
        assert len(h) == 64

    def test_none_previous_hash(self):
        """Genesis record (no previous hash) still produces a valid hash."""
        h = compute_record_hash({"genesis": True}, previous_hash=None)
        assert len(h) == 64

    def test_with_previous_hash(self):
        """Hash with previous_hash differs from without."""
        h_without = compute_record_hash({"data": 1}, previous_hash=None)
        h_with = compute_record_hash({"data": 1}, previous_hash="abc")
        assert h_without != h_with

    def test_empty_payload(self):
        """Empty dict payload still produces a valid hash."""
        h = compute_record_hash({})
        assert len(h) == 64
