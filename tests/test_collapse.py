from analysis.collapse import collapsed_token_reasons
from core.utils import utc_iso
from models.schemas import FeatureSet, MarketSnapshot


CONFIG = {
    "enabled": True,
    "max_price_drop_5m_pct": 45,
    "max_price_drop_1h_pct": 75,
    "max_snapshot_price_drop_pct": 70,
    "max_snapshot_liquidity_drop_pct": 70,
    "max_buy_sell_ratio": 0.25,
    "min_sells_5m": 50,
}


def _market(**changes):
    values = dict(
        ts=utc_iso(), network="solana", address="mint", price_change_5m_pct=-5,
        price_change_1h_pct=-10, buys_5m=30, sells_5m=20,
    )
    values.update(changes)
    return MarketSnapshot(**values)


def test_already_collapsed_price_is_suppressed() -> None:
    reasons = collapsed_token_reasons(
        _market(price_change_5m_pct=-60), FeatureSet(buy_sell_ratio=1.5), CONFIG
    )
    assert any(reason.startswith("price_5m_already_collapsed") for reason in reasons)


def test_massive_sales_are_suppressed() -> None:
    reasons = collapsed_token_reasons(
        _market(buys_5m=10, sells_5m=100), FeatureSet(buy_sell_ratio=0.1), CONFIG
    )
    assert any(reason.startswith("sales_already_dominant") for reason in reasons)


def test_ordinary_pullback_is_not_terminal_collapse() -> None:
    assert collapsed_token_reasons(
        _market(price_change_5m_pct=-15), FeatureSet(buy_sell_ratio=0.8), CONFIG
    ) == []

