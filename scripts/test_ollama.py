from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.runtime import relaunch_in_project_venv  # noqa: E402

relaunch_in_project_venv(ROOT)

from analysis.ollama_analyst import OllamaAnalyst  # noqa: E402
from core.config import load_settings  # noqa: E402
from core.utils import utc_iso  # noqa: E402
from models.schemas import (  # noqa: E402
    FeatureSet, MarketSnapshot, ScoreBreakdown, Scores, SecuritySnapshot, SocialSnapshot,
)


def main() -> int:
    settings = load_settings(ROOT)
    cfg = settings["ollama"]
    analyst = OllamaAnalyst(
        cfg["host"], cfg["model"], cfg["timeout_seconds"], cfg["temperature"],
        cfg["max_social_posts"], cfg.get("think", False), cfg.get("max_output_tokens", 900),
        cfg.get("keep_alive", "15m"),
    )
    analysis = analyst.analyze(
        MarketSnapshot(
            ts=utc_iso(), network="solana", address="TEST", symbol="TEST",
            price_usd=0.001, liquidity_usd=50000, market_cap_usd=200000,
            age_minutes=30, volume_5m_usd=10000, buys_5m=50, sells_5m=30,
        ),
        SecuritySnapshot(ts=utc_iso(), network="solana", address="TEST", available=False),
        SocialSnapshot(ts=utc_iso(), network="solana", address="TEST"),
        FeatureSet(buy_sell_ratio=1.67, buy_pressure=0.625, security_unknown=True),
        Scores(
            opportunity_raw=60, opportunity=50, risk=30, risk_penalty=0.214,
            components=ScoreBreakdown(),
        ),
        "WAIT",
    )
    print(analysis.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
