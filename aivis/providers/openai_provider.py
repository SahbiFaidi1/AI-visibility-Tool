"""OpenAI Responses API with the built-in web_search tool (this is what ChatGPT search does)."""
from __future__ import annotations

from typing import Any, Optional

from ..models import Citation
from .base import Provider, make_citation


class OpenAIProvider(Provider):
    label = "ChatGPT"
    supports_web_search = True
    default_model = "gpt-5.5"
    sdk_package = "openai"

    def __init__(self, cfg, run):
        super().__init__(cfg, run)
        openai = self._import("openai", "openai")
        self.client = openai.OpenAI(api_key=cfg.api_key, base_url=cfg.base_url or None,
                                    timeout=run.timeout_seconds, max_retries=0)

    def _tools(self) -> list[dict[str, Any]]:
        if not self.web_search:
            return []
        tool: dict[str, Any] = {"type": "web_search"}
        if self.run.country:
            tool["user_location"] = {"type": "approximate", "country": self.run.country}
        return [tool]

    def _query(self, prompt: str):
        kwargs: dict[str, Any] = dict(model=self.model, input=prompt)
        if self.run.system_prompt:
            kwargs["instructions"] = self.run.system_prompt
        tools = self._tools()
        if tools:
            kwargs["tools"] = tools
        resp = self.client.responses.create(**kwargs)
        text = getattr(resp, "output_text", "") or ""
        citations: list[Citation] = []
        for item in getattr(resp, "output", []) or []:
            if getattr(item, "type", "") != "message":
                continue
            for part in getattr(item, "content", []) or []:
                for ann in getattr(part, "annotations", []) or []:
                    if getattr(ann, "type", "") == "url_citation":
                        c = make_citation(getattr(ann, "url", None), getattr(ann, "title", None), "cited")
                        if c:
                            citations.append(c)
        return text, citations, {"id": getattr(resp, "id", None)}

    def _complete(self, prompt: str) -> str:
        resp = self.client.responses.create(model=self.model, input=prompt)
        return getattr(resp, "output_text", "") or ""
