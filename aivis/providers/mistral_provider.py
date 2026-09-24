"""Mistral via the Conversations API with the web_search connector (Le Chat-style answers).
Plain completions use chat.complete."""
from __future__ import annotations

from typing import Any

from ..models import Citation
from .base import Provider, make_citation


class MistralProvider(Provider):
    label = "Mistral"
    supports_web_search = True
    default_model = "mistral-medium-latest"
    sdk_package = "mistralai"

    def __init__(self, cfg, run):
        super().__init__(cfg, run)
        mod = self._import("mistralai.client", "mistralai")
        self.client = mod.Mistral(api_key=cfg.api_key, server_url=cfg.base_url or None,
                                  timeout_ms=run.timeout_seconds * 1000)
        self.search_tool = cfg.options.get("search_tool", "web_search")  # or web_search_premium

    def _query(self, prompt: str):
        if not self.web_search:
            return self._complete(prompt), [], None
        conv = self.client.beta.conversations if hasattr(self.client, "beta") else self.client.conversations
        kwargs: dict[str, Any] = dict(model=self.model, inputs=prompt, tools=[{"type": self.search_tool}], store=False)
        if self.run.system_prompt:
            kwargs["instructions"] = self.run.system_prompt
        resp = conv.start(**kwargs)
        text_parts: list[str] = []
        citations: list[Citation] = []
        for entry in getattr(resp, "outputs", None) or []:
            if getattr(entry, "type", "") != "message.output":
                continue
            content = getattr(entry, "content", None)
            if isinstance(content, str):
                text_parts.append(content)
                continue
            for chunk in content or []:
                ctype = getattr(chunk, "type", "")
                if ctype == "text":
                    text_parts.append(getattr(chunk, "text", "") or "")
                elif ctype == "tool_reference":
                    c = make_citation(getattr(chunk, "url", None), getattr(chunk, "title", None), "cited")
                    if c:
                        citations.append(c)
        return "".join(text_parts), citations, {"conversation_id": getattr(resp, "conversation_id", None)}

    def _complete(self, prompt: str) -> str:
        resp = self.client.chat.complete(model=self.model, messages=self._messages(prompt))
        content = resp.choices[0].message.content
        if isinstance(content, list):
            return "".join(getattr(c, "text", "") for c in content)
        return content or ""
