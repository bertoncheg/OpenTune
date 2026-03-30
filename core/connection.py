"""
OBD2 Connection Layer — ELM327 (real) and simulation mode.

Handles:
- ELM327 serial connection via pyserial
- Simulation mode with realistic fake vehicle data
- UDS send/receive primitives
- Live PID reads
- DTC history (Mode 03/07/0A), freeze frame (Mode 02), readiness (Mode 01 PID 01)
- Component activation (Mode 08)
"""
from __future__ import annotations

import platform
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from config import DEFAULT_PORT, DEFAULT_BAUD, CONNECTION_TIMEOUT


def detect_serial_port() -> str:
    """
    Auto-detect the ELM327 serial port by OS.
    Windows: scans COM1–COM20 via pyserial list_ports.
    macOS/Linux: scans /dev/tty.usbserial-* and /dev/ttyUSB*.
    Raises RuntimeError with a helpful message if nothing is found.
    """
    import serial.tools.list_ports  # type: ignore

    os_name = platform.system()

    if os_name == "Windows":
        candidates = [p.device for p in serial.tools.list_ports.comports()
                      if p.device.upper().startswith("COM")]
        if not candidates:
            raise RuntimeError(
                "No ELM327 adapter found.\n"
                "Connect ELM327, check Device Manager → Ports (COM & LPT)"
            )
        return candidates[0]
    else:
        # macOS / Linux
        import glob as _glob
        patterns = ["/dev/tty.usbserial-*", "/dev/ttyUSB*", "/dev/tty.SLAB_USBtoUART*"]
        for pattern in patterns:
            found = _glob.glob(pattern)
            if found:
                return found[0]
        raise RuntimeError(
            "No ELM327 adapter found.\n"
            "Connect ELM327 and check: ls /dev/tty.usbserial-* /dev/ttyUSB*"
        )


class ConnectionMode(str, Enum):
    REAL = "real"
    SIM = "sim"


@dataclass
class VehicleInfo:
    vin: str
    make: str
    model: str
    year: int
    engine: str
    protocol: str = "ISO 15765-4 CAN"

    def display_name(self) -> str:
        return f"{self.year} {self.make} {self.model}"


@dataclass
class LiveData:
    """Snapshot of live vehicle sensor data."""
    rpm: float = 0.0
    coolant_temp: float = 90.0
    intake_air_temp: float = 25.0
    throttle_pos: float = 15.0
    engine_load: float = 20.0
    maf: float = 4.5
    map: float = 101.0
    vehicle_speed: float = 0.0
    fuel_trim_short_b1: float = 1.6
    fuel_trim_long_b1: float = 0.0
    o2_b1s1: float = 0.45
    o2_b1s2: float = 0.7
    fuel_pressure: float = 300.0
    battery_voltage: float = 14.1
    timing_advance: float = 10.0
    timestamp: float = field(default_factory=time.time)

    def snapshot(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if k != "timestamp"}


@dataclass
class DTC:
    code: str
    description: str
    ecu: str
    severity: str  # "critical" | "warning" | "info"
    raw: bytes = field(default_factory=bytes)


# ---------------------------------------------------------------------------
# Simulation vehicle profiles
# ---------------------------------------------------------------------------

# Default sim: 2021 Lexus GX460 — realistic post-suspension-service fault scenario
GX460_PROFILE: dict = {
    "vin": "JTJAM7BX9M5300001",
    "make": "Lexus",
    "model": "GX460",
    "year": 2021,
    "engine": "4.6L V8 1UR-FE",
}

# Active faults matching the spec scenario
GX460_DTCS: list[dict] = [
    {
        "code": "C1840",
        "description": "KDSS Hydraulic Circuit Malfunction — rear pressure below spec, ride height -3.2cm",
        "ecu": "KDSS",
        "severity": "warning",
    },
    {
        "code": "C2116",
        "description": "TPMS Sensor Not Registered — right rear sensor missing",
        "ecu": "TPMS",
        "severity": "info",
    },
]

# Pending DTCs (pre-fault codes, not yet confirmed active)
GX460_PENDING_DTCS: list[dict] = [
    {
        "code": "P0172",
        "description": "System Too Rich (Bank 1) — LTFT trending negative, intermittent",
        "ecu": "ECM",
        "severity": "warning",
    },
]

# Permanent DTCs (require drive cycle to clear — cannot be cleared with Mode 04)
GX460_PERMANENT_DTCS: list[dict] = [
    {
        "code": "C1840",
        "description": "KDSS Hydraulic Circuit Malfunction — stored as permanent",
        "ecu": "KDSS",
        "severity": "warning",
    },
]

# Live data: 195°F coolant = 90.6°C, 72°F intake = 22.2°C, idle RPM, stationary
GX460_LIVE: dict = {
    "rpm": 800.0,
    "coolant_temp": 90.6,
    "intake_air_temp": 22.2,
    "throttle_pos": 0.8,
    "engine_load": 18.0,
    "maf": 4.2,
    "map": 100.0,
    "vehicle_speed": 0.0,
    "fuel_trim_short_b1": 1.6,
    "fuel_trim_long_b1": 0.0,
    "o2_b1s1": 0.44,
    "o2_b1s2": 0.68,
    "battery_voltage": 13.8,
}

SIM_VEHICLES: list[dict] = [
    GX460_PROFILE,   # Index 0 — used as default for --sim
    {
        "vin": "1HGCM82633A123456",
        "make": "Honda",
        "model": "Accord",
        "year": 2019,
        "engine": "2.0L Turbo I4",
    },
    {
        "vin": "WBAJB0C51BC123456",
        "make": "BMW",
        "model": "328i",
        "year": 2020,
        "engine": "2.0L Turbo I4 B48",
    },
    {
        "vin": "1G1YY2D71E5123456",
        "make": "Chevrolet",
        "model": "Corvette",
        "year": 2022,
        "engine": "6.2L V8 LT2",
    },
    {
        "vin": "JN1BJ0HP4EW123456",
        "make": "Nissan",
        "model": "Rogue",
        "year": 2021,
        "engine": "2.5L I4 QR25DE",
    },
    {
        "vin": "1FTFW1ET5EKE12345",
        "make": "Ford",
        "model": "F-150",
        "year": 2023,
        "engine": "3.5L EcoBoost V6",
    },
]

SIM_DTC_POOL: list[dict] = [
    {"code": "P0300", "description": "Random/Multiple Cylinder Misfire Detected", "ecu": "ECM", "severity": "critical"},
    {"code": "P0171", "description": "System Too Lean (Bank 1)", "ecu": "ECM", "severity": "warning"},
    {"code": "P0420", "description": "Catalyst System Efficiency Below Threshold (Bank 1)", "ecu": "ECM", "severity": "warning"},
    {"code": "P0507", "description": "Idle Air Control System RPM High", "ecu": "ECM", "severity": "warning"},
    {"code": "C0035", "description": "Left Front Wheel Speed Sensor Circuit", "ecu": "ABS", "severity": "critical"},
    {"code": "B1000", "description": "ECU Malfunction", "ecu": "BCM", "severity": "info"},
    {"code": "U0100", "description": "Lost Communication with ECM/PCM 'A'", "ecu": "BODY", "severity": "critical"},
    {"code": "P0128", "description": "Coolant Temperature Below Thermostat Regulating Temperature", "ecu": "ECM", "severity": "warning"},
]


class OBDConnection:
    """
    Unified OBD2 connection — wraps real ELM327 serial OR simulation.
    """

    def __init__(self, mode: ConnectionMode, port: str = DEFAULT_PORT, baud: int = DEFAULT_BAUD):
        self.mode = mode
        self.port = port
        self.baud = baud
        self.vehicle: Optional[VehicleInfo] = None
        self._serial = None
        self._live_data = LiveData()
        self._active_dtcs: list[DTC] = []
        self._pending_dtcs: list[DTC] = []
        self._permanent_dtcs: list[DTC] = []
        self._mil_on: bool = False
        self._dtc_count: int = 0
        self._connected = False
        self._sim_tick = 0

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> bool:
        if self.mode == ConnectionMode.SIM:
            return self._connect_sim()
        return self._connect_real()

    def _connect_sim(self) -> bool:
        # Always use GX460 scenario for consistent sim experience
        profile = GX460_PROFILE
        self.vehicle = VehicleInfo(
            vin=profile["vin"],
            make=profile["make"],
            model=profile["model"],
            year=profile["year"],
            engine=profile["engine"],
        )
        # GX460 live data — slight random drift for realism
        ld = GX460_LIVE
        self._live_data = LiveData(
            rpm=ld["rpm"] + random.uniform(-20, 20),
            coolant_temp=ld["coolant_temp"],
            intake_air_temp=ld["intake_air_temp"],
            throttle_pos=ld["throttle_pos"],
            engine_load=ld["engine_load"],
            maf=ld["maf"] + random.uniform(-0.2, 0.2),
            map=ld["map"],
            vehicle_speed=ld["vehicle_speed"],
            fuel_trim_short_b1=ld["fuel_trim_short_b1"],
            fuel_trim_long_b1=ld["fuel_trim_long_b1"],
            o2_b1s1=ld["o2_b1s1"],
            o2_b1s2=ld["o2_b1s2"],
            battery_voltage=ld["battery_voltage"] + random.uniform(-0.1, 0.1),
        )
        # GX460 active faults: C1840 (KDSS) + C2116 (TPMS)
        self._active_dtcs = [
            DTC(code=d["code"], description=d["description"], ecu=d["ecu"], severity=d["severity"])
            for d in GX460_DTCS
        ]
        # Pending DTCs (not yet confirmed)
        self._pending_dtcs = [
            DTC(code=d["code"], description=d["description"], ecu=d["ecu"], severity=d["severity"])
            for d in GX460_PENDING_DTCS
        ]
        # Permanent DTCs (cannot be cleared without drive cycle)
        self._permanent_dtcs = [
            DTC(code=d["code"], description=d["description"], ecu=d["ecu"], severity=d["severity"])
            for d in GX460_PERMANENT_DTCS
        ]
        # MIL off (chassis codes, not engine codes that trigger MIL)
        self._mil_on = False
        self._dtc_count = len(self._active_dtcs)
        self._connected = True
        return True

    def _connect_real(self) -> bool:
        try:
            import serial  # type: ignore
            port = self.port
            if port == DEFAULT_PORT:
                # No explicit port given — try to auto-detect
                try:
                    port = detect_serial_port()
                except RuntimeError as e:
                    print(str(e))
                    return False
            self._serial = serial.Serial(port, self.baud, timeout=CONNECTION_TIMEOUT)
            # ELM327 init sequence
            self._elm_cmd("ATZ")       # reset
            time.sleep(1.5)
            self._elm_cmd("ATE0")      # echo off
            self._elm_cmd("ATL0")      # linefeeds off
            self._elm_cmd("ATH1")      # headers on
            self._elm_cmd("ATSP0")     # auto protocol
            vin_raw = self._elm_cmd("0902")
            self.vehicle = self._parse_vin(vin_raw)
            self._connected = True
            return True
        except Exception:
            return False

    def disconnect(self) -> None:
        if self._serial:
            self._serial.close()
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ------------------------------------------------------------------
    # Live data
    # ------------------------------------------------------------------

    def read_live_data(self) -> LiveData:
        if self.mode == ConnectionMode.SIM:
            self._evolve_sim_data()
            return self._live_data
        return self._read_real_pids()

    def _evolve_sim_data(self) -> None:
        """Drift live data values realistically over time."""
        self._sim_tick += 1
        d = self._live_data
        d.rpm = max(650, d.rpm + random.uniform(-30, 30))
        d.coolant_temp = min(115, d.coolant_temp + random.uniform(-0.1, 0.2))
        d.throttle_pos = max(0, min(100, d.throttle_pos + random.uniform(-1, 1)))
        d.engine_load = max(5, min(100, d.engine_load + random.uniform(-1.5, 1.5)))
        d.maf = max(1, d.maf + random.uniform(-0.2, 0.2))
        d.o2_b1s1 = max(0, min(1.275, d.o2_b1s1 + random.uniform(-0.1, 0.1)))
        d.battery_voltage = max(9, min(16, d.battery_voltage + random.uniform(-0.05, 0.05)))
        d.fuel_trim_short_b1 += random.uniform(-0.5, 0.5)
        d.timestamp = time.time()

    def _read_real_pids(self) -> LiveData:
        """Read PIDs from real ELM327. Minimal implementation."""
        d = LiveData()
        try:
            raw_rpm = self._elm_cmd("010C")
            raw_temp = self._elm_cmd("0105")
            raw_speed = self._elm_cmd("010D")
            raw_throttle = self._elm_cmd("0111")
            raw_load = self._elm_cmd("0104")
            raw_maf = self._elm_cmd("0110")
            d.rpm = self._decode_rpm(raw_rpm)
            d.coolant_temp = self._decode_temp(raw_temp)
            d.vehicle_speed = self._decode_speed(raw_speed)
            d.throttle_pos = self._decode_percent(raw_throttle)
            d.engine_load = self._decode_percent(raw_load)
            d.maf = self._decode_maf(raw_maf)
        except Exception:
            pass
        d.timestamp = time.time()
        return d

    # ------------------------------------------------------------------
    # DTC scanning — Mode 03 (active), 07 (pending), 0A (permanent)
    # ------------------------------------------------------------------

    def read_dtcs(self, ecu: str = "ALL") -> list[DTC]:
        if self.mode == ConnectionMode.SIM:
            if ecu == "ALL":
                return list(self._active_dtcs)
            return [d for d in self._active_dtcs if d.ecu == ecu]
        return self._read_real_dtcs(ecu)

    def read_pending_dtcs(self) -> list[DTC]:
        """Mode 07 — pending DTCs (detected but not yet confirmed)."""
        if self.mode == ConnectionMode.SIM:
            return list(self._pending_dtcs)
        return self._read_mode07_dtcs()

    def read_permanent_dtcs(self) -> list[DTC]:
        """Mode 0A — permanent DTCs (cannot be cleared without drive cycle)."""
        if self.mode == ConnectionMode.SIM:
            return list(self._permanent_dtcs)
        return self._read_mode0a_dtcs()

    def read_mil_status(self) -> tuple[bool, int]:
        """Return (mil_on, confirmed_dtc_count) from Mode 01 PID 01."""
        if self.mode == ConnectionMode.SIM:
            return self._mil_on, self._dtc_count
        data = self._read_mode01_pid01_data()
        mil_on = bool(data[0] & 0x80)
        dtc_count = data[0] & 0x7F
        return mil_on, dtc_count

    def read_readiness_raw(self) -> bytes:
        """Return the 4 raw bytes from Mode 01 PID 01 for readiness monitor parsing."""
        if self.mode == ConnectionMode.SIM:
            return self._sim_readiness_bytes()
        return self._read_mode01_pid01_data()

    def read_freeze_frame(self, dtc_code: str, frame_number: int = 0) -> dict:
        """Mode 02 — freeze frame data captured when dtc_code triggered."""
        if self.mode == ConnectionMode.SIM:
            return self._sim_freeze_frame(dtc_code)
        return self._read_mode02(dtc_code, frame_number)

    def activate_component(self, component_id: int, action: int) -> bool:
        """Mode 08 — request control of on-board system component."""
        if self.mode == ConnectionMode.SIM:
            time.sleep(2.0)
            return True
        return self._send_mode08(component_id, action)

    def _read_real_dtcs(self, ecu: str) -> list[DTC]:
        """Mode 03 DTC read from real adapter."""
        dtcs: list[DTC] = []
        try:
            raw = self._elm_cmd("03")
            for code_raw in self._parse_dtc_response(raw):
                dtcs.append(DTC(code=code_raw, description="(description lookup pending)", ecu=ecu, severity="warning"))
        except Exception:
            pass
        return dtcs

    def _read_mode07_dtcs(self) -> list[DTC]:
        """Mode 07 — pending DTCs from real adapter."""
        dtcs: list[DTC] = []
        try:
            raw = self._elm_cmd("07")
            for code_raw in self._parse_dtc_response(raw):
                dtcs.append(DTC(code=code_raw, description="Pending fault — not yet confirmed", ecu="ECM", severity="warning"))
        except Exception:
            pass
        return dtcs

    def _read_mode0a_dtcs(self) -> list[DTC]:
        """Mode 0A — permanent DTCs from real adapter."""
        dtcs: list[DTC] = []
        try:
            raw = self._elm_cmd("0A")
            for code_raw in self._parse_dtc_response(raw):
                dtcs.append(DTC(code=code_raw, description="Permanent fault — drive cycle required to clear", ecu="ECM", severity="warning"))
        except Exception:
            pass
        return dtcs

    def _read_mode01_pid01_data(self) -> bytes:
        """Read Mode 01 PID 01, return the 4 data bytes (A B C D)."""
        raw = self._elm_cmd("0101")
        try:
            hex_parts = [p for p in raw.upper().split() if len(p) == 2]
            for i in range(len(hex_parts) - 1):
                if hex_parts[i] == "41" and hex_parts[i + 1] == "01":
                    data = hex_parts[i + 2: i + 6]
                    if len(data) >= 4:
                        return bytes(int(x, 16) for x in data[:4])
                    break
        except Exception:
            pass
        return bytes(4)

    def _read_mode02(self, dtc_code: str, frame_number: int = 0) -> dict:
        """Mode 02 — read freeze frame PIDs from real adapter."""
        result: dict = {"dtc_code": dtc_code}
        fn = f"{frame_number:02X}"
        pid_map = {
            "rpm": ("0C", self._decode_rpm),
            "coolant_temp": ("05", self._decode_temp),
            "vehicle_speed": ("0D", self._decode_speed),
            "engine_load": ("04", self._decode_percent),
            "fuel_trim_short_b1": ("06", self._decode_fuel_trim),
            "throttle_pos": ("11", self._decode_percent),
            "maf": ("10", self._decode_maf),
        }
        for field_name, (pid, decoder) in pid_map.items():
            try:
                raw = self._elm_cmd(f"02 {pid} {fn}")
                result[field_name] = decoder(raw)
            except Exception:
                result[field_name] = None
        return result

    def _sim_freeze_frame(self, dtc_code: str) -> dict:
        """Generate realistic freeze frame for sim — different conditions per code type."""
        if dtc_code.startswith("C2") or dtc_code.startswith("B"):
            # Body/TPMS codes — likely triggered at low speed or parking
            return {
                "dtc_code": dtc_code,
                "rpm": 720.0 + random.uniform(-30, 30),
                "vehicle_speed": 0.0,
                "coolant_temp": 85.0 + random.uniform(-2, 2),
                "engine_load": 12.0 + random.uniform(-2, 2),
                "fuel_trim_short_b1": 1.6 + random.uniform(-1.0, 1.0),
                "throttle_pos": 0.4 + random.uniform(-0.2, 0.2),
                "maf": 3.8 + random.uniform(-0.2, 0.2),
                "map": 101.0 + random.uniform(-2, 2),
            }
        else:
            # Chassis/engine codes — driving conditions
            return {
                "dtc_code": dtc_code,
                "rpm": 1850.0 + random.uniform(-100, 100),
                "vehicle_speed": 35.0 + random.uniform(-5, 5),
                "coolant_temp": 92.0 + random.uniform(-1, 2),
                "engine_load": 42.0 + random.uniform(-5, 5),
                "fuel_trim_short_b1": 6.25 + random.uniform(-2, 2),
                "throttle_pos": 28.0 + random.uniform(-3, 3),
                "maf": 18.5 + random.uniform(-1, 1),
                "map": 85.0 + random.uniform(-5, 5),
            }

    def _sim_readiness_bytes(self) -> bytes:
        """
        Simulate Mode 01 PID 01 readiness bytes for GX460.
        Byte A: MIL status + DTC count
        Byte B: Continuous monitors (misfire, fuel sys, components) — supported+ready
        Byte C: Non-continuous monitors — supported bitmask
        Byte D: Non-continuous monitors — not-complete bitmask (1=incomplete)
        """
        # Byte A: bit7=MIL(0=off), bits6-0=DTC count(2)
        byte_a = 0x02  # MIL off, 2 confirmed DTCs
        # Byte B: bits 0-2 = supported, bits 4-6 = not-complete (0=complete)
        # All continuous monitors supported and complete
        byte_b = 0x07  # Bits 0,1,2 set = misfire+fuel+components supported; bits 4,5,6 = 0 = all complete
        # Byte C: non-continuous supported
        # Bit 7=EGR, 6=O2_heater, 5=O2_sensor, 4=A/C, 3=sec_air, 2=evap, 1=htd_cat, 0=catalyst
        byte_c = 0xA5  # 0b10100101 = EGR+O2_sensor+evap+catalyst supported
        # Byte D: non-continuous not-complete (1=incomplete)
        # Evap (bit2) and O2 sensor (bit5) not yet complete
        byte_d = 0x24  # 0b00100100 = evap+O2_sensor not complete
        return bytes([byte_a, byte_b, byte_c, byte_d])

    def _send_mode08(self, component_id: int, action: int) -> bool:
        """Mode 08 — control on-board component via real adapter."""
        try:
            raw = self._elm_cmd(f"08 {component_id:02X} {action:02X}")
            return "48" in raw.upper()
        except Exception:
            return False

    def clear_dtcs(self) -> bool:
        if self.mode == ConnectionMode.SIM:
            self._active_dtcs.clear()
            return True
        try:
            resp = self._elm_cmd("04")
            return "44" in resp
        except Exception:
            return False

    def add_sim_dtc(self, code: str, description: str = "", ecu: str = "ECM", severity: str = "warning") -> None:
        """Add a DTC to the simulation (for testing)."""
        if self.mode == ConnectionMode.SIM:
            self._active_dtcs.append(DTC(code=code, description=description, ecu=ecu, severity=severity))

    # ------------------------------------------------------------------
    # UDS raw primitives
    # ------------------------------------------------------------------

    def send_uds(self, request_bytes: bytes, ecu_addr: int = 0x7E0) -> bytes:
        if self.mode == ConnectionMode.SIM:
            # Generic positive response simulation
            time.sleep(0.05)
            service = request_bytes[0] if request_bytes else 0
            return bytes([service + 0x40]) + request_bytes[1:]
        if self._serial:
            hex_cmd = " ".join(f"{b:02X}" for b in request_bytes)
            raw = self._elm_cmd(hex_cmd)
            return bytes.fromhex(raw.replace(" ", ""))
        return b""

    # ------------------------------------------------------------------
    # ELM327 low-level
    # ------------------------------------------------------------------

    def _elm_cmd(self, cmd: str, timeout: float = 2.0) -> str:
        if not self._serial:
            return ""
        self._serial.write((cmd + "\r").encode())
        time.sleep(0.05)
        end = time.time() + timeout
        buf = ""
        while time.time() < end:
            chunk = self._serial.read(self._serial.in_waiting or 1)
            if chunk:
                buf += chunk.decode(errors="ignore")
                if ">" in buf:
                    break
        return buf.strip().replace(">", "").strip()

    # ------------------------------------------------------------------
    # Decode helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _decode_rpm(raw: str) -> float:
        try:
            parts = raw.split()[-2:]
            a, b = int(parts[0], 16), int(parts[1], 16)
            return ((a * 256) + b) / 4.0
        except Exception:
            return 0.0

    @staticmethod
    def _decode_temp(raw: str) -> float:
        try:
            return int(raw.split()[-1], 16) - 40
        except Exception:
            return 0.0

    @staticmethod
    def _decode_speed(raw: str) -> float:
        try:
            return float(int(raw.split()[-1], 16))
        except Exception:
            return 0.0

    @staticmethod
    def _decode_percent(raw: str) -> float:
        try:
            return int(raw.split()[-1], 16) * 100.0 / 255.0
        except Exception:
            return 0.0

    @staticmethod
    def _decode_maf(raw: str) -> float:
        try:
            parts = raw.split()[-2:]
            a, b = int(parts[0], 16), int(parts[1], 16)
            return ((a * 256) + b) / 100.0
        except Exception:
            return 0.0

    @staticmethod
    def _decode_fuel_trim(raw: str) -> float:
        """Fuel trim: (A - 128) * 100 / 128  → range -100% to +99.2%"""
        try:
            val = int(raw.split()[-1], 16)
            return (val - 128) * 100.0 / 128.0
        except Exception:
            return 0.0

    @staticmethod
    def _parse_vin(raw: str) -> VehicleInfo:
        vin = raw.replace(" ", "").replace("\n", "")[-17:] if len(raw) >= 17 else "UNKNOWN"
        return VehicleInfo(vin=vin, make="Unknown", model="Unknown", year=0, engine="Unknown")

    @staticmethod
    def _parse_dtc_response(raw: str) -> list[str]:
        dtcs = []
        parts = raw.split()
        i = 0
        while i < len(parts) - 1:
            try:
                a = int(parts[i], 16)
                b = int(parts[i + 1], 16)
                if a == 0 and b == 0:
                    break
                prefix = {0: "P", 1: "C", 2: "B", 3: "U"}[(a >> 6) & 0x3]
                code = f"{prefix}{((a & 0x3F) << 8 | b):04X}"
                dtcs.append(code)
                i += 2
            except Exception:
                i += 1
        return dtcs
