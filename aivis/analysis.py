"""Deterministic text analysis: brand mentions, positions, citation classification."""
from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import urlparse

from .models import Answer, Brand, Citation, Mention

_URL_RE = re.compile(r"https?://[^\s<>\"'\)\]\}]+", re.IGNORECASE)


def domain_of(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return ""
    host = host.split("@")[-1].split(":")[0]
    return host.removeprefix("www.")


def _pattern(names: Iterable[str]) -> re.Pattern[str]:
    # Whole-word match, case-insensitive. Hyphens/spaces inside a name are
    # interchangeable so "Mercedes Benz" matches "Mercedes-Benz".
    parts = []
    for n in sorted(set(names), key=len, reverse=True):
        esc = re.escape(n.strip()).replace(r"\ ", r"[\s\-]+").replace(r"\-", r"[\s\-]+")
        parts.append(esc)
    body = "|".join(parts)
    return re.compile(rf"(?<![\w])(?:{body})(?![\w])", re.IGNORECASE)


class MentionDetector:
    def __init__(self, brands: list[Brand]):
        self.brands = brands
        self._patterns = {b.name: _pattern(b.all_names) for b in brands}

    def detect(self, text: str) -> list[Mention]:
        found: list[Mention] = []
        for brand in self.brands:
            matches = list(self._patterns[brand.name].finditer(text))
            if not matches:
                continue
            first = matches[0]
            start = max(0, first.start() - 80)
            end = min(len(text), first.end() + 80)
            snippet = text[start:end].replace("\n", " ").strip()
            found.append(Mention(brand=brand.name, count=len(matches), first_index=first.start(), position=0, snippet=snippet))
        found.sort(key=lambda m: m.first_index)
        for i, m in enumerate(found, start=1):
            m.position = i
        return found


def extract_inline_urls(text: str) -> list[Citation]:
    out: list[Citation] = []
    for raw in _URL_RE.findall(text or ""):
        url = raw.rstrip(".,;:!?")
        dom = domain_of(url)
        if dom:
            out.append(Citation(url=url, domain=dom, kind="inline"))
    return out


def dedupe_citations(citations: Iterable[Citation]) -> list[Citation]:
    """Keep one entry per URL; prefer the strongest kind (cited > retrieved > inline)."""
    rank = {"cited": 0, "retrieved": 1, "inline": 2}
    best: dict[str, Citation] = {}
    for c in citations:
        if not c.url:
            continue
        key = c.url.split("#")[0].rstrip("/")
        cur = best.get(key)
        if cur is None or rank.get(c.kind, 9) < rank.get(cur.kind, 9):
            best[key] = c
    return list(best.values())


def classify_domain(domain: str, brands: list[Brand]) -> str:
    """Return the brand name whose domains match, or 'other'."""
    d = (domain or "").lower().removeprefix("www.")
    for b in brands:
        for bd in b.domains:
            if d == bd or d.endswith("." + bd):
                return b.name
    return "other"


def enrich_answer(answer: Answer, brands: list[Brand]) -> dict:
    """Compute mentions and normalised citations for a stored answer."""
    detector = MentionDetector(brands)
    mentions = detector.detect(answer.text or "")
    cites = dedupe_citations([*answer.citations, *extract_inline_urls(answer.text or "")])
    return {
        "mentions": [m.to_dict() for m in mentions],
        "citations": [{**c.to_dict(), "owner": classify_domain(c.domain, brands)} for c in cites],
    }
