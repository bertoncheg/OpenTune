"""
AI Monitor — Intelligent live data analysis agent.

Listens to the anomaly queue from LiveMonitor and enriches alerts with
Claude's interpretation: what the anomaly means, likely causes, urgency.

Runs in a background thread — pushes enriched alerts to a display queue.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from queue import Queue, Empty
from typing import Optional

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from core.scanner import AnomalyAlert, LiveMonitor


@dataclass
class EnrichedAlert:
    raw: AnomalyAlert
    interpretation: str
    likely_causes: list[str]
    urgency: str  # "immediate" | "soon" | "monitor"
    suggested_action: str


MONITOR_SYSTEM_PROMPT = """You are OpenTune's live sensor analysis agent.
A vehicle sensor anomaly has been detected. Respond with a brief JSON object:
{
  "interpretation": "one sentence: what this reading pattern means mechanically",
  "likely_causes": ["cause 1", "cause 2", "cause 3"],
  "urgency": "immediate | soon | monitor",
  "suggested_action": "specific next step for the mechanic"
}
Be concise. Mechanics are reading this in a terminal while working.
"""


class AIMonitor:
    """
    Enriches raw anomaly alerts with Claude's interpretation.
    Falls back to basic alerts if API is unavailable.
    """

    def __init__(self, live_monitor: LiveMonitor):
        self.live_monitor = live_monitor
        self.enriched_queue: Queue[EnrichedAlert] = Queue()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._api_available = bool(ANTHROPIC_API_KEY)
        self._client = None

        if self._api_available:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            except ImportError:
                self._api_available = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="AIMonitor")
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)

    def drain_enriched(self) -> list[EnrichedAlert]:
        alerts: list[EnrichedAlert] = []
        try:
            while True:
                alerts.append(self.enriched_queue.get_nowait())
        except Empty:
            pass
        return alerts

    def get_snapshot(self) -> dict:
        """Return the latest live data snapshot from the underlying LiveMonitor."""
        data = self.live_monitor.get_current_data()
        return data.snapshot() if data else {}

    def get_anomalies(self) -> list[str]:
        """Return pending enriched anomalies as plain strings (drains the queue)."""
        return [
            f"[{a.urgency.upper()}] {a.raw.pid_name}: {a.interpretation}"
            for a in self.drain_enriched()
        ]

    # ------------------------------------------------------------------

    def _loop(self) -> None:
        while self._running:
            try:
                raw_alerts = self.live_monitor.drain_alerts()
                for alert in raw_alerts:
                    enriched = self._enrich(alert)
                    self.enriched_queue.put(enriched)
            except Exception:
                pass
            time.sleep(1.0)

    def _enrich(self, alert: AnomalyAlert) -> EnrichedAlert:
        if not self._api_available or not self._client:
            return self._basic_enrich(alert)

        prompt = (
            f"Sensor: {alert.pid_name}\n"
            f"Value: {alert.value:.2f} {alert.unit}\n"
            f"Anomaly: {alert.message}\n"
            f"Severity: {alert.severity}"
        )

        try:
            import json
            response = self._client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=300,
                system=MONITOR_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            if raw.startswith("```"):
                lines = raw.split("\n")
                raw = "\n".join(lines[1:])
                if raw.endswith("```"):
                    raw = raw[:-3].strip()
            data = json.loads(raw)
            return EnrichedAlert(
                raw=alert,
                interpretation=data.get("interpretation", alert.message),
                likely_causes=data.get("likely_causes", []),
                urgency=data.get("urgency", "monitor"),
                suggested_action=data.get("suggested_action", "Investigate further"),
            )
        except Exception:
            return self._basic_enrich(alert)

    def _basic_enrich(self, alert: AnomalyAlert) -> EnrichedAlert:
        urgency = "immediate" if alert.severity == "critical" else "monitor"
        return EnrichedAlert(
            raw=alert,
            interpretation=alert.message,
            likely_causes=["Sensor fault", "Mechanical issue", "Wiring problem"],
            urgency=urgency,
            suggested_action=f"Inspect {alert.pid_name} sensor and related circuit",
        )
