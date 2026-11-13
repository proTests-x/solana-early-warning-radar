from __future__ import annotations

from typing import Any

from core.utils import as_float
from models.schemas import FeatureSet, MarketSnapshot, SecuritySnapshot, SocialSnapshot


def calculate_features(
    market: MarketSnapshot,
    security: SecuritySnapshot,
    social: SocialSnapshot,
    previous_market: dict[str, Any] | None = None,
) -> FeatureSet:
    total_txns = market.buys_5m + market.sells_5m
    features = FeatureSet(
        buy_sell_ratio=round(market.buys_5m / max(market.sells_5m, 1), 4),
        buy_pressure=round(market.buys_5m / max(total_txns, 1), 4),
        volume_liquidity_ratio=round(market.volume_5m_usd / max(market.liquidity_usd, 1), 4),
        volume_mcap_ratio=round(market.volume_5m_usd / max(market.market_cap_usd, 1), 4),
        social_post_count=social.mention_count,
        social_interactions=social.interactions,
        influencer_weighted_mentions=round(social.influencer_mentions, 3),
        security_unknown=not security.available,
    )
    if previous_market:
        previous_volume = as_float(previous_market.get("volume_5m_usd"))
        if previous_volume > 0:
            features.volume_acceleration = round(market.volume_5m_usd / previous_volume, 4)
        previous_liquidity = as_float(previous_market.get("liquidity_usd"))
        if previous_liquidity > 0:
            features.liquidity_change_pct = round(
                (market.liquidity_usd / previous_liquidity - 1) * 100, 3
            )
        previous_price = as_float(previous_market.get("price_usd"))
        if previous_price > 0:
            features.price_change_since_snapshot_pct = round(
                (market.price_usd / previous_price - 1) * 100, 3
            )
    return features

