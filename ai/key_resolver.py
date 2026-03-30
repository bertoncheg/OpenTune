"""
OpenTune Key Resolver
Determines which AI provider to use.
On first run (no provider configured), shows an interactive menu and saves the choice.
Priority if already configured: AI_PROVIDER env var > API key detection > prompt.
"""
from __future__ import annotations
import os
import dataclasses
from pathlib import Path
from typing import Optional
from ai.providers import AIProvider, ProviderConfig, PROVIDER_DEFAULTS

_ENV_PATH = Path(__file__).parent.parent / ".env"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve_provider() -> ProviderConfig:
    """Return a ProviderConfig.  Prompts user on first run if nothing is set."""
    # 1. Explicit AI_PROVIDER override in env
    provider_name = os.getenv("AI_PROVIDER", "").strip().lower()
    if provider_name:
        return _cfg_for_named_provider(provider_name)

    # 2. Legacy: detect from existing API keys (no prompt needed for existing installs)
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    openai_key    = os.getenv("OPENAI_API_KEY")

    if anthropic_key:
        cfg = dataclasses.replace(PROVIDER_DEFAULTS[AIProvider.ANTHROPIC], api_key=anthropic_key)
        return cfg

    if openai_key:
        cfg = dataclasses.replace(PROVIDER_DEFAULTS[AIProvider.OPENAI], api_key=openai_key)
        return cfg

    # 3. Nothing configured — first-run prompt
    return _prompt_provider_choice()


def get_api_key(provider: AIProvider) -> Optional[str]:
    mapping = {
        AIProvider.ANTHROPIC: "ANTHROPIC_API_KEY",
        AIProvider.OPENAI:    "OPENAI_API_KEY",
    }
    env_var = mapping.get(provider)
    return os.getenv(env_var) if env_var else None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _cfg_for_named_provider(name: str) -> ProviderConfig:
    """Build a ProviderConfig from a saved AI_PROVIDER name."""
    try:
        provider = AIProvider(name)
    except ValueError:
        provider = AIProvider.OLLAMA  # safe fallback

    cfg = dataclasses.replace(PROVIDER_DEFAULTS[provider])

    if provider == AIProvider.ANTHROPIC:
        cfg = dataclasses.replace(cfg, api_key=os.getenv("ANTHROPIC_API_KEY"))
    elif provider == AIProvider.OPENAI:
        cfg = dataclasses.replace(cfg, api_key=os.getenv("OPENAI_API_KEY"))

    return cfg


def _prompt_provider_choice() -> ProviderConfig:
    """Interactive first-run setup. Saves AI_PROVIDER (and API key) to .env."""
    print()
    print("=" * 52)
    print("  OpenTune — First Run: AI Provider Setup")
    print("=" * 52)
    print("  Which AI provider do you use?")
    print()
    print("  [1] Anthropic (Claude)")
    print("  [2] OpenAI (GPT-4o / GPT-4)")
    print("  [3] Ollama  (local, free — must already be running)")
    print("  [4] Skip / configure manually later")
    print()

    try:
        choice = input("  Enter choice [1-4]: ").strip()
    except (EOFError, KeyboardInterrupt):
        choice = "4"

    menu = {"1": AIProvider.ANTHROPIC, "2": AIProvider.OPENAI, "3": AIProvider.OLLAMA}

    if choice not in menu:
        print("\n  Skipping setup. Set AI_PROVIDER in .env when ready.\n")
        return dataclasses.replace(PROVIDER_DEFAULTS[AIProvider.OLLAMA])

    provider = menu[choice]
    cfg = dataclasses.replace(PROVIDER_DEFAULTS[provider])

    # Optionally collect API key for cloud providers
    if provider in (AIProvider.ANTHROPIC, AIProvider.OPENAI):
        key_env = "ANTHROPIC_API_KEY" if provider == AIProvider.ANTHROPIC else "OPENAI_API_KEY"
        existing = os.getenv(key_env, "")
        if not existing:
            try:
                api_key = input(f"  Enter your {key_env} (leave blank to set later): ").strip()
            except (EOFError, KeyboardInterrupt):
                api_key = ""
            if api_key:
                cfg = dataclasses.replace(cfg, api_key=api_key)
                _write_env_key(_ENV_PATH, key_env, api_key)
                os.environ[key_env] = api_key
        else:
            cfg = dataclasses.replace(cfg, api_key=existing)

    # Persist the provider choice
    _write_env_key(_ENV_PATH, "AI_PROVIDER", provider.value)
    os.environ["AI_PROVIDER"] = provider.value

    print(f"\n  Saved: {cfg.display()}")
    print("  You can change this anytime in .env\n")
    return cfg


def _write_env_key(env_path: Path, key: str, value: str) -> None:
    """Upsert a key=value line in the .env file."""
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    updated = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}=") or line.startswith(f"{key} ="):
            lines[i] = f"{key}={value}"
            updated = True
            break

    if not updated:
        lines.append(f"{key}={value}")

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
