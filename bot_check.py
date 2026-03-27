from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

import requests

from main import run_once
from notifier import send_telegram_message_to


def _get_env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def _tg(method: str, token: str, *, params: Optional[dict] = None, timeout_s: int = 40) -> Dict[str, Any]:
    url = f"https://api.telegram.org/bot{token}/{method}"
    r = requests.get(url, params=params or {}, timeout=timeout_s)
    r.raise_for_status()
    return r.json()


def _handle_check(token: str, chat_id: str) -> None:
    # run_once() already sends summary + messages to TELEGRAM_CHAT_ID.
    # For "check", we want replies to the requesting chat, so we temporarily override TELEGRAM_CHAT_ID.
    old = os.environ.get("TELEGRAM_CHAT_ID")
    os.environ["TELEGRAM_CHAT_ID"] = str(chat_id)
    try:
        run_once()
    finally:
        if old is None:
            os.environ.pop("TELEGRAM_CHAT_ID", None)
        else:
            os.environ["TELEGRAM_CHAT_ID"] = old


def main() -> int:
    token = _get_env("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("Missing TELEGRAM_BOT_TOKEN")

    # Optional safety: if set, bot only responds in this chat id
    allowed_chat_id = _get_env("TELEGRAM_CHAT_ID")
    allowed_chat_id = allowed_chat_id if allowed_chat_id else ""

    offset = int(_get_env("TG_OFFSET") or "0")
    send_telegram_message_to(token, allowed_chat_id or "me", "🤖 Bot listener started. Send: check") if False else None

    while True:
        data = _tg("getUpdates", token, params={"timeout": 30, "offset": offset + 1})
        for upd in data.get("result", []) or []:
            upd_id = int(upd.get("update_id", 0))
            offset = max(offset, upd_id)

            msg = upd.get("message") or upd.get("edited_message") or {}
            text = (msg.get("text") or "").strip().lower()
            chat = msg.get("chat") or {}
            chat_id = str(chat.get("id") or "").strip()
            if not chat_id:
                continue

            if allowed_chat_id and chat_id != allowed_chat_id:
                # Ignore other chats for safety
                continue

            if text == "check":
                send_telegram_message_to(token, chat_id, "🔎 Checking Unstop now…")
                try:
                    _handle_check(token, chat_id)
                except Exception as e:
                    send_telegram_message_to(token, chat_id, f"❌ Error while checking: {e}")
            elif text in ("/start", "start", "help", "/help"):
                send_telegram_message_to(token, chat_id, "Send `check` to scan Unstop right now.")

        time.sleep(1)


if __name__ == "__main__":
    raise SystemExit(main())

