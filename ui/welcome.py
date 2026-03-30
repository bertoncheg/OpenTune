"""
Welcome Wizard ï¿½ First-run setup flow for OpenTune.

Screens:
  1 ï¿½ Identity / branding
  2 ï¿½ Ollama local AI setup (with install offer)
  3 ï¿½ Tier explanation
  4 ï¿½ Optional API key entry
  5 ï¿½ Ready to launch
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
from rich.columns import Columns
from rich import box

from config.settings_manager import (
    get_api_key, mark_first_run_complete, set_api_key, load_settings, save_settings,
)

console = Console()

# ---------------------------------------------------------------------------
# Logo & Branding
# ---------------------------------------------------------------------------

LOGO = r"""
     ï¿½ï¿½ï¿½ï¿½ï¿½ï¿½+ ï¿½ï¿½ï¿½ï¿½ï¿½ï¿½+ ï¿½ï¿½ï¿½ï¿½ï¿½ï¿½ï¿½+ï¿½ï¿½ï¿½+   ï¿½ï¿½+
    ï¿½ï¿½+---ï¿½ï¿½+ï¿½ï¿½+--ï¿½ï¿½+ï¿½ï¿½+----+ï¿½ï¿½ï¿½ï¿½+  ï¿½ï¿½ï¿½
    ï¿½ï¿½ï¿½   ï¿½ï¿½ï¿½ï¿½ï¿½ï¿½ï¿½ï¿½ï¿½++ï¿½ï¿½ï¿½ï¿½ï¿½+  ï¿½ï¿½+ï¿½ï¿½+ ï¿½ï¿½ï¿½
    ï¿½ï¿½ï¿½   ï¿½ï¿½ï¿½ï¿½ï¿½+---+ ï¿½ï¿½+--+  ï¿½ï¿½ï¿½+ï¿½ï¿½+ï¿½ï¿½ï¿½
    +ï¿½ï¿½ï¿½ï¿½ï¿½ï¿½++ï¿½ï¿½ï¿½     ï¿½ï¿½ï¿½ï¿½ï¿½ï¿½ï¿½+ï¿½ï¿½ï¿½ +ï¿½ï¿½ï¿½ï¿½ï¿½
     +-----+ +-+     +------++-+  +---+
              T U N E
"""

WRENCH_USB = r"""
        .--.          .------.
       /    \  .--.  | [::] |
      |  /\  \/    \ | [::] |
      | /  \ /  ()  \|______|
       \    X        |======|
        \  / \      /|  __  |
    .----\/   '----' | |  | |
   /  ___/            | |__| |
  |  /   \___         |______|
  | |       \  )-----'
   \ \   ___/ /
    '.\__/   /
       '----'
"""

TAGLINE = "Free. Open. Gets smarter with every fix."
MISSION = "The diagnostic database that belongs to everyone ï¿½ not to Snap-on."

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clear() -> None:
    console.clear()


def _pause(prompt: str = "  Press [bold cyan]Enter[/bold cyan] to continue...") -> None:
    console.print()
    console.print(prompt)
    input()


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
        installer_url = "https://ollama.ai/download/OllamaSetup.exe"
        installer_path = "OllamaSetup.exe"
        console.print("\n  [cyan]Downloading Ollama installer...[/cyan]")
        urllib.request.urlretrieve(installer_url, installer_path)
        console.print("  [cyan]Running installer...[/cyan]")
        subprocess.run([installer_path, "/S"], check=True)
        time.sleep(5)  # Give service time to start
        import os
        os.remove(installer_path)
        return True
    except Exception as e:
        console.print(f"  [red]Auto-install failed: {e}[/red]")
        return False


# ---------------------------------------------------------------------------
# Screen 1 ï¿½ Identity
# ---------------------------------------------------------------------------

def screen_identity() -> None:
    _clear()

    console.print()
    console.print(Text(LOGO, style="bold cyan"), justify="center")
    console.print(Text(WRENCH_USB, style="cyan"), justify="center")

    console.print(
        Panel(
            Text.assemble(
                Text(f"\n  {TAGLINE}\n", style="bold white"),
                Text(f"\n  {MISSION}\n", style="dim white"),
                Text(
                    "\n  -----------------------------------------------------\n",
                    style="dim cyan"
                ),
                Text(
                    "  Dealer tools cost $80,000. This costs nothing.\n"
                    "  Every repair you run trains the database. Forever.\n",
                    style="white"
                ),
            ),
            border_style="cyan",
            padding=(1, 4),
        )
    )

    console.print()
    console.print(Align.center("[bold cyan][ Let's get you set up ? ][/bold cyan]"))
    console.print()
    _pause()


# ---------------------------------------------------------------------------
# Screen 2 ï¿½ Ollama Setup (with install offer)
# ---------------------------------------------------------------------------

def screen_ollama_setup(ollama_model: str = "llama3.2:3b") -> bool:
    _clear()

    console.print(
        Panel(
            Text.assemble(
                Text("\n  ??  Local AI Engine Setup\n\n", style="bold white"),
                Text(
                    "  Ollama runs a private AI model on your machine.\n"
                    "  No internet. No API key. Completely free ï¿½ forever.\n",
                    style="dim white"
                ),
            ),
            title="[bold cyan]Step 1 of 4 ï¿½ Local AI[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )
    )
    console.print()

    try:
        from ai.ollama_setup import OllamaSetup, is_ollama_running

        # --- Offer to install if Ollama not found ---
        if not is_ollama_running():
            console.print(
                Panel(
                    Text.assemble(
                        Text("  Ollama not detected on this machine.\n\n", style="bold yellow"),
                        Text("  Here is how OpenTune AI works:\n\n", style="bold white"),

                        Text("  [ FREE ]  ", style="bold green"),
                        Text("Local model (Ollama)\n", style="bold white"),
                        Text(
                            "           Runs on your machine. No internet. No API key.\n"
                            "           Handles routine tasks: DTC lookups, code explanations,\n"
                            "           known procedures, basic chat. Fast. Private. Always free.\n\n",
                            style="dim white"
                        ),

                        Text("  [ CLOUD ] ", style="bold cyan"),
                        Text("API key model\n", style="bold white"),
                        Text(
                            "           Cloud AI for harder problems: first-principles\n"
                            "           engineering, edge cases, multi-system failures,\n"
                            "           vehicles with no prior community data.\n\n",
                            style="dim white"
                        ),

                        Text(
                            "  The logic:  simple task = free local model.\n"
                            "              complex task = smarter cloud model.\n"
                            "              OpenTune decides. You approve.\n\n",
                            style="white"
                        ),

                        Text(
                            "  Either way — every result, every procedure, every fix\n"
                            "  feeds the knowledge base. The database grows regardless\n"
                            "  of which AI powered it. That is the whole point.\n",
                            style="bold green"
                        ),
                    ),
                    title="[bold yellow]  AI Not Found[/bold yellow]",
                    border_style="yellow",
                    padding=(1, 3),
                )
            )
            console.print()
            console.print("  [bold cyan][I][/bold cyan] Install Ollama now (auto)    "
                          "[bold cyan][M][/bold cyan] I'll install manually    "
                          "[bold cyan][S][/bold cyan] Skip (use cloud key)")
            console.print()
            choice = Prompt.ask(
                "  Choose", choices=["I", "i", "M", "m", "S", "s"],
                default="I", show_choices=False
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

        # --- Ollama is running ï¿½ pull model if needed ---
        setup = OllamaSetup(model=ollama_model)
        console.print("  [cyan]Ollama detected. Checking model...[/cyan]")
        success = setup.auto_setup()

        if success:
            console.print()
            console.print(
                Panel(
                    Text.assemble(
                        Text("  ?  Local AI engine ready\n\n", style="bold green"),
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
                        Text("  ??  Model setup failed\n\n", style="bold yellow"),
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
        console.print(f"\n  [yellow]??  Ollama setup error: {e}[/yellow]")
        console.print("  [dim]You can still use OpenTune with a cloud API key.[/dim]")
        _save_ollama_disabled()
        _pause()
        return False


def _save_ollama_disabled() -> None:
    settings = load_settings()
    settings["ollama_enabled"] = False
    save_settings(settings)


# ---------------------------------------------------------------------------
# Screen 3 ï¿½ Tier Explanation
# ---------------------------------------------------------------------------

def screen_tiers() -> None:
    _clear()

    console.print(
        Panel(
            Text.assemble(
                Text("\n  How OpenTune AI works:\n\n", style="bold white"),
                Text("  ?  ", style="bold green"),
                Text("Free ï¿½ Local AI     ", style="bold green"),
                Text("Runs on your machine. Handles most jobs. No cost ever.\n", style="white"),
                Text("\n"),
                Text("  ?  ", style="bold yellow"),
                Text("Standard ($0.002)  ", style="bold yellow"),
                Text("Cloud AI for tougher diagnostics. Pennies per session.\n", style="white"),
                Text("\n"),
                Text("  ?  ", style="bold red"),
                Text("Deep ($0.08)       ", style="bold red"),
                Text("Full power. Complex edge cases. You decide when to use it.\n", style="white"),
                Text("\n\n"),
                Text(
                    "  OpenTune always tries Free first.\n"
                    "  It will ask before spending any of your credits.\n"
                    "  You are always in control.\n",
                    style="dim white"
                ),
            ),
            title="[bold cyan]Step 2 of 4 ï¿½ AI Tiers[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )
    )
    _pause()


# ---------------------------------------------------------------------------
# Screen 4 ï¿½ API Key (optional)
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
            title="[bold cyan]Step 3 of 4 ï¿½ API Key[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    console.print()
    console.print("  [bold cyan][A][/bold cyan] Add API Key    [bold cyan][S][/bold cyan] Skip ?")
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
                Text("  ?  API key saved (encrypted on this machine)", style="bold green"),
                border_style="green",
                padding=(0, 2),
            )
        )
        _pause()
        return key


# ---------------------------------------------------------------------------
# Screen 5 ï¿½ Ready
# ---------------------------------------------------------------------------

def screen_ready() -> None:
    _clear()

    console.print(Text(LOGO, style="bold green"), justify="center")
    console.print()
    console.print(
        Panel(
            Text.assemble(
                Text("\n  ?  You're in.\n\n", style="bold green"),
                Text(
                    "  OpenTune is ready to connect to your vehicle.\n"
                    "  Plug in your OBD2 adapter and let's find what's wrong.\n\n",
                    style="white"
                ),
                Text(
                    "  Every fix you run makes the database smarter.\n"
                    "  That's the whole point.\n",
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


