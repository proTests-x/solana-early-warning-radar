from analysis.ollama_analyst import OllamaAnalyst
from models.schemas import LLMAnalysis


def test_ollama_retries_after_error(monkeypatch) -> None:
    analyst = OllamaAnalyst("http://localhost", "test")
    calls = {"count": 0}

    def flaky(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise ValueError("JSON inválido")
        return LLMAnalysis(signal="WAIT", summary="recuperado")

    monkeypatch.setattr(analyst, "analyze", flaky)
    result = analyst.analyze_with_retry(
        None, None, None, None, None, "WAIT", max_attempts=2, retry_delay_seconds=0
    )
    assert result.summary == "recuperado"
    assert calls["count"] == 2


def test_ollama_does_not_queue_duplicate_after_timeout(monkeypatch) -> None:
    analyst = OllamaAnalyst("http://localhost", "test")
    calls = {"count": 0}

    def timeout(*args, **kwargs):
        calls["count"] += 1
        raise TimeoutError("timed out")

    monkeypatch.setattr(analyst, "analyze", timeout)
    try:
        analyst.analyze_with_retry(
            None, None, None, None, None, "WAIT",
            max_attempts=2, retry_delay_seconds=0,
        )
    except RuntimeError as exc:
        assert "1 intento(s)" in str(exc)
    else:
        raise AssertionError("Debió propagar el timeout")
    assert calls["count"] == 1
