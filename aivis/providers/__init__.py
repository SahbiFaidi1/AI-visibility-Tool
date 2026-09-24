"""Provider registry. Add a new engine by subclassing Provider and registering it here."""
from __future__ import annotations

from ..config import ProviderConfig, RunConfig
from .base import Provider, ProviderError

REGISTRY: dict[str, str] = {
    "openai": "aivis.providers.openai_provider:OpenAIProvider",
    "anthropic": "aivis.providers.anthropic_provider:AnthropicProvider",
    "gemini": "aivis.providers.gemini_provider:GeminiProvider",
    "perplexity": "aivis.providers.perplexity_provider:PerplexityProvider",
    "mistral": "aivis.providers.mistral_provider:MistralProvider",
    "openai_compatible": "aivis.providers.openai_compatible:OpenAICompatibleProvider",
    "mock": "aivis.providers.mock:MockProvider",
}


def provider_class(type_name: str) -> type[Provider]:
    path = REGISTRY.get(type_name.lower())
    if not path:
        raise ProviderError(f"Unknown provider type '{type_name}'. Known: {', '.join(sorted(REGISTRY))}")
    module_name, cls_name = path.split(":")
    module = __import__(module_name, fromlist=[cls_name])
    return getattr(module, cls_name)


def build_provider(cfg: ProviderConfig, run: RunConfig) -> Provider:
    return provider_class(cfg.type)(cfg, run)


__all__ = ["Provider", "ProviderError", "REGISTRY", "build_provider", "provider_class"]
