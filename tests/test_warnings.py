from analysis.warnings import exit_warning_reasons, rug_watch_reasons
from core.utils import utc_iso
from models.schemas import (
    AnalysisResult, Candidate, FeatureSet, MarketSnapshot, ScoreBreakdown, Scores,
    SecuritySnapshot, SocialSnapshot,
)
from notifications.telegram import format_alert


def _result(risk=70, activity=80, buy_sell=1.5, liquidity_change=None, price_change=None):
    return AnalysisResult(
        signal_id="id", created_at=utc_iso(), candidate=Candidate(address="mint"),
        market=MarketSnapshot(
            ts=utc_iso(), network="solana", address="mint", liquidity_usd=50000,
            market_cap_usd=200000, volume_5m_usd=10000, buys_5m=20, sells_5m=10,
        ),
        security=SecuritySnapshot(ts=utc_iso(), network="solana", address="mint"),
        social=SocialSnapshot(ts=utc_iso(), network="solana", address="mint"),
        features=FeatureSet(
            buy_sell_ratio=buy_sell, liquidity_change_pct=liquidity_change,
            price_change_since_snapshot_pct=price_change,
        ),
        scores=Scores(
            risk=risk, components=ScoreBreakdown(market_activity=activity),
            risk_reasons=["freezable"],
        ),
        rule_signal="AVOID", final_signal="AVOID",
    )


def test_rug_watch_requires_risk_and_activity() -> None:
    cfg = {"enabled": True, "min_risk_score": 65, "min_market_activity": 55}
    filters = {"min_liquidity_usd": 25000, "min_volume_5m_usd": 3000}
    assert rug_watch_reasons(_result(), cfg, filters) == ["freezable"]
    assert rug_watch_reasons(_result(risk=40), cfg, filters) == []
    assert rug_watch_reasons(_result(activity=20), cfg, filters) == []


def test_exit_warning_detects_deterioration_only_when_tracked() -> None:
    cfg = {
        "enabled": True, "liquidity_drop_pct": 15, "buy_sell_ratio_below": 0.8,
        "price_drop_pct": 20, "risk_jump_points": 25, "sell_acceleration_multiple": 2,
    }
    result = _result(risk=70, buy_sell=0.5, liquidity_change=-22, price_change=-30)
    result.market.sells_5m = 30
    reasons = exit_warning_reasons(
        result, {"buys_5m": 20, "sells_5m": 10}, {"last_risk": 30}, cfg
    )
    assert any(item.startswith("liquidity_drop") for item in reasons)
    assert any(item.startswith("buy_sell_ratio") for item in reasons)
    assert any(item.startswith("price_drop") for item in reasons)
    assert any(item.startswith("risk_jump") for item in reasons)
    assert any(item.startswith("sell_acceleration") for item in reasons)
    assert exit_warning_reasons(result, {"buys_5m": 20, "sells_5m": 10}, None, cfg) == []


def test_exit_warning_message_is_an_explicit_sale_alert() -> None:
    result = _result()
    result.notification_type = "EXIT_WARNING"
    result.warning_reasons = ["liquidity_drop:-20%"]
    message = format_alert(result)
    assert "ALERTA DE VENTA / SALIDA" in message
    assert "no garantiza" in message
