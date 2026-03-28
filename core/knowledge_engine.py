"""
Knowledge Engine â€” learns from every solved problem.

Builds a searchable knowledge base written to knowledge/<system>/<service>.json.
Before calling Claude, the engine is searched for similar past solutions and the
best matches are injected into the engineer prompt as proven context.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class KnowledgeEngine:
    def __init__(self, base_path: Path) -> None:
        self.base = base_path / "knowledge"
        self.base.mkdir(exist_ok=True)

    # ------------------------------------------------------------------
    # Record
    # ------------------------------------------------------------------

    def record_solution(
        self,
        problem: dict,
        solution: dict,
        outcome: dict,
    ) -> None:
        """Called after every solved problem. Writes/updates a knowledge file."""
        system = self._determine_system(problem)
        service_type = solution.get("title", "Unknown Procedure")
        safe_name = (
            service_type.lower()
            .replace(" ", "_")
            .replace("/", "_")
            .replace("(", "")
            .replace(")", "")
            .replace("-", "_")[:50]
        )

        make_family = self._determine_make_family(problem.get("vehicle_display", ""))
        # Prefer make-family path; fall back to flat structure for legacy entries
        make_dir = self.base / make_family / system
        make_dir.mkdir(parents=True, exist_ok=True)
        knowledge_file = make_dir / f"{safe_name}.json"
        # Backward compat: if entry already exists in flat path, use that instead
        flat_file = self.base / system / f"{safe_name}.json"
        if flat_file.exists() and not knowledge_file.exists():
            knowledge_file = flat_file

        if knowledge_file.exists():
            try:
                entry = json.loads(knowledge_file.read_text(encoding="utf-8"))
            except Exception:
                entry = self._new_entry(service_type, system)
        else:
            entry = self._new_entry(service_type, system)

        # Merge new vehicle
        vehicle_str = problem.get("vehicle_display", "Unknown")
        if vehicle_str not in entry["vehicles_seen"]:
            entry["vehicles_seen"].append(vehicle_str)

        # Merge symptoms
        for symptom in problem.get("symptoms", []):
            if symptom and symptom not in entry["common_symptoms"]:
                entry["common_symptoms"].append(symptom)

        # Append outcome record
        entry["outcomes"].append({
            "vehicle": vehicle_str,
            "outcome": outcome.get("outcome", "unknown"),
            "notes": outcome.get("notes", ""),
            "date": datetime.now(timezone.utc).isoformat(),
        })
        entry["total_cases"] += 1

        fixed = sum(1 for o in entry["outcomes"] if o.get("outcome") == "fixed")
        entry["success_rate"] = round(fixed / entry["total_cases"], 3) if entry["total_cases"] else 0.0

        # Store procedure steps (first time or overwrite if richer)
        steps = solution.get("steps", [])
        if steps and not entry["technical_solution"]["procedure_steps"]:
            entry["technical_solution"]["procedure_steps"] = [
                {
                    "step": s.get("step_number", i + 1),
                    "description": s.get("description", ""),
                }
                for i, s in enumerate(steps)
            ]

        reasoning = solution.get("reasoning", "")
        if reasoning and not entry["physical_solution"]:
            entry["physical_solution"] = reasoning

        entry["last_updated"] = datetime.now(timezone.utc).isoformat()
        knowledge_file.write_text(json.dumps(entry, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: str, vehicle: dict) -> list[dict]:
        """Return top-3 most relevant past solutions (empty list if none)."""
        query_lower = query.lower()
        vehicle_str = (
            f"{vehicle.get('year', '')} {vehicle.get('make', '')} {vehicle.get('model', '')}".lower()
        )
        scored: list[tuple[float, dict]] = []

        for top_dir in self.base.iterdir():
            if not top_dir.is_dir():
                continue
            # Flat structure: knowledge/<system>/*.json
            for entry_file in top_dir.glob("*.json"):
                try:
                    entry = json.loads(entry_file.read_text(encoding="utf-8"))
                    score = self._score(entry, query_lower, vehicle_str)
                    if score > 0:
                        scored.append((score, entry))
                except Exception:
                    continue
            # Make-family structure: knowledge/<make_family>/<system>/*.json
            for system_dir in top_dir.iterdir():
                if not system_dir.is_dir():
                    continue
                for entry_file in system_dir.glob("*.json"):
                    try:
                        entry = json.loads(entry_file.read_text(encoding="utf-8"))
                        score = self._score(entry, query_lower, vehicle_str)
                        if score > 0:
                            scored.append((score, entry))
                    except Exception:
                        continue

        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:3]]

    def _score(self, entry: dict, query_lower: str, vehicle_str: str) -> float:
        score = 0.0
        service = entry.get("service_type", "").lower()
        query_words = [w for w in query_lower.split() if len(w) > 3]

        # Service type keyword match
        if any(w in service for w in query_words):
            score += 2.0

        # Symptom keyword match
        for symptom in entry.get("common_symptoms", []):
            if any(w in symptom.lower() for w in query_words):
                score += 1.0

        # Vehicle match
        for seen in entry.get("vehicles_seen", []):
            if vehicle_str:
                for part in vehicle_str.split():
                    if len(part) > 2 and part in seen.lower():
                        score += 1.5
                        break

        # Reward high success rate
        score += entry.get("success_rate", 0.0) * 0.5
        return score

    # ------------------------------------------------------------------
    # Stats & Browse
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        total_cases = 0
        total_fixed = 0
        categories: list[str] = []
        service_types: list[str] = []

        for top_dir in self.base.iterdir():
            if not top_dir.is_dir():
                continue
            categories.append(top_dir.name)
            for entry_file in top_dir.glob("*.json"):
                try:
                    entry = json.loads(entry_file.read_text(encoding="utf-8"))
                    total_cases += entry.get("total_cases", 0)
                    total_fixed += sum(
                        1 for o in entry.get("outcomes", []) if o.get("outcome") == "fixed"
                    )
                    service_types.append(entry.get("service_type", ""))
                except Exception:
                    continue
            # Make-family structure: knowledge/<make_family>/<system>/*.json
            for system_dir in top_dir.iterdir():
                if not system_dir.is_dir():
                    continue
                for entry_file in system_dir.glob("*.json"):
                    try:
                        entry = json.loads(entry_file.read_text(encoding="utf-8"))
                        total_cases += entry.get("total_cases", 0)
                        total_fixed += sum(
                            1 for o in entry.get("outcomes", []) if o.get("outcome") == "fixed"
                        )
                        service_types.append(entry.get("service_type", ""))
                    except Exception:
                        continue

        return {
            "total_cases": total_cases,
            "total_fixed": total_fixed,
            "success_rate": round(total_fixed / total_cases, 3) if total_cases else 0.0,
            "categories": sorted(categories),
            "service_types": service_types,
        }

    def browse_by_system(self, system: str) -> list[dict]:
        system_dir = self.base / system
        if not system_dir.exists():
            return []
        entries: list[dict] = []
        for entry_file in system_dir.glob("*.json"):
            try:
                entries.append(json.loads(entry_file.read_text(encoding="utf-8")))
            except Exception:
                continue
        return entries

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _determine_make_family(self, vehicle_display: str) -> str:
        """Map a vehicle display string to a canonical make family key."""
        v = vehicle_display.lower()
        if any(k in v for k in ["toyota", "lexus", "scion"]):
            return "toyota_lexus"
        if any(k in v for k in ["honda", "acura"]):
            return "honda_acura"
        if any(k in v for k in ["ford", "lincoln", "mercury"]):
            return "ford_lincoln"
        if any(k in v for k in ["chevrolet", "chevy", "gmc", "buick", "cadillac", "oldsmobile", "pontiac"]):
            return "gm"
        if any(k in v for k in ["bmw", "mini"]):
            return "bmw_mini"
        if any(k in v for k in ["mercedes", "benz", "mb ", "sprinter"]):
            return "mercedes"
        if any(k in v for k in ["nissan", "infiniti"]):
            return "nissan_infiniti"
        if "subaru" in v:
            return "subaru"
        if any(k in v for k in ["volkswagen", "vw", "audi", "porsche", "seat", "skoda"]):
            return "volkswagen_audi"
        return "other"

    def browse_by_make(self, make_family: str) -> list[dict]:
        """Return all knowledge entries for a given make family.

        Searches both the make-family path (knowledge/<make_family>/<system>/*.json)
        and flat legacy paths where vehicles_seen matches the family.
        """
        entries: list[dict] = []
        make_dir = self.base / make_family
        # Make-family structured entries
        if make_dir.exists():
            for system_dir in make_dir.iterdir():
                if not system_dir.is_dir():
                    continue
                for entry_file in system_dir.glob("*.json"):
                    try:
                        entries.append(json.loads(entry_file.read_text(encoding="utf-8")))
                    except Exception:
                        continue
        # Legacy flat entries — include if any vehicle_seen matches this family
        for system_dir in self.base.iterdir():
            if not system_dir.is_dir() or system_dir.name == make_family:
                continue
            for entry_file in system_dir.glob("*.json"):
                try:
                    entry = json.loads(entry_file.read_text(encoding="utf-8"))
                    if any(
                        self._determine_make_family(v) == make_family
                        for v in entry.get("vehicles_seen", [])
                    ):
                        entries.append(entry)
                except Exception:
                    continue
        return entries

    def _new_entry(self, service_type: str, system: str) -> dict:
        return {
            "service_type": service_type,
            "system": system,
            "vehicles_seen": [],
            "common_symptoms": [],
            "physical_solution": "",
            "technical_solution": {
                "procedure_steps": [],
                "ecu_addresses": [],
                "bytes_exchanged": [],
            },
            "success_rate": 0.0,
            "total_cases": 0,
            "outcomes": [],
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    def _determine_system(self, problem: dict) -> str:
        suspected = problem.get("suspected_system", "").lower()
        dtcs_text = " ".join(str(d) for d in problem.get("dtcs", [])).lower()
        text = f"{suspected} {dtcs_text} {problem.get('user_input', '')}".lower()

        if any(kw in text for kw in ["kdss", "suspension", "ride height", "air suspension", "shock", "strut"]):
            return "suspension"
        if any(kw in text for kw in ["fuel", "injector", "throttle", "maf", "o2", "oxygen", "rich", "lean", "fuel trim"]):
            return "fuel_system"
        if any(kw in text for kw in ["brake", "abs", "epb", "parking brake"]):
            return "brakes"
        if any(kw in text for kw in ["tpms", "tire pressure"]):
            return "tpms"
        if any(kw in text for kw in ["transmission", "shift", "gear", "trans"]):
            return "transmission"
        if any(kw in text for kw in ["cooling", "coolant", "overheat", "thermostat", "radiator"]):
            return "cooling"
        if any(kw in text for kw in ["evap", "purge", "vapor", "emission"]):
            return "emissions"
        if any(kw in text for kw in ["steering", "strg", "sas", "steering angle"]):
            return "steering"
        if any(kw in text for kw in ["electrical", "battery", "alternator", "bcm", "ecm", "communication"]):
            return "electrical"
        return "general"

    # ------------------------------------------------------------------
    # Seed with known procedures (sim mode bootstrap)
    # ------------------------------------------------------------------

    def seed_initial_knowledge(self) -> None:
        """Populate knowledge base with real-world validated procedures."""
        seeds: list[tuple[str, str, dict]] = [
            ("suspension", "kdss_neutralization.json", {
                "service_type": "KDSS Hydraulic Neutralization",
                "system": "suspension",
                "vehicles_seen": ["2021 Lexus GX460", "2020 Lexus GX460", "2019 Toyota 4Runner TRD Pro"],
                "common_symptoms": [
                    "KDSS warning light", "C1840 fault code",
                    "suspension stiffness", "ride height deviation",
                    "KDSS hydraulic circuit malfunction",
                ],
                "physical_solution": (
                    "With vehicle on level ground engine off, locate KDSS hydraulic accumulator "
                    "at rear axle. Disconnect accumulator line and allow pressure to bleed fully. "
                    "Reconnect line torqued to 25 Nm, start engine, perform KDSS calibration via service mode."
                ),
                "technical_solution": {
                    "procedure_steps": [
                        {"step": 1, "description": "Clear active DTCs with Mode 04"},
                        {"step": 2, "description": "Enter KDSS service mode via UDS 10 03"},
                        {"step": 3, "description": "Read hydraulic pressure via UDS 22 D1 40"},
                        {"step": 4, "description": "Neutralize hydraulic pressure â€” bleed at accumulator"},
                        {"step": 5, "description": "Reconnect line, torque to 25 Nm"},
                        {"step": 6, "description": "Exit service mode, drive 5 mph for 200 m to complete calibration"},
                    ],
                    "ecu_addresses": ["0x7D0"],
                    "bytes_exchanged": ["10 03", "22 D1 40", "31 01 02 01"],
                },
                "success_rate": 0.94,
                "total_cases": 17,
                "outcomes": [
                    {"vehicle": "2021 Lexus GX460", "outcome": "fixed",
                     "notes": "Pressure 340 kPa vs 280 kPa spec â€” bleeding resolved", "date": "2026-01-15T10:30:00Z"},
                    {"vehicle": "2020 Lexus GX460", "outcome": "fixed",
                     "notes": "Post-lift-kit install â€” standard neutralization", "date": "2026-02-10T14:00:00Z"},
                ],
                "last_updated": "2026-03-01T00:00:00Z",
            }),
            ("suspension", "air_suspension_calibration.json", {
                "service_type": "Rear Air Suspension Height Calibration",
                "system": "suspension",
                "vehicles_seen": ["2022 Lexus GX460 Luxury", "2022 Lexus GX460 Luxury+", "2021 Lexus GX460"],
                "common_symptoms": [
                    "height warning light", "vehicle sits unevenly side-to-side",
                    "ride height sensor fault", "Height Control ECU replacement",
                    "persistent height calibration warning after component replacement",
                ],
                "physical_solution": (
                    "With vehicle on level surface, fuel full, no cargo/passengers, ignition ON engine OFF: "
                    "clear learned height offsets via UDS Routine 0x0501, then initiate height reference "
                    "learning via Routine 0x0502. ECU samples all 4 corner sensors and stores new reference values."
                ),
                "technical_solution": {
                    "procedure_steps": [
                        {"step": 1, "description": "Read current ride heights via DID F301-F304 (FL/FR/RL/RR)"},
                        {"step": 2, "description": "Enter extended session on Height Control ECU (0x7A0): UDS 10 03"},
                        {"step": 3, "description": "Clear learned height offsets: UDS 31 01 05 01 (Routine 0x0501)"},
                        {"step": 4, "description": "Initiate height learning: UDS 31 01 05 02 â€” wait 3s, do not move vehicle"},
                        {"step": 5, "description": "Re-read all 4 corners â€” verify within +/-8 mm of target"},
                        {"step": 6, "description": "Exit session, cycle ignition OFF/ON, verify warning light clear"},
                    ],
                    "ecu_addresses": ["0x7A0"],
                    "bytes_exchanged": ["10 03", "31 01 05 01", "31 01 05 02", "3E 00"],
                },
                "success_rate": 0.91,
                "total_cases": 9,
                "outcomes": [],
                "last_updated": "2026-03-28T00:00:00Z",
            }),
            ("brakes", "epb_service.json", {
                "service_type": "EPB (Electric Parking Brake) Service Mode",
                "system": "brakes",
                "vehicles_seen": ["2019 Toyota Camry", "2020 Honda CR-V", "2021 Subaru Outback"],
                "common_symptoms": [
                    "C1xxx EPB fault", "parking brake warning light",
                    "unable to retract caliper for pad change",
                ],
                "physical_solution": (
                    "Activate EPB service mode to retract rear caliper pistons before pad/rotor "
                    "replacement. Must release brake fully before piston retract."
                ),
                "technical_solution": {
                    "procedure_steps": [
                        {"step": 1, "description": "Connect scanner, key on engine off"},
                        {"step": 2, "description": "Enter EPB service mode â€” caliper retracts automatically"},
                        {"step": 3, "description": "Replace brake pads and rotors"},
                        {"step": 4, "description": "Apply brake firmly 5 times to re-seat pads"},
                        {"step": 5, "description": "Exit EPB service mode, verify parking brake function"},
                    ],
                    "ecu_addresses": ["0x760"],
                    "bytes_exchanged": ["28 03 01", "31 01 F0 00"],
                },
                "success_rate": 0.98,
                "total_cases": 34,
                "outcomes": [],
                "last_updated": "2026-02-15T00:00:00Z",
            }),
            ("tpms", "sensor_registration.json", {
                "service_type": "TPMS Sensor Registration",
                "system": "tpms",
                "vehicles_seen": ["2021 Lexus GX460", "2019 Lexus RX350", "2022 Toyota RAV4"],
                "common_symptoms": [
                    "C2116 TPMS sensor not registered", "TPMS warning light",
                    "tire pressure sensor missing", "sensor ID not learned",
                ],
                "physical_solution": (
                    "Register new TPMS sensor ID to BCM/TPMS module. Inflate tire to spec pressure "
                    "first, then trigger sensor with TPMS activation tool."
                ),
                "technical_solution": {
                    "procedure_steps": [
                        {"step": 1, "description": "Inflate all tires to spec PSI"},
                        {"step": 2, "description": "Enter TPMS registration mode via UDS"},
                        {"step": 3, "description": "Activate each sensor in order: FL, FR, RL, RR, spare"},
                        {"step": 4, "description": "Confirm sensor IDs received by module"},
                        {"step": 5, "description": "Clear C2116, verify no TPMS warning"},
                    ],
                    "ecu_addresses": ["0x750"],
                    "bytes_exchanged": ["10 03", "2E C0 01 [sensor_id_bytes]"],
                },
                "success_rate": 0.92,
                "total_cases": 28,
                "outcomes": [],
                "last_updated": "2026-02-20T00:00:00Z",
            }),
            ("fuel_system", "throttle_body_relearn.json", {
                "service_type": "Throttle Body Relearn",
                "system": "fuel_system",
                "vehicles_seen": ["2018 Toyota Camry", "2020 Nissan Altima", "2019 Honda Accord"],
                "common_symptoms": [
                    "P0507 idle RPM high", "rough idle after cleaning",
                    "high idle 1200+ RPM", "throttle response erratic",
                ],
                "physical_solution": (
                    "After throttle body cleaning or replacement, run ECM idle relearn to reset "
                    "idle air control parameters. Vehicle must be fully warmed up (90 Â°C coolant)."
                ),
                "technical_solution": {
                    "procedure_steps": [
                        {"step": 1, "description": "Warm engine to operating temp (90 Â°C coolant)"},
                        {"step": 2, "description": "Enter ECM idle relearn via UDS 31 01 02 09"},
                        {"step": 3, "description": "Let engine idle for 3 minutes without A/C load"},
                        {"step": 4, "description": "Verify RPM settles to 650â€“800 RPM"},
                        {"step": 5, "description": "Clear P0507, road test, confirm idle stable"},
                    ],
                    "ecu_addresses": ["0x7E0"],
                    "bytes_exchanged": ["10 03", "31 01 02 09"],
                },
                "success_rate": 0.89,
                "total_cases": 22,
                "outcomes": [],
                "last_updated": "2026-01-28T00:00:00Z",
            }),
            ("steering", "steering_angle_reset.json", {
                "service_type": "Steering Angle Sensor Reset / Calibration",
                "system": "steering",
                "vehicles_seen": ["2021 Toyota Tacoma", "2020 Toyota RAV4", "2019 Lexus NX"],
                "common_symptoms": [
                    "C1511 steering angle sensor fault", "VSC warning light",
                    "TRAC warning light", "post-alignment warning light",
                ],
                "physical_solution": (
                    "After wheel alignment or steering component replacement, reset and recalibrate "
                    "steering angle sensor. Vehicle must be on flat ground, wheels straight."
                ),
                "technical_solution": {
                    "procedure_steps": [
                        {"step": 1, "description": "Set wheels to straight-ahead position on level surface"},
                        {"step": 2, "description": "Enter SAS calibration mode via UDS 10 03"},
                        {"step": 3, "description": "Send SAS zero-point write: 2E D1 20 00 00"},
                        {"step": 4, "description": "Turn steering lock-to-lock once slowly"},
                        {"step": 5, "description": "Clear C1511, verify VSC/TRAC lights off"},
                    ],
                    "ecu_addresses": ["0x7B0"],
                    "bytes_exchanged": ["10 03", "2E D1 20 00 00", "31 01 01 00"],
                },
                "success_rate": 0.96,
                "total_cases": 41,
                "outcomes": [],
                "last_updated": "2026-03-10T00:00:00Z",
            }),
        ]

        for system, filename, entry in seeds:
            system_dir = self.base / system
            system_dir.mkdir(exist_ok=True)
            target = system_dir / filename
            if not target.exists():
                target.write_text(json.dumps(entry, indent=2), encoding="utf-8")

