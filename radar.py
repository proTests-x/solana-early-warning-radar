from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from analysis.features import calculate_features
from analysis.collapse import collapsed_token_reasons
from analysis.ollama_analyst import OllamaAnalyst
from analysis.scoring import calculate_scores, conservative_signal, hard_filter_reasons, rule_signal
from analysis.warnings import exit_warning_reasons, rug_watch_reasons
from core.http import HttpClient
from core.storage import JsonStorage
from core.utils import token_key, utc_iso
from models.schemas import AnalysisResult, Candidate, SecuritySnapshot, SocialSnapshot
from notifications.telegram import TelegramNotifier
from sources.dexscreener import DexScreenerSource
from sources.goplus import GoPlusSource
from sources.lunarcrush import LunarCrushSource
from sources.x_api import XSource


class Radar:
    def __init__(self, settings: dict[str, Any]) -> None:
        self.settings = settings
        root = Path(settings["project_root"])
        http_cfg = settings["http"]
        self.http = HttpClient(
            timeout=float(http_cfg["timeout_seconds"]),
            max_retries=int(http_cfg["max_retries"]),
            backoff=float(http_cfg["backoff_seconds"]),
            user_agent=str(http_cfg["user_agent"]),
        )
        self.storage = JsonStorage(root / "data")
        secrets = settings.get("secrets", {})
        self.dex = DexScreenerSource(self.http, settings["dexscreener"]["base_url"])
        self.goplus = GoPlusSource(
            self.http, settings["goplus"]["url"], str(secrets.get("goplus_bearer_token", ""))
        )
        self.x = XSource(
            self.http, settings["x"]["base_url"], str(secrets.get("x_bearer_token", "")),
            int(settings["x"]["max_results"]),
        )
        self.lunar = LunarCrushSource(
            self.http, settings["lunarcrush"]["base_url"],
            str(secrets.get("lunarcrush_api_key", "")),
        )
        ollama_cfg = settings["ollama"]
        self.ollama = OllamaAnalyst(
            host=ollama_cfg["host"], model=ollama_cfg["model"],
            timeout=float(ollama_cfg["timeout_seconds"]),
            temperature=float(ollama_cfg["temperature"]),
            max_social_posts=int(ollama_cfg["max_social_posts"]),
            think=bool(ollama_cfg.get("think", False)),
            max_output_tokens=int(ollama_cfg.get("max_output_tokens", 900)),
            keep_alive=str(ollama_cfg.get("keep_alive", "15m")),
        )
        self.telegram = TelegramNotifier(
            self.http, str(secrets.get("telegram_bot_token", "")),
            str(secrets.get("telegram_chat_id", "")),
        )

    def discover(self) -> list[Candidate]:
        found: dict[str, Candidate] = {}

        def merge(candidate: Candidate) -> None:
            current = found.setdefault(candidate.address, candidate)
            for source in candidate.sources:
                if source not in current.sources:
                    current.sources.append(source)
            current.boost_amount = max(current.boost_amount, candidate.boost_amount)
            if candidate.label and not current.label:
                current.label = candidate.label

        try:
            for candidate in self.dex.discover(self.settings):
                merge(candidate)
            self._api_status("dexscreener", True)
        except Exception as exc:
            self._api_status("dexscreener", False, str(exc))
            print(f"[discovery] DEX Screener degradado: {exc}")
        discovery = self.settings["discovery"]
        if discovery.get("manual_watchlist", True):
            for raw in self.settings.get("manual_watchlist", {}).get("tokens", []):
                if raw.get("enabled", True) and raw.get("chain", "solana") == self.settings["network"]:
                    address = str(raw.get("address") or "").strip()
                    if address:
                        merge(Candidate(
                            network=self.settings["network"], address=address,
                            label=str(raw.get("label") or ""), sources=["manual"],
                        ))
        if discovery.get("persistent_watchlist", True):
            watchlist = self.storage.read_json(self.storage.watchlist_path, {"tokens": {}})
            for key, raw in watchlist.get("tokens", {}).items():
                if raw.get("enabled", True):
                    address = str(raw.get("address") or key.split(":", 1)[-1])
                    merge(Candidate(
                        network=self.settings["network"], address=address,
                        label=str(raw.get("label") or ""), sources=["persistent_watchlist"],
                    ))
        limit = int(discovery.get("max_candidates_per_cycle", 40))
        tracked = [
            candidate for candidate in found.values()
            if "persistent_watchlist" in candidate.sources
        ]
        manual = [
            candidate for candidate in found.values()
            if "manual" in candidate.sources and "persistent_watchlist" not in candidate.sources
        ]
        priority_addresses = {candidate.address for candidate in tracked + manual}
        discovered = sorted(
            (candidate for candidate in found.values() if candidate.address not in priority_addresses),
            key=lambda c: c.boost_amount,
            reverse=True,
        )
        # Los tokens vigilados nunca compiten por cupo con nuevos descubrimientos.
        priority = tracked + manual
        candidates = priority + discovered[:max(0, limit - len(priority))]
        self._record_seen(candidates)
        return candidates

    def analyze_token(self, candidate: Candidate, force_llm: bool = False) -> AnalysisResult | None:
        network, address = candidate.network, candidate.address
        watch_record = self._watchlist_entry(network, address, include_disabled=True)
        previous_watch = (
            watch_record if watch_record and watch_record.get("enabled", True) else None
        )
        pairs = self.dex.get_pairs(network, address)
        pair = self.dex.select_primary_pair(pairs)
        if not pair:
            print(f"[market] sin pares para {address}")
            return None
        market = self.dex.normalize_pair(pair, network, address, candidate.boost_amount)
        market_path = self.storage.snapshot_path("market_snapshots", network, address)
        previous = self.storage.latest_snapshot("market_snapshots", network, address)
        self.storage.append_jsonl(market_path, market.model_dump())

        unknown_security = SecuritySnapshot(
            ts=utc_iso(), network=network, address=address, available=False,
            error="No consultado: el mercado no pasó los prefiltros",
        )
        market_blocks = hard_filter_reasons(market, unknown_security, self.settings["filters"])
        skip_sources = bool(set(market_blocks) & {
            "market_data_invalid", "liquidity_below_minimum", "market_cap_below_minimum",
            "market_cap_above_maximum", "volume_5m_below_minimum", "buys_5m_below_minimum",
            "pair_too_old", "pair_age_impossible",
        }) and not previous_watch
        if skip_sources:
            security = unknown_security
            social = SocialSnapshot(
                ts=utc_iso(), network=network, address=address,
                errors=["No consultado: el mercado no pasó los prefiltros"],
            )
        else:
            security = self._get_security(network, address)
            social = self._get_social(network, address, market.symbol)
        features = calculate_features(market, security, social, previous)
        scores = calculate_scores(market, security, social, features, self.settings["filters"])
        base_signal = rule_signal(scores, self.settings["alerts"])
        collapse_reasons = collapsed_token_reasons(
            market, features, self.settings["alerts"]["collapsed_tokens"]
        )
        if watch_record and watch_record.get("terminal_collapse"):
            collapse_reasons = list(dict.fromkeys(
                collapse_reasons + ["previously_marked_as_terminal_collapse"]
            ))
        llm_analysis = None
        llm_error = None
        should_run_llm = (
            self.settings["ollama"].get("enabled", True)
            and not scores.hard_blocks
            and not collapse_reasons
            and (force_llm or scores.opportunity_raw >= float(
                self.settings["ollama"].get("min_opportunity_to_analyze", 40)
            ))
        )
        if should_run_llm:
            try:
                llm_analysis = self.ollama.analyze_with_retry(
                    market, security, social, features, scores, base_signal,
                    max_attempts=int(self.settings["ollama"].get("max_attempts", 2)),
                    retry_delay_seconds=float(
                        self.settings["ollama"].get("retry_delay_seconds", 2)
                    ),
                )
                self.storage.append_jsonl(
                    self.storage.data_dir / "llm_analyses.jsonl",
                    {"ts": utc_iso(), "network": network, "address": address, **llm_analysis.model_dump()},
                )
            except Exception as exc:
                llm_error = str(exc)
                print(f"[ollama] {market.symbol or address}: {exc}")
        final_signal = conservative_signal(
            base_signal, llm_analysis.signal if llm_analysis else None, scores.hard_blocks
        )
        if collapse_reasons:
            final_signal = "AVOID"
        result = AnalysisResult(
            signal_id=str(uuid.uuid4()), created_at=utc_iso(), candidate=candidate,
            market=market, security=security, social=social, features=features, scores=scores,
            rule_signal=base_signal, final_signal=final_signal,
            llm=llm_analysis, llm_error=llm_error,
            notification_suppressed_reasons=collapse_reasons,
        )
        exit_reasons = exit_warning_reasons(
            result, previous, previous_watch, self.settings["alerts"]["exit_warnings"]
        )
        rug_reasons = rug_watch_reasons(
            result, self.settings["alerts"]["rug_watch"], self.settings["filters"]
        )
        # Una moneda vigilada recibe una última alerta de salida; una moneda ya
        # colapsada al descubrirla no se envía como oportunidad ni RUG_WATCH.
        if previous_watch and (exit_reasons or collapse_reasons):
            result.notification_type = "EXIT_WARNING"
            result.warning_reasons = list(dict.fromkeys(exit_reasons + collapse_reasons))
        elif collapse_reasons:
            result.notification_type = None
        elif rug_reasons:
            result.notification_type = "RUG_WATCH"
            result.warning_reasons = rug_reasons
        elif result.final_signal == "BUY_CANDIDATE":
            result.notification_type = "BUY_CANDIDATE"
        elif result.final_signal == "WAIT" and self.settings["alerts"].get("send_wait_signals", True):
            result.notification_type = "WAIT"
        elif result.final_signal == "AVOID" and self.settings["alerts"].get("send_avoid_signals", False):
            result.notification_type = "AVOID"
        self._maybe_alert(result)
        self.storage.append_jsonl(self.storage.data_dir / "alerts.jsonl", result.model_dump())
        self._update_watchlist(result)
        return result

    def run_cycle(self) -> list[AnalysisResult]:
        candidates = self.discover()
        print(f"[discovery] {len(candidates)} candidatos")
        results: list[AnalysisResult] = []
        for index, candidate in enumerate(candidates, start=1):
            try:
                print(f"[market] {index}/{len(candidates)} {candidate.address}")
                result = self.analyze_token(candidate)
                if result:
                    results.append(result)
                    print(
                        f"[signal] ${result.market.symbol or '?'} {result.final_signal} "
                        f"opp={result.scores.opportunity:.0f} risk={result.scores.risk:.0f}"
                    )
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                print(f"[error] {candidate.address}: {exc}")
        state = self.storage.read_json(self.storage.state_path, {})
        state["last_run"] = utc_iso()
        self.storage.write_json(self.storage.state_path, state)
        return results

    def _get_security(self, network: str, address: str) -> SecuritySnapshot:
        path = self.storage.snapshot_path("security_snapshots", network, address)
        cached = self.storage.latest_snapshot("security_snapshots", network, address)
        cache_minutes = float(self.settings["goplus"].get("cache_minutes", 10))
        if cached and _age_minutes(cached.get("ts")) < cache_minutes:
            return SecuritySnapshot.model_validate(cached)
        if not self.settings["goplus"].get("enabled", True):
            security = SecuritySnapshot(
                ts=utc_iso(), network=network, address=address, error="GoPlus desactivado"
            )
        else:
            try:
                security = self.goplus.fetch(network, address)
                self._api_status("goplus", True)
            except Exception as exc:
                security = SecuritySnapshot(
                    ts=utc_iso(), network=network, address=address,
                    available=False, error=str(exc),
                )
                self._api_status("goplus", False, str(exc))
        self.storage.append_jsonl(path, security.model_dump())
        return security

    def _get_social(self, network: str, address: str, symbol: str) -> SocialSnapshot:
        social = SocialSnapshot(ts=utc_iso(), network=network, address=address)
        posts = []
        if self.settings["x"].get("enabled", True) and self.x.enabled:
            try:
                posts.extend(self.x.search(symbol, address))
                social.available_sources.append("x")
                self._api_status("x", True)
            except Exception as exc:
                social.errors.append(f"X: {exc}")
                self._api_status("x", False, str(exc))
        if self.settings["lunarcrush"].get("enabled", True) and self.lunar.enabled and symbol:
            try:
                summary, lunar_posts = self.lunar.fetch(symbol)
                posts.extend(lunar_posts)
                social.available_sources.append("lunarcrush")
                social.sentiment = summary.get("sentiment")
                social.contributors = int(summary.get("contributors") or 0)
                social.interactions += int(summary.get("interactions") or 0)
                social.mention_count += int(summary.get("social_volume") or 0)
                self._api_status("lunarcrush", True)
            except Exception as exc:
                social.errors.append(f"LunarCrush: {exc}")
                self._api_status("lunarcrush", False, str(exc))
        weights = {
            str(item.get("username", "")).lower().lstrip("@"): float(item.get("weight", 1))
            for item in self.settings.get("influencers", {}).get("accounts", [])
            if item.get("enabled", True) and item.get("username")
        }
        for post in posts:
            post.author_weight = weights.get(post.author.lower().lstrip("@"), 1.0)
            if post.author.lower().lstrip("@") in weights:
                social.influencer_mentions += post.author_weight
        social.posts = posts
        social.mention_count += len(posts)
        social.interactions += sum(post.interactions for post in posts)
        self.storage.append_jsonl(
            self.storage.snapshot_path("social_snapshots", network, address), social.model_dump()
        )
        return social

    def _maybe_alert(self, result: AnalysisResult) -> None:
        alerts = self.settings["alerts"]
        if not result.notification_type or not self.telegram.enabled:
            return
        state = self.storage.read_json(self.storage.state_path, {})
        key = token_key(result.market.network, result.market.address)
        if result.notification_type == "EXIT_WARNING":
            bucket = "last_exit_warning_by_token"
            cooldown = float(alerts["exit_warnings"].get("cooldown_minutes", 5))
        elif result.notification_type == "RUG_WATCH":
            bucket = "last_rug_watch_by_token"
            cooldown = float(alerts["rug_watch"].get("cooldown_minutes", 60))
        else:
            bucket = "last_alert_by_token"
            cooldown = float(alerts["cooldown_minutes_per_token"])
        last = state.get(bucket, {}).get(key)
        if last and _age_minutes(last) < cooldown:
            return
        try:
            self.telegram.send_result(result)
            result.alert_sent = True
            state.setdefault(bucket, {})[key] = utc_iso()
            self.storage.write_json(self.storage.state_path, state)
        except Exception as exc:
            result.alert_error = str(exc)

    def _record_seen(self, candidates: list[Candidate]) -> None:
        state = self.storage.read_json(self.storage.state_path, {})
        seen = state.setdefault("seen_tokens", {})
        for candidate in candidates:
            key = token_key(candidate.network, candidate.address)
            item = seen.setdefault(key, {"first_seen": utc_iso()})
            item["last_seen"] = utc_iso()
            item["sources"] = candidate.sources
        self.storage.write_json(self.storage.state_path, state)

    def _update_watchlist(self, result: AnalysisResult) -> None:
        watchlist = self.storage.read_json(self.storage.watchlist_path, {"tokens": {}})
        key = token_key(result.market.network, result.market.address)
        tokens = watchlist.setdefault("tokens", {})
        existing = tokens.get(key)
        if existing and existing.get("terminal_collapse"):
            return
        if (
            existing
            and existing.get("watch_reason") == "ollama_retry"
            and result.llm_error is None
            and result.final_signal == "AVOID"
            and result.notification_type is None
        ):
            existing.update({
                "enabled": False, "watch_reason": "ollama_retry_complete",
                "updated_at": utc_iso(),
            })
            tokens[key] = existing
            self.storage.write_json(self.storage.watchlist_path, watchlist)
            return
        should_track = (
            (existing is not None and existing.get("enabled", True))
            or result.final_signal in {"WAIT", "BUY_CANDIDATE"}
            or result.notification_type == "RUG_WATCH"
            or "manual" in result.candidate.sources
            or result.llm_error is not None
        )
        if not should_track:
            return
        terminal_collapse = bool(result.notification_suppressed_reasons)
        tokens[key] = {
            "network": result.market.network, "address": result.market.address,
            "symbol": result.market.symbol, "label": result.candidate.label,
            "enabled": not terminal_collapse, "last_signal": result.final_signal,
            "watch_reason": (
                "high_rug_risk" if result.notification_type == "RUG_WATCH"
                else (
                    "manual" if "manual" in result.candidate.sources
                    else (
                        "ollama_retry" if result.llm_error is not None
                        else (existing or {}).get("watch_reason", "signal")
                    )
                )
            ),
            "last_opportunity": result.scores.opportunity, "last_risk": result.scores.risk,
            "first_added": (existing or {}).get("first_added", utc_iso()),
            "terminal_collapse": terminal_collapse,
            "collapse_reasons": result.notification_suppressed_reasons,
            "updated_at": utc_iso(),
        }
        self.storage.write_json(self.storage.watchlist_path, watchlist)

    def _watchlist_entry(
        self, network: str, address: str, *, include_disabled: bool = False
    ) -> dict[str, Any] | None:
        watchlist = self.storage.read_json(self.storage.watchlist_path, {"tokens": {}})
        entry = watchlist.get("tokens", {}).get(token_key(network, address))
        if not isinstance(entry, dict):
            return None
        if not include_disabled and not entry.get("enabled", True):
            return None
        return entry

    def _api_status(self, name: str, ok: bool, error: str | None = None) -> None:
        state = self.storage.read_json(self.storage.state_path, {})
        state.setdefault("api_status", {})[name] = {
            "ok": ok, "checked_at": utc_iso(), "error": error,
        }
        self.storage.write_json(self.storage.state_path, state)


def _age_minutes(value: Any) -> float:
    if not value:
        return float("inf")
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds() / 60
    except (TypeError, ValueError):
        return float("inf")
