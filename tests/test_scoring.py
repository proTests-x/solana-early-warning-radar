from analysis.features import calculate_features
from analysis.scoring import calculate_scores, conservative_signal, rule_signal
from core.utils import utc_iso
from models.schemas import MarketSnapshot, SecuritySnapshot, SocialSnapshot


FILTERS = {
    "max_age_minutes": 360,
    "min_liquidity_usd": 25000,
    "min_market_cap_usd": 50000,
    "max_market_cap_usd": 10000000,
    "min_volume_5m_usd": 3000,
    "min_buys_5m": 15,
    "max_price_change_5m_pct": 100,
}
ALERTS = {
    "min_opportunity_score": 65,
    "wait_opportunity_score": 50,
    "max_risk_score_for_candidate": 50,
}


def _market(**changes):
    values = dict(
        ts=utc_iso(), network="solana", address="mint", price_usd=0.001,
        liquidity_usd=100000, market_cap_usd=300000, volume_5m_usd=40000,
        buys_5m=100, sells_5m=40, price_change_5m_pct=5, age_minutes=30,
    )
    values.update(changes)
    return MarketSnapshot(**values)


def test_good_market_can_be_candidate() -> None:
    market = _market()
    security = SecuritySnapshot(ts=utc_iso(), network="solana", address="mint", available=True)
    social = SocialSnapshot(
        ts=utc_iso(), network="solana", address="mint", mention_count=30,
        interactions=3000, sentiment=70, influencer_mentions=3,
    )
    features = calculate_features(market, security, social)
    scores = calculate_scores(market, security, social, features, FILTERS)
    assert not scores.hard_blocks
    assert scores.opportunity >= 65
    assert rule_signal(scores, ALERTS) == "BUY_CANDIDATE"


def test_hard_filter_overrides_hype() -> None:
    market = _market(liquidity_usd=1000)
    security = SecuritySnapshot(ts=utc_iso(), network="solana", address="mint", available=True)
    social = SocialSnapshot(ts=utc_iso(), network="solana", address="mint", mention_count=1000)
    features = calculate_features(market, security, social)
    scores = calculate_scores(market, security, social, features, FILTERS)
    assert "liquidity_below_minimum" in scores.hard_blocks
    assert scores.opportunity == 0
    assert rule_signal(scores, ALERTS) == "AVOID"


def test_llm_cannot_raise_signal() -> None:
    assert conservative_signal("WAIT", "BUY_CANDIDATE", []) == "WAIT"
    assert conservative_signal("BUY_CANDIDATE", "AVOID", []) == "AVOID"
    assert conservative_signal("BUY_CANDIDATE", "BUY_CANDIDATE", ["blocked"]) == "AVOID"

