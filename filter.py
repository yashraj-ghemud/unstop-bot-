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
    mode = (h.mode or "").strip().lower()
    status = (getattr(h, "status", "") or "").strip().lower()
    fee_type = (getattr(h, "fee_type", "") or "").strip().lower()
    tags = " ".join([str(t) for t in (getattr(h, "tags", []) or [])]).lower()

    include = normalize_keywords(prefs.include_keywords)
    exclude = normalize_keywords(prefs.exclude_keywords)
    preferred_mode = (prefs.preferred_mode or "both").strip().lower()
    paid_filter = (getattr(prefs, "paid_filter", "any") or "any").strip().lower()
    status_filter = (getattr(prefs, "status_filter", "any") or "any").strip().lower()
    domain = (getattr(prefs, "domain", "") or "").strip().lower()
    category = (getattr(prefs, "category", "") or "").strip().lower()

    text_blob = f"{title}\n{desc}\n{mode}\n{status}\n{fee_type}\n{tags}".lower()

    if exclude and _contains_any(text_blob, exclude):
        return Stage1Result("fail", "Matched exclude keyword")

    # Paid/free filter
    if paid_filter in ("free", "paid"):
        if fee_type in ("", "unknown"):
            # infer from text
            if paid_filter == "free" and _contains_any(text_blob, ["paid", "fee", "charges", "₹", "rs", "inr"]):
                return Stage1Result("fail", "Looks paid/fee-based")
            if paid_filter == "paid" and _contains_any(text_blob, ["free", "no fee", "no fees"]):
                return Stage1Result("fail", "Looks free")
        else:
            if paid_filter != fee_type:
                return Stage1Result("fail", f"Fee type mismatch ({fee_type})")

    # Status filter
    if status_filter in ("live", "expired", "recent"):
        if not status or status == "unknown":
            return Stage1Result("ambiguous", "Status missing")
        if status_filter != status:
            return Stage1Result("fail", f"Status mismatch ({status})")

    # Mode must match if preference isn't both.
    if preferred_mode in ("online", "offline"):
        if mode in ("unknown", ""):
            return Stage1Result("ambiguous", "Mode missing")
        if preferred_mode != mode and not (preferred_mode == "online" and mode == "both") and not (
            preferred_mode == "offline" and mode == "both"
        ):
            return Stage1Result("fail", f"Mode mismatch ({mode})")

    # Domain/category (best-effort): if selected, require match in tags or text
    if domain and domain != "any":
        if domain not in text_blob:
            return Stage1Result("ambiguous", "Domain not detected in listing")
    if category and category != "any":
        if category not in text_blob:
            return Stage1Result("ambiguous", "Category not detected in listing")

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

    # If description is long and location/mode are unknown, send to LLM.
    if len(desc) > 350 and mode in ("unknown", ""):
        return Stage1Result("ambiguous", "Needs LLM classification (long description)")

    return Stage1Result("pass", "Matched stage-1 rules")

