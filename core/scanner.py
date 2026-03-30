"""
ECU Scanner & Live Data Monitor

- Full ECU scan on connect
- DTC history (active/pending/permanent)
- Freeze frame data
- Readiness monitors
- Background thread polling key PIDs
- Anomaly detection with threshold checking
- Alert queue consumed by the main chat loop
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from queue import Queue, Empty
from typing import Optional

from config import (
    MONITOR_POLL_INTERVAL,
    ANOMALY_CHECK_INTERVAL,
    ANOMALY_THRESHOLDS,
)
from core.connection import OBDConnection, DTC, LiveData


@dataclass
class ScanResult:
    vehicle_display: str
    vin: str
    dtcs: list[DTC]
    live_snapshot: LiveData
    ecu_map: dict[str, str]  # ecu_name -> status
    duration_s: float


@dataclass
class AnomalyAlert:
    pid_name: str
    value: float
    unit: str
    threshold_type: str  # "high" | "low" | "warn"
    message: str
    timestamp: float = field(default_factory=time.time)
    severity: str = "warning"  # "warning" | "critical"


@dataclass
class DTCHistoryResult:
    """Complete DTC history across all three modes."""
    active: list[DTC]        # Mode 03 — confirmed/active
    pending: list[DTC]       # Mode 07 — detected but not yet confirmed
    permanent: list[DTC]     # Mode 0A — cannot be cleared without drive cycle
    mil_on: bool
    confirmed_count: int


@dataclass
class ReadinessMonitor:
    """Single OBD2 readiness monitor status."""
    name: str
    supported: bool          # ECU supports this monitor
    complete: bool           # Monitor has completed its test
    category: str            # "continuous" | "non-continuous"


@dataclass
class ReadinessResult:
    """All readiness monitors for emissions testing."""
    monitors: list[ReadinessMonitor]
    mil_on: bool
    confirmed_dtc_count: int


@dataclass
class FreezeFrameData:
    """Sensor snapshot captured by ECU at the moment a DTC triggered."""
    dtc_code: str
    rpm: Optional[float]
    vehicle_speed: Optional[float]
    coolant_temp: Optional[float]
    engine_load: Optional[float]
    fuel_trim_short_b1: Optional[float]
    throttle_pos: Optional[float]
    maf: Optional[float]
    map: Optional[float]


ECU_MAP: dict[str, str] = {
    "ECM": "Engine Control Module",
    "TCM": "Transmission Control Module",
    "ABS": "Anti-lock Brake System",
    "BCM": "Body Control Module",
    "SRS": "Supplemental Restraint System",
    "HVAC": "Climate Control Module",
    "TPMS": "Tire Pressure Monitor",
    "STRG": "Steering Angle Sensor",
}

PID_UNITS: dict[str, str] = {
    "rpm": "RPM",
    "coolant_temp": "°C",
    "intake_air_temp": "°C",
    "throttle_pos": "%",
    "engine_load": "%",
    "maf": "g/s",
    "map": "kPa",
    "vehicle_speed": "km/h",
    "fuel_trim_short_b1": "%",
    "fuel_trim_long_b1": "%",
    "o2_b1s1": "V",
    "o2_b1s2": "V",
    "battery_voltage": "V",
    "fuel_pressure": "kPa",
    "timing_advance": "°",
}

# Readiness monitor definitions — (name, byte, bit, category)
# Byte B (index 1): continuous monitors — bits 0-2 = supported, bits 4-6 = not-complete
# Byte C (index 2): non-continuous supported bitmask
# Byte D (index 3): non-continuous not-complete bitmask
_CONTINUOUS_MONITORS: list[tuple[str, int]] = [
    ("Misfire", 0),
    ("Fuel System", 1),
    ("Components", 2),
]

_NONCONTINUOUS_MONITORS: list[tuple[str, int]] = [
    ("Catalyst", 0),
    ("Heated Catalyst", 1),
    ("Evap System", 2),
    ("Secondary Air", 3),
    ("A/C Refrigerant", 4),
    ("O2 Sensor", 5),
    ("O2 Sensor Heater", 6),
    ("EGR System", 7),
]


class ECUScanner:
    """Runs full ECU scans and reads DTC history, freeze frames, readiness."""

    def __init__(self, connection: OBDConnection):
        self.conn = connection

    def full_scan(self) -> ScanResult:
        start = time.time()
        dtcs = self.conn.read_dtcs("ALL")
        live = self.conn.read_live_data()
        ecu_map = self._probe_ecus()
        vehicle = self.conn.vehicle
        return ScanResult(
            vehicle_display=vehicle.display_name() if vehicle else "Unknown Vehicle",
            vin=vehicle.vin if vehicle else "UNKNOWN",
            dtcs=dtcs,
            live_snapshot=live,
            ecu_map=ecu_map,
            duration_s=time.time() - start,
        )

    def scan_dtc_history(self) -> DTCHistoryResult:
        """Read all DTC categories: active (Mode 03), pending (Mode 07), permanent (Mode 0A)."""
        active = self.conn.read_dtcs("ALL")
        pending = self.conn.read_pending_dtcs()
        permanent = self.conn.read_permanent_dtcs()
        mil_on, confirmed_count = self.conn.read_mil_status()
        return DTCHistoryResult(
            active=active,
            pending=pending,
            permanent=permanent,
            mil_on=mil_on,
            confirmed_count=confirmed_count,
        )

    def read_freeze_frame(self, dtc_code: str) -> FreezeFrameData:
        """Read Mode 02 freeze frame for a specific DTC code."""
        raw = self.conn.read_freeze_frame(dtc_code)
        return FreezeFrameData(
            dtc_code=dtc_code,
            rpm=raw.get("rpm"),
            vehicle_speed=raw.get("vehicle_speed"),
            coolant_temp=raw.get("coolant_temp"),
            engine_load=raw.get("engine_load"),
            fuel_trim_short_b1=raw.get("fuel_trim_short_b1"),
            throttle_pos=raw.get("throttle_pos"),
            maf=raw.get("maf"),
            map=raw.get("map"),
        )

    def read_readiness_monitors(self) -> ReadinessResult:
        """Parse Mode 01 PID 01 readiness monitor bytes into structured result."""
        raw_bytes = self.conn.read_readiness_raw()
        return self._parse_readiness(raw_bytes)

    def _parse_readiness(self, data: bytes) -> ReadinessResult:
        if len(data) < 4:
            data = data + bytes(4 - len(data))

        byte_a, byte_b, byte_c, byte_d = data[0], data[1], data[2], data[3]

        mil_on = bool(byte_a & 0x80)
        dtc_count = byte_a & 0x7F

        monitors: list[ReadinessMonitor] = []

        # Continuous monitors from byte B
        for name, bit in _CONTINUOUS_MONITORS:
            supported = bool(byte_b & (1 << bit))
            incomplete = bool(byte_b & (1 << (bit + 4)))
            monitors.append(ReadinessMonitor(
                name=name,
                supported=supported,
                complete=supported and not incomplete,
                category="continuous",
            ))

        # Non-continuous monitors from bytes C (supported) and D (not-complete)
        for name, bit in _NONCONTINUOUS_MONITORS:
            supported = bool(byte_c & (1 << bit))
            incomplete = bool(byte_d & (1 << bit))
            monitors.append(ReadinessMonitor(
                name=name,
                supported=supported,
                complete=supported and not incomplete,
                category="non-continuous",
            ))

        return ReadinessResult(
            monitors=monitors,
            mil_on=mil_on,
            confirmed_dtc_count=dtc_count,
        )

    def _probe_ecus(self) -> dict[str, str]:
        """Attempt to contact each known ECU and report status."""
        result: dict[str, str] = {}
        for ecu_short, ecu_full in ECU_MAP.items():
            if self.conn.mode.value == "sim":
                import random
                result[ecu_short] = "OK" if random.random() > 0.3 else "NO RESPONSE"
            else:
                try:
                    resp = self.conn.send_uds(bytes([0x10, 0x01]))
                    result[ecu_short] = "OK" if resp else "NO RESPONSE"
                except Exception:
                    result[ecu_short] = "ERROR"
        return result


class LiveMonitor:
    """
    Background thread that continuously polls live data and detects anomalies.
    Anomaly alerts are placed on an alert_queue for the main thread to consume.
    """

    def __init__(self, connection: OBDConnection):
        self.conn = connection
        self.alert_queue: Queue[AnomalyAlert] = Queue()
        self._current_data: Optional[LiveData] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_anomaly_check = 0.0
        self._suppressed: set[str] = set()  # suppress repeating alerts for N seconds
        self._suppression_until: dict[str, float] = {}

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="LiveMonitor")
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)

    def get_current_data(self) -> Optional[LiveData]:
        return self._current_data

    def drain_alerts(self) -> list[AnomalyAlert]:
        alerts: list[AnomalyAlert] = []
        try:
            while True:
                alerts.append(self.alert_queue.get_nowait())
        except Empty:
            pass
        return alerts

    # ------------------------------------------------------------------

    def _loop(self) -> None:
        while self._running:
            try:
                data = self.conn.read_live_data()
                self._current_data = data
                now = time.time()
                if now - self._last_anomaly_check >= ANOMALY_CHECK_INTERVAL:
                    self._check_anomalies(data)
                    self._last_anomaly_check = now
            except Exception:
                pass
            time.sleep(MONITOR_POLL_INTERVAL)

    def _check_anomalies(self, data: LiveData) -> None:
        snapshot = data.snapshot()
        now = time.time()
        for pid, value in snapshot.items():
            if not isinstance(value, (int, float)):
                continue
            thresholds = ANOMALY_THRESHOLDS.get(pid)
            if not thresholds:
                continue
            unit = PID_UNITS.get(pid, "")
            suppress_key = f"{pid}"
            if now < self._suppression_until.get(suppress_key, 0):
                continue

            alert: Optional[AnomalyAlert] = None

            if value > thresholds["max"]:
                alert = AnomalyAlert(
                    pid_name=pid,
                    value=value,
                    unit=unit,
                    threshold_type="high",
                    message=f"{pid.upper()} critically high: {value:.1f}{unit} (max {thresholds['max']})",
                    severity="critical",
                )
            elif value < thresholds["min"]:
                alert = AnomalyAlert(
                    pid_name=pid,
                    value=value,
                    unit=unit,
                    threshold_type="low",
                    message=f"{pid.upper()} critically low: {value:.1f}{unit} (min {thresholds['min']})",
                    severity="critical",
                )
            elif thresholds.get("warn") is not None and value >= thresholds["warn"]:
                alert = AnomalyAlert(
                    pid_name=pid,
                    value=value,
                    unit=unit,
                    threshold_type="warn",
                    message=f"{pid.upper()} approaching limit: {value:.1f}{unit} (warn ≥ {thresholds['warn']})",
                    severity="warning",
                )

            if alert:
                self.alert_queue.put(alert)
                # Suppress same PID for 60 seconds to avoid spam
                self._suppression_until[suppress_key] = now + 60.0
