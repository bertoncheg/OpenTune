"""
OpenTune Ollama Setup
Checks for local Ollama installation and available models.
Used when no cloud API key is present — free local inference.
"""
from __future__ import annotations
import subprocess
import urllib.request
import json
from typing import Optional


OLLAMA_BASE_URL = "http://localhost:11434"
PREFERRED_MODELS = ["mistral", "llama3", "llama3.1", "phi3", "gemma2"]


def is_ollama_running() -> bool:
    """Check if Ollama server is reachable."""
    try:
        with urllib.request.urlopen(f"{OLLAMA_BASE_URL}/api/tags", timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


def list_models() -> list[str]:
    """Return list of locally available Ollama models."""
    try:
        with urllib.request.urlopen(f"{OLLAMA_BASE_URL}/api/tags", timeout=2) as resp:
            data = json.loads(resp.read())
            return [m["name"].split(":")[0] for m in data.get("models", [])]
    except Exception:
        return []


def best_available_model() -> Optional[str]:
    """Return the best available model from preferred list, or first available."""
    available = list_models()
    for preferred in PREFERRED_MODELS:
        if preferred in available:
            return preferred
    return available[0] if available else None


def ollama_status() -> dict:
    """Return full status dict for display."""
    running = is_ollama_running()
    models = list_models() if running else []
    best = best_available_model() if running else None
    return {
        "running": running,
        "models": models,
        "best_model": best,
        "url": OLLAMA_BASE_URL,
    }


def check_and_report() -> str:
    """One-line status string for startup display."""
    status = ollama_status()
    if not status["running"]:
        return "Ollama not detected — install from ollama.com for free local AI"
    if not status["models"]:
        return "Ollama running but no models installed — run: ollama pull mistral"
    return f"Running FREE on local AI  ({status['best_model']})"
