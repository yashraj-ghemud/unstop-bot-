from __future__ import annotations

import re
from dataclasses import dataclass

from config import Preferences, normalize_keywords
from scraper import Hackathon


HACKATHON_TITLE_HINTS = [
    "hackathon",
    "hack",
    "ideathon",
    "innovation",
    "challenge",
    "code",
    "build",
]


@dataclass(frozen=True)
class Stage1Result:
    decision: str  # "pass" | "fail" | "ambiguous"
    reason: str


def _contains_any(haystack: str, needles: list[str]) -> bool:
    hs = haystack.lower()
    return any(n in hs for n in needles if n)


def _contains_any_word(haystack: str, words: list[str]) -> bool:
    # word-ish boundary match to avoid "hack" inside unrelated tokens
    hs = haystack.lower()
    for w in words:
        w = (w or "").strip().lower()
        if not w:
            continue
        if re.search(rf"(?<!\w){re.escape(w)}(?!\w)", hs):
            return True
    return False


def stage1_filter(h: Hackathon, prefs: Preferences) -> Stage1Result:
    title = (h.title or "").strip()
    desc = (h.description or "").strip()
    loc = (h.location or "").strip()
    mode = (h.mode or "").strip().lower()

    include = normalize_keywords(prefs.include_keywords)
    exclude = normalize_keywords(prefs.exclude_keywords)
    city = (prefs.city_must_include or "").strip().lower()
    preferred_mode = (prefs.preferred_mode or "both").strip().lower()

    text_blob = f"{title}\n{desc}\n{loc}\n{mode}".lower()

    if exclude and _contains_any(text_blob, exclude):
        return Stage1Result("fail", "Matched exclude keyword")

    # Mode must match if preference isn't both.
    if preferred_mode in ("online", "offline"):
        if mode in ("unknown", ""):
            return Stage1Result("ambiguous", "Mode missing")
        if preferred_mode != mode and not (preferred_mode == "online" and mode == "both") and not (
            preferred_mode == "offline" and mode == "both"
        ):
            return Stage1Result("fail", f"Mode mismatch ({mode})")

    # City check: if location is present and doesn't contain the city => fail; if missing => ambiguous
    if city:
        if loc:
            if city not in loc.lower():
                return Stage1Result("fail", f"Location not in {prefs.city_must_include}")
        else:
            return Stage1Result("ambiguous", "Location missing")

    # Must look like a hackathon: title contains hack words OR include_keywords match.
    if include:
        if not _contains_any(title.lower(), include) and not _contains_any(desc.lower(), include):
            # include list present but not found — ambiguous if title looks hackathon-ish, else fail
            if _contains_any_word(title, HACKATHON_TITLE_HINTS):
                return Stage1Result("ambiguous", "No include keyword match; title looks hackathon-ish")
            return Stage1Result("fail", "No include keyword match")
    else:
        if not _contains_any_word(title, HACKATHON_TITLE_HINTS):
            return Stage1Result("fail", "Title doesn't look like a hackathon")

    # Prize threshold: if prize is unknown (0) we keep ambiguous; if known but below threshold => fail
    if prefs.min_prize_inr > 0:
        if h.prize_inr <= 0:
            return Stage1Result("ambiguous", "Prize missing/unknown")
        if h.prize_inr < prefs.min_prize_inr:
            return Stage1Result("fail", f"Prize below {prefs.min_prize_inr}")

    # If description is long and location/mode are unknown, send to LLM.
    if len(desc) > 350 and (not loc or mode in ("unknown", "")):
        return Stage1Result("ambiguous", "Needs LLM classification (long description)")

    return Stage1Result("pass", "Matched stage-1 rules")

