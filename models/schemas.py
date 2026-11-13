from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


Signal = Literal["BUY_CANDIDATE", "WAIT", "AVOID"]


class Candidate(BaseModel):
    network: str = "solana"
    address: str
    label: str = ""
    sources: list[str] = Field(default_factory=list)
    boost_amount: float = 0


class MarketSnapshot(BaseModel):
    ts: str
    network: str
    address: str
    pair_address: str = ""
    dex_id: str = ""
    url: str = ""
    name: str = ""
    symbol: str = ""
    price_usd: float = 0
    liquidity_usd: float = 0
    market_cap_usd: float = 0
    fdv_usd: float = 0
    pair_created_at_ms: int | None = None
    age_minutes: float | None = None
    volume_5m_usd: float = 0
    volume_1h_usd: float = 0
    volume_6h_usd: float = 0
    volume_24h_usd: float = 0
    buys_5m: int = 0
    sells_5m: int = 0
    price_change_5m_pct: float = 0
    price_change_1h_pct: float = 0
    links: list[dict[str, Any]] = Field(default_factory=list)
    boost_amount: float = 0
    data_quality: Literal["ok", "degraded", "invalid"] = "ok"


class SecuritySnapshot(BaseModel):
    ts: str
    network: str
    address: str
    available: bool = False
    error: str | None = None
    non_transferable: bool | None = None
    freezable: bool | None = None
    mintable: bool | None = None
    metadata_modifiable: bool | None = None
    transfer_hook: bool | None = None
    fees_modifiable: bool | None = None
    blacklist: bool | None = None
    creator_malicious: bool | None = None
    creator: str | None = None
    top1_holder_pct: float | None = None
    top10_holders_pct: float | None = None
    holder_count: int | None = None
    raw_risks: list[str] = Field(default_factory=list)


class SocialPost(BaseModel):
    id: str = ""
    source: str
    author: str = ""
    text: str = ""
    created_at: str | None = None
    likes: int = 0
    reposts: int = 0
    interactions: int = 0
    author_weight: float = 1.0


class SocialSnapshot(BaseModel):
    ts: str
    network: str
    address: str
    available_sources: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    posts: list[SocialPost] = Field(default_factory=list)
    mention_count: int = 0
    interactions: int = 0
    sentiment: float | None = None
    contributors: int = 0
    influencer_mentions: float = 0


class FeatureSet(BaseModel):
    buy_sell_ratio: float = 0
    buy_pressure: float = 0
    volume_liquidity_ratio: float = 0
    volume_mcap_ratio: float = 0
    volume_acceleration: float | None = None
    liquidity_change_pct: float | None = None
    price_change_since_snapshot_pct: float | None = None
    social_post_count: int = 0
    social_interactions: int = 0
    influencer_weighted_mentions: float = 0
    security_unknown: bool = True


class ScoreBreakdown(BaseModel):
    market_activity: float = 0
    buy_pressure: float = 0
    liquidity_quality: float = 0
    early_stage: float = 0
    social_activity: float = 0
    influencer_activity: float = 0


class Scores(BaseModel):
    opportunity_raw: float = 0
    opportunity: float = 0
    risk: float = 0
    risk_penalty: float = 0
    components: ScoreBreakdown = Field(default_factory=ScoreBreakdown)
    hard_blocks: list[str] = Field(default_factory=list)
    risk_reasons: list[str] = Field(default_factory=list)


class LLMAnalysis(BaseModel):
    signal: Signal
    confidence_label: Literal["low", "medium", "high"] = "low"
    summary: str
    bull_case: list[str] = Field(default_factory=list)
    bear_case: list[str] = Field(default_factory=list)
    rug_warning_signs: list[str] = Field(default_factory=list)
    entry_conditions: list[str] = Field(default_factory=list)
    exit_warning_conditions: list[str] = Field(default_factory=list)
    data_quality_notes: list[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    signal_id: str
    created_at: str
    candidate: Candidate
    market: MarketSnapshot
    security: SecuritySnapshot
    social: SocialSnapshot
    features: FeatureSet
    scores: Scores
    rule_signal: Signal
    final_signal: Signal
    llm: LLMAnalysis | None = None
    llm_error: str | None = None
    notification_type: Literal[
        "BUY_CANDIDATE", "WAIT", "AVOID", "RUG_WATCH", "EXIT_WARNING"
    ] | None = None
    warning_reasons: list[str] = Field(default_factory=list)
    notification_suppressed_reasons: list[str] = Field(default_factory=list)
    alert_sent: bool = False
    alert_error: str | None = None
