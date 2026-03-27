from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

import requests

from config import Preferences
from main import run_once
from notifier import send_telegram_message_to
from user_prefs import (
    clear_user_state,
    get_user_preferences,
    get_user_state,
    set_user_preferences,
    set_user_state,
)


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
        prefs, _ = get_user_preferences(str(chat_id))
        run_once(prefs)
    finally:
        if old is None:
            os.environ.pop("TELEGRAM_CHAT_ID", None)
        else:
            os.environ["TELEGRAM_CHAT_ID"] = old


def _kb(button_rows: list[list[str]], *, one_time: bool = True) -> dict:
    return {
        "keyboard": [[{"text": b} for b in row] for row in button_rows],
        "resize_keyboard": True,
        "one_time_keyboard": one_time,
    }


def _start_filter_wizard(token: str, chat_id: str) -> None:
    set_user_state(str(chat_id), {"awaiting": "mode"})
    send_telegram_message_to(
        token,
        str(chat_id),
        "Choose your preferred mode.",
        reply_markup=_kb([["Online", "Offline", "Both"]]),
    )


def _handle_filter_reply(token: str, chat_id: str, text_raw: str) -> bool:
    """
    Returns True if message was consumed by the filter wizard.
    """
    st = get_user_state(str(chat_id))
    step = (st.get("awaiting") or "").strip()
    if not step:
        return False

    text = (text_raw or "").strip().lower()
    prefs, _ = get_user_preferences(str(chat_id))

    if step == "mode":
        if text not in ("online", "offline", "both"):
            send_telegram_message_to(token, str(chat_id), "Please choose: Online / Offline / Both.")
            return True
        prefs = Preferences(
            preferred_mode=text,
            include_keywords=prefs.include_keywords,
            exclude_keywords=prefs.exclude_keywords,
            min_prize_inr=prefs.min_prize_inr,
            city_must_include=prefs.city_must_include,
        )
        set_user_preferences(str(chat_id), prefs, setup_complete=False)
        set_user_state(str(chat_id), {"awaiting": "city"})
        send_telegram_message_to(
            token,
            str(chat_id),
            "Choose your city filter.",
            reply_markup=_kb([["Pune"], ["Any"]]),
        )
        return True

    if step == "city":
        if text not in ("pune", "any"):
            send_telegram_message_to(token, str(chat_id), "Please choose: Pune or Any.")
            return True
        city = "Pune" if text == "pune" else ""
        prefs = Preferences(
            preferred_mode=prefs.preferred_mode,
            include_keywords=prefs.include_keywords,
            exclude_keywords=prefs.exclude_keywords,
            min_prize_inr=prefs.min_prize_inr,
            city_must_include=city,
        )
        set_user_preferences(str(chat_id), prefs, setup_complete=False)
        set_user_state(str(chat_id), {"awaiting": "prize"})
        send_telegram_message_to(
            token,
            str(chat_id),
            "Choose minimum prize (INR).",
            reply_markup=_kb([["0", "5000", "10000"], ["50000"]]),
        )
        return True

    if step == "prize":
        if text not in ("0", "5000", "10000", "50000"):
            send_telegram_message_to(token, str(chat_id), "Pick one: 0 / 5000 / 10000 / 50000.")
            return True
        prefs = Preferences(
            preferred_mode=prefs.preferred_mode,
            include_keywords=prefs.include_keywords,
            exclude_keywords=prefs.exclude_keywords,
            min_prize_inr=int(text),
            city_must_include=prefs.city_must_include,
        )
        set_user_preferences(str(chat_id), prefs, setup_complete=True)
        clear_user_state(str(chat_id))
        city_label = prefs.city_must_include if prefs.city_must_include else "Any"
        send_telegram_message_to(
            token,
            str(chat_id),
            f"✅ Filter saved:\n- Mode: {prefs.preferred_mode}\n- City: {city_label}\n- Min prize: {prefs.min_prize_inr}\n\nNow send: check",
        )
        return True

    return False


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

            # If user is in the filter wizard, consume their replies first.
            if _handle_filter_reply(token, chat_id, msg.get("text") or ""):
                continue

            if text in ("/start", "start"):
                prefs, setup = get_user_preferences(chat_id)
                if not setup:
                    send_telegram_message_to(token, chat_id, "Welcome! Let’s set your filters first.")
                    _start_filter_wizard(token, chat_id)
                else:
                    city_label = prefs.city_must_include if prefs.city_must_include else "Any"
                    send_telegram_message_to(
                        token,
                        chat_id,
                        f"You're already set.\n- Mode: {prefs.preferred_mode}\n- City: {city_label}\n- Min prize: {prefs.min_prize_inr}\n\nSend: check\nOr change filters: /filter",
                    )
            elif text == "/filter":
                send_telegram_message_to(token, chat_id, "Let’s update your filters.")
                _start_filter_wizard(token, chat_id)
            elif text == "check":
                send_telegram_message_to(token, chat_id, "🔎 Checking Unstop now…")
                try:
                    _handle_check(token, chat_id)
                except Exception as e:
                    send_telegram_message_to(token, chat_id, f"❌ Error while checking: {e}")
            elif text in ("help", "/help"):
                send_telegram_message_to(
                    token,
                    chat_id,
                    "Commands:\n- /start: setup\n- /filter: change filters\n- check: scan now",
                )

        time.sleep(1)


if __name__ == "__main__":
    raise SystemExit(main())

