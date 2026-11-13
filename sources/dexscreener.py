from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.http import HttpClient
from core.utils import as_float, as_int, utc_iso
from models.schemas import Candidate, MarketSnapshot


class DexScreenerSource:
    def __init__(self, http: HttpClient, base_url: str = "https://api.dexscreener.com") -> None:
        self.http = http
        self.base_url = base_url.rstrip("/")

    def discover(self, settings: dict[str, Any]) -> list[Candidate]:
        network = settings["network"]
        discovery = settings["discovery"]
        found: dict[str, Candidate] = {}

        def add(raw: dict[str, Any], source: str) -> None:
            if raw.get("chainId") != network or not raw.get("tokenAddress"):
                return
            address = str(raw["tokenAddress"])
            candidate = found.setdefault(address, Candidate(network=network, address=address))
            if source not in candidate.sources:
                candidate.sources.append(source)
            if source == "dexscreener_boost":
                candidate.boost_amount = max(
                    candidate.boost_amount,
                    as_float(raw.get("amount")) + as_float(raw.get("totalAmount")),
                )

        if discovery.get("profiles", True):
            payload = self.http.get_json(f"{self.base_url}/token-profiles/latest/v1")
            for raw in _items(payload):
                add(raw, "dexscreener_profile")
        if discovery.get("boosts", True):
            payload = self.http.get_json(f"{self.base_url}/token-boosts/latest/v1")
            for raw in _items(payload):
                add(raw, "dexscreener_boost")
        return list(found.values())

    def get_pairs(self, network: str, address: str) -> list[dict[str, Any]]:
        payload = self.http.get_json(f"{self.base_url}/token-pairs/v1/{network}/{address}")
        pairs = _items(payload)
        return [pair for pair in pairs if pair.get("chainId") == network]

    @staticmethod
    def select_primary_pair(pairs: list[dict[str, Any]]) -> dict[str, Any] | None:
        valid = [pair for pair in pairs if isinstance(pair, dict)]
        if not valid:
            return None
        return max(valid, key=lambda p: as_float((p.get("liquidity") or {}).get("usd")))

    @staticmethod
    def normalize_pair(
        pair: dict[str, Any], network: str, address: str, boost_amount: float = 0
    ) -> MarketSnapshot:
        now = datetime.now(timezone.utc)
        created_ms = as_int(pair.get("pairCreatedAt"), default=0) or None
        age_minutes = None
        data_quality = "ok"
        if created_ms:
            age_minutes = (now.timestamp() * 1000 - created_ms) / 60000
            if age_minutes < -5:
                data_quality = "invalid"
        else:
            data_quality = "degraded"
        base = pair.get("baseToken") or {}
        quote = pair.get("quoteToken") or {}
        token = base if str(base.get("address", "")) == address else quote
        volumes = pair.get("volume") or {}
        txns = pair.get("txns") or {}
        m5 = txns.get("m5") or {}
        changes = pair.get("priceChange") or {}
        liquidity = pair.get("liquidity") or {}
        info = pair.get("info") or {}
        links = info.get("socials") or []
        if info.get("websites"):
            links = list(links) + list(info["websites"])
        market_cap = as_float(pair.get("marketCap")) or as_float(pair.get("fdv"))
        return MarketSnapshot(
            ts=utc_iso(now),
            network=network,
            address=address,
            pair_address=str(pair.get("pairAddress") or ""),
            dex_id=str(pair.get("dexId") or ""),
            url=str(pair.get("url") or ""),
            name=str(token.get("name") or ""),
            symbol=str(token.get("symbol") or ""),
            price_usd=as_float(pair.get("priceUsd")),
            liquidity_usd=as_float(liquidity.get("usd")),
            market_cap_usd=market_cap,
            fdv_usd=as_float(pair.get("fdv")),
            pair_created_at_ms=created_ms,
            age_minutes=age_minutes,
            volume_5m_usd=as_float(volumes.get("m5")),
            volume_1h_usd=as_float(volumes.get("h1")),
            volume_6h_usd=as_float(volumes.get("h6")),
            volume_24h_usd=as_float(volumes.get("h24")),
            buys_5m=as_int(m5.get("buys")),
            sells_5m=as_int(m5.get("sells")),
            price_change_5m_pct=as_float(changes.get("m5")),
            price_change_1h_pct=as_float(changes.get("h1")),
            links=links if isinstance(links, list) else [],
            boost_amount=boost_amount,
            data_quality=data_quality,
        )


def _items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("pairs", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        if payload.get("tokenAddress"):
            return [payload]
    return []

