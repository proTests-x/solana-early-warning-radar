from __future__ import annotations

import random
import time
from typing import Any

import requests


class HttpError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class HttpClient:
    def __init__(
        self,
        timeout: float = 15,
        max_retries: int = 2,
        backoff: float = 0.8,
        user_agent: str = "memecoin-radar/0.1",
    ) -> None:
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff = backoff
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent, "Accept": "application/json"})

    def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        return self._request("GET", url, params=params, headers=headers)

    def post_json(
        self,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        return self._request("POST", url, json=json, data=data, headers=headers)

    def _request(self, method: str, url: str, **kwargs: Any) -> Any:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.request(method, url, timeout=self.timeout, **kwargs)
                if response.status_code == 429 or response.status_code >= 500:
                    raise HttpError(
                        f"{method} {url} devolvió HTTP {response.status_code}",
                        status_code=response.status_code,
                    )
                if not response.ok:
                    detail = response.text[:300].replace("\n", " ")
                    raise HttpError(
                        f"{method} {url} devolvió HTTP {response.status_code}: {detail}",
                        status_code=response.status_code,
                    )
                try:
                    return response.json()
                except ValueError as exc:
                    raise HttpError(f"{method} {url} devolvió JSON inválido") from exc
            except (requests.Timeout, requests.ConnectionError, HttpError) as exc:
                last_error = exc
                retryable = not isinstance(exc, HttpError) or exc.status_code in {429, 500, 502, 503, 504}
                if attempt >= self.max_retries or not retryable:
                    break
                delay = self.backoff * (2**attempt) + random.uniform(0, self.backoff / 4)
                time.sleep(delay)
        if isinstance(last_error, HttpError):
            raise last_error
        raise HttpError(f"No se pudo completar {method} {url}: {last_error}") from last_error

