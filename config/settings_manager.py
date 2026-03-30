"""
Settings Manager — Read/write/encrypt config/settings.json.

API keys are encrypted with Fernet using a machine-derived key so they
are secure at rest but not portable between machines.
"""
from __future__ import annotations

import json
import os
import platform
import uuid
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Fernet encryption helpers
# ---------------------------------------------------------------------------

def _get_machine_id() -> bytes:
    """Return a stable machine identifier used as the encryption seed."""
    system = platform.system()
    mid = ""

    if system == "Windows":
        try:
            import subprocess
            result = subprocess.run(
                ["wmic", "csproduct", "get", "UUID"],
                capture_output=True, text=True, timeout=5
            )
            lines = result.stdout.strip().splitlines()
            if len(lines) >= 2:
                mid = lines[1].strip()
        except Exception:
            pass

    elif system == "Darwin":
        try:
            import subprocess
            result = subprocess.run(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.splitlines():
                if "IOPlatformUUID" in line:
                    mid = line.split('"')[-2]
                    break
        except Exception:
            pass

    if not mid:
        # Fallback: use hostname + username as a stable-ish seed
        mid = platform.node() + "-" + (os.environ.get("USERNAME") or os.environ.get("USER") or "user")

    return mid.encode("utf-8")


def _make_fernet():
    """Build a Fernet cipher keyed from this machine's ID."""
    try:
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        import base64

        machine_id = _get_machine_id()
        salt = b"opentune-v1-salt"  # fixed per-app salt
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100_000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(machine_id))
        return Fernet(key)
    except ImportError:
        return None


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string. Returns ciphertext or plaintext if crypto unavailable."""
    f = _make_fernet()
    if f is None:
        return plaintext
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a string. Returns original or ciphertext if crypto unavailable."""
    f = _make_fernet()
    if f is None:
        return ciphertext
    try:
        return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except Exception:
        return ciphertext


# ---------------------------------------------------------------------------
# Settings file path
# ---------------------------------------------------------------------------

_SETTINGS_DIR = Path(__file__).parent  # config/
_SETTINGS_FILE = _SETTINGS_DIR / "settings.json"

_DEFAULTS: dict[str, Any] = {
    "first_run_complete": False,
    "api_key": None,
    "api_key_provider": "anthropic",
    "ollama_enabled": True,
    "ollama_model": "llama3.2:3b",
    "preferred_port": None,
    "theme": "dark",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_settings() -> dict[str, Any]:
    """Load settings.json, returning defaults for any missing keys."""
    settings = dict(_DEFAULTS)
    if _SETTINGS_FILE.exists():
        try:
            data = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
            settings.update(data)
        except Exception:
            pass
    return settings


def save_settings(settings: dict[str, Any]) -> None:
    """Persist settings dict to settings.json."""
    _SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    _SETTINGS_FILE.write_text(
        json.dumps(settings, indent=2), encoding="utf-8"
    )


def get(key: str, default: Any = None) -> Any:
    """Get a single setting value."""
    return load_settings().get(key, default)


def set_value(key: str, value: Any) -> None:
    """Set a single setting value and persist."""
    settings = load_settings()
    settings[key] = value
    save_settings(settings)


def is_first_run() -> bool:
    """Return True if the wizard has not yet completed."""
    return not bool(get("first_run_complete", False))


def mark_first_run_complete() -> None:
    set_value("first_run_complete", True)


# ---------------------------------------------------------------------------
# API key helpers
# ---------------------------------------------------------------------------

def get_api_key() -> Optional[str]:
    """Return decrypted API key, or None if not set."""
    raw = get("api_key")
    if not raw:
        return None
    return decrypt_value(raw)


def set_api_key(plaintext_key: str, provider: str = "anthropic") -> None:
    """Encrypt and store API key."""
    settings = load_settings()
    settings["api_key"] = encrypt_value(plaintext_key)
    settings["api_key_provider"] = provider
    save_settings(settings)


def clear_api_key() -> None:
    settings = load_settings()
    settings["api_key"] = None
    settings["api_key_provider"] = "anthropic"
    save_settings(settings)


def reset_to_defaults() -> None:
    """Wipe settings back to factory defaults (re-triggers wizard)."""
    save_settings(dict(_DEFAULTS))
