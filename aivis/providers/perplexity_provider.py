"""Perplexity. Default: the Agent API (`responses.create`), which always searches the web.
Set `api: chat` to use the legacy Sonar chat-completions endpoint (model `sonar`)."""
from __future__ import annotations

from typing import Any

from ..models import Citation
from .base import Provider, make_citation


class PerplexityProvider(Provider):
    label = "Perplexity"
    supports_web_search = True
    default_model = None
    sdk_package = "perplexityai"

    def __init__(self, cfg, run):
        super().__init__(cfg, run)
        pplx = self._import("perplexity", "perplexityai")
        self.client = pplx.Perplexity(api_key=cfg.api_key, base_url=cfg.base_url or None,
                                      timeout=run.timeout_seconds, max_retries=0)
        self.api = str(cfg.options.get("api", "responses")).lower()
        self.preset = cfg.options.get("preset")
        if self.api == "chat" and not self.model:
            self.model = "sonar"
        if not self.model and not self.preset:
            self.preset = "low"

    # -- Agent / responses API -------------------------------------------------
    def _responses(self, prompt: str):
        kwargs: dict[str, Any] = {"input": prompt}
        if self.model:
            kwargs["model"] = self.model
        if self.preset:
            kwargs["preset"] = self.preset
        if self.run.system_prompt:
            kwargs["instructions"] = self.run.system_prompt
        resp = self.client.responses.create(**kwargs)
        text_parts: list[str] = []
        citations: list[Citation] = []
        for item in getattr(resp, "output", None) or []:
            itype = getattr(item, "type", "")
            if itype == "message":
                for part in getattr(item, "content", None) or []:
                    t = getattr(part, "text", None)
                    if t:
                        text_parts.append(t)
                    for ann in getattr(part, "annotations", None) or []:
                        c = make_citation(getattr(ann, "url", None), getattr(ann, "title", None), "cited")
                        if c:
                            citations.append(c)
            elif itype == "search_results":
                for r in getattr(item, "results", None) or []:
                    c = make_citation(getattr(r, "url", None), getattr(r, "title", None), "retrieved")
                    if c:
                        citations.append(c)
        text = "\n".join(text_parts) or (getattr(resp, "output_text", None) or "")
        return text, citations, {"id": getattr(resp, "id", None), "model": getattr(resp, "model", None)}

    # -- legacy chat completions ----------------------------------------------
    def _chat(self, prompt: str):
        resp = self.client.chat.completions.create(model=self.model, messages=self._messages(prompt))
        text = resp.choices[0].message.content or ""
        citations: list[Citation] = []
        for r in getattr(resp, "search_results", None) or []:
            c = make_citation(getattr(r, "url", None), getattr(r, "title", None), "retrieved")
            if c:
                citations.append(c)
        for url in getattr(resp, "citations", None) or []:
            c = make_citation(url, None, "cited")
            if c:
                citations.append(c)
        return text, citations, {"id": getattr(resp, "id", None)}

    def _query(self, prompt: str):
        return self._chat(prompt) if self.api == "chat" else self._responses(prompt)

    def _complete(self, prompt: str) -> str:
        text, _, _ = self._query(prompt)
        return text
