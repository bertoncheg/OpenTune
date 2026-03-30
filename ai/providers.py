"""
OpenTune AI Provider Registry

Maps API key prefixes to provider configuration for auto-detection.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ProviderConfig:
    name: str                    # e.g. "anthropic", "openai"
    litellm_prefix: str          # e.g. "anthropic/", "openai/"
    default_model: str           # full model string passed to litellm
    key_env_var: str             # env var name this provider expects
    base_url: str | None = None  # override base URL if needed


# ---------------------------------------------------------------------------
# Registry — ordered so more-specific prefixes are checked first
# ---------------------------------------------------------------------------

_PROVIDERS: list[tuple[str, ProviderConfig]] = [
    # Anthropic  — must come before generic "sk-" check
    (
        r"^sk-ant-",
        ProviderConfig(
            name="anthropic",
            litellm_prefix="anthropic/",
            default_model="anthropic/claude-haiku-3-5",
            key_env_var="ANTHROPIC_API_KEY",
        ),
    ),
    # OpenRouter — must come before generic "sk-" check
    (
        r"^sk-or-",
        ProviderConfig(
            name="openrouter",
            litellm_prefix="openrouter/",
            default_model="openrouter/auto",
            key_env_var="OPENROUTER_API_KEY",
            base_url="https://openrouter.ai/api/v1",
        ),
    ),
    # OpenAI
    (
        r"^sk-",
        ProviderConfig(
            name="openai",
            litellm_prefix="openai/",
            default_model="openai/gpt-4o-mini",
            key_env_var="OPENAI_API_KEY",
        ),
    ),
    # Google / Gemini
    (
        r"^AIza",
        ProviderConfig(
            name="gemini",
            litellm_prefix="gemini/",
            default_model="gemini/gemini-1.5-flash",
            key_env_var="GEMINI_API_KEY",
        ),
    ),
    # Groq
    (
        r"^gsk_",
        ProviderConfig(
            name="groq",
            litellm_prefix="groq/",
            default_model="groq/llama-3.1-8b-instant",
            key_env_var="GROQ_API_KEY",
        ),
    ),
]

_KNOWN_PREFIXES = ["sk-ant-", "sk-or-", "sk-", "AIza", "gsk_"]


def detect_provider(api_key: str) -> ProviderConfig:
    """
    Match *api_key* against known prefix patterns and return a ProviderConfig.

    Raises ValueError for unknown keys with a helpful message listing known prefixes.
    """
    for pattern, config in _PROVIDERS:
        if re.match(pattern, api_key):
            return config

    raise ValueError(
        f"Unknown API key format. Could not detect provider.\n"
        f"Known key prefixes: {', '.join(_KNOWN_PREFIXES)}\n"
        f"Set AI_PROVIDER explicitly to override auto-detection."
    )
