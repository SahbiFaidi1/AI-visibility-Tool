"""Anthropic Messages API with the web_search server tool."""
from __future__ import annotations

from typing import Any

from ..models import Citation
from .base import Provider, make_citation


class AnthropicProvider(Provider):
    label = "Claude"
    supports_web_search = True
    default_model = "claude-sonnet-5"
    sdk_package = "anthropic"

    def __init__(self, cfg, run):
        super().__init__(cfg, run)
        anthropic = self._import("anthropic", "anthropic")
        self.client = anthropic.Anthropic(api_key=cfg.api_key, base_url=cfg.base_url or None,
                                          timeout=run.timeout_seconds, max_retries=0)
        self.tool_version = cfg.options.get("tool_version", "web_search_20250305")
        self.max_uses = int(cfg.options.get("max_searches", 5))
        self.max_tokens = int(cfg.options.get("max_tokens", 2048))

    def _tools(self) -> list[dict[str, Any]]:
        if not self.web_search:
            return []
        tool: dict[str, Any] = {"type": self.tool_version, "name": "web_search", "max_uses": self.max_uses}
        if self.run.country:
            tool["user_location"] = {"type": "approximate", "country": self.run.country}
        return [tool]

    def _query(self, prompt: str):
        kwargs: dict[str, Any] = dict(model=self.model, max_tokens=self.max_tokens,
                                      messages=[{"role": "user", "content": prompt}])
        if self.run.system_prompt:
            kwargs["system"] = self.run.system_prompt
        tools = self._tools()
        if tools:
            kwargs["tools"] = tools
        resp = self.client.messages.create(**kwargs)

        text_parts: list[str] = []
        citations: list[Citation] = []
        for block in resp.content:
            btype = getattr(block, "type", "")
            if btype == "text":
                text_parts.append(block.text)
                for cit in getattr(block, "citations", None) or []:
                    if getattr(cit, "type", "") == "web_search_result_location":
                        c = make_citation(getattr(cit, "url", None), getattr(cit, "title", None), "cited")
                        if c:
                            citations.append(c)
            elif btype == "web_search_tool_result":
                content = getattr(block, "content", None)
                if isinstance(content, list):
                    for r in content:
                        if getattr(r, "type", "") == "web_search_result":
                            c = make_citation(getattr(r, "url", None), getattr(r, "title", None), "retrieved")
                            if c:
                                citations.append(c)
        return "".join(text_parts), citations, {"id": resp.id, "stop_reason": resp.stop_reason}

    def _complete(self, prompt: str) -> str:
        resp = self.client.messages.create(model=self.model, max_tokens=512,
                                           messages=[{"role": "user", "content": prompt}])
        return "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text")
