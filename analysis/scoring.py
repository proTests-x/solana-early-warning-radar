from __future__ import annotations

import math
from typing import Any

from core.utils import clamp
from models.schemas import FeatureSet, MarketSnapshot, ScoreBreakdown, Scores, SecuritySnapshot, SocialSnapshot


def calculate_scores(
    market: MarketSnapshot,
    security: SecuritySnapshot,
    social: SocialSnapshot,
    features: FeatureSet,
    filters: dict[str, Any],
) -> Scores:
    hard_blocks = hard_filter_reasons(market, security, filters)
    market_activity = clamp(
        35 * _ratio_score(market.volume_5m_usd, float(filters["min_volume_5m_usd"]), 4)
        + 35 * _ratio_score(market.buys_5m, float(filters["min_buys_5m"]), 4)
        + 30 * clamp((market.price_change_5m_pct + 5) / 25, 0, 1)
    )
    buy_pressure = clamp((features.buy_pressure - 0.4) / 0.4 * 100)
    liquidity_quality = clamp(
        65 * _ratio_score(market.liquidity_usd, float(filters["min_liquidity_usd"]), 4)
        + 35 * _balanced_activity(features.volume_liquidity_ratio)
    )
    age = market.age_minutes
    if age is None or age < 0:
        early_stage = 0
    elif age <= 15:
        early_stage = 55 + age
    else:
        early_stage = clamp(100 - (age - 15) * 100 / max(float(filters["max_age_minutes"]) - 15, 1))
    social_activity = clamp(
        50 * min(1, social.mention_count / 20)
        + 35 * min(1, math.log1p(social.interactions) / math.log(10001))
        + 15 * (social.sentiment / 100 if social.sentiment is not None else 0)
    )
    influencer_activity = clamp(features.influencer_weighted_mentions * 18)
    components = ScoreBreakdown(
        market_activity=round(market_activity, 2), buy_pressure=round(buy_pressure, 2),
        liquidity_quality=round(liquidity_quality, 2), early_stage=round(early_stage, 2),
        social_activity=round(social_activity, 2), influencer_activity=round(influencer_activity, 2),
    )
    raw = (
        0.24 * market_activity + 0.20 * buy_pressure + 0.16 * liquidity_quality
        + 0.12 * early_stage + 0.18 * social_activity + 0.10 * influencer_activity
    )
    risk, risk_reasons = _risk_score(market, security, features, filters)
    risk_penalty = min(0.75, risk / 140)
    adjusted = 0 if hard_blocks else raw * (1 - risk_penalty)
    return Scores(
        opportunity_raw=round(raw, 2), opportunity=round(clamp(adjusted), 2),
        risk=round(clamp(risk), 2), risk_penalty=round(risk_penalty, 3),
        components=components, hard_blocks=hard_blocks, risk_reasons=risk_reasons,
    )


def hard_filter_reasons(
    market: MarketSnapshot, security: SecuritySnapshot, filters: dict[str, Any]
) -> list[str]:
    reasons: list[str] = []
    if market.data_quality == "invalid" or market.price_usd <= 0:
        reasons.append("market_data_invalid")
    if market.liquidity_usd < float(filters["min_liquidity_usd"]):
        reasons.append("liquidity_below_minimum")
    if market.market_cap_usd < float(filters["min_market_cap_usd"]):
        reasons.append("market_cap_below_minimum")
    if market.market_cap_usd > float(filters["max_market_cap_usd"]):
        reasons.append("market_cap_above_maximum")
    if market.volume_5m_usd < float(filters["min_volume_5m_usd"]):
        reasons.append("volume_5m_below_minimum")
    if market.buys_5m < int(filters["min_buys_5m"]):
        reasons.append("buys_5m_below_minimum")
    if market.age_minutes is not None and market.age_minutes > float(filters["max_age_minutes"]):
        reasons.append("pair_too_old")
    if market.price_change_5m_pct > float(filters["max_price_change_5m_pct"]):
        reasons.append("price_change_5m_above_maximum")
    if market.age_minutes is not None and market.age_minutes < -5:
        reasons.append("pair_age_impossible")
    if security.non_transferable is True:
        reasons.append("token_non_transferable")
    if security.creator_malicious is True:
        reasons.append("creator_marked_malicious")
    if security.blacklist is True:
        reasons.append("blacklist_capability")
    return reasons


def rule_signal(scores: Scores, alerts: dict[str, Any]) -> str:
    if scores.hard_blocks or scores.risk > float(alerts["max_risk_score_for_candidate"]):
        return "AVOID"
    if scores.opportunity >= float(alerts["min_opportunity_score"]):
        return "BUY_CANDIDATE"
    if scores.opportunity >= float(alerts["wait_opportunity_score"]):
        return "WAIT"
    return "AVOID"


def conservative_signal(rule: str, llm: str | None, hard_blocks: list[str]) -> str:
    if hard_blocks:
        return "AVOID"
    order = {"AVOID": 0, "WAIT": 1, "BUY_CANDIDATE": 2}
    if llm not in order:
        return rule
    return min((rule, llm), key=lambda item: order[item])


def _risk_score(
    market: MarketSnapshot, security: SecuritySnapshot, features: FeatureSet,
    filters: dict[str, Any],
) -> tuple[float, list[str]]:
    risk = 0.0
    reasons: list[str] = []

    def add(points: float, reason: str) -> None:
        nonlocal risk
        risk += points
        reasons.append(reason)

    if not security.available:
        add(22, "security_data_unknown")
    if market.liquidity_usd < float(filters["min_liquidity_usd"]) * 1.5:
        add(16, "thin_liquidity")
    if features.volume_liquidity_ratio > 1.5:
        add(12, "extreme_volume_vs_liquidity")
    elif features.volume_liquidity_ratio > 0.8:
        add(6, "high_volume_vs_liquidity")
    if market.price_change_5m_pct > float(filters["max_price_change_5m_pct"]):
        add(18, "parabolic_price_change")
    if features.buy_pressure < 0.4 and market.buys_5m + market.sells_5m >= 10:
        add(12, "selling_pressure")
    if market.age_minutes is not None and market.age_minutes < 15:
        add(8, "extremely_young_pair")
    for enabled, points, reason in (
        (security.freezable, 14, "freezable"), (security.mintable, 10, "mintable"),
        (security.transfer_hook, 18, "transfer_hook"),
        (security.fees_modifiable, 14, "modifiable_fees"),
        (security.metadata_modifiable, 4, "modifiable_metadata"),
    ):
        if enabled is True:
            add(points, reason)
    if security.top1_holder_pct is not None and security.top1_holder_pct > 0.25:
        add(18, "top1_holder_concentration")
    if security.top10_holders_pct is not None and security.top10_holders_pct > 0.65:
        add(14, "top10_holder_concentration")
    if features.liquidity_change_pct is not None and features.liquidity_change_pct <= -15:
        add(25, "liquidity_falling_fast")
    return risk, reasons


def _ratio_score(value: float, minimum: float, full_multiple: float) -> float:
    if minimum <= 0:
        return 1
    return clamp(value / (minimum * full_multiple), 0, 1)


def _balanced_activity(ratio: float) -> float:
    if ratio <= 0:
        return 0
    if ratio <= 0.5:
        return ratio / 0.5
    if ratio <= 1.0:
        return 1
    return clamp(1 - (ratio - 1) / 2, 0, 1)
