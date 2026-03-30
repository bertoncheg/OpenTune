"""
OpenTune Ollama Setup Manager
Handles local Ollama detection, model pulling, and availability checks.
"""
from __future__ import annotations

from rich.console import Console

console = Console()

_BASE_URL = "http://localhost:11434"


def is_ollama_running() -> bool:
    """GET http://localhost:11434 with 2s timeout. Return True if status 200."""
    try:
        import requests
        resp = requests.get(_BASE_URL, timeout=2)
        return resp.status_code == 200
    except Exception:
        return False


def list_local_models() -> list[str]:
    """GET /api/tags and return list of model name strings."""
    try:
        import requests
        resp = requests.get(f"{_BASE_URL}/api/tags", timeout=5)
        if resp.status_code != 200:
            return []
        data = resp.json()
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def pull_model(model_name: str) -> bool:
    """
    POST /api/pull with streaming response.
    Prints Rich progress while streaming. Returns True on success.
    """
    try:
        import requests
        import json

        console.print(f"[cyan]Pulling Ollama model: [bold]{model_name}[/bold]...[/cyan]")
        resp = requests.post(
            f"{_BASE_URL}/api/pull",
            json={"name": model_name},
            stream=True,
            timeout=300,
        )
        if resp.status_code != 200:
            console.print(f"[red]Pull request failed: HTTP {resp.status_code}[/red]")
            return False

        last_status = ""
        for line in resp.iter_lines():
            if not line:
                continue
            try:
                event = json.loads(line)
                status = event.get("status", "")
                if status != last_status:
                    console.print(f"  [dim]{status}[/dim]")
                    last_status = status
                if event.get("error"):
                    console.print(f"[red]Pull error: {event['error']}[/red]")
                    return False
            except Exception:
                pass

        console.print(f"[green]Model [bold]{model_name}[/bold] ready.[/green]")
        return True
    except Exception as exc:
        console.print(f"[red]Failed to pull model: {exc}[/red]")
        return False


def auto_setup(preferred_model: str = "llama3.2:3b") -> str | None:
    """
    Check if Ollama is running and the preferred model is available.
    Pull the model if needed. Returns model_name on success, None if Ollama not running.
    """
    try:
        if not is_ollama_running():
            return None

        local_models = list_local_models()
        # Check for exact match or name-prefix match (handles tag variants)
        base_name = preferred_model.split(":")[0]
        already_pulled = any(
            m == preferred_model or m.startswith(base_name + ":")
            for m in local_models
        )

        if already_pulled:
            return preferred_model

        console.print(
            f"[yellow]Model [bold]{preferred_model}[/bold] not found locally — pulling...[/yellow]"
        )
        success = pull_model(preferred_model)
        return preferred_model if success else None
    except Exception:
        return None
