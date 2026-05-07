"""
Deterministic helpers for repeatable model features and synthetic series.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import numpy as np


def stable_hash_int(*parts: Any, modulo: int = 2**32) -> int:
    """Return a stable integer hash for the provided values."""
    payload = json.dumps(parts, sort_keys=True, default=str, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return int(digest[:16], 16) % modulo


def stable_rng(*parts: Any) -> np.random.Generator:
    """Return a deterministic RNG seeded from the provided values."""
    return np.random.default_rng(stable_hash_int(*parts))

