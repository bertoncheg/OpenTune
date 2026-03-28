"""
VehicleResearcher — Self-learning background research engine.

When a vehicle connects with an unknown make or no knowledge-base entry,
this module fires a background Claude API call to research the vehicle,
analyze any DTCs, and write results directly into the knowledge base.
"""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Optional


class VehicleResearcher:
    """
    Background vehicle research engine powered by Claude.

    Usage:
        researcher = VehicleResearcher(api_key, kb_path)
        researcher.start_research(vin, dtcs, live_data)
        # ... later, in the menu loop ...
        if researcher.is_done():
            print(researcher.get_summary())
    """

    def __init__(self, api_key: str, knowledge_base_path: Path) -> None:
        self.api_key = api_key
        self.kb_path = Path(knowledge_base_path)
        self._thread: Optional[threading.Thread] = None
        self.status: str = "idle"          # idle | researching | done | error
        self.result_summary: str = ""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_research(self, vin: str, dtcs: list, live_data: dict) -> None:
        """Start background research thread. No-op if already running."""
        if self.status == "researching":
            return
        self.status = "researching"
        self.result_summary = ""
        self._thread = threading.Thread(
            target=self._research,
            args=(vin, dtcs, live_data),
            daemon=True,
            name="VehicleResearcher",
        )
        self._thread.start()

    def is_done(self) -> bool:
        return self.status in ("done", "error")

    def get_summary(self) -> str:
        return self.result_summary

    # ------------------------------------------------------------------
    # Background worker
    # ------------------------------------------------------------------

    def _research(self, vin: str, dtcs: list, live_data: dict) -> None:
        try:
            import anthropic
        except ImportError:
            self.status = "error"
            self.result_summary = "anthropic package not installed"
            return

        try:
            client = anthropic.Anthropic(api_key=self.api_key)
            prompt = self._build_prompt(vin, dtcs, live_data)

            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            data = self._parse_json(raw)

            if data:
                self._write_knowledge(vin, data)
                self.result_summary = self._build_summary(data)
                self.status = "done"
            else:
                self.status = "error"
                self.result_summary = "Research returned unparseable response"

        except Exception as exc:
            self.status = "error"
            self.result_summary = f"Research failed: {exc}"

    # ------------------------------------------------------------------
    # Prompt builder
    # ------------------------------------------------------------------

    def _build_prompt(self, vin: str, dtcs: list, live_data: dict) -> str:
        dtc_list = ", ".join(str(d) for d in dtcs) if dtcs else "none"
        rpm = live_data.get("rpm", "N/A")
        coolant = live_data.get("coolant_temp", "N/A")
        battery = live_data.get("battery_voltage", "N/A")

        return (
            "You are the OpenTune vehicle research engine. "
            "A vehicle just connected with the following data. "
            "Research this vehicle and return ONLY valid JSON (no markdown, no explanation).\n\n"
            f"VIN: {vin}\n"
            f"DTCs found: {dtc_list}\n"
            f"Live data: RPM {rpm}, Coolant {coolant}C, Battery {battery}V\n\n"
            "Return JSON:\n"
            "{\n"
            '  "vehicle": {"year": int, "make": str, "model": str, "trim": str, "engine": str, "hybrid": bool},\n'
            '  "dtc_analysis": [\n'
            '    {"code": str, "description": str, "system": str, "severity": str,\n'
            '     "likely_cause": str, "recommended_action": str}\n'
            "  ],\n"
            '  "knowledge_base_entry": {\n'
            '    "title": str,\n'
            '    "system": str,\n'
            '    "applicable_makes": [str],\n'
            '    "applicable_models": [str],\n'
            '    "year_range": str,\n'
            '    "symptoms": [str],\n'
            '    "steps": [{"step_number": int, "description": str}],\n'
            '    "outcome_summary": str\n'
            "  }\n"
            "}"
        )

    # ------------------------------------------------------------------
    # JSON parsing (strips markdown fences if present)
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_json(raw: str) -> Optional[dict]:
        text = raw.strip()
        # Strip markdown code fences
        if text.startswith("```"):
            text = re.sub(r"^```[a-z]*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
        try:
            return json.loads(text)
        except Exception:
            # Try to extract the first JSON object
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except Exception:
                    pass
        return None

    # ------------------------------------------------------------------
    # Write results to knowledge base
    # ------------------------------------------------------------------

    def _write_knowledge(self, vin: str, data: dict) -> None:
        self.kb_path.mkdir(parents=True, exist_ok=True)

        # 1. Vehicle-specific profile
        vehicle = data.get("vehicle", {})
        vehicles_dir = self.kb_path / "vehicles"
        vehicles_dir.mkdir(parents=True, exist_ok=True)

        safe_vin = f"{vin[:3]}_{vin[-6:]}" if len(vin) == 17 else vin.replace(" ", "_")
        vehicle_file = vehicles_dir / f"{safe_vin}.json"
        vehicle_payload = {
            "vin_prefix": vin[:3] if len(vin) >= 3 else vin,
            "vin": vin,
            "vehicle": vehicle,
            "dtc_analysis": data.get("dtc_analysis", []),
        }
        try:
            vehicle_file.write_text(
                json.dumps(vehicle_payload, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

        # 2. Knowledge base procedure entry
        kb_entry = data.get("knowledge_base_entry")
        if kb_entry:
            system = kb_entry.get("system", "general").lower().replace(" ", "_")
            title = kb_entry.get("title", "untitled").lower()
            safe_title = re.sub(r"[^a-z0-9_]+", "_", title)[:60].strip("_")

            system_dir = self.kb_path / system
            system_dir.mkdir(parents=True, exist_ok=True)

            entry_file = system_dir / f"{safe_title}.json"
            try:
                entry_file.write_text(
                    json.dumps(kb_entry, indent=2), encoding="utf-8"
                )
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Summary string for UI display
    # ------------------------------------------------------------------

    @staticmethod
    def _build_summary(data: dict) -> str:
        vehicle = data.get("vehicle", {})
        year = vehicle.get("year", "")
        make = vehicle.get("make", "")
        model = vehicle.get("model", "")
        engine = vehicle.get("engine", "")
        dtc_count = len(data.get("dtc_analysis", []))

        parts = [str(p) for p in [year, make, model] if p]
        vehicle_str = " ".join(parts) if parts else "Unknown vehicle"
        if engine:
            vehicle_str += f" ({engine})"

        if dtc_count:
            return f"{vehicle_str} identified — {dtc_count} DTC(s) analyzed"
        return f"{vehicle_str} identified and profiled"
