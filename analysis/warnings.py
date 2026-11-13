from __future__ import annotations

from typing import Any

from core.utils import as_float
from models.schemas import AnalysisResult


def exit_warning_reasons(
    result: AnalysisResult,
    previous_market: dict[str, Any] | None,
    previous_watch: dict[str, Any] | None,
    config: dict[str, Any],
) -> list[str]:
    if not config.get("enabled", True) or not previous_watch:
        return []
    reasons: list[str] = []
    features = result.features
    if (
        features.liquidity_change_pct is not None
        and features.liquidity_change_pct <= -float(config.get("liquidity_drop_pct", 15))
    ):
        reasons.append(f"liquidity_drop:{features.liquidity_change_pct:.1f}%")
    ratio_limit = float(config.get("buy_sell_ratio_below", 0.8))
    previous_ratio = None
    if previous_market:
        previous_ratio = as_float(previous_market.get("buys_5m")) / max(
            as_float(previous_market.get("sells_5m")), 1
        )
    if (
        result.features.buy_sell_ratio < ratio_limit
        and (
            previous_ratio is None
            or previous_ratio >= ratio_limit
            or result.features.buy_sell_ratio <= previous_ratio * 0.7
        )
    ):
        reasons.append(f"buy_sell_ratio:{result.features.buy_sell_ratio:.2f}x")
    if (
        features.price_change_since_snapshot_pct is not None
        and features.price_change_since_snapshot_pct <= -float(config.get("price_drop_pct", 20))
    ):
        reasons.append(f"price_drop:{features.price_change_since_snapshot_pct:.1f}%")
    previous_risk = as_float(previous_watch.get("last_risk"), default=-1)
    if previous_risk >= 0:
        jump = result.scores.risk - previous_risk
        if jump >= float(config.get("risk_jump_points", 25)):
            reasons.append(f"risk_jump:{previous_risk:.0f}->{result.scores.risk:.0f}")
    if previous_market:
        previous_sells = as_float(previous_market.get("sells_5m"))
        multiple = float(config.get("sell_acceleration_multiple", 2))
        if (
            previous_sells > 0
            and result.market.sells_5m >= previous_sells * multiple
            and result.market.sells_5m > result.market.buys_5m
        ):
            reasons.append(
                f"sell_acceleration:{result.market.sells_5m / previous_sells:.1f}x"
            )
    return reasons


def rug_watch_reasons(
    result: AnalysisResult,
    config: dict[str, Any],
    filters: dict[str, Any],
) -> list[str]:
    if not config.get("enabled", True):
        return []
    if result.scores.risk < float(config.get("min_risk_score", 65)):
        return []
    if result.scores.components.market_activity < float(config.get("min_market_activity", 55)):
        return []
    if result.market.liquidity_usd < float(filters.get("min_liquidity_usd", 0)):
        return []
    if result.market.volume_5m_usd < float(filters.get("min_volume_5m_usd", 0)):
        return []
    reasons = list(result.scores.risk_reasons)
    reasons.extend(result.scores.hard_blocks)
    return reasons or ["high_composite_risk"]
