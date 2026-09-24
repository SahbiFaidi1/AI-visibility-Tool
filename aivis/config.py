"""Load and validate config.yaml plus .env."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml
from dotenv import load_dotenv

from .models import Brand


DEFAULT_KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "perplexity": "PERPLEXITY_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "openai_compatible": None,
    "mock": None,
}


class ConfigError(Exception):
    pass


@dataclass
class Prompt:
    id: str
    text: str
    category: str = "discovery"


@dataclass
class ProviderConfig:
    id: str
    type: str
    model: Optional[str] = None
    enabled: bool = True
    web_search: bool = True
    api_key_env: Optional[str] = None
    base_url: Optional[str] = None
    options: dict[str, Any] = field(default_factory=dict)  # anything else, passed to the adapter

    @property
    def api_key(self) -> Optional[str]:
        env = self.api_key_env or DEFAULT_KEY_ENV.get(self.type)
        return os.environ.get(env) if env else None

    @property
    def key_env_name(self) -> Optional[str]:
        return self.api_key_env or DEFAULT_KEY_ENV.get(self.type)


@dataclass
class RunConfig:
    repeats: int = 1
    concurrency: int = 4
    per_provider_concurrency: int = 2
    timeout_seconds: int = 120
    retries: int = 2
    system_prompt: Optional[str] = None
    country: Optional[str] = None


@dataclass
class SentimentConfig:
    enabled: bool = True
    provider: Optional[str] = None


@dataclass
class Config:
    brand: Brand
    competitors: list[Brand]
    prompts: list[Prompt]
    providers: list[ProviderConfig]
    run: RunConfig
    sentiment: SentimentConfig
    db_path: Path
    source_path: Optional[Path] = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def brands(self) -> list[Brand]:
        return [self.brand, *self.competitors]

    @property
    def enabled_providers(self) -> list[ProviderConfig]:
        return [p for p in self.providers if p.enabled]

    def provider(self, provider_id: str) -> Optional[ProviderConfig]:
        return next((p for p in self.providers if p.id == provider_id), None)


def _as_list(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [v]
    return [str(x) for x in v]


def _brand(d: Any, is_target: bool = False) -> Brand:
    if isinstance(d, str):
        return Brand(name=d, is_target=is_target)
    if not isinstance(d, dict) or not d.get("name"):
        raise ConfigError(f"Brand entries need a name: {d!r}")
    return Brand(
        name=str(d["name"]),
        aliases=_as_list(d.get("aliases")),
        domains=[x.lower().removeprefix("www.") for x in _as_list(d.get("domains"))],
        is_target=is_target,
    )


def _prompts(items: Any) -> list[Prompt]:
    out: list[Prompt] = []
    if not items:
        raise ConfigError("config needs at least one prompt")
    for i, item in enumerate(items, start=1):
        if isinstance(item, str):
            out.append(Prompt(id=f"p{i:03d}", text=item.strip()))
        elif isinstance(item, dict) and item.get("text"):
            out.append(Prompt(id=str(item.get("id") or f"p{i:03d}"), text=str(item["text"]).strip(),
                              category=str(item.get("category") or "discovery").lower()))
        else:
            raise ConfigError(f"Prompt #{i} must be a string or have a text field")
    return out


def _providers(items: Any) -> list[ProviderConfig]:
    if not items:
        raise ConfigError("config needs at least one provider")
    known = {"id", "type", "model", "enabled", "web_search", "api_key_env", "base_url"}
    out: list[ProviderConfig] = []
    for item in items:
        if not isinstance(item, dict) or not item.get("id") or not item.get("type"):
            raise ConfigError(f"Provider entries need id and type: {item!r}")
        out.append(ProviderConfig(
            id=str(item["id"]),
            type=str(item["type"]).lower(),
            model=item.get("model"),
            enabled=bool(item.get("enabled", True)),
            web_search=bool(item.get("web_search", True)),
            api_key_env=item.get("api_key_env"),
            base_url=item.get("base_url"),
            options={k: v for k, v in item.items() if k not in known},
        ))
    ids = [p.id for p in out]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ConfigError(f"Duplicate provider ids: {sorted(dupes)}")
    return out


def load_config(path: str | Path = "config.yaml", env_path: str | Path | None = None) -> Config:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}. Run `aivis init` to create one.")
    load_dotenv(env_path or path.parent / ".env")
    load_dotenv()  # also the cwd .env, without overriding

    with path.open() as f:
        raw = yaml.safe_load(f) or {}

    brand = _brand(raw.get("brand"), is_target=True)
    competitors = [_brand(c) for c in (raw.get("competitors") or [])]
    names = [b.name.lower() for b in [brand, *competitors]]
    if len(set(names)) != len(names):
        raise ConfigError("Brand and competitor names must be unique")

    run_raw = raw.get("run") or {}
    run = RunConfig(
        repeats=max(1, int(run_raw.get("repeats", 1))),
        concurrency=max(1, int(run_raw.get("concurrency", 4))),
        per_provider_concurrency=max(1, int(run_raw.get("per_provider_concurrency", 2))),
        timeout_seconds=int(run_raw.get("timeout_seconds", 120)),
        retries=max(0, int(run_raw.get("retries", 2))),
        system_prompt=run_raw.get("system_prompt") or None,
        country=run_raw.get("country") or None,
    )
    sent_raw = raw.get("sentiment") or {}
    sentiment = SentimentConfig(enabled=bool(sent_raw.get("enabled", True)), provider=sent_raw.get("provider") or None)

    storage = raw.get("storage") or {}
    db_path = Path(storage.get("db") or "data/aivis.db")
    if not db_path.is_absolute():
        db_path = (path.parent / db_path).resolve()

    return Config(
        brand=brand,
        competitors=competitors,
        prompts=_prompts(raw.get("prompts")),
        providers=_providers(raw.get("providers")),
        run=run,
        sentiment=sentiment,
        db_path=db_path,
        source_path=path.resolve(),
        raw=raw,
    )
