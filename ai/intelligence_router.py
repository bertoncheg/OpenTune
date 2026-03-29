"""
OpenTune Intelligence Router
Routes AI calls to the correct provider (Anthropic / OpenAI / Ollama).
Single entry point for all inference — swap providers without touching engineer.py.
"""
from __future__ import annotations
from typing import Optional
from ai.providers import AIProvider, ProviderConfig
from ai.key_resolver import resolve_provider


def call(
    system_prompt: str,
    user_message: str,
    provider_cfg: Optional[ProviderConfig] = None,
    max_tokens: int = 4096,
    temperature: float = 0.2,
) -> str:
    """
    Route an inference call to the best available provider.
    Returns the response text string.
    """
    cfg = provider_cfg or resolve_provider()

    if cfg.provider == AIProvider.ANTHROPIC:
        return _call_anthropic(system_prompt, user_message, cfg, max_tokens, temperature)
    elif cfg.provider == AIProvider.OPENAI:
        return _call_openai(system_prompt, user_message, cfg, max_tokens, temperature)
    elif cfg.provider == AIProvider.OLLAMA:
        return _call_ollama(system_prompt, user_message, cfg, max_tokens)
    else:
        raise ValueError(f"Unknown provider: {cfg.provider}")


def _call_anthropic(system: str, user: str, cfg: ProviderConfig, max_tokens: int, temperature: float) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=cfg.api_key)
    msg = client.messages.create(
        model=cfg.model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return msg.content[0].text


def _call_openai(system: str, user: str, cfg: ProviderConfig, max_tokens: int, temperature: float) -> str:
    import openai
    client = openai.OpenAI(api_key=cfg.api_key)
    resp = client.chat.completions.create(
        model=cfg.model,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content


def _call_ollama(system: str, user: str, cfg: ProviderConfig, max_tokens: int) -> str:
    import urllib.request, json
    payload = json.dumps({
        "model": cfg.model,
        "prompt": f"{system}\n\n{user}",
        "stream": False,
        "options": {"num_predict": max_tokens},
    }).encode()
    req = urllib.request.Request(
        f"{cfg.base_url}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
        return data.get("response", "")
