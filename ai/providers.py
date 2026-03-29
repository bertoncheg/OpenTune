"""
OpenTune AI Providers
Abstraction layer for Anthropic, OpenAI, and Ollama (local free inference).
"""
from __future__ import annotations
from enum import Enum
from dataclasses import dataclass
from typing import Optional


class AIProvider(Enum):
    ANTHROPIC = "anthropic"
    OPENAI    = "openai"
    OLLAMA    = "ollama"


@dataclass
class ProviderConfig:
    provider: AIProvider
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    free: bool = False

    def display(self) -> str:
        if self.free:
            return f"LOCAL  {self.model} (free)"
        return f"{self.provider.value.upper()}  {self.model}"


PROVIDER_DEFAULTS = {
    AIProvider.ANTHROPIC: ProviderConfig(
        provider=AIProvider.ANTHROPIC,
        model="claude-sonnet-4-6",
    ),
    AIProvider.OPENAI: ProviderConfig(
        provider=AIProvider.OPENAI,
        model="gpt-4o-mini",
    ),
    AIProvider.OLLAMA: ProviderConfig(
        provider=AIProvider.OLLAMA,
        model="mistral",
        base_url="http://localhost:11434",
        free=True,
    ),
}
