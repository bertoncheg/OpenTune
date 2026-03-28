"""
Live Process Scanner — 60-second time-series data capture with AI analysis.

Monitors key PIDs every 2 seconds, builds a time-series dataset, then sends
to Claude for anomaly/pattern analysis with streaming output.

Sim mode generates realistic fake data with 3 intentional anomalies:
  1. Elevated and drifting LTFT (lean condition)
  2. Slow O2 switching (sensor response or rich bias)
  3. Brief RPM spike at ~33% through scan (misfire-like event)
"""
from __future__ import annotations

import time
import random
from dataclasses import dataclass, field
from typing import Optional, Iterator, Callable

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from core.connection import OBDConnection, ConnectionMode

SCAN_DURATION_SECONDS: int = 60
POLL_INTERVAL_SECONDS: int = 2

LIVE_SCAN_SYSTEM_PROMPT = (
    "You are an automotive diagnostic AI. Analyze this live data stream from a running vehicle. "
    "Identify: anomalies (values outside normal range), patterns (gradual drift, intermittent spikes), "
    "correlations between sensors. Write a plain-English irregularities report. Use this format:\n"
    "FINDINGS: [numbered list of issues found]\n"
    "NORMAL: [what looks good]\n"
    "PRIORITY: [what to investigate first and why]\n"
    "Be specific — include actual values and normal ranges."
)


@dataclass
class LiveScanSession:
    vehicle_display: str
    vin: str
    start_time: float = field(default_factory=time.time)
    readings: list[dict] = field(default_factory=list)
    analysis_report: str = ""


class LiveProcessScanner:
    """
    Orchestrates a live 60-second process scan and AI analysis.
    Works in both real and sim mode.
    """

    def __init__(self, conn: OBDConnection) -> None:
        self.conn = conn
        self._client = None
        self._api_available = bool(ANTHROPIC_API_KEY)
        if self._api_available:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            except ImportError:
                self._api_available = False

    def check_engine_running(self) -> bool:
        """Return True if engine RPM > 0 (sim always returns True)."""
        if self.conn.mode == ConnectionMode.SIM:
            return True
        data = self.conn.read_live_data()
        return data.rpm > 0

    def collect_scan_data(
        self,
        duration_seconds: int = SCAN_DURATION_SECONDS,
        poll_interval: int = POLL_INTERVAL_SECONDS,
        progress_callback: Optional[Callable[[float, float], None]] = None,
    ) -> list[dict]:
        """
        Poll sensors every poll_interval seconds for duration_seconds total.
        Calls progress_callback(elapsed_s, total_s) before each sleep.
        Returns time-series list of reading dicts.
        """
        readings: list[dict] = []
        n_samples = duration_seconds // poll_interval
        start = time.time()

        for i in range(n_samples):
            elapsed = time.time() - start
            if progress_callback:
                progress_callback(elapsed, float(duration_seconds))

            if self.conn.mode == ConnectionMode.SIM:
                reading = self._sim_reading(i, n_samples)
            else:
                data = self.conn.read_live_data()
                reading = {
                    "timestamp": time.time(),
                    "elapsed_s": elapsed,
                    "rpm": data.rpm,
                    "maf": data.maf,
                    "o2_b1s1": data.o2_b1s1,
                    "o2_b1s2": data.o2_b1s2,
                    "coolant_temp": data.coolant_temp,
                    "intake_air_temp": data.intake_air_temp,
                    "throttle_pos": data.throttle_pos,
                    "fuel_trim_short_b1": data.fuel_trim_short_b1,
                    "fuel_trim_long_b1": data.fuel_trim_long_b1,
                    "battery_voltage": data.battery_voltage,
                    "engine_load": data.engine_load,
                    "misfire_count_cyl1": None,
                    "misfire_count_cyl2": None,
                    "misfire_count_cyl3": None,
                    "misfire_count_cyl4": None,
                }
            readings.append(reading)
            time.sleep(poll_interval)

        return readings

    def _sim_reading(self, index: int, total: int) -> dict:
        """
        Generate sim reading with 3 built-in anomalies for demo/testing:
          Anomaly 1: LTFT drifts +8% → +18% over scan (lean condition)
          Anomaly 2: O2 B1S1 switching slowly — stays rich-biased (65% duty high)
          Anomaly 3: RPM spike at 30-37% through scan (brief misfire event)
        """
        progress = index / max(total - 1, 1)

        # Anomaly 1: LTFT gradual lean drift
        ltft = 8.0 + progress * 10.0 + random.uniform(-0.5, 0.5)

        # Anomaly 2: O2 B1S1 slow switching — 65% high, 35% low
        o2_cycle = (index * 0.55) % 1.0  # ~0.55 cycles per sample = slow
        if o2_cycle < 0.65:
            o2_val = 0.85 + random.uniform(-0.04, 0.04)  # Rich — stays high
        else:
            o2_val = 0.10 + random.uniform(-0.04, 0.04)  # Lean

        # Anomaly 3: RPM spike between 30–37% progress
        in_spike = 0.30 <= progress <= 0.37
        rpm_spike = random.uniform(150, 220) if in_spike else 0.0
        misfire_cyl1 = random.randint(1, 3) if in_spike else 0

        return {
            "timestamp": time.time(),
            "elapsed_s": float(index * POLL_INTERVAL_SECONDS),
            "rpm": max(650, 820.0 + rpm_spike + random.uniform(-15, 15)),
            "maf": 4.3 + random.uniform(-0.15, 0.15),
            "o2_b1s1": max(0.0, min(1.275, o2_val)),
            "o2_b1s2": 0.70 + random.uniform(-0.04, 0.04),
            "coolant_temp": 90.8 + random.uniform(-0.4, 0.4),
            "intake_air_temp": 22.5 + random.uniform(-0.3, 0.3),
            "throttle_pos": 1.2 + random.uniform(-0.2, 0.2),
            "fuel_trim_short_b1": 1.6 + random.uniform(-1.2, 1.2),
            "fuel_trim_long_b1": ltft,
            "battery_voltage": 13.85 + random.uniform(-0.08, 0.08),
            "engine_load": 19.0 + random.uniform(-1.5, 1.5),
            "misfire_count_cyl1": misfire_cyl1,
            "misfire_count_cyl2": 0,
            "misfire_count_cyl3": 0,
            "misfire_count_cyl4": 0,
        }

    def analyze_with_claude(self, readings: list[dict]) -> Iterator[str]:
        """
        Stream AI analysis of the scan data. Yields text chunks as they arrive.
        Falls back to basic local analysis if API is unavailable.
        """
        if not self._api_available or not self._client:
            yield self._basic_analysis(readings)
            return

        summary = self._build_summary(readings)
        prompt = (
            f"Time-series scan data: {len(readings)} samples "
            f"at {POLL_INTERVAL_SECONDS}s intervals ({len(readings) * POLL_INTERVAL_SECONDS}s total)\n\n"
            f"{summary}"
        )

        try:
            with self._client.messages.stream(
                model=CLAUDE_MODEL,
                max_tokens=1000,
                system=LIVE_SCAN_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                for chunk in stream.text_stream:
                    yield chunk
        except Exception as e:
            yield f"\n[Stream error: {e}]\n"
            yield self._basic_analysis(readings)

    def _build_summary(self, readings: list[dict]) -> str:
        """Compact statistical summary of the time-series data for the Claude prompt."""
        if not readings:
            return "No data captured."

        pids = [k for k in readings[0] if k not in ("timestamp", "elapsed_s")]
        lines: list[str] = []

        for pid in pids:
            vals = [r[pid] for r in readings if isinstance(r.get(pid), (int, float))]
            if not vals:
                continue
            min_v = min(vals)
            max_v = max(vals)
            avg_v = sum(vals) / len(vals)
            first, last = vals[0], vals[-1]
            range_v = max_v - min_v
            trend = ""
            if range_v > 0 and abs(last - first) > range_v * 0.25:
                trend = f" | drift {first:.2f}→{last:.2f}"
            lines.append(f"  {pid}: min={min_v:.2f} max={max_v:.2f} avg={avg_v:.2f}{trend}")

        return "\n".join(lines)

    def _basic_analysis(self, readings: list[dict]) -> str:
        """Local fallback analysis — no Claude API needed."""
        findings: list[str] = []
        normal: list[str] = []
        priority = ""

        if not readings:
            return "FINDINGS:\n  No data captured.\n\nNORMAL:\n  N/A\n\nPRIORITY:\n  Check connection."

        # LTFT trend
        ltfts = [r["fuel_trim_long_b1"] for r in readings if isinstance(r.get("fuel_trim_long_b1"), float)]
        if ltfts:
            max_ltft = max(ltfts)
            avg_ltft = sum(ltfts) / len(ltfts)
            if max_ltft > 15:
                findings.append(
                    f"1. Long-term fuel trim elevated (avg {avg_ltft:.1f}%, max {max_ltft:.1f}%) — "
                    f"normal range is ±10%. Lean condition indicated."
                )
                priority = "Investigate lean condition — LTFT >15% suggests fuel delivery issue, vacuum leak, or MAF sensor fault."
            elif abs(avg_ltft) <= 10:
                normal.append(f"Long-term fuel trim within normal range (avg {avg_ltft:.1f}%)")

        # O2 switching pattern
        o2s = [r["o2_b1s1"] for r in readings if isinstance(r.get("o2_b1s1"), float)]
        if o2s:
            avg_o2 = sum(o2s) / len(o2s)
            high_count = sum(1 for v in o2s if v > 0.6)
            high_pct = high_count / len(o2s) * 100
            if high_pct > 60:
                findings.append(
                    f"2. O2 sensor B1S1 high-side bias — {high_pct:.0f}% of readings >0.6V "
                    f"(avg {avg_o2:.2f}V). Normal is ~50/50 switching 0.1–0.9V."
                )
            else:
                normal.append(f"O2 sensor B1S1 switching normally (avg {avg_o2:.2f}V)")

        # RPM stability
        rpms = [r["rpm"] for r in readings if isinstance(r.get("rpm"), float)]
        if rpms:
            rpm_range = max(rpms) - min(rpms)
            if rpm_range > 200:
                findings.append(
                    f"3. RPM instability detected — range {min(rpms):.0f}–{max(rpms):.0f} RPM. "
                    f"Idle should be stable within ±50 RPM."
                )
            else:
                normal.append(f"RPM stable at idle ({min(rpms):.0f}–{max(rpms):.0f} RPM)")

        # Coolant
        coolants = [r["coolant_temp"] for r in readings if isinstance(r.get("coolant_temp"), float)]
        if coolants and max(coolants) < 105:
            normal.append(f"Coolant temp normal ({min(coolants):.1f}–{max(coolants):.1f}°C)")

        # Battery
        batts = [r["battery_voltage"] for r in readings if isinstance(r.get("battery_voltage"), float)]
        if batts:
            avg_batt = sum(batts) / len(batts)
            if 13.0 <= avg_batt <= 14.8:
                normal.append(f"Battery voltage normal (avg {avg_batt:.2f}V)")
            else:
                findings.append(f"4. Battery voltage out of range (avg {avg_batt:.2f}V, normal 13.0–14.8V)")

        if not priority and findings:
            priority = findings[0].split("—")[0].strip(" 1234567890.") + " — address highest-numbered finding first."
        elif not priority:
            priority = "No significant anomalies — vehicle appears to be operating normally."

        report = "FINDINGS:\n"
        if findings:
            report += "\n".join(f"  {f}" for f in findings)
        else:
            report += "  No significant anomalies detected."

        report += "\n\nNORMAL:\n"
        if normal:
            report += "\n".join(f"  • {n}" for n in normal)
        else:
            report += "  (insufficient data for normal assessment)"

        report += f"\n\nPRIORITY:\n  {priority}"
        return report
