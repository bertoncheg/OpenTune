"""
OpenTune v0.1.0
Open Diagnostics. Infinite Solutions.

Entry point — terminal UI, connection flow, chat loop, session logging.
"""
from __future__ import annotations

import colorama
colorama.init()

import argparse
import sys
import time
from typing import Optional, TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich.columns import Columns
from rich.rule import Rule
from rich.live import Live
from rich.spinner import Spinner
from rich import box
import questionary
from questionary import Style as QStyle

from pathlib import Path

from config import OPENTUNE_VERSION, ANTHROPIC_API_KEY, CLAUDE_MODEL, SESSION_LOG_DIR
from core.connection import OBDConnection, ConnectionMode, DTC, LiveData
from core.vehicle_researcher import VehicleResearcher
from core.scanner import ECUScanner, LiveMonitor, ScanResult
from core.session_logger import SessionLogger
from core.component_test import ComponentTester, COMPONENT_TESTS
from core.vehicle_profiles import VehicleProfileManager
from core.knowledge_engine import KnowledgeEngine
from core.live_scan import LiveProcessScanner
from ai.engineer import ProcedureEngineer, EngineeredProcedure, ProcedureStep, ProblemUnderstanding
from ai.monitor import AIMonitor
from core.quips import quip

console = Console()

# ---------------------------------------------------------------------------
# Arrow-key menu style & choices
# ---------------------------------------------------------------------------

# Detect interactive terminal — questionary needs a real console
INTERACTIVE_TTY = hasattr(sys.stdin, 'isatty') and sys.stdin.isatty()

QSTYLE = QStyle([
    ('pointer', 'fg:cyan bold'),
    ('selected', 'fg:white bold'),
    ('highlighted', 'fg:white'),
])

MENU_CHOICES = [
    questionary.Choice('  DTC Scan',           '1'),
    questionary.Choice('  Live Process Scan',  '2'),
    questionary.Choice('  DTC History',        '3'),
    questionary.Choice('  Freeze Frame',       '4'),
    questionary.Choice('  Readiness Monitors', '5'),
    questionary.Choice('  Component Test',     '6'),
    questionary.Choice('  Procedure History',  '7'),
    questionary.Choice('  Vehicle Profiles',   '8'),
    questionary.Choice('  Export Report',      '9'),
    questionary.Choice('  Knowledge Base',     'K'),
    questionary.Choice('  Chat with AI',       '0'),
    questionary.Choice('  Quit',               'Q'),
]

MENU_TEXT = (
    "\n"
    "   [bold white][1][/bold white]  DTC Scan\n"
    "   [bold white][2][/bold white]  Live Process Scan\n"
    "   [bold white][3][/bold white]  DTC History\n"
    "   [bold white][4][/bold white]  Freeze Frame\n"
    "   [bold white][5][/bold white]  Readiness Monitors\n"
    "   [bold white][6][/bold white]  Component Test\n"
    "   [bold white][7][/bold white]  Procedure History\n"
    "   [bold white][8][/bold white]  Vehicle Profiles\n"
    "   [bold white][9][/bold white]  Export Report\n"
    "   [bold cyan][K][/bold cyan]  Knowledge Base\n"
    "   [bold cyan][0][/bold cyan]  Chat with AI\n"
    "   [bold red][Q][/bold red]  Quit\n"
)

# ---------------------------------------------------------------------------
# ASCII Art & Branding
# ---------------------------------------------------------------------------

OPENTUNE_ASCII = r"""
 ██████╗ ██████╗ ███████╗███╗   ██╗████████╗██╗   ██╗███╗   ██╗███████╗
██╔═══██╗██╔══██╗██╔════╝████╗  ██║╚══██╔══╝██║   ██║████╗  ██║██╔════╝
██║   ██║██████╔╝█████╗  ██╔██╗ ██║   ██║   ██║   ██║██╔██╗ ██║█████╗
██║   ██║██╔═══╝ ██╔══╝  ██║╚██╗██║   ██║   ██║   ██║██║╚██╗██║██╔══╝
╚██████╔╝██║     ███████╗██║ ╚████║   ██║   ╚██████╔╝██║ ╚████║███████╗
 ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝ ╚═╝  ╚═══╝╚══════╝"""

TAGLINE = "Open Diagnostics. Infinite Solutions."


def render_launch_screen(mode: ConnectionMode, vehicle_display: str = "—", vin: str = "—") -> None:
    console.clear()

    # ASCII art with cyan/blue gradient
    art_lines = OPENTUNE_ASCII.split("\n")
    colors = ["bold cyan", "bold cyan", "cyan", "cyan", "blue", "bold blue", "bold blue"]
    art_text = Text()
    for i, line in enumerate(art_lines):
        color = colors[min(i, len(colors) - 1)]
        art_text.append(line + "\n", style=color)

    console.print()
    console.print(art_text, justify="center")
    console.print()

    tagline = Text(TAGLINE, style="bold white", justify="center")
    console.print(tagline, justify="center")
    console.print()

    # Info bar
    mode_label = Text()
    mode_label.append("  MODE  ", style="bold black on cyan" if mode == ConnectionMode.SIM else "bold black on green")
    mode_label.append(f"  {mode.value.upper()}  ", style="bold white")

    version_text = Text(f"  v{OPENTUNE_VERSION}  ", style="dim white")
    vehicle_text = Text(f"  {vehicle_display}  ", style="white")
    vin_text = Text(f"  VIN: {vin}  ", style="dim cyan")

    api_status = Text()
    if ANTHROPIC_API_KEY:
        api_status.append("  AI ENGINE  ", style="bold black on bright_cyan")
        api_status.append("  ONLINE  ", style="bold green")
    else:
        api_status.append("  AI ENGINE  ", style="bold black on yellow")
        api_status.append("  SCAN ONLY  ", style="bold yellow")

    console.print(Columns([mode_label, version_text, vehicle_text, vin_text, api_status], padding=(0, 1)), justify="center")
    console.print()
    console.print(Rule(style="dim cyan"))
    console.print()


# ---------------------------------------------------------------------------
# DTC display
# ---------------------------------------------------------------------------

def render_dtc_table(dtcs: list[DTC]) -> None:
    if not dtcs:
        console.print(Panel("[dim]No active DTCs detected[/dim]", title="[green]ECU SCAN[/green]", border_style="green"))
        return

    table = Table(
        title="Active Diagnostic Trouble Codes",
        box=box.SIMPLE_HEAVY,
        border_style="cyan",
        header_style="bold cyan",
        show_lines=False,
    )
    table.add_column("CODE", style="bold yellow", width=10)
    table.add_column("DESCRIPTION", style="white")
    table.add_column("ECU", style="cyan", width=10)
    table.add_column("SEVERITY", width=12)

    severity_styles = {
        "critical": "bold red",
        "warning": "bold yellow",
        "info": "dim white",
    }

    for dtc in dtcs:
        sev_text = Text(dtc.severity.upper(), style=severity_styles.get(dtc.severity, "white"))
        table.add_row(dtc.code, dtc.description, dtc.ecu, sev_text)

    console.print(table)


# ---------------------------------------------------------------------------
# Live data display
# ---------------------------------------------------------------------------

def render_live_data_panel(data: LiveData) -> None:
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("PID", style="dim cyan", width=24)
    table.add_column("VALUE", style="white")

    snap = data.snapshot()
    pid_labels = {
        "rpm": "Engine RPM",
        "coolant_temp": "Coolant Temp",
        "intake_air_temp": "Intake Air Temp",
        "throttle_pos": "Throttle Position",
        "engine_load": "Engine Load",
        "maf": "Mass Airflow (MAF)",
        "map": "Manifold Pressure",
        "vehicle_speed": "Vehicle Speed",
        "fuel_trim_short_b1": "STFT Bank 1",
        "fuel_trim_long_b1": "LTFT Bank 1",
        "o2_b1s1": "O2 Sensor B1S1",
        "battery_voltage": "Battery Voltage",
    }
    units = {
        "rpm": "RPM", "coolant_temp": "°C", "intake_air_temp": "°C",
        "throttle_pos": "%", "engine_load": "%", "maf": "g/s",
        "map": "kPa", "vehicle_speed": "km/h", "fuel_trim_short_b1": "%",
        "fuel_trim_long_b1": "%", "o2_b1s1": "V", "battery_voltage": "V",
    }
    for pid, label in pid_labels.items():
        val = snap.get(pid)
        if val is not None:
            unit = units.get(pid, "")
            table.add_row(label, f"{val:.2f} {unit}")

    console.print(Panel(table, title="[cyan]LIVE DATA[/cyan]", border_style="dim cyan"))


# ---------------------------------------------------------------------------
# Scan display
# ---------------------------------------------------------------------------

def render_scan_result(result: ScanResult) -> None:
    console.print()
    console.print(Rule("[bold cyan]ECU SCAN COMPLETE[/bold cyan]"))
    console.print()

    # ECU map
    ecu_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    ecu_table.add_column("ECU", style="cyan", width=10)
    ecu_table.add_column("STATUS", width=14)

    for ecu, status in result.ecu_map.items():
        style = "green" if status == "OK" else ("dim" if status == "UNKNOWN" else "dim red")
        ecu_table.add_row(ecu, Text(status, style=style))

    console.print(
        Panel(ecu_table, title=f"[cyan]ECU MAP — {result.vehicle_display}[/cyan]", border_style="cyan")
    )

    render_dtc_table(result.dtcs)
    render_live_data_panel(result.live_snapshot)

    console.print(f"[dim]Scan completed in {result.duration_s:.2f}s  •  VIN: {result.vin}[/dim]")
    quip('dtc_scan')
    console.print()


# ---------------------------------------------------------------------------
# Procedure display & execution
# ---------------------------------------------------------------------------

def render_procedure(proc: EngineeredProcedure) -> None:
    console.print()
    badge = "[bold cyan]ENGINEERED[/bold cyan]" if proc.engineered else "[bold blue]KNOWN PATTERN[/bold blue]"
    conf_color = "green" if proc.confidence >= 0.8 else "yellow" if proc.confidence >= 0.6 else "red"
    conf_text = f"[{conf_color}]{proc.confidence:.0%}[/{conf_color}]"

    console.print(Panel(
        f"[bold white]{proc.title}[/bold white]\n\n"
        f"[dim]Confidence:[/dim] {conf_text}    [dim]Est. time:[/dim] [white]{proc.estimated_time}[/white]    {badge}",
        border_style="cyan",
        title="[bold cyan]PROCEDURE[/bold cyan]",
    ))

    if proc.reasoning:
        console.print(Panel(
            f"[dim]{proc.reasoning}[/dim]",
            title="[dim]Reasoning[/dim]",
            border_style="dim",
        ))

    if proc.safety_notes:
        for note in proc.safety_notes:
            console.print(f"[bold yellow]  ⚠  {note}[/bold yellow]")
        console.print()

    console.print(f"[bold cyan]Steps ({len(proc.steps)}):[/bold cyan]")
    console.print()
    for step in proc.steps:
        console.print(f"  [cyan]{step.step_number:>2}.[/cyan] [white]{step.description}[/white]")
        if step.expected_result:
            console.print(f"      [dim]→ Expected: {step.expected_result}[/dim]")
    console.print()


def execute_procedure(
    proc: EngineeredProcedure,
    conn: OBDConnection,
    live_monitor: LiveMonitor,
) -> list[dict]:
    """Walk through procedure steps, execute what we can, prompt mechanic for manual steps."""
    executed_steps: list[dict] = []

    for step in proc.steps:
        console.print()
        console.print(Rule(f"[cyan]Step {step.step_number}[/cyan]"))
        console.print(f"  [white]{step.description}[/white]")

        step_record: dict = {
            "step": step.step_number,
            "description": step.description,
            "action_type": step.action_type,
            "status": "pending",
            "result": "",
        }

        if step.action_type == "instruct_mechanic":
            instruction = step.action_data.get("instruction", step.description)
            console.print(f"\n  [bold yellow]ACTION REQUIRED:[/bold yellow] {instruction}\n")
            resp = Prompt.ask("  [dim]Press ENTER when done, or type 'skip' to skip[/dim]", default="")
            step_record["status"] = "skip" if resp.lower() == "skip" else "ok"
            step_record["result"] = resp or "Completed by mechanic"

        elif step.action_type == "read_pid":
            pid = step.action_data.get("pid", "all")
            data = live_monitor.get_current_data()
            if data:
                snap = data.snapshot()
                if pid == "all":
                    result_str = f"Snapshot captured: RPM={snap.get('rpm', 0):.0f}, Coolant={snap.get('coolant_temp', 0):.1f}°C"
                else:
                    val = snap.get(pid, "N/A")
                    result_str = f"{pid} = {val}"
                console.print(f"  [green]READ:[/green] {result_str}")
                step_record["status"] = "ok"
                step_record["result"] = result_str
            else:
                console.print("  [dim]No live data available[/dim]")
                step_record["status"] = "skip"

        elif step.action_type == "send_uds":
            service = step.action_data.get("service", "0x00")
            console.print(f"  [cyan]UDS:[/cyan] Sending {service}")
            try:
                req = bytes([int(x, 16) for x in step.action_data.get("data", "00").split()])
                resp = conn.send_uds(req)
                result_str = resp.hex() if resp else "No response"
                console.print(f"  [green]RESPONSE:[/green] {result_str}")
                step_record["status"] = "ok"
                step_record["result"] = result_str
            except Exception as e:
                console.print(f"  [red]ERROR:[/red] {e}")
                step_record["status"] = "fail"
                step_record["result"] = str(e)

        elif step.action_type == "verify":
            pid = step.action_data.get("pid", "")
            target = step.action_data.get("value", 0)
            operator = step.action_data.get("operator", ">")
            data = live_monitor.get_current_data()
            if data:
                snap = data.snapshot()
                actual = snap.get(pid, 0)
                ops = {">": actual > target, "<": actual < target, "==": actual == target, ">=": actual >= target, "<=": actual <= target}
                passed = ops.get(operator, False)
                symbol = "[green]PASS[/green]" if passed else "[yellow]FAIL[/yellow]"
                console.print(f"  {symbol} {pid} = {actual:.2f} (expected {operator} {target})")
                step_record["status"] = "ok" if passed else "fail"
                step_record["result"] = f"{pid}={actual:.2f} expected {operator} {target}"
            else:
                step_record["status"] = "skip"

        elif step.action_type == "wait":
            secs = step.action_data.get("seconds", 3)
            reason = step.action_data.get("reason", "stabilizing")
            console.print(f"  [dim]Waiting {secs}s — {reason}...[/dim]")
            for i in range(int(secs)):
                time.sleep(1)
                console.print(f"  [dim]  {i+1}/{secs}[/dim]", end="\r")
            console.print()
            step_record["status"] = "ok"
            step_record["result"] = f"Waited {secs}s"

        else:
            console.print(f"  [dim]Unknown action type: {step.action_type}[/dim]")
            step_record["status"] = "skip"

        if step.expected_result:
            console.print(f"  [dim]Expected: {step.expected_result}[/dim]")

        executed_steps.append(step_record)

    return executed_steps


# ---------------------------------------------------------------------------
# Outcome capture
# ---------------------------------------------------------------------------

def capture_outcome() -> tuple[str, str]:
    console.print()
    console.print(Rule("[cyan]OUTCOME[/cyan]"))
    console.print()
    outcome = Prompt.ask(
        "  [bold white]Did this resolve the issue?[/bold white]",
        choices=["fixed", "not_fixed", "unknown"],
        default="unknown",
    )
    notes = Prompt.ask("  [dim]Notes (optional)[/dim]", default="")
    return outcome, notes


# ---------------------------------------------------------------------------
# Alert display
# ---------------------------------------------------------------------------

def display_alerts(alerts: list) -> None:
    for alert in alerts:
        if hasattr(alert, "raw"):
            # EnrichedAlert
            raw = alert.raw
            urgency_style = {
                "immediate": "bold red",
                "soon": "bold yellow",
                "monitor": "dim yellow",
            }.get(alert.urgency, "yellow")
            console.print(
                f"\n[{urgency_style}]  ⚡ ANOMALY [{alert.urgency.upper()}][/{urgency_style}] "
                f"[white]{raw.pid_name.upper()}:[/white] {alert.interpretation}"
            )
            if alert.likely_causes:
                console.print(f"  [dim]Possible causes: {', '.join(alert.likely_causes[:2])}[/dim]")
            console.print(f"  [dim]→ {alert.suggested_action}[/dim]")
        else:
            # Raw AnomalyAlert
            style = "bold red" if alert.severity == "critical" else "bold yellow"
            console.print(f"\n  [{style}]⚡ {alert.message}[/{style}]")


# ---------------------------------------------------------------------------
# Plan summary (conversational — shown before confirmation)
# ---------------------------------------------------------------------------

def render_plan_summary(proc: EngineeredProcedure) -> None:
    """Show a brief, conversational plan — not the full procedure panel."""
    conf_color = "green" if proc.confidence >= 0.8 else "yellow" if proc.confidence >= 0.6 else "red"

    console.print(f"[bold white]Plan:[/bold white]  [dim]({proc.title})[/dim]")
    console.print()
    for step in proc.steps:
        console.print(f"  [cyan]{step.step_number}.[/cyan] {step.description}")
    console.print()
    if proc.estimated_time:
        console.print(f"  [dim]Estimated time: {proc.estimated_time}[/dim]  "
                      f"[dim]Confidence: [{conf_color}]{proc.confidence:.0%}[/{conf_color}][/dim]")
    if proc.safety_notes:
        for note in proc.safety_notes:
            console.print(f"  [bold yellow]  ⚠  {note}[/bold yellow]")
    console.print()


# ---------------------------------------------------------------------------
# Feature 2: DTC History
# ---------------------------------------------------------------------------

def feature_dtc_history(scanner: ECUScanner) -> None:
    with console.status("[cyan]Reading DTC history...[/cyan]", spinner="dots"):
        result = scanner.scan_dtc_history()

    console.print()
    console.print(Rule("[bold cyan]DTC HISTORY[/bold cyan]"))

    mil_style = "bold red" if result.mil_on else "bold green"
    mil_label = "ON" if result.mil_on else "OFF"
    console.print(f"  MIL: [{mil_style}]{mil_label}[/{mil_style}]   "
                  f"Confirmed count: [bold white]{result.confirmed_count}[/bold white]")
    console.print()

    sections = [
        ("ACTIVE", result.active, "red"),
        ("PENDING", result.pending, "yellow"),
        ("PERMANENT", result.permanent, "magenta"),
    ]
    for label, dtcs, color in sections:
        if dtcs:
            table = Table(
                title=f"{label} DTCs",
                box=box.SIMPLE_HEAVY,
                border_style=color,
                header_style=f"bold {color}",
                show_lines=False,
            )
            table.add_column("CODE", style="bold yellow", width=10)
            table.add_column("DESCRIPTION", style="white")
            table.add_column("ECU", style="cyan", width=10)
            table.add_column("SEV", width=10)
            sev_styles = {"critical": "bold red", "warning": "bold yellow", "info": "dim white"}
            for dtc in dtcs:
                table.add_row(dtc.code, dtc.description, dtc.ecu,
                              Text(dtc.severity.upper(), style=sev_styles.get(dtc.severity, "white")))
            console.print(table)
        else:
            console.print(f"  [dim]{label}: none[/dim]")
        console.print()

    try:
        Prompt.ask("[dim]Press ENTER to return to menu[/dim]", default="")
    except (KeyboardInterrupt, EOFError):
        pass


# ---------------------------------------------------------------------------
# Feature 3: Freeze Frame
# ---------------------------------------------------------------------------

def feature_freeze_frame(scanner: ECUScanner, active_dtcs: list[DTC]) -> None:
    if not active_dtcs:
        console.print("[dim]No active DTCs — no freeze frames available.[/dim]")
        try:
            Prompt.ask("[dim]Press ENTER to return[/dim]", default="")
        except (KeyboardInterrupt, EOFError):
            pass
        return

    console.print()
    console.print(Rule("[bold cyan]FREEZE FRAME DATA[/bold cyan]"))
    console.print("[dim]Snapshot of sensor values captured when each DTC triggered.[/dim]")
    console.print()

    for i, dtc in enumerate(active_dtcs):
        console.print(f"  [bold cyan]{i + 1}.[/bold cyan] {dtc.code} — {dtc.description[:60]}")
    console.print(f"  [bold cyan]{len(active_dtcs) + 1}.[/bold cyan] [dim]Back to menu[/dim]")
    console.print()

    try:
        choice = Prompt.ask("[bold white]Select DTC[/bold white]", default=str(len(active_dtcs) + 1))
        idx = int(choice.strip()) - 1
        if idx < 0 or idx >= len(active_dtcs):
            return
    except (KeyboardInterrupt, EOFError, ValueError):
        return

    dtc = active_dtcs[idx]
    console.print()
    with console.status(f"[cyan]Reading freeze frame for {dtc.code}...[/cyan]", spinner="dots"):
        ff = scanner.read_freeze_frame(dtc.code)

    table = Table(
        title=f"Snapshot when {dtc.code} triggered",
        box=box.SIMPLE_HEAVY,
        border_style="cyan",
        header_style="bold cyan",
        show_lines=False,
    )
    table.add_column("SENSOR", style="dim cyan", width=26)
    table.add_column("VALUE AT FAULT", style="bold white")

    pid_labels = {
        "rpm": ("Engine RPM", "RPM"),
        "vehicle_speed": ("Vehicle Speed", "km/h"),
        "coolant_temp": ("Coolant Temp", "°C"),
        "engine_load": ("Engine Load", "%"),
        "fuel_trim_short_b1": ("Short Fuel Trim B1", "%"),
        "throttle_pos": ("Throttle Position", "%"),
        "maf": ("Mass Airflow (MAF)", "g/s"),
        "map": ("Manifold Pressure", "kPa"),
    }
    for field, (label, unit) in pid_labels.items():
        val = getattr(ff, field, None)
        if val is not None:
            table.add_row(label, f"{val:.2f} {unit}")

    console.print(table)
    console.print()
    try:
        Prompt.ask("[dim]Press ENTER to return[/dim]", default="")
    except (KeyboardInterrupt, EOFError):
        pass


# ---------------------------------------------------------------------------
# Feature 4: Readiness Monitors
# ---------------------------------------------------------------------------

def feature_readiness_monitors(scanner: ECUScanner) -> None:
    with console.status("[cyan]Reading readiness monitors...[/cyan]", spinner="dots"):
        result = scanner.read_readiness_monitors()

    console.print()
    console.print(Rule("[bold cyan]READINESS MONITORS[/bold cyan]"))
    mil_style = "bold red" if result.mil_on else "bold green"
    console.print(f"  MIL: [{mil_style}]{'ON' if result.mil_on else 'OFF'}[/{mil_style}]   "
                  f"Confirmed DTCs: [bold white]{result.confirmed_dtc_count}[/bold white]")
    console.print()

    table = Table(
        title="OBD2 Readiness Monitor Status",
        box=box.SIMPLE_HEAVY,
        border_style="cyan",
        header_style="bold cyan",
        show_lines=False,
    )
    table.add_column("MONITOR", style="white", width=22)
    table.add_column("CATEGORY", style="dim cyan", width=16)
    table.add_column("STATUS", width=18)

    not_ready: list[str] = []
    for mon in result.monitors:
        if not mon.supported:
            status = Text("— NOT SUPPORTED", style="dim")
        elif mon.complete:
            status = Text("✅ READY", style="bold green")
        else:
            status = Text("⚠  NOT READY", style="bold yellow")
            not_ready.append(mon.name)
        table.add_row(mon.name, mon.category, status)

    console.print(table)

    if not_ready:
        console.print()
        console.print(Panel(
            f"[bold yellow]{len(not_ready)} monitor(s) not complete:[/bold yellow] "
            f"{', '.join(not_ready)}\n\n"
            "[dim]Drive cycle required before emissions test.\n"
            "Typically: highway cruise 55–65 mph + city stop-and-go cycle.\n"
            "Check manufacturer drive cycle procedure for exact requirements.[/dim]",
            title="[yellow]EMISSIONS GUIDANCE[/yellow]",
            border_style="yellow",
        ))

    console.print()
    try:
        Prompt.ask("[dim]Press ENTER to return[/dim]", default="")
    except (KeyboardInterrupt, EOFError):
        pass


# ---------------------------------------------------------------------------
# Feature 5: Component Test
# ---------------------------------------------------------------------------

def feature_component_test(conn: OBDConnection) -> None:
    tester = ComponentTester(conn)
    tests = tester.get_available_tests()

    while True:
        console.print()
        console.print(Rule("[bold cyan]COMPONENT TEST[/bold cyan]"))
        console.print("[dim]Activate on-board components for diagnostic verification.[/dim]")
        console.print()

        for i, test in enumerate(tests):
            console.print(f"  [bold cyan]{i + 1}.[/bold cyan] {test.name}  "
                          f"[dim]({test.description})[/dim]")
        console.print(f"  [bold cyan]{len(tests) + 1}.[/bold cyan] [dim]Back to menu[/dim]")
        console.print()

        try:
            choice = Prompt.ask("[bold white]Select component[/bold white]",
                                default=str(len(tests) + 1))
            idx = int(choice.strip()) - 1
        except (KeyboardInterrupt, EOFError, ValueError):
            break

        if idx < 0 or idx >= len(tests):
            break

        test = tests[idx]

        # Safety warning + confirmation
        console.print()
        console.print(Panel(
            f"[bold yellow]⚠  SAFETY WARNING[/bold yellow]\n\n{test.safety_warning}",
            border_style="yellow",
        ))
        console.print()
        try:
            confirm = Prompt.ask(
                f"  Activate [bold white]{test.name}[/bold white]? (yes/no)",
                default="no",
            )
        except (KeyboardInterrupt, EOFError):
            break

        if confirm.lower() not in ("yes", "y"):
            console.print("[dim]  Test cancelled.[/dim]")
            continue

        with console.status(f"[cyan]Activating {test.name}...[/cyan]", spinner="dots"):
            result = tester.run_test(test)

        if result.success:
            console.print(f"\n  [bold green]✅ {result.message}[/bold green]  "
                          f"[dim]({result.duration_seconds:.1f}s)[/dim]")
        else:
            console.print(f"\n  [bold red]✗ {result.message}[/bold red]")
        console.print()


# ---------------------------------------------------------------------------
# Feature 6: Procedure History
# ---------------------------------------------------------------------------

def feature_procedure_history(logger: SessionLogger) -> None:
    records = logger.read_procedure_history()

    console.print()
    console.print(Rule("[bold cyan]PROCEDURE HISTORY[/bold cyan]"))

    if not records:
        console.print("[dim]  No procedures logged yet.[/dim]")
        console.print()
        try:
            Prompt.ask("[dim]Press ENTER to return[/dim]", default="")
        except (KeyboardInterrupt, EOFError):
            pass
        return

    table = Table(
        title=f"All Logged Procedures ({len(records)} total)",
        box=box.SIMPLE_HEAVY,
        border_style="cyan",
        header_style="bold cyan",
        show_lines=False,
    )
    table.add_column("DATE", style="dim cyan", width=12)
    table.add_column("VEHICLE", style="white", width=22)
    table.add_column("PROCEDURE", style="white")
    table.add_column("OUTCOME", width=12)
    table.add_column("NOTES", style="dim white", width=24)

    outcome_styles = {"fixed": "bold green", "not_fixed": "bold red", "unknown": "dim yellow"}
    fixed_count = 0
    for rec in records:
        date_str = rec.get("timestamp", "")[:10]
        outcome = rec.get("outcome", "unknown")
        if outcome == "fixed":
            fixed_count += 1
        table.add_row(
            date_str,
            rec.get("vehicle", "—")[:22],
            rec.get("procedure", "—")[:40],
            Text(outcome.upper(), style=outcome_styles.get(outcome, "white")),
            rec.get("notes", "")[:24],
        )

    console.print(table)

    total = len(records)
    rate = fixed_count / total if total else 0
    console.print()
    console.print(
        f"  [dim]Total: [bold white]{total}[/bold white]   "
        f"Fixed: [bold green]{fixed_count}[/bold green]   "
        f"Success rate: [bold cyan]{rate:.0%}[/bold cyan][/dim]"
    )
    console.print()
    try:
        Prompt.ask("[dim]Press ENTER to return[/dim]", default="")
    except (KeyboardInterrupt, EOFError):
        pass


# ---------------------------------------------------------------------------
# Feature 7: Vehicle Profiles
# ---------------------------------------------------------------------------

def feature_vehicle_profiles(
    profiles: VehicleProfileManager,
    conn: OBDConnection,
) -> None:
    while True:
        console.print()
        console.print(Rule("[bold cyan]VEHICLE PROFILES[/bold cyan]"))
        all_profiles = profiles.get_all()

        if all_profiles:
            table = Table(
                box=box.SIMPLE_HEAVY,
                border_style="cyan",
                header_style="bold cyan",
                show_lines=False,
            )
            table.add_column("#", style="dim cyan", width=4)
            table.add_column("NICKNAME", style="bold white", width=20)
            table.add_column("VIN", style="dim cyan", width=18)
            table.add_column("SESSIONS", style="white", width=10)
            table.add_column("LAST SEEN", style="dim", width=12)
            for i, p in enumerate(all_profiles):
                table.add_row(
                    str(i + 1),
                    p.nickname[:20],
                    p.vin[:17],
                    str(p.session_count),
                    p.last_seen[:10],
                )
            console.print(table)
        else:
            console.print("[dim]  No saved profiles.[/dim]")

        console.print()
        console.print("  [bold cyan]S[/bold cyan] Save current vehicle   "
                      "[bold cyan]D[/bold cyan] Delete a profile   "
                      "[bold cyan]Q[/bold cyan] Back to menu")
        console.print()

        try:
            cmd = Prompt.ask("[bold white]Action[/bold white]", default="Q").strip().upper()
        except (KeyboardInterrupt, EOFError):
            break

        if cmd == "Q":
            break

        if cmd == "S":
            vehicle = conn.vehicle
            if not vehicle:
                console.print("[dim]  No vehicle connected.[/dim]")
                continue
            try:
                nickname = Prompt.ask(
                    f"  Nickname for [bold white]{vehicle.display_name()}[/bold white]",
                    default=vehicle.display_name(),
                )
            except (KeyboardInterrupt, EOFError):
                continue
            profiles.save_profile(
                vin=vehicle.vin,
                make=vehicle.make,
                model=vehicle.model,
                year=vehicle.year,
                engine=vehicle.engine,
                nickname=nickname,
            )
            console.print(f"  [green]Profile saved: {nickname}[/green]")

        elif cmd == "D":
            if not all_profiles:
                continue
            try:
                idx_str = Prompt.ask("  Profile # to delete", default="0")
                idx = int(idx_str) - 1
                if 0 <= idx < len(all_profiles):
                    p = all_profiles[idx]
                    confirm = Prompt.ask(
                        f"  Delete [bold white]{p.nickname}[/bold white]? (yes/no)",
                        default="no",
                    )
                    if confirm.lower() in ("yes", "y"):
                        profiles.delete_profile(p.vin)
                        console.print("[dim]  Profile deleted.[/dim]")
            except (KeyboardInterrupt, EOFError, ValueError):
                pass


# ---------------------------------------------------------------------------
# Feature 8: Export Report
# ---------------------------------------------------------------------------

def feature_export_report(
    scan_result: ScanResult,
    live_monitor: LiveMonitor,
    logger: SessionLogger,
) -> None:
    console.print()
    console.print(Rule("[bold cyan]EXPORT REPORT[/bold cyan]"))

    reports_dir = Path(SESSION_LOG_DIR) / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    today = time.strftime("%Y-%m-%d")
    safe_vin = scan_result.vin.replace(" ", "_")[:17]
    report_path = reports_dir / f"{today}_{safe_vin}_report.txt"

    live_data = live_monitor.get_current_data()
    procedure_records = logger.read_procedure_history(vin=scan_result.vin)

    # Build report text
    lines: list[str] = [
        "=" * 72,
        "  OPENTUNE DIAGNOSTIC REPORT",
        f"  Generated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
        "=" * 72,
        "",
        f"  Vehicle:    {scan_result.vehicle_display}",
        f"  VIN:        {scan_result.vin}",
        f"  Scan date:  {today}",
        "",
        "-" * 72,
        "  ACTIVE DTCs",
        "-" * 72,
    ]
    if scan_result.dtcs:
        for dtc in scan_result.dtcs:
            lines.append(f"  [{dtc.severity.upper():8}] {dtc.code}  {dtc.description}  (ECU: {dtc.ecu})")
    else:
        lines.append("  None detected.")

    lines += ["", "-" * 72, "  LIVE DATA SNAPSHOT", "-" * 72]
    if live_data:
        snap = live_data.snapshot()
        pid_labels = {
            "rpm": "Engine RPM", "coolant_temp": "Coolant Temp", "engine_load": "Engine Load",
            "maf": "MAF", "throttle_pos": "Throttle Pos", "vehicle_speed": "Vehicle Speed",
            "fuel_trim_short_b1": "STFT B1", "fuel_trim_long_b1": "LTFT B1",
            "o2_b1s1": "O2 B1S1", "battery_voltage": "Battery Voltage",
        }
        units = {
            "rpm": "RPM", "coolant_temp": "°C", "engine_load": "%", "maf": "g/s",
            "throttle_pos": "%", "vehicle_speed": "km/h", "fuel_trim_short_b1": "%",
            "fuel_trim_long_b1": "%", "o2_b1s1": "V", "battery_voltage": "V",
        }
        for pid, label in pid_labels.items():
            val = snap.get(pid)
            if val is not None:
                lines.append(f"  {label:<24} {val:.2f} {units.get(pid, '')}")
    else:
        lines.append("  No live data available.")

    lines += ["", "-" * 72, "  PROCEDURES RUN THIS VIN", "-" * 72]
    if procedure_records:
        for rec in procedure_records:
            lines.append(f"  {rec.get('timestamp', '')[:10]}  {rec.get('procedure', '—')[:50]}  "
                         f"[{rec.get('outcome', '?').upper()}]")
    else:
        lines.append("  None logged for this VIN.")

    # AI recommendations section
    lines += ["", "-" * 72, "  AI RECOMMENDATIONS", "-" * 72]
    ai_recs = _generate_ai_recommendations(scan_result, live_data)
    lines.append(ai_recs)
    lines += ["", "=" * 72, "  END OF REPORT", "=" * 72]

    report_text = "\n".join(lines)

    # Save to file
    try:
        report_path.write_text(report_text, encoding="utf-8")
    except Exception as exc:
        console.print(f"[red]Failed to save report: {exc}[/red]")
        return

    # Rich preview
    console.print()
    console.print(Panel(
        report_text[:2000] + ("[truncated...]" if len(report_text) > 2000 else ""),
        title="[cyan]REPORT PREVIEW[/cyan]",
        border_style="cyan",
    ))
    console.print()
    console.print(f"  [bold green]Report saved:[/bold green] [cyan]{report_path}[/cyan]")
    quip('export')
    console.print()
    try:
        Prompt.ask("[dim]Press ENTER to return[/dim]", default="")
    except (KeyboardInterrupt, EOFError):
        pass


def _generate_ai_recommendations(scan_result: ScanResult, live_data) -> str:
    if not ANTHROPIC_API_KEY:
        dtc_text = ", ".join(d.code for d in scan_result.dtcs) or "none"
        return (
            f"  Active codes: {dtc_text}\n"
            "  [API key required for AI recommendations — add ANTHROPIC_API_KEY to .env]"
        )
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        dtc_block = "\n".join(
            f"    {d.code} — {d.description} (ECU: {d.ecu}, severity: {d.severity})"
            for d in scan_result.dtcs
        ) or "    None"
        live_block = ""
        if live_data:
            snap = live_data.snapshot()
            live_block = "\n".join(f"    {k}: {v}" for k, v in list(snap.items())[:8])
        prompt = (
            f"Vehicle: {scan_result.vehicle_display}\nVIN: {scan_result.vin}\n\n"
            f"Active DTCs:\n{dtc_block}\n\nLive data:\n{live_block}\n\n"
            "Write 3–5 concise actionable recommendations for the mechanic. "
            "Reference specific codes and sensor values. Plain text, no markdown."
        )
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        return "  " + response.content[0].text.strip().replace("\n", "\n  ")
    except Exception as exc:
        return f"  [AI recommendation generation failed: {exc}]"


# ---------------------------------------------------------------------------
# Feature K: Knowledge Base Browser
# ---------------------------------------------------------------------------

def feature_knowledge_base(knowledge: KnowledgeEngine) -> None:
    while True:
        console.print()
        console.print(Rule("[bold cyan]KNOWLEDGE BASE[/bold cyan]"))

        stats = knowledge.get_stats()
        console.print(
            f"  Problems solved: [bold white]{stats['total_cases']}[/bold white]   "
            f"Fixed: [bold green]{stats['total_fixed']}[/bold green]   "
            f"Success rate: [bold cyan]{stats['success_rate']:.0%}[/bold cyan]\n"
            f"  Categories: [dim]{', '.join(stats['categories']) or 'none yet'}[/dim]"
        )
        console.print()

        if stats["categories"]:
            for i, cat in enumerate(stats["categories"]):
                console.print(f"  [bold cyan]{i + 1}.[/bold cyan] {cat.replace('_', ' ').title()}")
        else:
            console.print("[dim]  No knowledge entries yet. Solve problems and record outcomes to build the knowledge base.[/dim]")

        console.print(f"\n  [bold cyan]Q.[/bold cyan] [dim]Back to menu[/dim]")
        console.print()

        try:
            choice = Prompt.ask("[bold white]Select category[/bold white]", default="Q").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if choice.upper() == "Q":
            break

        try:
            idx = int(choice) - 1
            cats = stats["categories"]
            if 0 <= idx < len(cats):
                system = cats[idx]
                entries = knowledge.browse_by_system(system)
                _render_knowledge_entries(system, entries)
        except ValueError:
            pass


def _render_knowledge_entries(system: str, entries: list[dict]) -> None:
    console.print()
    console.print(Rule(f"[cyan]{system.replace('_', ' ').title()}[/cyan]"))

    if not entries:
        console.print("[dim]  No entries.[/dim]")
        return

    for entry in entries:
        rate = entry.get("success_rate", 0)
        cases = entry.get("total_cases", 0)
        rate_color = "green" if rate >= 0.85 else "yellow" if rate >= 0.6 else "red"
        console.print(Panel(
            f"[bold white]{entry.get('service_type', '—')}[/bold white]\n"
            f"[dim]Success rate:[/dim] [{rate_color}]{rate:.0%}[/{rate_color}]  "
            f"[dim]Cases:[/dim] [white]{cases}[/white]\n\n"
            f"[dim]Vehicles:[/dim] {', '.join(entry.get('vehicles_seen', [])[:3])}\n\n"
            f"[dim]Symptoms:[/dim] {'; '.join(entry.get('common_symptoms', [])[:3])}\n\n"
            f"[dim]Solution:[/dim] {entry.get('physical_solution', '—')[:200]}",
            border_style="dim cyan",
        ))

    try:
        Prompt.ask("[dim]Press ENTER to return[/dim]", default="")
    except (KeyboardInterrupt, EOFError):
        pass


# ---------------------------------------------------------------------------
# Feature 2 (Live Process Scan) — existing live_scan wrapper
# ---------------------------------------------------------------------------

def feature_live_process_scan(conn: OBDConnection, scan_result: ScanResult) -> None:
    from core.live_scan import LiveProcessScanner, SCAN_DURATION_SECONDS, POLL_INTERVAL_SECONDS

    console.print()
    console.print(Rule("[bold cyan]LIVE PROCESS SCAN[/bold cyan]"))
    console.print(f"[dim]{SCAN_DURATION_SECONDS}-second time-series capture with AI analysis.[/dim]")
    console.print()

    scanner = LiveProcessScanner(conn)
    readings: list[dict] = []

    def _progress(elapsed: float, total: float) -> None:
        pct = min(int(elapsed / total * 40), 40)
        bar = "█" * pct + "░" * (40 - pct)
        console.print(f"  [{bar}]  {elapsed:.0f}/{total:.0f}s", end="\r")

    with console.status("[cyan]Collecting data...[/cyan]", spinner="arc"):
        try:
            readings = scanner.collect_scan_data(
                duration_seconds=SCAN_DURATION_SECONDS,
                poll_interval=POLL_INTERVAL_SECONDS,
                progress_callback=_progress,
            )
        except Exception as exc:
            console.print(f"[red]Scan error: {exc}[/red]")
            return

    console.print()
    console.print(f"[dim]Captured {len(readings)} readings. Analyzing...[/dim]")
    console.print()

    report_text = ""
    console.print(Panel("", title="[cyan]LIVE SCAN ANALYSIS[/cyan]", border_style="cyan"))
    for chunk in scanner.analyze_with_claude(readings):
        report_text += chunk
        console.print(chunk, end="")

    console.print()
    console.print()
    try:
        Prompt.ask("[dim]Press ENTER to return[/dim]", default="")
    except (KeyboardInterrupt, EOFError):
        pass


# ---------------------------------------------------------------------------
# Main menu
# ---------------------------------------------------------------------------

def run_main_menu(
    conn: OBDConnection,
    scan_result: ScanResult,
    live_monitor: LiveMonitor,
    ai_monitor: AIMonitor,
    engineer: ProcedureEngineer,
    logger: SessionLogger,
    profiles: VehicleProfileManager,
    knowledge: KnowledgeEngine,
    manual_vehicle: dict = {},
    researcher: Optional[VehicleResearcher] = None,
) -> None:
    scanner = ECUScanner(conn)
    _research_printed = False

    while True:
        # Check if background research just completed — print once
        if researcher is not None and not _research_printed and researcher.is_done():
            _research_printed = True
            summary = researcher.get_summary()
            if summary:
                console.print(f"[bold cyan]  Research complete:[/bold cyan] {summary}")
                console.print()

        # Drain and display any anomaly alerts
        if ANTHROPIC_API_KEY:
            alerts = ai_monitor.drain_enriched()
        else:
            alerts = live_monitor.drain_alerts()
        if alerts:
            display_alerts(alerts)

        console.print()

        if INTERACTIVE_TTY:
            try:
                choice = questionary.select(
                    "OPENTUNE MENU",
                    choices=MENU_CHOICES,
                    style=QSTYLE,
                ).ask()
                if choice is None: choice = 'Q'
            except Exception:
                choice = 'Q'
        else:
            console.print(Panel(MENU_TEXT, title='[bold cyan]OPENTUNE MENU[/bold cyan]',
                                border_style='cyan', padding=(0, 2)))
            console.print()
            try:
                choice = Prompt.ask('[bold cyan]Select[/bold cyan]', default='').strip().upper()
            except (KeyboardInterrupt, EOFError):
                choice = 'Q'
        if choice is None or choice == "Q":
            console.print("[dim]Goodbye.[/dim]")
            break

        elif choice == "1":
            console.print("[dim]Re-scanning ECUs...[/dim]")
            with console.status("[cyan]Scanning...[/cyan]", spinner="arc"):
                new_result = scanner.full_scan()
            render_scan_result(new_result)
            scan_result.dtcs[:] = new_result.dtcs

        elif choice == "2":
            feature_live_process_scan(conn, scan_result)

        elif choice == "3":
            feature_dtc_history(scanner)

        elif choice == "4":
            feature_freeze_frame(scanner, scan_result.dtcs)

        elif choice == "5":
            feature_readiness_monitors(scanner)

        elif choice == "6":
            feature_component_test(conn)

        elif choice == "7":
            feature_procedure_history(logger)

        elif choice == "8":
            feature_vehicle_profiles(profiles, conn)

        elif choice == "9":
            feature_export_report(scan_result, live_monitor, logger)

        elif choice == "K":
            feature_knowledge_base(knowledge)

        elif choice == "0":
            _run_chat_session(conn, scan_result, live_monitor, ai_monitor, engineer, logger, knowledge, manual_vehicle=manual_vehicle)


def _run_chat_session(
    conn: OBDConnection,
    scan_result: ScanResult,
    live_monitor: LiveMonitor,
    ai_monitor: AIMonitor,
    engineer: ProcedureEngineer,
    logger: SessionLogger,
    knowledge: KnowledgeEngine,
    manual_vehicle: dict = {},
) -> None:
    """Single chat interaction from the menu."""
    run_chat_loop(conn, scan_result, live_monitor, ai_monitor, engineer, logger, knowledge=knowledge, manual_vehicle=manual_vehicle)


# ---------------------------------------------------------------------------
# Main chat loop
# ---------------------------------------------------------------------------

def run_chat_loop(
    conn: OBDConnection,
    scan_result: ScanResult,
    live_monitor: LiveMonitor,
    ai_monitor: AIMonitor,
    engineer: ProcedureEngineer,
    logger: SessionLogger,
    knowledge: Optional[KnowledgeEngine] = None,
    manual_vehicle: dict = {},
) -> None:
    console.print()
    console.print(Rule("[bold cyan]DIAGNOSTIC CHAT[/bold cyan]"))
    console.print("[dim]Describe any vehicle problem. Commands: scan | live | dtcs | help | back | quit[/dim]")
    console.print()

    vin = scan_result.vin
    vehicle = scan_result.vehicle_display
    dtcs = scan_result.dtcs

    while True:
        # Drain and display any anomaly alerts
        if ANTHROPIC_API_KEY:
            alerts = ai_monitor.drain_enriched()
        else:
            alerts = live_monitor.drain_alerts()
        if alerts:
            display_alerts(alerts)
            console.print()

        try:
            user_input = Prompt.ask("\n[bold cyan]mechanic[/bold cyan]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Session ended.[/dim]")
            break

        if not user_input.strip():
            continue

        cmd = user_input.strip().lower()

        # Built-in commands
        if cmd in ("quit", "exit", "q"):
            console.print("[dim]Goodbye.[/dim]")
            break

        if cmd in ("back", "menu", "b"):
            break

        if cmd == "scan":
            console.print("[dim]Re-scanning ECUs...[/dim]")
            scanner = ECUScanner(conn)
            new_result = scanner.full_scan()
            render_scan_result(new_result)
            dtcs = new_result.dtcs
            continue

        if cmd == "live":
            data = live_monitor.get_current_data()
            if data:
                render_live_data_panel(data)
            else:
                console.print("[dim]No live data yet[/dim]")
            continue

        if cmd == "dtcs":
            render_dtc_table(dtcs)
            continue

        if cmd == "help":
            help_table = Table(box=box.SIMPLE, show_header=False)
            help_table.add_column("CMD", style="cyan", width=16)
            help_table.add_column("DESC", style="white")
            help_table.add_row("scan", "Re-scan all ECUs")
            help_table.add_row("live", "Show live data snapshot")
            help_table.add_row("dtcs", "List active DTCs")
            help_table.add_row("help", "Show this help")
            help_table.add_row("quit", "Exit OpenTune")
            help_table.add_row("<anything>", "Describe a problem — AI engineers a solution")
            console.print(Panel(help_table, title="[cyan]COMMANDS[/cyan]", border_style="dim"))
            continue

        # ----------------------------------------------------------------
        # All other input goes to the AI — two-phase diagnostic flow
        # ----------------------------------------------------------------
        console.print()
        console.print("[dim cyan]Before I run anything — let me check what the system sees.[/dim cyan]")
        console.print()

        live_data = live_monitor.get_current_data()
        context = {
            "vehicle_display": vehicle,
            "vin": vin,
            "dtcs": dtcs,
            "live_data": live_data,
            "ecu_map": scan_result.ecu_map,
            "manual_vehicle": manual_vehicle,
        }

        # Phase 1: Understand the problem
        with console.status("[cyan]Reading vehicle state...[/cyan]", spinner="dots"):
            understanding = engineer.understand_problem(user_input, context)

        # Display findings
        if understanding.data_highlights:
            for highlight in understanding.data_highlights:
                console.print(f"  [cyan]→[/cyan] {highlight}")
            console.print()

        # Check for known OBDAgent procedures
        known, proc_name = engineer.check_known_procedures(understanding)
        if known:
            console.print(f"  [dim]Reference procedure available: [white]{proc_name}[/white][/dim]")
            console.print()

        # Ask ONE clarifying question if needed
        clarification = ""
        if understanding.needs_clarification and understanding.clarifying_question:
            console.print(f"  [white]{understanding.clarifying_question}[/white]")
            console.print()
            try:
                clarification = Prompt.ask("[bold cyan]mechanic[/bold cyan]")
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Session ended.[/dim]")
                break
            console.print()

        # Phase 2: Engineer the solution
        if clarification:
            console.print(f"[dim cyan]Got it. Engineering solution...[/dim cyan]")
        else:
            console.print(f"[dim cyan]Engineering solution...[/dim cyan]")
        console.print()

        with console.status("[cyan]Designing procedure...[/cyan]", spinner="arc"):
            proc = engineer.engineer_solution(understanding, context, clarification=clarification)
        quip('ai_engineer')

        # Show brief plan summary + safety notes
        render_plan_summary(proc)

        # Natural-language confirmation — never a blunt Y/N gate
        try:
            confirm_raw = Prompt.ask("[bold white]Ready to start?[/bold white]", default="yes")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Session ended.[/dim]")
            break

        confirm = confirm_raw.strip().lower()
        if confirm in ("no", "n", "skip", "cancel", "stop", "abort"):
            console.print("[dim]Procedure skipped.[/dim]")
            logger.log(
                vin=vin, vehicle=vehicle, user_input=user_input,
                procedure_engineered=proc.engineered, procedure_title=proc.title,
                steps_executed=[], outcome="unknown", notes="Skipped by mechanic",
                live_data_snapshot=live_data.snapshot() if live_data else {},
                dtcs=dtcs, ai_reasoning=proc.reasoning, confidence=proc.confidence,
            )
            continue

        # Show full procedure detail before stepping through it
        render_procedure(proc)

        executed = execute_procedure(proc, conn, live_monitor)
        outcome, notes = capture_outcome()

        logger.log(
            vin=vin, vehicle=vehicle, user_input=user_input,
            procedure_engineered=proc.engineered, procedure_title=proc.title,
            steps_executed=executed, outcome=outcome, notes=notes,
            live_data_snapshot=live_data.snapshot() if live_data else {},
            dtcs=dtcs, ai_reasoning=proc.reasoning, confidence=proc.confidence,
        )

        # Log to procedure history
        logger.log_procedure(
            vin=vin, vehicle=vehicle, procedure=proc.title,
            outcome=outcome, notes=notes,
        )

        # Record to knowledge engine
        if knowledge is not None:
            try:
                problem_dict = {
                    "vehicle_display": vehicle,
                    "vin": vin,
                    "suspected_system": understanding.suspected_system,
                    "symptoms": understanding.symptoms,
                    "dtcs": [d.code for d in dtcs],
                    "user_input": user_input,
                }
                solution_dict = {
                    "title": proc.title,
                    "reasoning": proc.reasoning,
                    "steps": [
                        {"step_number": s.step_number, "description": s.description}
                        for s in proc.steps
                    ],
                }
                knowledge.record_solution(
                    problem=problem_dict,
                    solution=solution_dict,
                    outcome={"outcome": outcome, "notes": notes},
                )
            except Exception:
                pass

        result_style = {"fixed": "bold green", "not_fixed": "bold red", "unknown": "bold yellow"}.get(outcome, "white")
        console.print(f"\n[{result_style}]  Outcome logged: {outcome.upper()}[/{result_style}]")
        quip('knowledge_write')
        console.print(f"[dim]  Session log: {logger.log_file_path()}[/dim]")
        console.print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Manual Vehicle Entry
# ---------------------------------------------------------------------------

def prompt_manual_vehicle(existing_vehicle=None) -> dict:
    """
    Prompt mechanic to manually enter vehicle info.
    Returns dict with year, make, model, vin (all optional).
    """
    console.print()
    console.print(Rule("[bold cyan]VEHICLE IDENTIFICATION[/bold cyan]"))
    console.print()
    if existing_vehicle:
        console.print(f"  [dim]Detected: [white]{existing_vehicle}[/white] — press ENTER to keep, or type to override[/dim]")
    else:
        console.print("  [dim]No vehicle detected. Enter details so the AI can reason accurately.[/dim]")
        console.print("  [dim]Press ENTER to skip any field.[/dim]")
    console.print()
    try:
        year  = Prompt.ask("  [bold cyan]Year [/bold cyan] ", default="").strip()
        make  = Prompt.ask("  [bold cyan]Make [/bold cyan] ", default="").strip()
        model = Prompt.ask("  [bold cyan]Model[/bold cyan] ", default="").strip()
        vin   = Prompt.ask("  [bold cyan]VIN  [/bold cyan] ", default="").strip()
    except (KeyboardInterrupt, EOFError):
        return {}
    result = {}
    if year:  result["year"]  = year
    if make:  result["make"]  = make
    if model: result["model"] = model
    if vin:   result["vin"]   = vin
    if result:
        parts = [year, make, model]
        display = " ".join(p for p in parts if p) or "Unknown"
        console.print()
        console.print(f"  [green]Vehicle set:[/green] [bold white]{display}[/bold white]" +
                      (f"  [dim cyan]VIN: {vin}[/dim cyan]" if vin else ""))
        console.print()
    return result

# ---------------------------------------------------------------------------
# No-car chat loop (AI-only, no OBD connection)
# ---------------------------------------------------------------------------

def un_no_car_chat(engineer: ProcedureEngineer, logger: SessionLogger, knowledge: KnowledgeEngine) -> None:
    """Chat loop for no-car mode — AI only, no live data or DTCs."""
    console.print()
    console.print(
        "[bold cyan]OpenTune:[/bold cyan] What is your vehicle — year, make, model, and trim? "
        "Describe what you're dealing with and let's figure it out."
    )
    console.print()

    context: dict = {
        "vehicle_display": "Unknown",
        "vin": "UNKNOWN",
        "dtcs": [],
        "live_data": None,
        "ecu_map": {},
        "manual_vehicle": {},
        "no_car_mode": True,
    }

    while True:
        try:
            user_input = Prompt.ask("\n[bold cyan]mechanic[/bold cyan]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Session ended.[/dim]")
            break

        if not user_input.strip():
            continue

        cmd = user_input.strip().lower()
        if cmd in ("quit", "exit", "q"):
            console.print("[dim]Goodbye.[/dim]")
            break

        # Two-phase AI flow
        console.print()
        console.print("[dim cyan]Before I run anything — let me check what you've told me.[/dim cyan]")
        console.print()

        with console.status("[cyan]Reading what you've told me...[/cyan]", spinner="dots"):
            understanding = engineer.understand_problem(user_input, context)

        if understanding.data_highlights:
            for highlight in understanding.data_highlights:
                console.print(f"  [cyan]→[/cyan] {highlight}")
            console.print()

        clarification = ""
        if understanding.needs_clarification and understanding.clarifying_question:
            console.print(f"  [white]{understanding.clarifying_question}[/white]")
            console.print()
            try:
                clarification = Prompt.ask("[bold cyan]mechanic[/bold cyan]")
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Session ended.[/dim]")
                break
            console.print()

        if clarification:
            console.print("[dim cyan]Got it. Engineering solution...[/dim cyan]")
        else:
            console.print("[dim cyan]Engineering solution...[/dim cyan]")
        console.print()

        with console.status("[cyan]Designing procedure...[/cyan]", spinner="arc"):
            proc = engineer.engineer_solution(understanding, context, clarification=clarification)
        quip('ai_engineer')

        # Show plan only — no execution (no OBD connection)
        render_plan_summary(proc)
        console.print("[dim]Connect an ELM327 adapter and relaunch to execute this procedure with live data.[/dim]")
        quip('chat')
        console.print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="opentune",
        description="OpenTune — Open Diagnostics. Infinite Solutions.",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--sim", action="store_true", default=False, help="Simulation mode")
    mode_group.add_argument("--real", action="store_true", help="Real ELM327 adapter")
    parser.add_argument("--port", default=None, help="Serial port for ELM327 (e.g. /dev/ttyUSB0)")
    return parser.parse_args()


def select_mode_interactive() -> tuple[ConnectionMode, Optional[str]]:
    """Show mode selection screen and return (mode, port). Called only when no CLI flag passed."""
    while True:
        console.print()
        panel_content = (
            "\n"
            "   [bold white][1][/bold white]  [cyan]SIM[/cyan]   — Simulation  [dim](no adapter needed)[/dim]\n"
            "\n"
            "   [bold white][2][/bold white]  [cyan]REAL[/cyan]  — ELM327 Hardware\n"
        )
        console.print(Panel(
            panel_content,
            title="[bold cyan]Select Connection Mode[/bold cyan]",
            border_style="cyan",
            padding=(0, 2),
        ))

        try:
            choice = Prompt.ask("\n[bold cyan]Mode[/bold cyan]", default="1").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Exiting.[/dim]")
            sys.exit(0)

        if choice == "1":
            return ConnectionMode.SIM, None

        if choice == "2":
            try:
                port_input = Prompt.ask(
                    "[dim]Port (press Enter to auto-detect, or type e.g. COM4 or /dev/tty.usbserial-0001)[/dim]",
                    default="",
                ).strip()
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Exiting.[/dim]")
                sys.exit(0)
            return ConnectionMode.REAL, port_input or None

        console.print("[bold red]  Invalid choice — enter 1 or 2[/bold red]")


def main() -> None:
    args = parse_args()

    from config import DEFAULT_PORT

    # If no mode flag passed, show interactive mode selection screen first
    if not args.sim and not args.real:
        # Show ASCII art before mode selection
        console.clear()
        art_lines = OPENTUNE_ASCII.split("\n")
        colors = ["bold cyan", "bold cyan", "cyan", "cyan", "blue", "bold blue", "bold blue"]
        art_text = Text()
        for i, line in enumerate(art_lines):
            color = colors[min(i, len(colors) - 1)]
            art_text.append(line + "\n", style=color)
        console.print()
        console.print(art_text, justify="center")
        console.print()
        console.print(Text(TAGLINE, style="bold white"), justify="center")
        console.print(Rule(style="dim cyan"))

        mode, selected_port = select_mode_interactive()
        port = selected_port or args.port or DEFAULT_PORT
    else:
        mode = ConnectionMode.REAL if args.real else ConnectionMode.SIM
        port = args.port or DEFAULT_PORT

    # Show launch screen (no vehicle info yet)
    render_launch_screen(mode)

    # Connect
    console.print(f"[dim]Connecting in [bold]{mode.value.upper()}[/bold] mode...[/dim]")
    console.print()

    conn = OBDConnection(mode=mode, port=port)

    with console.status("[cyan]Establishing connection...[/cyan]", spinner="dots"):
        connected = conn.connect()

    vehicle = conn.vehicle if connected else None
    vehicle_display = vehicle.display_name() if vehicle else None

    # -----------------------------------------------------------------------
    # NO-CAR MODE: real adapter selected but no connection or no vehicle
    # -----------------------------------------------------------------------
    if mode == ConnectionMode.REAL and not connected:
        console.print()
        console.print(Panel(
            "[bold yellow]Full diagnostic features require OBD2 connection.[/bold yellow]\n"
            "[white]Running in AI Chat mode.[/white]\n\n"
            "[dim]Connect an ELM327 adapter and relaunch for full ECU scan, live data, "
            "component tests, and procedure execution.[/dim]",
            title="[yellow]NO CONNECTION[/yellow]",
            border_style="yellow",
        ))
        console.print()

        logger = SessionLogger()
        base_path = Path(__file__).parent
        knowledge = KnowledgeEngine(base_path)
        knowledge.seed_initial_knowledge()
        engineer = ProcedureEngineer(knowledge_engine=knowledge)

        un_no_car_chat(engineer, logger, knowledge)

        if connected:
            conn.disconnect()
        console.print()
        console.print(Rule("[dim]OpenTune session ended[/dim]"))
        console.print()
        return

    # -----------------------------------------------------------------------
    # CONNECTED MODE: sim always here; real with vehicle detected
    # -----------------------------------------------------------------------

    # Manual vehicle entry: only if vehicle wasn't auto-detected
    manual_info: dict = {}
    if not vehicle_display:
        manual_info = prompt_manual_vehicle(existing_vehicle=vehicle_display)

    # Merge manual info into vehicle display / vin
    if manual_info:
        parts = [manual_info.get("year", ""), manual_info.get("make", ""), manual_info.get("model", "")]
        manual_display = " ".join(p for p in parts if p)
        if manual_display:
            vehicle_display = manual_display
        if manual_info.get("vin"):
            vin = manual_info["vin"]
        else:
            vin = vehicle.vin if vehicle else "UNKNOWN"
    else:
        vin = vehicle.vin if vehicle else "UNKNOWN"

    vehicle_display = vehicle_display or "Unknown"
    vin = vin or "UNKNOWN"

    # Refresh launch screen with vehicle info
    render_launch_screen(mode, vehicle_display, vin)

    console.print(f"[green]  Connected to [bold]{vehicle_display}[/bold]  (VIN: {vin})[/green]")
    console.print()

    # Full ECU scan
    console.print("[dim]Running full ECU scan...[/dim]")
    scanner = ECUScanner(conn)
    with console.status("[cyan]Scanning all ECUs...[/cyan]", spinner="arc"):
        scan_result = scanner.full_scan()

    render_scan_result(scan_result)

    # Self-learning: start background research if vehicle is unknown
    researcher: Optional[VehicleResearcher] = None
    _research_printed = False
    if ANTHROPIC_API_KEY:
        vehicle_make = conn.vehicle.make if conn.vehicle else "Unknown"
        if vehicle_make in ("Unknown", "") or vin == "UNKNOWN":
            researcher = VehicleResearcher(ANTHROPIC_API_KEY, Path(__file__).parent / "knowledge_base")
            live_snap = scan_result.live_snapshot.snapshot() if scan_result.live_snapshot else {}
            dtc_codes = [d.code for d in scan_result.dtcs]
            researcher.start_research(vin, dtc_codes, live_snap)
            console.print("[dim cyan]  Researching vehicle in background...[/dim cyan]")
            console.print()

    # Start live monitor
    live_monitor = LiveMonitor(conn)
    live_monitor.start()

    # Start AI monitor
    ai_monitor = AIMonitor(live_monitor)
    if ANTHROPIC_API_KEY:
        ai_monitor.start()

    # Init logger, knowledge engine, vehicle profiles
    logger = SessionLogger()
    base_path = Path(__file__).parent
    knowledge = KnowledgeEngine(base_path)
    knowledge.seed_initial_knowledge()
    profiles = VehicleProfileManager()

    # Init engineer with knowledge engine
    engineer = ProcedureEngineer(knowledge_engine=knowledge)

    if not ANTHROPIC_API_KEY:
        console.print(Panel(
            "[bold yellow]No ANTHROPIC_API_KEY found[/bold yellow]\n\n"
            "[white]Running in scan-only mode.[/white]\n"
            "[dim]Set ANTHROPIC_API_KEY in .env to enable AI procedure engineering.[/dim]",
            border_style="yellow",
            title="[yellow]API KEY MISSING[/yellow]",
        ))
        console.print()

    # Auto-save vehicle profile
    if conn.vehicle:
        v = conn.vehicle
        profiles.save_profile(
            vin=v.vin, make=v.make, model=v.model,
            year=v.year, engine=v.engine,
        )

    # Main menu
    try:
        run_main_menu(
            conn, scan_result, live_monitor, ai_monitor,
            engineer, logger, profiles, knowledge,
            manual_vehicle=manual_info,
            researcher=researcher,
        )
    finally:
        live_monitor.stop()
        if ANTHROPIC_API_KEY:
            ai_monitor.stop()
        conn.disconnect()

    console.print()
    console.print(Rule("[dim]OpenTune session ended[/dim]"))
    console.print(f"[dim]Session data: {logger.log_file_path()}[/dim]")
    console.print()


if __name__ == "__main__":
    main()















