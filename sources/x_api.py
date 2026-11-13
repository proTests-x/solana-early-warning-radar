from __future__ import annotations

from typing import Any

from core.http import HttpClient
from core.utils import as_int
from models.schemas import SocialPost


class XSource:
    def __init__(self, http: HttpClient, base_url: str, bearer_token: str, max_results: int = 20) -> None:
        self.http = http
        self.base_url = base_url.rstrip("/")
        self.bearer_token = bearer_token
        self.max_results = max(10, min(100, max_results))

    @property
    def enabled(self) -> bool:
        return bool(self.bearer_token)

    def search(self, symbol: str, address: str) -> list[SocialPost]:
        terms = [f'"{address}"']
        clean_symbol = symbol.strip().lstrip("$")
        if clean_symbol and len(clean_symbol) >= 2:
            terms.insert(0, f"${clean_symbol}")
        query = f"({' OR '.join(terms)}) -is:retweet"
        payload = self.http.get_json(
            f"{self.base_url}/tweets/search/recent",
            params={
                "query": query,
                "max_results": self.max_results,
                "tweet.fields": "created_at,public_metrics,author_id",
                "expansions": "author_id",
                "user.fields": "username",
            },
            headers={"Authorization": f"Bearer {self.bearer_token}"},
        )
        users = {
            str(user.get("id")): str(user.get("username") or "")
            for user in (payload.get("includes", {}).get("users", []) if isinstance(payload, dict) else [])
        }
        posts: list[SocialPost] = []
        for item in payload.get("data", []) if isinstance(payload, dict) else []:
            metrics = item.get("public_metrics") or {}
            posts.append(
                SocialPost(
                    id=str(item.get("id") or ""),
                    source="x",
                    author=users.get(str(item.get("author_id")), ""),
                    text=str(item.get("text") or ""),
                    created_at=item.get("created_at"),
                    likes=as_int(metrics.get("like_count")),
                    reposts=as_int(metrics.get("retweet_count")),
                    interactions=sum(as_int(metrics.get(key)) for key in (
                        "like_count", "retweet_count", "reply_count", "quote_count"
                    )),
                )
            )
        return posts

