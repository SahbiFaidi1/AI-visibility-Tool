"""Google Gemini via google-genai with Google Search grounding."""
from __future__ import annotations

from typing import Any

from ..models import Citation
from .base import Provider, make_citation


class GeminiProvider(Provider):
    label = "Gemini"
    supports_web_search = True
    default_model = "gemini-2.5-flash"
    sdk_package = "google-genai"

    def __init__(self, cfg, run):
        super().__init__(cfg, run)
        genai = self._import("google.genai", "google-genai")
        self.types = self._import("google.genai.types", "google-genai")
        http_options = self.types.HttpOptions(timeout=run.timeout_seconds * 1000)
        self.client = genai.Client(api_key=cfg.api_key, http_options=http_options)

    def _config(self, search: bool):
        kwargs: dict[str, Any] = {}
        if self.run.system_prompt:
            kwargs["system_instruction"] = self.run.system_prompt
        if search and self.web_search:
            kwargs["tools"] = [self.types.Tool(google_search=self.types.GoogleSearch())]
        return self.types.GenerateContentConfig(**kwargs) if kwargs else None

    def _query(self, prompt: str):
        resp = self.client.models.generate_content(model=self.model, contents=prompt, config=self._config(True))
        text = getattr(resp, "text", None) or ""
        citations: list[Citation] = []
        queries: list[str] = []
        for cand in getattr(resp, "candidates", None) or []:
            gm = getattr(cand, "grounding_metadata", None)
            if not gm:
                continue
            queries.extend(getattr(gm, "web_search_queries", None) or [])
            for chunk in getattr(gm, "grounding_chunks", None) or []:
                web = getattr(chunk, "web", None)
                if not web:
                    continue
                # Gemini returns redirect URIs; `domain` carries the real site.
                c = make_citation(getattr(web, "uri", None), getattr(web, "title", None), "cited",
                                  domain=getattr(web, "domain", None))
                if c:
                    citations.append(c)
        return text, citations, {"search_queries": queries[:10]}

    def _complete(self, prompt: str) -> str:
        resp = self.client.models.generate_content(model=self.model, contents=prompt, config=self._config(False))
        return getattr(resp, "text", None) or ""
