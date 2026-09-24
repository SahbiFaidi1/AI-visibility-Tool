"""Provider interface. Every AI engine adapter implements `query` (with web search
when the engine supports it) and `complete` (plain completion, used for judging)."""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, Optional

from ..config import ProviderConfig, RunConfig
from ..models import Answer, Citation


class ProviderError(Exception):
    """Raised for configuration problems (missing key, missing SDK)."""


class Provider(ABC):
    #: human-friendly engine label, e.g. "ChatGPT"
    label: str = "Provider"
    #: whether this adapter can turn web search on
    supports_web_search: bool = False
    #: default model when config omits one
    default_model: Optional[str] = None
    #: python package required (for a friendly install hint)
    sdk_package: Optional[str] = None

    def __init__(self, cfg: ProviderConfig, run: RunConfig):
        self.cfg = cfg
        self.run = run
        self.model = cfg.model or self.default_model or ""
        self.web_search = bool(cfg.web_search and self.supports_web_search)
        if self.needs_api_key and not cfg.api_key:
            raise ProviderError(
                f"Provider '{cfg.id}' ({cfg.type}) needs an API key. "
                f"Set {cfg.key_env_name or 'api_key_env'} in .env")

    needs_api_key: bool = True

    # -- public API ---------------------------------------------------------
    def query(self, prompt: str) -> Answer:
        """Ask the engine like a user would. Returns text + citations."""
        started = time.perf_counter()
        text, citations, raw = self._query(prompt)
        latency = int((time.perf_counter() - started) * 1000)
        return Answer(provider_id=self.cfg.id, model=self.model, prompt_id="", prompt_text=prompt,
                      category="", repeat_index=0, text=text or "", citations=citations,
                      latency_ms=latency, raw=raw)

    def complete(self, prompt: str) -> str:
        """Plain completion without web search (for judging/sentiment)."""
        return self._complete(prompt)

    def ping(self) -> str:
        """Minimal live call used by `aivis check`. Returns a short status string."""
        text = self._complete("Reply with the single word OK.")
        return (text or "").strip()[:40] or "(empty reply)"

    # -- to implement -------------------------------------------------------
    @abstractmethod
    def _query(self, prompt: str) -> tuple[str, list[Citation], Optional[dict[str, Any]]]: ...

    @abstractmethod
    def _complete(self, prompt: str) -> str: ...

    # -- helpers ------------------------------------------------------------
    def _messages(self, prompt: str) -> list[dict[str, str]]:
        msgs: list[dict[str, str]] = []
        if self.run.system_prompt:
            msgs.append({"role": "system", "content": self.run.system_prompt})
        msgs.append({"role": "user", "content": prompt})
        return msgs

    @staticmethod
    def _import(module: str, package: str):
        try:
            return __import__(module, fromlist=["*"])
        except ImportError as e:
            raise ProviderError(f"Missing SDK: pip install {package}") from e


def make_citation(url: Optional[str], title: Optional[str] = None, kind: str = "cited",
                  domain: Optional[str] = None) -> Optional[Citation]:
    from ..analysis import domain_of
    if not url:
        return None
    dom = (domain or domain_of(url) or "").lower().removeprefix("www.")
    if not dom:
        return None
    return Citation(url=url, domain=dom, title=title or "", kind=kind)
