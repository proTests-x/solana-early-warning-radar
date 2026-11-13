from analysis.features import calculate_features
from core.utils import utc_iso
from models.schemas import MarketSnapshot, SecuritySnapshot, SocialSnapshot


def test_features_use_previous_snapshot() -> None:
    market = MarketSnapshot(
        ts=utc_iso(), network="solana", address="mint", price_usd=2,
        liquidity_usd=120, market_cap_usd=1000, volume_5m_usd=60,
        buys_5m=30, sells_5m=10,
    )
    security = SecuritySnapshot(ts=utc_iso(), network="solana", address="mint", available=True)
    social = SocialSnapshot(ts=utc_iso(), network="solana", address="mint", mention_count=3)
    result = calculate_features(
        market, security, social,
        {"price_usd": 1, "liquidity_usd": 100, "volume_5m_usd": 30},
    )
    assert result.buy_sell_ratio == 3
    assert result.buy_pressure == 0.75
    assert result.volume_acceleration == 2
    assert result.liquidity_change_pct == 20
    assert result.price_change_since_snapshot_pct == 100
    assert result.security_unknown is False

