from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional

import requests

from scraper import Hackathon


@dataclass(frozen=True)
class TelegramConfig:
    bot_token: str
    chat_id: str


def load_telegram_config() -> Optional[TelegramConfig]:
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
    if not token or not chat_id:
        return None
    return TelegramConfig(bot_token=token, chat_id=chat_id)


def _escape(s: str) -> str:
    # plain text mode; keep simple (no markdown escaping needed)
    return (s or "").strip()


def format_hackathon_message(h: Hackathon) -> str:
    title = _escape(h.title)
    mode = _escape(h.mode or "unknown")
    loc = _escape(h.location or "unknown")
    prize = f"₹{h.prize_inr:,}" if h.prize_inr and h.prize_inr > 0 else "Not mentioned"
    deadline = _escape(h.deadline or "Not mentioned")
    url = _escape(h.url)

    lines = [
        "🚨 New Hackathon Alert!",
        f"🏆 {title}",
        f"🧑‍💻 Mode: {mode}",
        f"📍 Location: {loc}",
        f"💰 Prize: {prize}",
        f"⏳ Deadline: {deadline}",
        f"🔗 {url}",
    ]
    return "\n".join(lines)


def send_telegram_message(cfg: TelegramConfig, text: str, *, timeout_s: int = 20) -> None:
    send_telegram_message_to(cfg.bot_token, cfg.chat_id, text, timeout_s=timeout_s)


def send_telegram_message_to(
    bot_token: str,
    chat_id: str,
    text: str,
    *,
    reply_markup: Optional[dict[str, Any]] = None,
    timeout_s: int = 20,
) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    r = requests.post(url, json=payload, timeout=timeout_s)
    r.raise_for_status()


def send_summary(cfg: TelegramConfig, new_count: int) -> None:
    send_telegram_message(cfg, f"✅ Unstop scan complete. New hackathons found: {new_count}")

