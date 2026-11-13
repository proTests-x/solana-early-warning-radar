from __future__ import annotations

import json
import time
from typing import Any

from models.schemas import FeatureSet, LLMAnalysis, MarketSnapshot, Scores, SecuritySnapshot, SocialSnapshot


SYSTEM_PROMPT = """Eres la capa explicativa conservadora de un radar especulativo de memecoins.
No inventes ni recalcules métricas. No conviertas scores en probabilidades. No prometas ganancias.
Trata los tokens jóvenes como riesgo extremo. Busca contradicciones entre hype, compradores y liquidez.
Da prioridad a la posibilidad de vender, liquidez, concentración y capacidades del creador.
Si hard_blocks no está vacío, signal debe ser AVOID.
BUY_CANDIDATE solo significa que las reglas heurísticas permiten revisión humana.
Puedes bajar una señal por contradicciones, pero nunca elevar la señal indicada en max_allowed_signal.
Responde exclusivamente según el esquema JSON solicitado y en español."""


class OllamaAnalyst:
    def __init__(
        self, host: str, model: str, timeout: float = 90, temperature: float = 0.1,
        max_social_posts: int = 20, think: bool = False, max_output_tokens: int = 900,
        keep_alive: str = "15m",
    ) -> None:
        self.host = host
        self.model = model
        self.timeout = timeout
        self.temperature = temperature
        self.max_social_posts = max_social_posts
        self.think = think
        self.max_output_tokens = max_output_tokens
        self.keep_alive = keep_alive

    def analyze(
        self,
        market: MarketSnapshot,
        security: SecuritySnapshot,
        social: SocialSnapshot,
        features: FeatureSet,
        scores: Scores,
        max_allowed_signal: str,
    ) -> LLMAnalysis:
        try:
            from ollama import Client
        except ImportError as exc:
            raise RuntimeError("La librería ollama no está instalada") from exc
        client = Client(host=self.host, timeout=self.timeout)
        payload = {
            "token": {
                "network": market.network, "address": market.address,
                "name": market.name, "symbol": market.symbol, "age_minutes": market.age_minutes,
            },
            "market": market.model_dump(exclude={"links"}),
            "security": security.model_dump(exclude={"error"}),
            "social": {
                **social.model_dump(exclude={"posts"}),
                "posts": [post.model_dump() for post in social.posts[: self.max_social_posts]],
            },
            "features": features.model_dump(),
            "scores": scores.model_dump(),
            "max_allowed_signal": max_allowed_signal,
        }
        response = client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            format=LLMAnalysis.model_json_schema(),
            think=self.think,
            options={"temperature": self.temperature, "num_predict": self.max_output_tokens},
            keep_alive=self.keep_alive,
        )
        message = getattr(response, "message", None)
        content = getattr(message, "content", None)
        if content is None and isinstance(response, dict):
            content = (response.get("message") or {}).get("content")
        if not content:
            raise RuntimeError("Ollama devolvió una respuesta vacía")
        return LLMAnalysis.model_validate_json(content)

    def analyze_with_retry(
        self,
        market: MarketSnapshot,
        security: SecuritySnapshot,
        social: SocialSnapshot,
        features: FeatureSet,
        scores: Scores,
        max_allowed_signal: str,
        *,
        max_attempts: int = 2,
        retry_delay_seconds: float = 2,
    ) -> LLMAnalysis:
        attempts = max(1, int(max_attempts))
        errors: list[str] = []
        for attempt in range(1, attempts + 1):
            try:
                return self.analyze(
                    market, security, social, features, scores, max_allowed_signal
                )
            except Exception as exc:
                errors.append(f"intento {attempt}: {exc}")
                # El servidor puede seguir generando después de que el cliente agota
                # su timeout. Reintentar de inmediato crearía una cola duplicada.
                if _is_timeout_error(exc):
                    break
                if attempt < attempts and retry_delay_seconds > 0:
                    time.sleep(retry_delay_seconds)
        raise RuntimeError(
            f"Ollama falló después de {len(errors)} intento(s): {' | '.join(errors)}"
        )


def _is_timeout_error(exc: Exception) -> bool:
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    return "timeout" in name or "timed out" in message or "timeout" in message
