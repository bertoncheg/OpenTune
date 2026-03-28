"""
OpenTune Configuration
"""
import os
import platform
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

OPENTUNE_VERSION = "0.1.0"

# Claude API
ANTHROPIC_API_KEY: str | None = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-opus-4-6")

# Session logging
SESSION_LOG_DIR: str = os.getenv("SESSION_LOG_DIR", str(Path(__file__).parent / "sessions"))

# OBD connection defaults
_default_port = "COM3" if platform.system() == "Windows" else "/dev/ttyUSB0"
DEFAULT_PORT: str = os.getenv("OBD_PORT", _default_port)
DEFAULT_BAUD: int = int(os.getenv("OBD_BAUD", "38400"))
CONNECTION_TIMEOUT: float = float(os.getenv("OBD_TIMEOUT", "10.0"))

# Live monitor intervals (seconds)
MONITOR_POLL_INTERVAL: float = 0.5
ANOMALY_CHECK_INTERVAL: float = 2.0

# Thresholds for anomaly detection
ANOMALY_THRESHOLDS: dict = {
    "coolant_temp": {"min": -40, "max": 120, "warn": 105},
    "rpm": {"min": 0, "max": 8000, "warn": 6500},
    "throttle_pos": {"min": 0, "max": 100, "warn": None},
    "engine_load": {"min": 0, "max": 100, "warn": 95},
    "maf": {"min": 0, "max": 655.35, "warn": None},
    "map": {"min": 0, "max": 255, "warn": None},
    "fuel_pressure": {"min": 0, "max": 765, "warn": None},
    "o2_b1s1": {"min": 0.0, "max": 1.275, "warn": None},
    "battery_voltage": {"min": 9.0, "max": 16.0, "warn": 14.8},
    "intake_air_temp": {"min": -40, "max": 66, "warn": 60},
    "vehicle_speed": {"min": 0, "max": 255, "warn": None},
    "fuel_trim_short_b1": {"min": -100, "max": 99.2, "warn": 25},
    "fuel_trim_long_b1": {"min": -100, "max": 99.2, "warn": 25},
}
