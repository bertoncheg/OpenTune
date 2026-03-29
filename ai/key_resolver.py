"""
OpenTune Key Resolver
Determines which AI provider to use based on available API keys.
Priority: Anthropic > OpenAI > Ollama (local/free)
"""
from __future__ import annotations
import os
from typing import Optional
from ai.providers import AIProvider, ProviderConfig, PROVIDER_DEFAULTS


def resolve_provider() -> ProviderConfig:
    """Return the best available provider config based on env keys."""
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    openai_key    = os.getenv("OPENAI_API_KEY")

    if anthropic_key:
        cfg = PROVIDER_DEFAULTS[AIProvider.ANTHROPIC]
        cfg.api_key = anthropic_key
        return cfg

    if openai_key:
        cfg = PROVIDER_DEFAULTS[AIProvider.OPENAI]
        cfg.api_key = openai_key
        return cfg

    # Fall through to local Ollama
    return PROVIDER_DEFAULTS[AIProvider.OLLAMA]


def get_api_key(provider: AIProvider) -> Optional[str]:
    mapping = {
        AIProvider.ANTHROPIC: "ANTHROPIC_API_KEY",
        AIProvider.OPENAI:    "OPENAI_API_KEY",
    }
    env_var = mapping.get(provider)
    return os.getenv(env_var) if env_var else None
