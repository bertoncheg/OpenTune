"""
Tests for ai/key_resolver.py — prefix detection only, no real API calls.
"""
import pytest
import sys
import os

# Allow running from repo root without installation
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from ai.providers import detect_provider
from ai.key_resolver import resolve_provider


# ---------------------------------------------------------------------------
# detect_provider / resolve_provider — prefix matching
# ---------------------------------------------------------------------------

class TestProviderDetection:
    def test_anthropic_key(self):
        cfg = detect_provider("sk-ant-api03-abc123")
        assert cfg.name == "anthropic"
        assert cfg.litellm_prefix == "anthropic/"
        assert "haiku" in cfg.default_model

    def test_openrouter_key(self):
        cfg = detect_provider("sk-or-v1-abc123")
        assert cfg.name == "openrouter"
        assert cfg.base_url is not None

    def test_openai_key(self):
        cfg = detect_provider("sk-proj-abc123")
        assert cfg.name == "openai"
        assert cfg.litellm_prefix == "openai/"
        assert "gpt" in cfg.default_model

    def test_gemini_key(self):
        cfg = detect_provider("AIzaSyAbc123")
        assert cfg.name == "gemini"
        assert "gemini" in cfg.default_model

    def test_groq_key(self):
        cfg = detect_provider("gsk_abc123xyz")
        assert cfg.name == "groq"
        assert "llama" in cfg.default_model or "groq" in cfg.default_model

    def test_unknown_key_raises(self):
        with pytest.raises(ValueError, match="Unknown API key format"):
            detect_provider("totally-unknown-key-format")

    def test_unknown_key_lists_prefixes(self):
        with pytest.raises(ValueError) as exc_info:
            detect_provider("xyz-not-a-real-key")
        assert "sk-ant-" in str(exc_info.value)

    def test_resolve_provider_delegates(self):
        """resolve_provider should return the same result as detect_provider."""
        cfg1 = detect_provider("sk-ant-test")
        cfg2 = resolve_provider("sk-ant-test")
        assert cfg1.name == cfg2.name

    # Edge cases
    def test_anthropic_before_openai(self):
        """sk-ant- must not be matched by the generic sk- (OpenAI) rule."""
        cfg = detect_provider("sk-ant-something")
        assert cfg.name == "anthropic", "Anthropic prefix should win over generic sk-"

    def test_openrouter_before_openai(self):
        """sk-or- must not be matched by the generic sk- rule."""
        cfg = detect_provider("sk-or-something")
        assert cfg.name == "openrouter"

    def test_empty_key_raises(self):
        with pytest.raises(ValueError):
            detect_provider("")
