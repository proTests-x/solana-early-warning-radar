from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from typing import Any, Iterable


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_iso(value: datetime | None = None) -> str:
    value = value or utc_now()
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError, OverflowError):
        return default


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def first_present(mapping: dict[str, Any], names: Iterable[str], default: Any = None) -> Any:
    for name in names:
        value = mapping.get(name)
        if value is not None and value != "":
            return value
    return default


def truthy_flag(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, dict):
        value = value.get("value", value.get("status"))
    if isinstance(value, (list, tuple, set)):
        return bool(value)
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "2"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    return None


def stable_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def token_key(network: str, address: str) -> str:
    return f"{network.lower()}:{address}"
