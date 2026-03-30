"""
Welcome Wizard - First-run setup flow for OpenTune.

Screens:
  1 - Identity / branding
  2 - Ollama local AI setup (with install offer)
  3 - AI Tier explanation
  4 - Optional API key entry
  5 - Ready to launch
"""
from __future__ import annotations

import re
import time
import subprocess
import platform
from typing import Optional

from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.text import Text
from rich import box

from config.settings_manager import (
    get_api_key, mark_first_run_complete, set_api_key, load_settings, save_settings,
)

console = Console()

# ---------------------------------------------------------------------------
# Logo & Branding
# ---------------------------------------------------------------------------

LOGO = r"""
  ___  ____  ___  _  _  ____  _  _  _  _  ____
 / __)( ___)(  _)( \( )(_  _)( )( )( \( )( ___)
( (__  )__)  ) _) )  (   )(   )()(  )  (  )__)
 \___)(____)(___)(_(\_) (__)  \__/ (_(\_)(____) 
"""

TAGLINE = "Free. Open. Gets smarter with every fix."
MISSION = "The diagnostic database that belongs to everyone."

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clear() -> None:
    console.clear()


def _pause(prompt: str = "  Press [bold cyan]Enter[/bold cyan] to continue...") -> None:
    console.print()
    console.print(prompt)
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        pass


def _validate_api_key(key: str) -> bool:
    key = key.strip()
    return bool(re.match(r"^sk-(ant-|)[a-zA-Z0-9\-_]{20,}$", key))


def _detect_key_provider(key: str) -> str:
    if key.startswith("sk-ant-"):
        return "anthropic"
    return "openai"


def _install_ollama_windows() -> bool:
    """Download and run Ollama installer silently on Windows."""
    try:
        import urllib.request
        import os
        installer_url = "https://ollama.ai/download/OllamaSetup.exe"
        installer_path = "OllamaSetup.exe"
        console.print("\n  [cyan]Downloading Ollama installer...[/cyan]")
        urllib.request.urlretrieve(installer_url, installer_path)
        console.print("  [cyan]Running installer...[/cyan]")
        subprocess.run([installer_path, "/S"], check=True)
        time.sleep(5)
        os.remove(installer_path)
        return True
    except Exception as e:
        console.print(f"  [red]Auto-install failed: {e}[/red]")
        return False


def _save_ollama_disabled() -> None:
    settings = load_settings()
    settings["ollama_enabled"] = False
    save_settings(settings)


# ---------------------------------------------------------------------------
# Screen 1 - Identity
# ---------------------------------------------------------------------------

def screen_identity() -> None:
    _clear()

    console.print()
    console.print(Text(LOGO, style="bold cyan"), justify="center")

    console.print(
        Panel(
            Text.assemble(
                Text(f"\n  {TAGLINE}\n", style="bold white"),
                Text(f"\n  {MISSION}\n", style="dim white"),
                Text(
                    "\n  -------------------------------------------------------\n",
                    style="dim cyan"
                ),
                Text(
                    "  The knowledge is free. The tool is free.\n"
                    "  Every repair you run trains the database. Forever.\n",
                    style="white"
                ),
            ),
            border_style="cyan",
            padding=(1, 4),
        )
    )

    console.print()
    console.print(Align.center("[bold cyan][ Let us get you set up ][/bold cyan]"))
    console.print()
    _pause()


# ---------------------------------------------------------------------------
# Screen 2 - Ollama Setup (with install offer)
# ---------------------------------------------------------------------------

def screen_ollama_setup(ollama_model: str = "llama3.2:3b") -> bool:
    _clear()

    console.print(
        Panel(
            Text.assemble(
                Text("\n  Local AI Engine Setup\n\n", style="bold white"),
                Text(
                    "  Ollama runs a private AI model on your machine.\n"
                    "  No internet. No API key. Completely free - forever.\n",
                    style="dim white"
                ),
            ),
            title="[bold cyan]Step 1 of 4 - Local AI[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )
    )
    console.print()

    try:
        from ai.ollama_setup import OllamaSetup, is_ollama_running

        if not is_ollama_running():
            console.print(
                Panel(
                    Text.assemble(
                        Text("  Ollama not detected on this machine.\n\n", style="bold yellow"),
                        Text("  How OpenTune AI works:\n\n", style="bold white"),

                        Text("  [ FREE ]  ", style="bold green"),
                        Text("Local model (Ollama)\n", style="bold white"),
                        Text(
                            "            Runs on your hardware. No internet. No API key.\n"
                            "            Handles routine tasks: DTC lookups, code explanations,\n"
                            "            known procedures, basic chat. Fast. Private. Always free.\n\n",
                            style="dim white"
                        ),

                        Text("  [ CLOUD ] ", style="bold cyan"),
                        Text("API key model\n", style="bold white"),
                        Text(
                            "            Cloud AI for harder problems: first-principles engineering,\n"
                            "            edge cases, multi-system failures, vehicles with no prior data.\n\n",
                            style="dim white"
                        ),

                        Text(
                            "  The logic:  simple task = free local model.\n"
                            "              complex task = smarter cloud model.\n"
                            "              OpenTune decides. You approve.\n\n",
                            style="white"
                        ),

                        Text(
                            "  Either way - every result, every procedure, every fix\n"
                            "  feeds the knowledge base. The database grows regardless\n"
                            "  of which AI powered it. That is the whole point.\n",
                            style="bold green"
                        ),
                    ),
                    title="[bold yellow]  AI Engine Not Found[/bold yellow]",
                    border_style="yellow",
                    padding=(1, 3),
                )
            )
            console.print()
            console.print(
                "  [bold cyan][I][/bold cyan] Install Ollama now (auto)    "
                "[bold cyan][M][/bold cyan] Manual install    "
                "[bold cyan][S][/bold cyan] Skip (use cloud key)"
            )
            console.print()
            choice = Prompt.ask(
                "  Choose", choices=["I", "i", "M", "m", "S", "s"],
                default="S", show_choices=False
            ).upper()

            if choice == "I":
                if platform.system() == "Windows":
                    ok = _install_ollama_windows()
                    if ok:
                        console.print("  [green]Ollama installed! Checking...[/green]")
                        time.sleep(3)
                    else:
                        console.print(
                            "\n  [yellow]Auto-install failed. Download manually:[/yellow]"
                            "\n  [bold]https://ollama.ai/download[/bold]"
                            "\n  Then relaunch OpenTune.\n"
                        )
                        _pause()
                        _save_ollama_disabled()
                        return False
                else:
                    console.print(
                        "\n  [yellow]Auto-install only supported on Windows right now.[/yellow]"
                        "\n  Download at: [bold]https://ollama.ai/download[/bold]"
                        "\n  After install, run: [bold]ollama pull llama3.2:3b[/bold]"
                        "\n  Then relaunch OpenTune.\n"
                    )
                    _pause()
                    _save_ollama_disabled()
                    return False

            elif choice == "M":
                console.print(
                    Panel(
                        Text.assemble(
                            Text("\n  Manual Install Instructions:\n\n", style="bold white"),
                            Text("  1. Download: ", style="dim"),
                            Text("https://ollama.ai/download\n", style="bold cyan"),
                            Text("  2. Install and run Ollama\n", style="dim"),
                            Text("  3. In a terminal: ", style="dim"),
                            Text("ollama pull llama3.2:3b\n", style="bold"),
                            Text("  4. Relaunch OpenTune\n", style="dim"),
                        ),
                        border_style="cyan",
                        padding=(1, 2),
                    )
                )
                _pause()
                _save_ollama_disabled()
                return False

            else:  # Skip
                console.print("\n  [dim]Skipped. You can enable local AI later from Settings.[/dim]")
                _pause()
                _save_ollama_disabled()
                return False

        # Ollama is running - pull model if needed
        setup = OllamaSetup(model=ollama_model)
        console.print("  [cyan]Ollama detected. Checking model...[/cyan]")
        success = setup.auto_setup()

        if success:
            console.print()
            console.print(
                Panel(
                    Text.assemble(
                        Text("  Local AI engine ready\n\n", style="bold green"),
                        Text(f"  Model: {ollama_model}\n", style="dim green"),
                        Text(
                            "  Runs on your computer. No internet required. Free forever.",
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
                        Text("  Model setup failed\n\n", style="bold yellow"),
                        Text(f"  {setup.error_message}\n\n", style="yellow"),
                        Text("  You can still use OpenTune with a cloud API key.", style="dim"),
                    ),
                    border_style="yellow",
                    padding=(1, 2),
                )
            )
            _save_ollama_disabled()

        _pause()
        return success

    except Exception as e:
        console.print(f"\n  [yellow]Ollama setup error: {e}[/yellow]")
        console.print("  [dim]You can still use OpenTune with a cloud API key.[/dim]")
        _save_ollama_disabled()
        _pause()
        return False


# ---------------------------------------------------------------------------
# Screen 3 - AI Tier Explanation
# ---------------------------------------------------------------------------

def screen_tiers() -> None:
    _clear()

    console.print(
        Panel(
            Text.assemble(
                Text("\n  How OpenTune chooses which AI to use:\n\n", style="bold white"),

                Text("  TIER 1  FREE     ", style="bold green"),
                Text("Local model (Ollama)\n", style="bold white"),
                Text(
                    "                   Runs on your hardware. No internet. No API key.\n"
                    "                   DTC lookups, code explanations, known procedures,\n"
                    "                   routine chat. Fast. Private. Always free.\n\n",
                    style="dim white"
                ),

                Text("  TIER 2  CLOUD    ", style="bold cyan"),
                Text("API key model\n", style="bold white"),
                Text(
                    "                   Harder problems. First-principles engineering.\n"
                    "                   Edge cases, rare failures, vehicles with no prior data.\n"
                    "                   You bring the key. You control the spend.\n\n",
                    style="dim white"
                ),

                Text("  TIER 3  DEEP     ", style="bold magenta"),
                Text("Full reasoning model\n", style="bold white"),
                Text(
                    "                   Maximum capability. Multi-system analysis.\n"
                    "                   Unknown failure modes. Complex wiring faults.\n"
                    "                   Only fires when you approve it.\n\n",
                    style="dim white"
                ),

                Text(
                    "  OpenTune starts at Tier 1 every time.\n"
                    "  It steps up only when the problem demands it, and only with your approval.\n\n",
                    style="white"
                ),

                Text(
                    "  The key insight:\n"
                    "  It does not matter which tier solves the problem.\n"
                    "  Every outcome - every procedure, every fix, every dead end -\n"
                    "  is written to the knowledge base. The database grows either way.\n"
                    "  That is how it gets smarter. Forever.\n",
                    style="bold green"
                ),
            ),
            title="[bold cyan]Step 2 of 4 - AI Tiers[/bold cyan]",
            border_style="cyan",
            padding=(1, 3),
        )
    )
    _pause()


# ---------------------------------------------------------------------------
# Screen 4 - API Key (optional)
# ---------------------------------------------------------------------------

def screen_api_key() -> Optional[str]:
    _clear()
    console.print(
        Panel(
            Text.assemble(
                Text("\n  API Key (optional)\n\n", style="bold white"),
                Text(
                    "  You can skip this and run entirely on free local AI.\n"
                    "  Add a key anytime later from Settings.\n",
                    style="dim"
                ),
            ),
            title="[bold cyan]Step 3 of 4 - API Key[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    console.print()
    console.print("  [bold cyan][A][/bold cyan] Add API Key    [bold cyan][S][/bold cyan] Skip")
    console.print()

    choice = Prompt.ask(
        "  Choose", choices=["A", "a", "S", "s"], default="S", show_choices=False
    ).upper()

    if choice != "A":
        console.print("\n  [dim]Skipped. You can add a key later from Settings.[/dim]")
        _pause()
        return None

    while True:
        console.print()
        console.print("  [dim]Paste your API key (sk-ant-... or sk-...):[/dim]")
        key = Prompt.ask("  API Key", password=True).strip()

        if not key:
            console.print("  [yellow]No key entered. Skipping.[/yellow]")
            _pause()
            return None

        if not _validate_api_key(key):
            console.print("  [red]Invalid format. Expected sk-ant-... or sk-...[/red]")
            if not Confirm.ask("  Try again?", default=True):
                _pause()
                return None
            continue

        set_api_key(key, _detect_key_provider(key))
        console.print()
        console.print(
            Panel(
                Text("  API key saved (encrypted on this machine)", style="bold green"),
                border_style="green",
                padding=(0, 2),
            )
        )
        _pause()
        return key


# ---------------------------------------------------------------------------
# Screen 5 - Ready
# ---------------------------------------------------------------------------

def screen_ready() -> None:
    _clear()

    console.print(Text(LOGO, style="bold green"), justify="center")
    console.print()
    console.print(
        Panel(
            Text.assemble(
                Text("\n  You are in.\n\n", style="bold green"),
                Text(
                    "  OpenTune is ready to connect to your vehicle.\n"
                    "  Plug in your OBD2 adapter and let us find what is wrong.\n\n",
                    style="white"
                ),
                Text(
                    "  Every fix you run makes the database smarter.\n"
                    "  That is the whole point.\n",
                    style="dim white"
                ),
            ),
            border_style="green",
            padding=(2, 4),
        )
    )
    console.print()
    console.print(Align.center("[bold green][ Launching OpenTune... ][/bold green]"))
    console.print()

    mark_first_run_complete()
    time.sleep(2)


# ---------------------------------------------------------------------------
# Main wizard entry point
# ---------------------------------------------------------------------------

def run_wizard(skip_ollama: bool = False) -> None:
    try:
        screen_identity()

        if not skip_ollama:
            settings = load_settings()
            model = settings.get("ollama_model", "llama3.2:3b")
            screen_ollama_setup(ollama_model=model)

        screen_tiers()
        screen_api_key()
        screen_ready()

    except KeyboardInterrupt:
        console.print("\n\n  [dim]Setup cancelled. You can re-run the wizard from Settings.[/dim]\n")
        mark_first_run_complete()
    except Exception as e:
        console.print(f"\n\n  [red]Wizard error: {e}[/red]")
        console.print("  [dim]Continuing to OpenTune...[/dim]\n")
        mark_first_run_complete()
