from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

import requests

from config import Preferences
from env_loader import load_env
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
            paid_filter=getattr(prefs, "paid_filter", "any"),
            status_filter=getattr(prefs, "status_filter", "any"),
            domain=getattr(prefs, "domain", "Engineering"),
            category=getattr(prefs, "category", "Any"),
            include_keywords=prefs.include_keywords,
            exclude_keywords=prefs.exclude_keywords,
        )
        set_user_preferences(str(chat_id), prefs, setup_complete=False)
        set_user_state(str(chat_id), {"awaiting": "fee"})
        send_telegram_message_to(
            token,
            str(chat_id),
            "Choose paid/free filter.",
            reply_markup=_kb([["Free", "Paid", "Any"]]),
        )
        return True

    if step == "fee":
        if text not in ("free", "paid", "any"):
            send_telegram_message_to(token, str(chat_id), "Please choose: Free / Paid / Any.")
            return True
        prefs = Preferences(
            preferred_mode=prefs.preferred_mode,
            paid_filter=text,
            status_filter=getattr(prefs, "status_filter", "any"),
            domain=getattr(prefs, "domain", "Engineering"),
            category=getattr(prefs, "category", "Any"),
            include_keywords=prefs.include_keywords,
            exclude_keywords=prefs.exclude_keywords,
        )
        set_user_preferences(str(chat_id), prefs, setup_complete=False)
        set_user_state(str(chat_id), {"awaiting": "status"})
        send_telegram_message_to(
            token,
            str(chat_id),
            "Choose event status.",
            reply_markup=_kb([["Live", "Recent", "Expired"], ["Any"]]),
        )
        return True

    if step == "status":
        if text not in ("live", "recent", "expired", "any"):
            send_telegram_message_to(token, str(chat_id), "Pick: Live / Recent / Expired / Any.")
            return True
        prefs = Preferences(
            preferred_mode=prefs.preferred_mode,
            paid_filter=getattr(prefs, "paid_filter", "any"),
            status_filter=text,
            domain=getattr(prefs, "domain", "Engineering"),
            category=getattr(prefs, "category", "Any"),
            include_keywords=prefs.include_keywords,
            exclude_keywords=prefs.exclude_keywords,
        )
        set_user_preferences(str(chat_id), prefs, setup_complete=False)
        set_user_state(str(chat_id), {"awaiting": "domain"})
        send_telegram_message_to(
            token,
            str(chat_id),
            "Choose domain.",
            reply_markup=_kb([["Engineering", "Management"], ["Arts & Science", "Medicine"], ["Law", "Others"]]),
        )
        return True

    if step == "domain":
        allowed = {
            "engineering": "Engineering",
            "management": "Management",
            "arts & science": "Arts & Science",
            "medicine": "Medicine",
            "law": "Law",
            "others": "Others",
        }
        if text not in allowed:
            send_telegram_message_to(token, str(chat_id), "Choose a domain from the buttons.")
            return True
        prefs = Preferences(
            preferred_mode=prefs.preferred_mode,
            paid_filter=getattr(prefs, "paid_filter", "any"),
            status_filter=getattr(prefs, "status_filter", "any"),
            domain=allowed[text],
            category=getattr(prefs, "category", "Any"),
            include_keywords=prefs.include_keywords,
            exclude_keywords=prefs.exclude_keywords,
        )
        set_user_preferences(str(chat_id), prefs, setup_complete=False)
        set_user_state(str(chat_id), {"awaiting": "category"})

        # Category list (from your screenshot). We show a short menu + allow typing.
        send_telegram_message_to(
            token,
            str(chat_id),
            "Choose a category (or type your own category name).\nCommon options:",
            reply_markup=_kb(
                [
                    ["Software Development", "Data & Analytics"],
                    ["Artificial Intelligence & Machine Learning", "Cybersecurity"],
                    ["Cloud & Infrastructure", "Product Management"],
                    ["Quality Assurance & Testing", "IT & Systems"],
                    ["Any"],
                ],
                one_time=False,
            ),
        )
        return True

    if step == "category":
        # accept anything, but keep simple normalization
        cat = text_raw.strip()
        if not cat:
            send_telegram_message_to(token, str(chat_id), "Please pick a category or type one.")
            return True
        if cat.lower() == "any":
            cat = "Any"

        prefs = Preferences(
            preferred_mode=prefs.preferred_mode,
            paid_filter=getattr(prefs, "paid_filter", "any"),
            status_filter=getattr(prefs, "status_filter", "any"),
            domain=getattr(prefs, "domain", "Engineering"),
            category=cat,
            include_keywords=prefs.include_keywords,
            exclude_keywords=prefs.exclude_keywords,
        )
        set_user_preferences(str(chat_id), prefs, setup_complete=True)
        clear_user_state(str(chat_id))
        send_telegram_message_to(
            token,
            str(chat_id),
            "✅ Filter saved:\n"
            f"- Mode: {prefs.preferred_mode}\n"
            f"- Fee: {prefs.paid_filter}\n"
            f"- Status: {prefs.status_filter}\n"
            f"- Domain: {prefs.domain}\n"
            f"- Category: {prefs.category}\n\n"
            "Now send: check",
        )
        return True

    return False


def main() -> int:
    load_env()
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
                    send_telegram_message_to(
                        token,
                        chat_id,
                        "You're already set.\n"
                        f"- Mode: {prefs.preferred_mode}\n"
                        f"- Fee: {getattr(prefs,'paid_filter','any')}\n"
                        f"- Status: {getattr(prefs,'status_filter','any')}\n"
                        f"- Domain: {getattr(prefs,'domain','')}\n"
                        f"- Category: {getattr(prefs,'category','')}\n\n"
                        "Send: check\nOr change filters: /filter",
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

