from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ConfigError(RuntimeError):
    pass


def _read_json(path: Path, required: bool = True) -> dict[str, Any]:
    if not path.exists():
        if required:
            raise ConfigError(f"No existe el archivo de configuración: {path}")
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"No se pudo leer JSON válido de {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path} debe contener un objeto JSON")
    return data


def _merge(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def load_settings(root: Path | None = None) -> dict[str, Any]:
    root = root or PROJECT_ROOT
    example = _read_json(root / "config" / "config.example.json")
    configured = _read_json(root / "config" / "config.json", required=False)
    settings = _merge(example, configured)
    settings["secrets"] = _read_json(root / "config" / "secrets.json", required=False)
    settings["influencers"] = _read_json(root / "config" / "influencers.json", required=False)
    settings["manual_watchlist"] = _read_json(
        root / "config" / "manual_watchlist.json", required=False
    )
    settings["project_root"] = root
    _validate(settings)
    return settings


def _validate(settings: dict[str, Any]) -> None:
    if settings.get("network") != "solana":
        raise ConfigError("El MVP implementa network='solana'")
    if int(settings.get("poll_seconds", 0)) < 1:
        raise ConfigError("poll_seconds debe ser mayor que cero")
    filters = settings.get("filters", {})
    if float(filters.get("min_liquidity_usd", 0)) < 0:
        raise ConfigError("min_liquidity_usd no puede ser negativo")
    alerts = settings.get("alerts", {})
    wait_score = float(alerts.get("wait_opportunity_score", 0))
    buy_score = float(alerts.get("min_opportunity_score", 0))
    if not 0 <= wait_score <= buy_score <= 100:
        raise ConfigError("Los umbrales de oportunidad deben cumplir 0 <= WAIT <= BUY <= 100")

