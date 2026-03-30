"""
OpenTune Key Resolver

Auto-detects the AI provider from an API key and returns a ready-to-use
completion callable backed by litellm (preferred) or the openai SDK (fallback).
"""
from __future__ import annotations

import os
from typing import Callable, Any

from ai.providers import ProviderConfig, detect_provider


def resolve_provider(api_key: str) -> ProviderConfig:
    """
    Inspect *api_key* and return the matching ProviderConfig.

    Raises ValueError if the key prefix is not recognised.
    """
    return detect_provider(api_key)


def get_litellm_client(
    api_key: str,
    model_override: str | None = None,
) -> tuple[ProviderConfig, Callable[..., Any]]:
    """
    Resolve the provider for *api_key* and return ``(provider_config, completion_fn)``.

    *completion_fn* has the same signature as ``litellm.completion`` / ``openai.chat.completions.create``:
        completion_fn(model, messages, *, system=None, max_tokens=1024, stream=False, **kwargs)

    Strategy:
      1. Try to import litellm — preferred because it handles all providers uniformly.
      2. Fall back to the openai SDK with base_url patching for OpenAI-compatible providers.
      3. Fall back to the anthropic SDK for Anthropic keys.
    """
    config = resolve_provider(api_key)
    model = model_override or config.default_model

    # ------------------------------------------------------------------
    # Attempt 1: litellm
    # ------------------------------------------------------------------
    try:
        import litellm  # type: ignore

        # Inject the key into the environment variable litellm expects
        os.environ[config.key_env_var] = api_key
        if config.base_url:
            os.environ["OPENROUTER_API_BASE"] = config.base_url  # litellm convention

        def _litellm_completion(
            messages: list[dict],
            *,
            system: str | None = None,
            max_tokens: int = 1024,
            stream: bool = False,
            **kwargs: Any,
        ) -> Any:
            full_messages = messages
            if system:
                full_messages = [{"role": "system", "content": system}] + messages
            return litellm.completion(
                model=model,
                messages=full_messages,
                max_tokens=max_tokens,
                stream=stream,
                **kwargs,
            )

        return config, _litellm_completion

    except ImportError:
        pass

    # ------------------------------------------------------------------
    # Attempt 2: anthropic SDK (for Anthropic keys)
    # ------------------------------------------------------------------
    if config.name == "anthropic":
        try:
            import anthropic  # type: ignore

            client = anthropic.Anthropic(api_key=api_key)
            # Strip "anthropic/" prefix for native SDK
            native_model = model.removeprefix("anthropic/")

            def _anthropic_completion(
                messages: list[dict],
                *,
                system: str | None = None,
                max_tokens: int = 1024,
                stream: bool = False,
                **kwargs: Any,
            ) -> Any:
                return client.messages.create(
                    model=native_model,
                    messages=messages,
                    system=system or "",
                    max_tokens=max_tokens,
                    stream=stream,
                    **kwargs,
                )

            return config, _anthropic_completion

        except ImportError:
            pass

    # ------------------------------------------------------------------
    # Attempt 3: openai SDK with base_url patching (OpenAI-compatible)
    # ------------------------------------------------------------------
    try:
        import openai  # type: ignore

        client_kwargs: dict[str, Any] = {"api_key": api_key}
        if config.base_url:
            client_kwargs["base_url"] = config.base_url

        client = openai.OpenAI(**client_kwargs)
        # Strip provider prefix for openai-compatible endpoints
        native_model = model.split("/", 1)[-1] if "/" in model else model

        def _openai_completion(
            messages: list[dict],
            *,
            system: str | None = None,
            max_tokens: int = 1024,
            stream: bool = False,
            **kwargs: Any,
        ) -> Any:
            full_messages = messages
            if system:
                full_messages = [{"role": "system", "content": system}] + messages
            return client.chat.completions.create(
                model=native_model,
                messages=full_messages,
                max_tokens=max_tokens,
                stream=stream,
                **kwargs,
            )

        return config, _openai_completion

    except ImportError:
        pass

    raise RuntimeError(
        f"No suitable SDK found for provider '{config.name}'. "
        "Install litellm (`pip install litellm`) or the provider's own SDK."
    )
