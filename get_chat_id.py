from __future__ import annotations

import os
from typing import Any, Dict

import requests

from env_loader import load_env


def main() -> int:
    load_env()
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        raise SystemExit("Missing TELEGRAM_BOT_TOKEN (set it in env/.env first).")

    r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=30)
    r.raise_for_status()
    data: Dict[str, Any] = r.json()

    for upd in data.get("result", []) or []:
        msg = upd.get("message") or upd.get("edited_message") or {}
        chat = msg.get("chat") or {}
        chat_id = chat.get("id")
        username = chat.get("username")
        first_name = chat.get("first_name")
        text = msg.get("text")
        if chat_id is None:
            continue
        print(f"chat_id={chat_id} username=@{username} name={first_name} last_text={text}")

    print("\nTip: send a message to your bot, then run this again.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

