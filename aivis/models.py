"""Plain data records shared across the pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional


@dataclass
class Citation:
    """A URL the engine used or cited while answering.

    kind is one of:
      cited      – explicitly attached to a span of the answer text
      retrieved  – returned by the engine's search step but not necessarily cited inline
      inline     – a bare URL found in the answer text by regex
    """
    url: str
    domain: str
    title: str = ""
    kind: str = "cited"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Answer:
    """One provider's response to one prompt."""
    provider_id: str
    model: str
    prompt_id: str
    prompt_text: str
    category: str
    repeat_index: int
    text: str = ""
    citations: list[Citation] = field(default_factory=list)
    latency_ms: int = 0
    error: Optional[str] = None
    raw: Optional[dict[str, Any]] = None  # provider-specific debugging info, kept small

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.text.strip())


@dataclass
class Mention:
    """A tracked brand appearing in an answer."""
    brand: str
    count: int
    first_index: int          # character offset of first occurrence
    position: int             # 1 = first tracked brand mentioned in this answer
    snippet: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Brand:
    name: str
    aliases: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    is_target: bool = False

    @property
    def all_names(self) -> list[str]:
        seen: list[str] = []
        for n in [self.name, *self.aliases]:
            if n and n not in seen:
                seen.append(n)
        return seen
