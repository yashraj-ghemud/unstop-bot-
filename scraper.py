from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

import requests
from bs4 import BeautifulSoup


@dataclass(frozen=True)
class Hackathon:
    title: str
    description: str
    mode: str
    location: str
    deadline: str
    url: str
    status: str  # live|expired|recent|unknown
    fee_type: str  # free|paid|any|unknown
    tags: List[str]


_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)


def _as_text(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    return str(v)


def _pick(d: Dict[str, Any], keys: Iterable[str]) -> Any:
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return None


def _parse_prize_inr(obj: Dict[str, Any]) -> int:
    raw = _pick(
        obj,
        [
            "prize",
            "prize_money",
            "prizeMoney",
            "total_prize",
            "totalPrize",
            "prize_amount",
        ],
    )
    s = _as_text(raw).lower()
    if not s:
        return 0

    # Try to extract a largest numeric amount.
    nums = re.findall(r"(\d[\d,]*)", s)
    if not nums:
        return 0
    vals = []
    for n in nums:
        try:
            vals.append(int(n.replace(",", "")))
        except ValueError:
            pass
    if not vals:
        return 0
    return max(vals)


def _normalize_mode(mode: str) -> str:
    m = mode.strip().lower()
    if not m:
        return "unknown"
    if "online" in m or "virtual" in m:
        return "online"
    if "offline" in m or "in-person" in m or "in person" in m:
        return "offline"
    if "hybrid" in m:
        return "both"
    return m


def _hackathon_from_obj(obj: Dict[str, Any]) -> Optional[Hackathon]:
    title = _as_text(_pick(obj, ["title", "name", "event_name", "opportunityTitle"])).strip()
    if not title:
        return None
    description = _as_text(_pick(obj, ["description", "desc", "about", "detail", "summary"]))
    url = _as_text(_pick(obj, ["url", "link", "permalink", "opportunityUrl", "public_url"])).strip()
    if url and url.startswith("/"):
        url = "https://unstop.com" + url

    mode = _normalize_mode(_as_text(_pick(obj, ["mode", "event_mode", "eventMode", "event_type"])))
    location = _as_text(_pick(obj, ["location", "city", "venue", "address", "event_city"]))
    deadline = _as_text(
        _pick(
            obj,
            [
                "deadline",
                "registration_deadline",
                "reg_deadline",
                "registrationDeadline",
                "end_date",
                "endDate",
            ],
        )
    )
    return Hackathon(
        title=title,
        description=description.strip(),
        mode=mode,
        location=location.strip(),
        deadline=deadline.strip(),
        url=url,
        status="unknown",
        fee_type="unknown",
        tags=[],
    )


def _extract_items_from_json(data: Any) -> List[Dict[str, Any]]:
    """
    Unstop responses have changed over time; this walks likely keys to find list items.
    """
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if not isinstance(data, dict):
        return []

    for key in ("data", "items", "results", "hackathons", "opportunities", "list"):
        v = data.get(key)
        if isinstance(v, list):
            return [x for x in v if isinstance(x, dict)]
        if isinstance(v, dict):
            for subkey in ("items", "results", "data", "list"):
                sv = v.get(subkey)
                if isinstance(sv, list):
                    return [x for x in sv if isinstance(x, dict)]

    return []


def fetch_open_hackathons(max_pages: int = 20, timeout_s: int = 30) -> List[Hackathon]:
    """
    Best-effort fetcher:
    - Primary: `https://api.unstop.com/hackathons/` (JSON-ish)
    - Fallback: try to locate embedded JSON in the HTML and parse it.
    """
    session = requests.Session()
    session.headers.update({"User-Agent": _UA, "Accept": "application/json, text/html;q=0.9,*/*;q=0.8"})

    out: List[Hackathon] = []

    for page in range(1, max_pages + 1):
        url = "https://api.unstop.com/hackathons/"
        r = session.get(url, params={"page": page}, timeout=timeout_s)
        content_type = (r.headers.get("content-type") or "").lower()

        data: Any = None
        if "application/json" in content_type:
            try:
                data = r.json()
            except Exception:
                data = None
        else:
            # Fallback: attempt to parse JSON from the body.
            body = r.text or ""
            # Common: <script id="__NEXT_DATA__" type="application/json">...</script>
            m = re.search(r'__NEXT_DATA__" type="application/json">(.+?)</script>', body, re.DOTALL)
            if m:
                try:
                    data = json.loads(m.group(1))
                except Exception:
                    data = None

        if data is None:
            # Fallback to HTML scraping from the API site (works even when JSON isn't available).
            return _fetch_from_api_site(session=session, timeout_s=timeout_s)

        items = _extract_items_from_json(data)
        if not items:
            break

        page_hacks = 0
        for obj in items:
            h = _hackathon_from_obj(obj)
            if h is None:
                continue
            # ensure we at least have a url
            if not h.url:
                continue
            out.append(h)
            page_hacks += 1

        if page_hacks == 0:
            break

    # De-dupe within a run
    dedup: Dict[str, Hackathon] = {}
    for h in out:
        dedup[h.url] = h
    return list(dedup.values())


def _infer_status(text: str) -> str:
    t = (text or "").lower()
    if "days left" in t or "day left" in t or "hours left" in t:
        return "live"
    if "expired" in t or "ended" in t or "closed" in t:
        return "expired"
    if "posted" in t:
        return "recent"
    return "unknown"


def _infer_fee_type(text: str) -> str:
    t = (text or "").lower()
    if "free" in t and "fee" not in t:
        return "free"
    if "paid" in t or "entry fee" in t or "registration fee" in t:
        return "paid"
    return "unknown"


def _fetch_from_api_site(session: requests.Session, timeout_s: int) -> List[Hackathon]:
    """
    Scrape `https://api.unstop.com/hackathons/` HTML listing.
    This endpoint is generally accessible even when `unstop.com` blocks scraping.
    """
    r = session.get("https://api.unstop.com/hackathons/", timeout=timeout_s)
    r.raise_for_status()
    soup = BeautifulSoup(r.text or "", "html.parser")

    hacks: dict[str, Hackathon] = {}

    # The page shows multiple hackathons with links to detail pages under /hackathons/<slug>
    for a in soup.find_all("a", href=True):
        href = str(a.get("href") or "")
        if not href:
            continue
        if href.startswith("/"):
            href = "https://api.unstop.com" + href
        if not href.startswith("https://api.unstop.com/hackathons/"):
            continue
        if href.rstrip("/").endswith("/hackathons"):
            continue

        title = (a.get_text(" ", strip=True) or "").strip()
        # If anchor has no text, try previous header
        if not title:
            prev_h = a.find_previous(["h1", "h2", "h3"])
            if prev_h:
                title = (prev_h.get_text(" ", strip=True) or "").strip()
        if not title:
            title = href.rsplit("/", 1)[-1].replace("-", " ").strip()

        context = ""
        parent = a.parent
        if parent:
            context = parent.get_text(" ", strip=True)
        status = _infer_status(context)
        fee_type = _infer_fee_type(context)

        hacks[href] = Hackathon(
            title=title,
            description="",
            mode="unknown",
            location="",
            deadline="",
            url=href.replace("https://api.unstop.com", "https://unstop.com"),
            status=status,
            fee_type=fee_type,
            tags=[],
        )

    return list(hacks.values())

