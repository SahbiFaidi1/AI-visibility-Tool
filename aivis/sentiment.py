"""LLM-judged sentiment for each tracked brand mentioned in an answer."""
from __future__ import annotations

import json
import re
from typing import Optional

from .providers.base import Provider

_JUDGE_PROMPT = """You are grading how an AI assistant's answer portrays specific brands.

Answer to grade:
\"\"\"
{answer}
\"\"\"

Brands to grade: {brands}

For each brand, decide whether the answer's portrayal of that brand is "positive", "neutral" or "negative".
- positive: recommended, praised, listed as a top/best choice, or described favourably
- neutral: merely listed or described factually without judgement
- negative: criticised, warned against, or described unfavourably

Reply with ONLY a JSON object mapping each brand name exactly as given to one of the three labels, e.g.
{{"BrandA": "positive", "BrandB": "neutral"}}"""

VALID = {"positive", "neutral", "negative"}


def judge_sentiment(judge: Provider, answer_text: str, brands: list[str]) -> dict[str, str]:
    if not brands or not answer_text.strip():
        return {}
    prompt = _JUDGE_PROMPT.format(answer=answer_text[:6000], brands=", ".join(brands))
    raw = judge.complete(prompt)
    return parse_labels(raw, brands)


def parse_labels(raw: Optional[str], brands: list[str]) -> dict[str, str]:
    if not raw:
        return {}
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return {}
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}
    out: dict[str, str] = {}
    lower = {b.lower(): b for b in brands}
    for k, v in data.items():
        b = lower.get(str(k).strip().lower())
        label = str(v).strip().lower()
        if b and label in VALID:
            out[b] = label
    return out


def sentiment_score(labels: list[str]) -> Optional[float]:
    """0–100: all positive = 100, all neutral = 50, all negative = 0 (Peec-style)."""
    labels = [l for l in labels if l in VALID]
    if not labels:
        return None
    pos = sum(1 for l in labels if l == "positive")
    neu = sum(1 for l in labels if l == "neutral")
    return round(100 * (pos + 0.5 * neu) / len(labels), 1)
