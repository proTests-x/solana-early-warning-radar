from __future__ import annotations

from typing import Any

from models.schemas import FeatureSet, MarketSnapshot


def collapsed_token_reasons(
    market: MarketSnapshot,
    features: FeatureSet,
    config: dict[str, Any],
) -> list[str]:
    """Detecta tokens que ya parecen colapsados; no intenta probar intención de rug."""
    if not config.get("enabled", True):
        return []
    reasons: list[str] = []
    if market.price_change_5m_pct <= -float(config.get("max_price_drop_5m_pct", 45)):
        reasons.append(f"price_5m_already_collapsed:{market.price_change_5m_pct:.1f}%")
    if market.price_change_1h_pct <= -float(config.get("max_price_drop_1h_pct", 75)):
        reasons.append(f"price_1h_already_collapsed:{market.price_change_1h_pct:.1f}%")
    if (
        features.price_change_since_snapshot_pct is not None
        and features.price_change_since_snapshot_pct
        <= -float(config.get("max_snapshot_price_drop_pct", 70))
    ):
        reasons.append(
            f"price_snapshot_already_collapsed:{features.price_change_since_snapshot_pct:.1f}%"
        )
    if (
        features.liquidity_change_pct is not None
        and features.liquidity_change_pct
        <= -float(config.get("max_snapshot_liquidity_drop_pct", 70))
    ):
        reasons.append(
            f"liquidity_already_collapsed:{features.liquidity_change_pct:.1f}%"
        )
    if (
        features.buy_sell_ratio <= float(config.get("max_buy_sell_ratio", 0.25))
        and market.sells_5m >= int(config.get("min_sells_5m", 50))
    ):
        reasons.append(
            f"sales_already_dominant:{market.buys_5m}/{market.sells_5m}"
        )
    return reasons
