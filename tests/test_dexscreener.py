from sources.dexscreener import DexScreenerSource


def test_selects_most_liquid_pair_and_normalizes() -> None:
    pairs = [
        {"chainId": "solana", "liquidity": {"usd": 10}},
        {
            "chainId": "solana", "dexId": "raydium", "pairAddress": "pair",
            "baseToken": {"address": "mint", "name": "Token", "symbol": "TOK"},
            "quoteToken": {"address": "quote", "symbol": "SOL"},
            "priceUsd": "0.25", "liquidity": {"usd": 50000}, "marketCap": 200000,
            "volume": {"m5": 10000, "h1": 20000},
            "txns": {"m5": {"buys": 30, "sells": 10}},
            "priceChange": {"m5": 5}, "pairCreatedAt": 1,
        },
    ]
    pair = DexScreenerSource.select_primary_pair(pairs)
    assert pair["pairAddress"] == "pair"
    snapshot = DexScreenerSource.normalize_pair(pair, "solana", "mint")
    assert snapshot.symbol == "TOK"
    assert snapshot.price_usd == 0.25
    assert snapshot.buys_5m == 30

