"""Any OpenAI-compatible chat-completions endpoint: xAI Grok, DeepSeek, OpenRouter, Groq,
Together, a local Ollama... Web search is whatever the endpoint does on its own; citations
are picked up if the response carries `citations`/`annotations`, otherwise from URLs in the text."""
from __future__ import annotations

from typing import Any

from ..models import Citation
from .base import Provider, ProviderError, make_citation


class OpenAICompatibleProvider(Provider):
    label = "OpenAI-compatible"
    supports_web_search = False
    sdk_package = "openai"

    def __init__(self, cfg, run):
        if not cfg.base_url:
            raise ProviderError(f"Provider '{cfg.id}' (openai_compatible) needs base_url")
        if not cfg.model:
            raise ProviderError(f"Provider '{cfg.id}' (openai_compatible) needs model")
        self.needs_api_key = bool(cfg.api_key_env)
        super().__init__(cfg, run)
        openai = self._import("openai", "openai")
        self.client = openai.OpenAI(api_key=cfg.api_key or "none", base_url=cfg.base_url,
                                    timeout=run.timeout_seconds, max_retries=0)
        self.label = cfg.options.get("label", cfg.id)
        self.extra_body: dict[str, Any] = dict(cfg.options.get("extra_body") or {})

    def _query(self, prompt: str):
        resp = self.client.chat.completions.create(model=self.model, messages=self._messages(prompt),
                                                   extra_body=self.extra_body or None)
        msg = resp.choices[0].message
        text = msg.content or ""
        citations: list[Citation] = []
        for url in getattr(resp, "citations", None) or []:
            c = make_citation(url, None, "cited")
            if c:
                citations.append(c)
        for ann in getattr(msg, "annotations", None) or []:
            uc = getattr(ann, "url_citation", None)
            c = make_citation(getattr(uc, "url", None), getattr(uc, "title", None), "cited") if uc else None
            if c:
                citations.append(c)
        return text, citations, {"id": getattr(resp, "id", None)}

    def _complete(self, prompt: str) -> str:
        resp = self.client.chat.completions.create(model=self.model, messages=[{"role": "user", "content": prompt}])
        return resp.choices[0].message.content or ""
