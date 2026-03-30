"""
OBD Detector â€” ELM327 adapter detection and hot-plug polling.

Scans COM ports (Windows) and /dev/tty* (macOS/Linux) for ELM327 adapters.
Background thread polls every 10 seconds and fires a callback when state changes.
"""
from __future__ import annotations

import platform
import threading
import time
from typing import Callable, Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

console = Console()

# ELM327 USB VID/PID pairs (most common clones included)
_ELM327_VIDS = {0x0403, 0x10C4, 0x1A86, 0x067B, 0x04D8}

POLL_INTERVAL = 10  # seconds between background polls


# ---------------------------------------------------------------------------
# Port discovery helpers
# ---------------------------------------------------------------------------

def _candidate_ports() -> list[str]:
    """Return a list of serial port device strings to try."""
    system = platform.system()

    try:
        from serial.tools import list_ports
        all_ports = list_ports.comports()

        # Prioritise ports that look like ELM327 by VID
        elm_ports = [
            p.device for p in all_ports
            if (p.vid in _ELM327_VIDS if p.vid else False)
        ]
        other_ports = [
            p.device for p in all_ports
            if p.device not in elm_ports
        ]
        return elm_ports + other_ports

    except ImportError:
        # pyserial not installed â€” fall back to OS-specific guesses
        if system == "Windows":
            return [f"COM{i}" for i in range(1, 17)]
        else:
            import glob
            return (
                glob.glob("/dev/tty.usbserial*")
                + glob.glob("/dev/ttyUSB*")
                + glob.glob("/dev/tty.OBDII*")
                + glob.glob("/dev/cu.usbserial*")
            )


def _probe_port(port: str, timeout: float = 1.5) -> bool:
    """
    Send 'ATI\\r' to *port* and check the response contains 'ELM'.
    Returns True if the port responds like an ELM327.
    """
    try:
        import serial
        with serial.Serial(port, baudrate=38400, timeout=timeout) as ser:
            ser.reset_input_buffer()
            ser.write(b"ATI\r")
            time.sleep(0.3)
            response = ser.read(ser.in_waiting or 64).decode("ascii", errors="ignore")
            return "ELM" in response.upper()
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Public scan function
# ---------------------------------------------------------------------------

def detect_adapter(sim: bool = False, show_progress: bool = True) -> Optional[str]:
    """
    Scan all candidate serial ports for an ELM327 adapter.

    Args:
        sim: If True, return a fake port string immediately.
        show_progress: Show a Rich progress bar during the scan.

    Returns:
        Port string (e.g. "COM3" or "/dev/ttyUSB0") or None.
    """
    if sim:
        return "SIM"

    ports = _candidate_ports()
    if not ports:
        return None

    if show_progress:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Scanning for OBD adapter..."),
            TimeElapsedColumn(),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task("", total=None)
            for port in ports:
                if _probe_port(port):
                    return port
        return None
    else:
        for port in ports:
            if _probe_port(port):
                return port
        return None


# ---------------------------------------------------------------------------
# Background hot-plug poller
# ---------------------------------------------------------------------------

class AdapterPoller:
    """
    Background thread that polls for adapter presence every POLL_INTERVAL
    seconds and fires callbacks when the adapter appears or disappears.
    """

    def __init__(
        self,
        on_connect: Optional[Callable[[str], None]] = None,
        on_disconnect: Optional[Callable[[], None]] = None,
        sim: bool = False,
    ):
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect
        self.sim = sim

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._current_port: Optional[str] = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="AdapterPoller"
        )
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)

    def current_port(self) -> Optional[str]:
        return self._current_port

    # ------------------------------------------------------------------

    def _loop(self) -> None:
        while self._running:
            port = detect_adapter(sim=self.sim, show_progress=False)

            if port and not self._current_port:
                # Adapter appeared
                self._current_port = port
                if self.on_connect:
                    try:
                        self.on_connect(port)
                    except Exception:
                        pass

            elif not port and self._current_port:
                # Adapter disappeared
                self._current_port = None
                if self.on_disconnect:
                    try:
                        self.on_disconnect()
                    except Exception:
                        pass

            # Sleep in small increments so stop() is responsive
            for _ in range(POLL_INTERVAL * 2):
                if not self._running:
                    return
                time.sleep(0.5)

