from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Set


@dataclass
class SeenState:
    seen_urls: Set[str]


def load_seen(path: str | Path) -> SeenState:
    p = Path(path)
    if not p.exists():
        return SeenState(seen_urls=set())
    data = json.loads(p.read_text(encoding="utf-8"))
    urls = data.get("seen_urls", [])
    if not isinstance(urls, list):
        urls = []
    return SeenState(seen_urls=set([u for u in urls if isinstance(u, str) and u.strip()]))


def save_seen(path: str | Path, state: SeenState) -> None:
    p = Path(path)
    p.write_text(
        json.dumps({"seen_urls": sorted(state.seen_urls)}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def clear_seen(path: str | Path) -> None:
    save_seen(path, SeenState(seen_urls=set()))

