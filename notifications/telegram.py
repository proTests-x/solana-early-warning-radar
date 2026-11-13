from __future__ import annotations

from typing import Any

from core.http import HttpClient
from models.schemas import AnalysisResult


class TelegramNotifier:
    def __init__(self, http: HttpClient, bot_token: str = "", chat_id: str = "") -> None:
        self.http = http
        self.bot_token = bot_token.strip()
        self.chat_id = str(chat_id).strip()

    @property
    def enabled(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def send_result(self, result: AnalysisResult) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("Telegram no está configurado")
        return self.http.post_json(
            f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
            data={"chat_id": self.chat_id, "text": format_alert(result), "disable_web_page_preview": "true"},
        )


def format_alert(result: AnalysisResult) -> str:
    market = result.market
    features = result.features
    scores = result.scores
    kind = result.notification_type or result.final_signal
    icon = {
        "BUY_CANDIDATE": "🔥", "WAIT": "👀", "AVOID": "⛔",
        "RUG_WATCH": "🚩", "EXIT_WARNING": "🚨",
    }[kind]
    lines = [
        f"{icon} {kind} — ${market.symbol or '?'}",
        "",
        f"Red: {market.network}",
        f"Edad: {_number(market.age_minutes, 1)} min",
        f"Precio: ${market.price_usd:.10g}",
        f"MCap: {_money(market.market_cap_usd)}",
        f"Liquidez: {_money(market.liquidity_usd)}",
        "",
        f"Vol 5m: {_money(market.volume_5m_usd)}",
        f"Compras/Ventas: {market.buys_5m} / {market.sells_5m}",
        f"Buy/Sell: {features.buy_sell_ratio:.2f}x",
        f"Precio 5m: {market.price_change_5m_pct:+.1f}%",
        "",
        f"Opportunity: {scores.opportunity:.0f}/100 (raw {scores.opportunity_raw:.0f})",
        f"Risk: {scores.risk:.0f}/100",
    ]
    if kind == "RUG_WATCH":
        lines += [
            "", "⚠️ ALTO RIESGO — NO ES SEÑAL DE COMPRA",
            "Hay actividad suficiente para vigilarlo, pero también señales compatibles con rug o restricciones de salida.",
        ]
    elif kind == "EXIT_WARNING":
        lines += [
            "", "🚨 ALERTA DE VENTA / SALIDA",
            "Deterioro rápido detectado. Revisa una posible venta o salida inmediata. El precio observado no garantiza que la operación pueda ejecutarse.",
        ]
    if result.warning_reasons:
        lines += ["", "Motivos de alerta:"] + [
            f"• {_human_reason(item)}" for item in result.warning_reasons[:7]
        ]
    if result.llm:
        lines += ["", "🧠 Qwen:", result.llm.summary]
        if result.llm.bull_case and kind not in {"RUG_WATCH", "EXIT_WARNING"}:
            lines += ["", "A favor:"] + [f"• {item}" for item in result.llm.bull_case[:4]]
        risks = result.llm.bear_case + result.llm.rug_warning_signs
        if risks:
            lines += ["", "Riesgos:"] + [f"• {item}" for item in risks[:5]]
        if result.llm.exit_warning_conditions:
            lines += ["", "⚠️ Vigilar salida:"] + [
                f"• {item}" for item in result.llm.exit_warning_conditions[:4]
            ]
    elif scores.risk_reasons:
        lines += ["", "Riesgos detectados:"] + [f"• {item}" for item in scores.risk_reasons[:5]]
    if scores.hard_blocks:
        lines += ["", "Bloqueos:"] + [f"• {item}" for item in scores.hard_blocks]
    lines += ["", "Contrato:", market.address]
    if market.url:
        lines += ["", "DexScreener:", market.url]
    text = "\n".join(lines)
    return text[:4096]


def _money(value: float) -> str:
    if value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:.2f}"


def _number(value: float | None, decimals: int) -> str:
    return "desconocida" if value is None else f"{value:.{decimals}f}"


def _human_reason(value: str) -> str:
    return value.replace("_", " ").replace(":", ": ")
