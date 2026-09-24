"""Offline provider that fabricates plausible answers. Deterministic per prompt so
repeated runs are comparable. Used for tests and for trying the dashboard without keys."""
from __future__ import annotations

import hashlib
import random
import re

from ..models import Citation
from .base import Provider

_OPENERS = [
    "Here are the brands that come up most often for that question:",
    "Based on recent reviews and owner surveys, the standouts are:",
    "Several manufacturers are worth a look:",
]
_PRAISE = ["is widely praised for reliability", "leads on technology", "offers strong value",
           "has an excellent dealer network", "sets the benchmark in this segment"]
_CRITIC = ["has had quality-control complaints recently", "is comparatively expensive to maintain"]


class MockProvider(Provider):
    label = "Mock"
    supports_web_search = True
    default_model = "mock-1"
    needs_api_key = False

    def __init__(self, cfg, run):
        super().__init__(cfg, run)
        self._brands = list(cfg.options.get("brands") or [])
        self._brand_domains = dict(cfg.options.get("brand_domains") or {})

    def set_brands(self, names: list[str], domains: dict[str, str]) -> None:
        self._brands = names
        self._brand_domains = domains

    def _rng(self, prompt: str) -> random.Random:
        seed = int(hashlib.sha256(f"{self.cfg.id}|{prompt}".encode()).hexdigest()[:12], 16)
        return random.Random(seed)

    def _query(self, prompt: str):
        rng = self._rng(prompt)
        brands = list(self._brands) or ["Alpha Motors", "Beta Cars", "Gamma Auto"]
        named = [b for b in brands if re.search(rf"(?<!\w){re.escape(b)}(?!\w)", prompt, re.I)]
        k = rng.randint(max(1, len(brands) // 3), max(1, min(len(brands), 5)))
        chosen = rng.sample(brands, k)
        for b in named:
            if b not in chosen:
                chosen.insert(0, b)
        lines = [rng.choice(_OPENERS), ""]
        cites: list[Citation] = []
        for i, b in enumerate(chosen, start=1):
            tone = rng.choice(_PRAISE) if rng.random() > 0.2 else rng.choice(_CRITIC)
            lines.append(f"{i}. **{b}** {tone}.")
            dom = self._brand_domains.get(b)
            if dom and rng.random() > 0.5:
                cites.append(Citation(url=f"https://{dom}/models", domain=dom, title=f"{b} official site", kind="cited"))
        for dom in rng.sample(["caranddriver.com", "edmunds.com", "topgear.com", "reddit.com", "consumerreports.org", "autoexpress.co.uk"], 2):
            cites.append(Citation(url=f"https://{dom}/best-{rng.randint(1, 99)}", domain=dom, title=dom, kind="retrieved"))
        lines += ["", "Ultimately the right choice depends on budget and priorities."]
        return "\n".join(lines), cites, {"mock": True}

    def _complete(self, prompt: str) -> str:
        if "JSON object mapping" in prompt:
            m = re.search(r"Brands to grade:\s*(.+)", prompt)
            names = [n.strip() for n in (m.group(1) if m else "").split(",") if n.strip()]
            rng = self._rng(prompt[:200])
            return "{" + ", ".join(f'"{n}": "{rng.choice(["positive", "positive", "neutral", "negative"])}"' for n in names) + "}"
        return "OK"
