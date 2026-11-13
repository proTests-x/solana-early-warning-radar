from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Iterable


class JsonStorage:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self._ensure_layout()

    def _ensure_layout(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        for name in ("market_snapshots", "social_snapshots", "security_snapshots", "evaluations"):
            (self.data_dir / name).mkdir(parents=True, exist_ok=True)
        defaults = {
            "state.json": {"last_run": None, "last_alert_by_token": {}, "seen_tokens": {}, "api_status": {}},
            "watchlist.json": {"tokens": {}},
        }
        for name, value in defaults.items():
            path = self.data_dir / name
            if not path.exists():
                self.write_json(path, value)

    def read_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            return default

    def write_json(self, path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        with tmp.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)

    def append_jsonl(self, path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def read_jsonl(self, path: Path, limit: int | None = None) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        records: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8-sig") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict):
                    records.append(item)
        return records[-limit:] if limit else records

    def snapshot_path(self, category: str, network: str, address: str) -> Path:
        safe_network = re.sub(r"[^a-zA-Z0-9_-]", "_", network)
        safe_address = re.sub(r"[^a-zA-Z0-9_-]", "_", address)
        return self.data_dir / category / f"{safe_network}_{safe_address}.jsonl"

    @property
    def state_path(self) -> Path:
        return self.data_dir / "state.json"

    @property
    def watchlist_path(self) -> Path:
        return self.data_dir / "watchlist.json"

    def latest_snapshot(self, category: str, network: str, address: str) -> dict[str, Any] | None:
        records = self.read_jsonl(self.snapshot_path(category, network, address), limit=1)
        return records[-1] if records else None

    def append_many(self, path: Path, values: Iterable[Any]) -> None:
        for value in values:
            self.append_jsonl(path, value)
