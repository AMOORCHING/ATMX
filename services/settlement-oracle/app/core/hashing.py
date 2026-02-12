"""Deterministic hashing utilities for immutable audit records.

Each settlement record is hash-chained: the hash of the current record includes
the hash of the previous record, forming a tamper-evident chain similar to a
blockchain but without the consensus overhead.
"""

import hashlib
import json
from datetime import datetime
from typing import Any

from app.core.config import settings


def canonical_json(data: dict[str, Any]) -> str:
    """Produce a deterministic JSON string (sorted keys, no whitespace)."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=_json_default)


def _json_default(obj: Any) -> str:
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def compute_record_hash(payload: dict[str, Any], previous_hash: str | None = None) -> str:
    """Compute a SHA-256 hash over the canonical JSON payload + previous hash.

    Args:
        payload: The settlement record data to hash.
        previous_hash: Hash of the preceding record in the chain. None for genesis.

    Returns:
        Hex-encoded hash digest.
    """
    algo = settings.settlement_hash_algorithm
    h = hashlib.new(algo)
    if previous_hash:
        h.update(previous_hash.encode("utf-8"))
    h.update(canonical_json(payload).encode("utf-8"))
    return h.hexdigest()
