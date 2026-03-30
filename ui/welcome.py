"""
Welcome Wizard — First-run setup flow for OpenTune.

5 screens, all Rich-based:
  Screen 1 — Identity / branding
  Screen 2 — Ollama local AI setup (blocking progress bars)
  Screen 3 — Tier explanation (plain English)
  Screen 4 — Optional API key entry
  Screen 5 — Ready to launch

Writes first_run_complete=True to settings.json on finish.
"""
from __future__ import annotations

import re
import time
from typing import Optional

from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.rule import Rule
from rich.text import Text
from rich import print as rprint

from config.settings_manager import (
    get_api_key, mark_first_run_complete, set_api_key, load_settings, save_settings,
)

console = Console()

# ---------------------------------------------------------------------------
# Branding constants (verbatim from spec)
# ---------------------------------------------------------------------------

VALUE_PROP = (
    "Every fix you run makes OpenTune smarter. "
    "The diagnostic database that belongs to everyone."
)
TAGLINE = (
    "OpenTune learns from every repair. "
    "An open database, built by mechanics, for mechanics."
)

LOGO = r"""
   ___                _____
  / _ \ _ __  ___ _ |_   _|_  _ _ _  ___
 | (_) | '_ \/ -_) ' \| || || | ' \/ -_)
  \___/| .__/\___|_||_|_| \_,_|_||_\___|
       |_|
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clear() -> None:
    console.clear()


def _pause(prompt: str = "Press [bold cyan]Enter[/bold cyan] to continue...") -> None:
    console.print()
    console.print(f"  {prompt}")
    input()


def _validate_api_key(key: str) -> bool:
    """Accept Anthropic sk-ant-... or OpenAI sk-... format."""
    key = key.strip()
    return bool(re.match(r"^sk-(ant-|)[a-zA-Z0-9\-_]{20,}$", key))


def _detect_key_provider(key: str) -> str:
    if key.startswith("sk-ant-"):
        return "anthropic"
    return "openai"


# ---------------------------------------------------------------------------
# Screen 1 — Identity
# ---------------------------------------------------------------------------

def screen_identity() -> None:
    _clear()
    logo_text = Text(LOGO, style="bold cyan")
    tagline_text = Text(f"\n  {TAGLINE}\n", style="dim white")
    value_text = Text(f"\n  {VALUE_PROP}\n", style="white")

    body = Text.assemble(logo_text, tagline_text, value_text)

    console.print(
        Panel(
            body,
            title="[bold cyan]Welcome to OpenTune[/bold cyan]",
            border_style="cyan",
            padding=(1, 4),
        )
    )

    console.print()
    console.print(Align.center("[bold cyan][ Get Started → ][/bold cyan]"))
    console.print()
    _pause()


# ---------------------------------------------------------------------------
# Screen 2 — Ollama Setup
# ---------------------------------------------------------------------------

def screen_ollama_setup(ollama_model: str = "llama3.2:3b") -> bool:
    """Run Ollama setup with Rich progress bars. Returns True on success."""
    _clear()
    console.print(
        Panel(
            Text.assemble(
                Text("\n  Setting up your local AI engine...\n\n", style="bold white"),
                Text(
                    "  Runs on your computer. No internet required. Completely free.\n",
                    style="dim"
                ),
            ),
            title="[bold cyan]Step 1 of 4 — Local AI Setup[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )
    )
    console.print()

    try:
        from ai.ollama_setup import OllamaSetup
        setup = OllamaSetup(model=ollama_model)
        success = setup.auto_setup()

        if success:
            console.print()
            console.print(
                Panel(
                    Text.assemble(
                        Text("  ✅ Local AI engine ready\n\n", style="bold green"),
                        Text(
                            "  Runs on your computer. No internet required. Completely free.",
                            style="dim green"
                        ),
                    ),
                    border_style="green",
                    padding=(1, 2),
                )
            )
            settings = load_settings()
            settings["ollama_enabled"] = True
            settings["ollama_model"] = ollama_model
            save_settings(settings)
        else:
            console.print()
            console.print(
                Panel(
                    Text.assemble(
                        Text("  ⚠️  Local AI setup failed\n\n", style="bold yellow"),
                        Text(f"  {setup.error_message}\n\n", style="yellow"),
                        Text(
                            "  You can still use OpenTune with a cloud API key.",
                            style="dim"
                        ),
                    ),
                    border_style="yellow",
                    padding=(1, 2),
                )
            )
            settings = load_settings()
            settings["ollama_enabled"] = False
            save_settings(settings)

        _pause()
        return success

    except Exception as e:
        console.print(f"\n  [yellow]⚠️  Ollama setup error: {e}[/yellow]")
        console.print("  [dim]You can still use OpenTune with a cloud API key.[/dim]")
        settings = load_settings()
        settings["ollama_enabled"] = False
        save_settings(settings)
        _pause()
        return False


# ---------------------------------------------------------------------------
# Screen 3 — Tier Explanation
# ---------------------------------------------------------------------------

def screen_tiers() -> None:
    _clear()

    tier_content = Text.assemble(
        Text("\n  How OpenTune AI works:\n\n", style="bold white"),
        Text("  🟢 ", style="green"),
        Text("Free (Local)      ", style="bold green"),
        Text("— Handles most jobs. Runs on your machine.\n", style="white"),
        Text("\n"),
        Text("  🟡 ", style="yellow"),
        Text("Standard ($0.002) ", style="bold yellow"),
        Text("— Tougher diagnostics. Uses your API key.\n", style="white"),
        Text("\n"),
        Text("  🔴 ", style="red"),
        Text("Deep Analysis ($0.08) ", style="bold red"),
        Text("— Complex edge cases. Uses your API key.\n", style="white"),
        Text("\n\n"),
        Text(
            "  OpenTune always tries the free tier first.\n"
            "  If it's not confident, it'll ask before spending any credits.\n"
            "  You're always in control.\n",
            style="dim white"
        ),
    )

    console.print(
        Panel(
            tier_content,
            title="[bold cyan]Step 2 of 4 — How Pricing Works[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )
    )
    _pause()


# ---------------------------------------------------------------------------
# Screen 4 — API Key (optional)
# ---------------------------------------------------------------------------

def screen_api_key() -> Optional[str]:
    """
    Prompt the user to add an API key (optional).
    Returns the API key string if added, or None if skipped.
    """
    _clear()
    console.print(
        Panel(
            Text.assemble(
                Text("\n  Add an API key? (optional)\n\n", style="bold white"),
                Text(
                    "  You can skip this and run on free local AI.\n"
                    "  Add a key later anytime from Settings.\n",
                    style="dim"
                ),
            ),
            title="[bold cyan]Step 3 of 4 — API Key[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    console.print()
    console.print("  [bold cyan][A][/bold cyan] Add API Key    [bold cyan][S][/bold cyan] Skip for Now →")
    console.print()

    choice = Prompt.ask(
        "  Choose",
        choices=["A", "a", "S", "s"],
        default="S",
        show_choices=False,
    ).upper()

    if choice != "A":
        console.print("\n  [dim]Skipped. You can add a key later from Settings.[/dim]")
        _pause()
        return None

    # API key input loop
    while True:
        console.print()
        console.print(
            "  [dim]Paste your API key below (sk-ant-... or sk-...):[/dim]"
        )
        key = Prompt.ask("  API Key", password=True)
        key = key.strip()

        if not key:
            console.print("  [yellow]No key entered. Skipping.[/yellow]")
            _pause()
            return None

        if not _validate_api_key(key):
            console.print(
                "  [red]Invalid key format. Expected sk-ant-... or sk-...[/red]"
            )
            retry = Confirm.ask("  Try again?", default=True)
            if not retry:
                console.print("  [dim]Skipping for now.[/dim]")
                _pause()
                return None
            continue

        provider = _detect_key_provider(key)
        set_api_key(key, provider)

        console.print()
        console.print(
            Panel(
                Text("  ✅ API key saved (encrypted on this machine)", style="bold green"),
                border_style="green",
                padding=(0, 2),
            )
        )
        _pause()
        return key


# ---------------------------------------------------------------------------
# Screen 5 — Ready
# ---------------------------------------------------------------------------

def screen_ready() -> None:
    _clear()
    console.print(
        Panel(
            Text.assemble(
                Text("\n  ✅ OpenTune is ready.\n\n", style="bold green"),
                Text(
                    "  Your vehicle knows what's wrong.\n"
                    "  Let's find out how to fix it.\n",
                    style="white"
                ),
            ),
            title="[bold cyan]Step 4 of 4 — All Set[/bold cyan]",
            border_style="green",
            padding=(2, 4),
        )
    )
    console.print()
    console.print(Align.center("[bold green][ Launch → ][/bold green]"))
    console.print()

    mark_first_run_complete()

    time.sleep(1.5)


# ---------------------------------------------------------------------------
# Main wizard entry point
# ---------------------------------------------------------------------------

def run_wizard(skip_ollama: bool = False) -> None:
    """
    Run the complete 5-screen welcome wizard.
    Call this when first_run_complete is False.
    """
    try:
        # Screen 1 — Identity
        screen_identity()

        # Screen 2 — Ollama setup
        if not skip_ollama:
            settings = load_settings()
            model = settings.get("ollama_model", "llama3.2:3b")
            screen_ollama_setup(ollama_model=model)

        # Screen 3 — Tier explanation
        screen_tiers()

        # Screen 4 — API key
        screen_api_key()

        # Screen 5 — Ready
        screen_ready()

    except KeyboardInterrupt:
        console.print("\n\n  [dim]Setup cancelled. You can re-run the wizard from Settings.[/dim]\n")
        # Still mark first run complete so we don't trap the user
        mark_first_run_complete()
