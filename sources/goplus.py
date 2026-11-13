from __future__ import annotations

from typing import Any

from core.http import HttpClient
from core.utils import as_float, as_int, first_present, truthy_flag, utc_iso
from models.schemas import SecuritySnapshot


class GoPlusSource:
    def __init__(self, http: HttpClient, url: str, bearer_token: str = "") -> None:
        self.http = http
        self.url = url
        self.bearer_token = bearer_token

    def fetch(self, network: str, address: str) -> SecuritySnapshot:
        headers = {"Authorization": f"Bearer {self.bearer_token}"} if self.bearer_token else None
        payload = self.http.get_json(
            self.url, params={"contract_addresses": address}, headers=headers
        )
        result = payload.get("result", payload) if isinstance(payload, dict) else {}
        raw = _find_token_result(result, address)
        if not raw:
            return SecuritySnapshot(
                ts=utc_iso(), network=network, address=address, available=False,
                error="GoPlus no devolvió datos para el token",
            )
        holders = raw.get("holders") or raw.get("top_holders") or []
        percentages = [
            as_float(item.get("percent"))
            for item in holders
            if isinstance(item, dict) and not _excluded_holder(item)
        ]
        risks: list[str] = []
        for field in ("risk_item", "risk_items", "warning", "warnings"):
            value = raw.get(field)
            if isinstance(value, list):
                risks.extend(str(item) for item in value)
            elif value:
                risks.append(str(value))
        non_transferable = truthy_flag(
            first_present(raw, ("non_transferable", "is_non_transferable", "cannot_transfer"))
        )
        if non_transferable is None:
            transferable = truthy_flag(raw.get("transferable"))
            non_transferable = None if transferable is None else not transferable
        creator = _first_address(raw.get("creators")) or str(raw.get("creator") or "") or None
        return SecuritySnapshot(
            ts=utc_iso(),
            network=network,
            address=address,
            available=True,
            non_transferable=non_transferable,
            freezable=_feature_enabled(raw, ("freezable", "freeze_authority")),
            mintable=_feature_enabled(raw, ("mintable",)),
            metadata_modifiable=_feature_enabled(
                raw, ("metadata_modifiable", "metadata_mutable")
            ),
            transfer_hook=_feature_enabled(raw, ("transfer_hook", "has_transfer_hook")),
            fees_modifiable=truthy_flag(
                first_present(
                    raw,
                    ("fees_modifiable", "fee_modifiable", "transfer_fee_upgradable"),
                )
            ),
            blacklist=truthy_flag(raw.get("blacklist")),
            creator_malicious=_creator_malicious(raw),
            creator=creator,
            top1_holder_pct=max(percentages, default=0) or None,
            top10_holders_pct=sum(sorted(percentages, reverse=True)[:10]) or None,
            holder_count=as_int(raw.get("holder_count"), default=0) or None,
            raw_risks=risks,
        )


def _find_token_result(result: Any, address: str) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {}
    if address in result and isinstance(result[address], dict):
        return result[address]
    lower = address.lower()
    for key, value in result.items():
        if str(key).lower() == lower and isinstance(value, dict):
            return value
    if any(key in result for key in ("name", "symbol", "creator", "mintable")):
        return result
    return {}


def _excluded_holder(holder: dict[str, Any]) -> bool:
    tag = str(holder.get("tag") or holder.get("name") or "").lower()
    return any(word in tag for word in ("burn", "pool", "liquidity", "locker", "dead"))


def _feature_enabled(raw: dict[str, Any], names: tuple[str, ...]) -> bool | None:
    value = first_present(raw, names)
    if value is None:
        return None
    return truthy_flag(value)


def _first_address(value: Any) -> str | None:
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and item.get("address"):
                return str(item["address"])
            if isinstance(item, str) and item:
                return item
    return None


def _creator_malicious(raw: dict[str, Any]) -> bool | None:
    direct = truthy_flag(
        first_present(raw, ("creator_malicious", "malicious_creator", "is_malicious"))
    )
    if direct is not None:
        return direct
    found_authority = False
    stack: list[Any] = [raw.get("creators"), raw.get("metadata_mutable"), raw.get("mintable")]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            if "malicious_address" in current:
                found_authority = True
                if truthy_flag(current.get("malicious_address")) is True:
                    return True
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    return False if found_authority else None
