from __future__ import annotations

from decimal import Decimal
from typing import Any


try:
    import numpy as np
except Exception:  # pragma: no cover - numpy may be unavailable in some test envs
    np = None


def normalize_payload(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if np is not None and isinstance(value, np.generic):
        if isinstance(value, np.bool_):
            return bool(value)
        if isinstance(value, np.integer):
            return int(value)
        if isinstance(value, np.floating):
            return float(value)
        return normalize_payload(value.item())
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {key: normalize_payload(val) for key, val in value.items()}
    if isinstance(value, list):
        return [normalize_payload(item) for item in value]
    if isinstance(value, tuple):
        return [normalize_payload(item) for item in value]
    raise TypeError(f"Unsupported payload type: {type(value).__name__}")
