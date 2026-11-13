from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from core.http import HttpClient
from core.utils import as_float, as_int
from models.schemas import SocialPost


class LunarCrushSource:
    def __init__(self, http: HttpClient, base_url: str, api_key: str) -> None:
        self.http = http
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def fetch(self, topic: str) -> tuple[dict[str, Any], list[SocialPost]]:
        topic = re.sub(r"[^a-z0-9 $]", "", topic.lower()).strip()
        if not topic:
            return {}, []
        encoded = quote(topic, safe="")
        headers = {"Authorization": f"Bearer {self.api_key}"}
        summary_payload = self.http.get_json(
            f"{self.base_url}/public/topic/{encoded}/v1", headers=headers
        )
        posts_payload = self.http.get_json(
            f"{self.base_url}/public/topic/{encoded}/posts/v1", headers=headers
        )
        summary = summary_payload.get("data", summary_payload) if isinstance(summary_payload, dict) else {}
        posts: list[SocialPost] = []
        for item in posts_payload.get("data", []) if isinstance(posts_payload, dict) else []:
            creator = item.get("creator_display_name") or item.get("creator_name") or item.get("creator_id")
            text = item.get("body") or item.get("title") or item.get("text") or ""
            interactions = as_int(item.get("interactions") or item.get("interactions_24h"))
            posts.append(
                SocialPost(
                    id=str(item.get("id") or ""), source="lunarcrush", author=str(creator or ""),
                    text=str(text), created_at=str(item.get("post_created") or item.get("time") or "") or None,
                    interactions=interactions,
                )
            )
        normalized = {
            "sentiment": as_float(summary.get("sentiment"), default=-1),
            "contributors": as_int(summary.get("num_contributors") or summary.get("contributors_24h")),
            "social_volume": as_int(summary.get("social_volume_24h") or summary.get("num_posts")),
            "interactions": as_int(summary.get("interactions_24h") or summary.get("interactions")),
        }
        if normalized["sentiment"] < 0:
            normalized["sentiment"] = None
        return normalized, posts

