from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List


@dataclass(frozen=True)
class Preferences:
    # preferred_mode: "online" | "offline" | "both"
    preferred_mode: str
    include_keywords: List[str]
    exclude_keywords: List[str]
    min_prize_inr: int
    city_must_include: str


PREFERENCES = Preferences(
    preferred_mode="both",
    include_keywords=[
        "hackathon",
        "hack",
        "ideathon",
        "innovation",
        "challenge",
        "build",
        "code",
    ],
    exclude_keywords=[
        "paid entry",
        "entry fee",
        "registration fee",
    ],
    min_prize_inr=0,
    city_must_include="Pune",
)


def normalize_keywords(words: Iterable[str]) -> list[str]:
    return [w.strip().lower() for w in words if w and w.strip()]

