from __future__ import annotations

import os
import sys
from typing import List

from env_loader import load_env
from classifier import classify_with_groq
from config import PREFERENCES, Preferences
from filter import stage1_filter
from notifier import format_hackathon_message, load_telegram_config, send_summary, send_telegram_message
from scraper import Hackathon, fetch_open_hackathons
from state import load_seen, save_seen


SEEN_PATH = os.environ.get("SEEN_PATH", "seen.json")


def _should_use_llm() -> bool:
    return (os.environ.get("USE_LLM", "1").strip().lower() not in ("0", "false", "no"))


def run_once(prefs: Preferences | None = None) -> int:
    load_env()
    prefs = prefs or PREFERENCES
    hacks = fetch_open_hackathons()

    state = load_seen(SEEN_PATH)

    tg = load_telegram_config()
    if tg is None:
        print("Missing TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID; will run but not notify.", file=sys.stderr)

    new_items: List[Hackathon] = []
    for h in hacks:
        if h.url in state.seen_urls:
            continue

        s1 = stage1_filter(h, prefs)
        if s1.decision == "fail":
            continue

        if s1.decision == "pass":
            new_items.append(h)
            continue

        # ambiguous => LLM
        if _should_use_llm():
            dec = classify_with_groq(h)
            if dec.is_relevant:
                # If LLM detects a mode, prefer it
                if dec.mode_detected and dec.mode_detected != "unknown":
                    h = Hackathon(
                        title=h.title,
                        description=h.description,
                        mode=dec.mode_detected,
                        location=h.location,
                        prize_inr=h.prize_inr,
                        deadline=h.deadline,
                        url=h.url,
                    )
                new_items.append(h)
        else:
            # If LLM disabled, treat ambiguous as skip (safe default)
            continue

    # Notify + persist
    if tg is not None:
        send_summary(tg, len(new_items))
        for h in new_items:
            send_telegram_message(tg, format_hackathon_message(h))

    # Mark all fetched as seen ONLY if they were notified as "new"
    for h in new_items:
        state.seen_urls.add(h.url)

    save_seen(SEEN_PATH, state)
    print(f"Done. New sent: {len(new_items)}. Total seen: {len(state.seen_urls)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_once())

