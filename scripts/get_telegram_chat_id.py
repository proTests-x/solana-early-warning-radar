from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.runtime import relaunch_in_project_venv  # noqa: E402

relaunch_in_project_venv(ROOT)

from core.config import load_settings  # noqa: E402
from core.http import HttpClient  # noqa: E402


def main() -> int:
    settings = load_settings(ROOT)
    token = str(settings.get("secrets", {}).get("telegram_bot_token", "")).strip()
    if not token:
        print("Configura telegram_bot_token en config/secrets.json primero.")
        return 2
    cfg = settings["http"]
    http = HttpClient(cfg["timeout_seconds"], cfg["max_retries"], cfg["backoff_seconds"])
    payload = http.get_json(f"https://api.telegram.org/bot{token}/getUpdates")
    chats: dict[str, str] = {}
    for update in payload.get("result", []):
        message = update.get("message") or update.get("channel_post") or {}
        chat = message.get("chat") or {}
        if chat.get("id") is not None:
            name = chat.get("title") or chat.get("username") or chat.get("first_name") or "sin nombre"
            chats[str(chat["id"])] = str(name)
    if not chats:
        print("No hay chats. Envía primero un mensaje al bot y vuelve a ejecutar el script.")
        return 1
    for chat_id, name in chats.items():
        print(f"chat_id={chat_id}  nombre={name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
