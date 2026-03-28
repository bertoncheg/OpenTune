"""
OpenTune — The open-source, AI-native vehicle diagnostic terminal.

Built for independent mechanics who are locked out of the dealer monopoly.
Every other tool is a menu. OpenTune thinks.

When a problem has no known solution, it engineers one from first principles
using live sensor data, DTC correlation, and real-time reasoning.

ProcedureEngineer is the generative core — a two-phase AI diagnostic engine:
  Phase 1 (understand_problem): Reads vehicle state + mechanic's complaint,
           identifies the affected system, highlights key data, asks ONE clarifying question.
  Phase 2 (engineer_solution):  Engineers a precise step-by-step procedure after context
           is complete — from first principles, for working mechanics.

Every session feeds the community knowledge base. Every solution logged is a solution
every mechanic in the world can use tomorrow. This is the community's tool.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Optional, Generator

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from core.connection import DTC, LiveData


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ProblemUnderstanding:
    symptoms: list[str]
    suspected_system: str          # e.g. "KDSS", "TPMS", "ENGINE", "TRANSMISSION"
    confidence: float              # 0.0–1.0
    needs_clarification: bool
    clarifying_question: str       # empty string if needs_clarification is False
    data_highlights: list[str]     # key findings from DTCs and live data
    original_input: str = ""       # raw mechanic input, preserved for Phase 2
    dtcs: list = field(default_factory=list)   # DTC objects for check_known_procedures


@dataclass
class ProcedureStep:
    step_number: int
    description: str
    action_type: str           # "read_pid" | "send_uds" | "instruct_mechanic" | "verify" | "wait"
    action_data: dict          # action-specific params
    expected_result: str = ""
    status: str = "pending"    # "pending" | "ok" | "fail" | "skip"
    result: str = ""


@dataclass
class EngineeredProcedure:
    title: str
    steps: list[ProcedureStep]
    confidence: float
    reasoning: str
    data_requirements: list[str]
    safety_notes: list[str]
    estimated_time: str
    engineered: bool = True   # True = built on the fly, False = from known pattern


# ---------------------------------------------------------------------------
# Phase 1: Understand prompt
# ---------------------------------------------------------------------------

UNDERSTAND_SYSTEM_PROMPT = """You are the OpenTune community diagnostic engine — the intake intelligence of the first open-source, AI-native vehicle diagnostic terminal.

You exist for independent mechanics who are locked out of the dealer monopoly. Your job is to read
the vehicle's actual data and tell the mechanic what it means — not recite menus, not say
"procedure not found." Think, then speak.

Your role: Given a mechanic's description and current vehicle state, READ the data first —
DTCs, live sensors, ECU map — then synthesize what you see into a focused intake response.

If this problem does not match any known DTC registry or documented failure mode, flag it explicitly
in data_highlights. Novel problems are the most valuable sessions for the OpenTune knowledge base —
they become solutions every mechanic in the world can use tomorrow.

Output ONLY valid JSON, no text outside the JSON:

{
  "symptoms": ["list what you observe — be specific, reference actual values and codes"],
  "suspected_system": "which system is most likely affected (e.g. KDSS, TPMS, ENGINE, SUSPENSION)",
  "confidence": 0.0 to 1.0,
  "needs_clarification": true or false,
  "clarifying_question": "ONE targeted question that would meaningfully change the procedure — reference what you observed. Empty string if needs_clarification is false.",
  "data_highlights": ["key findings, e.g.: 'C1840 active — KDSS hydraulic fault', 'Rear ride height -3.2cm below spec', or 'NOVEL: no registry match for this fault signature'"]
}

Rules:
- If the problem is clear from the data, set needs_clarification to false.
- If knowing context (e.g. recent service, mileage, when it started) would change the approach, ask.
- Write as if speaking to a working mechanic — terse, technical, no filler words.
- Always reference actual DTC codes and actual sensor values in your highlights.
- If the fault is novel or undocumented, say so — that honesty serves the community.
"""


# ---------------------------------------------------------------------------
# Phase 2: Engineer prompt
# ---------------------------------------------------------------------------

ENGINEER_SYSTEM_PROMPT = """You are OpenTune — the open-source community diagnostic engine. The first AI-native vehicle diagnostic terminal built for independent mechanics who are locked out of the dealer monopoly.

Your job: given a mechanic's problem description and full vehicle context, engineer a precise
step-by-step diagnostic and repair procedure. You reason from first principles using:
- OBD2 / UDS protocol knowledge
- Live sensor data patterns and fault signatures
- DTC code meanings and known failure modes
- Mechanical and electrical system relationships

When engineering a novel procedure — one where no documented registry match exists — note it
explicitly in the reasoning field. These are the most valuable sessions for the OpenTune
knowledge base. Every novel solution logged is a solution every mechanic in the world can use tomorrow.

Always write steps a working mechanic can follow. No jargon without explanation. No steps that
assume dealer-only equipment or factory scan tools. If a step requires specialized hardware,
name a commonly available alternative or explain the underlying test so the mechanic can adapt.

Output FORMAT — respond with ONLY valid JSON, no markdown, no explanation outside the JSON:

{
  "title": "Short procedure title",
  "confidence": 0.0 to 1.0,
  "reasoning": "Why this approach — fault signature analysis, what data pointed where. Flag 'NOVEL PROCEDURE' if this is undocumented.",
  "estimated_time": "e.g. 15-20 min",
  "data_requirements": ["list of PIDs or data you need to read"],
  "safety_notes": ["any safety considerations"],
  "steps": [
    {
      "step_number": 1,
      "description": "Human-readable step description",
      "action_type": "read_pid | send_uds | instruct_mechanic | verify | wait",
      "action_data": {},
      "expected_result": "what success looks like"
    }
  ]
}

Action types:
- read_pid: {"pid": "coolant_temp"} — read a live data value
- send_uds: {"service": "0x10", "subfunction": "0x03", "data": "hex string"} — UDS command
- instruct_mechanic: {"instruction": "physically do X"} — manual step
- verify: {"condition": "RPM > 600", "pid": "rpm", "operator": ">", "value": 600}
- wait: {"seconds": 5, "reason": "allow system to stabilize"}

Confidence guide:
- 0.9+ : High confidence, clear fault signature matches known failure mode
- 0.7-0.9: Good confidence, procedure should resolve or narrow down the issue
- 0.5-0.7: Moderate — exploratory, gather more data
- <0.5: Low — recommend further physical inspection

Always include safety notes for anything involving fuel, high voltage, or moving parts.
"""


# ---------------------------------------------------------------------------
# Known procedure mapping (mirrors OBDAgent dtc_library.py)
# ---------------------------------------------------------------------------

_DTC_PROCEDURE_MAP: dict[str, str] = {
    # KDSS
    "C1831": "kdss_neutralization", "C1832": "kdss_neutralization",
    "C1833": "kdss_neutralization", "C1834": "kdss_neutralization",
    "C1840": "kdss_neutralization",
    # TPMS
    "C2111": "tpms_programming", "C2112": "tpms_programming",
    "C2113": "tpms_programming", "C2114": "tpms_programming",
    "C2115": "tpms_programming", "C2116": "tpms_programming",
    "C2117": "tpms_programming", "C2118": "tpms_programming",
    # Steering Angle Sensor
    "C1511": "sas_reset", "C1513": "sas_reset",
    "C1514": "sas_reset", "C1524": "sas_reset",
    # EPB
    "C1600": "epb_service", "C1601": "epb_service",
    "C1602": "epb_service", "C1603": "epb_service",
    "C1604": "epb_service", "C1605": "epb_service",
    # Throttle
    "P0120": "throttle_relearn", "P0121": "throttle_relearn",
    "P0505": "throttle_relearn",
}

_SYSTEM_KEYWORD_MAP: dict[str, str] = {
    "kdss": "kdss_neutralization",
    "kinetic dynamic": "kdss_neutralization",
    "tpms": "tpms_programming",
    "tire pressure": "tpms_programming",
    "steering angle": "sas_reset",
    "sas": "sas_reset",
    "epb": "epb_service",
    "electric parking brake": "epb_service",
    "parking brake": "epb_service",
    "throttle": "throttle_relearn",
    "throttle body": "throttle_relearn",
    "air suspension": "air_suspension_calibration",
    "ride height": "air_suspension_calibration",
    "height calibration": "air_suspension_calibration",
}

from pathlib import Path as _Path


def _resolve_obdagent_proc_dir() -> str:
    candidate = _Path(__file__).parent.parent.parent / "Desktop" / "obdagent-toyota" / "procedures"
    if candidate.exists():
        return str(candidate)
    fallback = _Path("C:/Users/berto/OneDrive/Desktop/obdagent-toyota/procedures")
    if fallback.exists():
        return str(fallback)
    return str(candidate)


_OBDAGENT_PROC_DIR = _resolve_obdagent_proc_dir()


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _build_understand_prompt(user_input: str, context: dict) -> str:
    vehicle = context.get("vehicle_display", "Unknown Vehicle")
    vin = context.get("vin", "UNKNOWN")
    dtcs: list[DTC] = context.get("dtcs", [])
    live_data: Optional[LiveData] = context.get("live_data")
    ecu_map: dict = context.get("ecu_map", {})

    dtc_block = "\n".join(
        f"  [{d.severity.upper()}] {d.code} — {d.description} (ECU: {d.ecu})"
        for d in dtcs
    ) or "  None detected"

    live_block = (
        "\n".join(f"  {k}: {v}" for k, v in live_data.snapshot().items())
        if live_data else "  Not available"
    )

    ecu_block = (
        "\n".join(f"  {k}: {v}" for k, v in ecu_map.items()) or "  Not scanned"
    )

    return f"""MECHANIC COMPLAINT: {user_input}

VEHICLE: {vehicle}
VIN: {vin}

ACTIVE DTCs:
{dtc_block}

LIVE DATA SNAPSHOT:
{live_block}

ECU MAP:
{ecu_block}

Analyze what you see and produce a structured intake response.
"""


def _build_engineer_prompt(
    understanding: ProblemUnderstanding,
    context: dict,
    clarification: str = "",
    knowledge_context: str = "",
) -> str:
    vehicle = context.get("vehicle_display", "Unknown Vehicle")
    vin = context.get("vin", "UNKNOWN")
    dtcs: list[DTC] = context.get("dtcs", [])
    live_data: Optional[LiveData] = context.get("live_data")
    ecu_map: dict = context.get("ecu_map", {})

    dtc_block = "\n".join(
        f"  [{d.severity.upper()}] {d.code} — {d.description} (ECU: {d.ecu})"
        for d in dtcs
    ) or "  None detected"

    live_block = (
        "\n".join(f"  {k}: {v}" for k, v in live_data.snapshot().items())
        if live_data else "  Not available"
    )

    clarification_block = (
        f"\nMECHANIC CLARIFICATION: {clarification}\n" if clarification else ""
    )
    knowledge_block = (
        f"\nKNOWLEDGE BASE — PROVEN SOLUTIONS FOR SIMILAR PROBLEMS:\n{knowledge_context}\n"
        if knowledge_context else ""
    )

    return f"""MECHANIC COMPLAINT: {understanding.original_input}
{clarification_block}{knowledge_block}
PROBLEM UNDERSTANDING:
  Suspected system: {understanding.suspected_system}
  Symptoms: {', '.join(understanding.symptoms)}
  Data highlights: {', '.join(understanding.data_highlights)}

VEHICLE: {vehicle}
VIN: {vin}

ACTIVE DTCs:
{dtc_block}

LIVE DATA:
{live_block}

ECU MAP:
{', '.join(f"{k}:{v}" for k, v in ecu_map.items())}

Engineer a precise step-by-step procedure to resolve this.
"""


# ---------------------------------------------------------------------------
# ProcedureEngineer
# ---------------------------------------------------------------------------

class ProcedureEngineer:
    """
    Generative core — two-phase diagnostic AI.

    Phase 1: understand_problem() — reads data, asks clarifying question if needed.
    Phase 2: engineer_solution()  — builds the procedure after context is complete.
    """

    def __init__(self, knowledge_engine=None) -> None:
        self._client = None
        self._api_available = bool(ANTHROPIC_API_KEY)
        self._knowledge = knowledge_engine  # optional KnowledgeEngine instance
        if self._api_available:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            except ImportError:
                self._api_available = False

    @property
    def api_available(self) -> bool:
        return self._api_available

    # ------------------------------------------------------------------
    # Phase 1
    # ------------------------------------------------------------------

    def understand_problem(
        self,
        user_input: str,
        context: dict,
    ) -> ProblemUnderstanding:
        """
        Phase 1: Read vehicle state + complaint, return structured understanding.
        Always reads live data context before deciding if clarification is needed.
        """
        if not self._api_available or not self._client:
            return self._fallback_understanding(user_input, context)

        prompt = _build_understand_prompt(user_input, context)

        try:
            response = self._client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=600,
                system=UNDERSTAND_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            return self._parse_understanding(raw, user_input, context)
        except Exception:
            return self._fallback_understanding(user_input, context)

    # ------------------------------------------------------------------
    # Phase 2
    # ------------------------------------------------------------------

    def engineer_solution(
        self,
        understanding: ProblemUnderstanding,
        context: dict,
        clarification: str = "",
    ) -> EngineeredProcedure:
        """
        Phase 2: Engineer a procedure after problem is fully understood.
        Only called once the mechanic's question (if any) has been answered.
        """
        if not self._api_available or not self._client:
            return self._fallback_procedure(
                understanding.original_input,
                context.get("dtcs", []),
            )

        # Search knowledge base for similar past solutions
        knowledge_context = ""
        if self._knowledge is not None:
            try:
                vehicle_dict = {
                    "year": "", "make": "", "model": "",
                }
                vd = context.get("vehicle_display", "")
                parts = vd.split()
                if len(parts) >= 3:
                    vehicle_dict = {"year": parts[0], "make": parts[1], "model": " ".join(parts[2:])}
                query = f"{understanding.suspected_system} {' '.join(understanding.symptoms[:2])} {understanding.original_input}"
                past_solutions = self._knowledge.search(query, vehicle_dict)
                if past_solutions:
                    lines = []
                    for sol in past_solutions:
                        lines.append(
                            f"  [{sol['service_type']}] (success rate {sol['success_rate']:.0%}, "
                            f"{sol['total_cases']} cases)\n"
                            f"  Symptoms: {', '.join(sol.get('common_symptoms', [])[:3])}\n"
                            f"  Solution: {sol.get('physical_solution', '')[:200]}"
                        )
                    knowledge_context = "\n\n".join(lines)
            except Exception:
                pass

        prompt = _build_engineer_prompt(understanding, context, clarification, knowledge_context)

        try:
            response = self._client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=2048,
                system=ENGINEER_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            return self._parse_procedure(raw)
        except Exception as e:
            return self._fallback_procedure(
                understanding.original_input,
                context.get("dtcs", []),
                error=str(e),
            )

    # ------------------------------------------------------------------
    # Known procedure lookup
    # ------------------------------------------------------------------

    def check_known_procedures(
        self, understanding: ProblemUnderstanding
    ) -> tuple[bool, str]:
        """
        Check if a known OBDAgent procedure exists for this problem.
        Returns (True, procedure_name) if found, else (False, "").
        Checks OBDAgent DTC library first, then system keyword matching.
        """
        # 1. Try DTC library from OBDAgent
        try:
            import sys as _sys
            _sys.path.insert(0, _OBDAGENT_PROC_DIR)
            from dtc_library import DTC_DATABASE  # type: ignore
            for dtc in understanding.dtcs:
                info = DTC_DATABASE.get(dtc.code)
                if info and info.recommended_procedure:
                    proc_file = os.path.join(
                        _OBDAGENT_PROC_DIR, f"{info.recommended_procedure}.py"
                    )
                    if os.path.exists(proc_file):
                        return True, info.recommended_procedure
        except Exception:
            pass

        # 2. Hardcoded DTC map
        for dtc in understanding.dtcs:
            proc_name = _DTC_PROCEDURE_MAP.get(dtc.code)
            if proc_name:
                proc_file = os.path.join(_OBDAGENT_PROC_DIR, f"{proc_name}.py")
                if os.path.exists(proc_file):
                    return True, proc_name

        # 3. System keyword match
        system_lower = understanding.suspected_system.lower()
        for keyword, proc_name in _SYSTEM_KEYWORD_MAP.items():
            if keyword in system_lower:
                proc_file = os.path.join(_OBDAGENT_PROC_DIR, f"{proc_name}.py")
                if os.path.exists(proc_file):
                    return True, proc_name

        return False, ""

    # ------------------------------------------------------------------
    # Streaming (Phase 2, for callers that want streaming output)
    # ------------------------------------------------------------------

    def engineer_solution_streaming(
        self,
        understanding: ProblemUnderstanding,
        context: dict,
        clarification: str = "",
    ) -> Generator[str, None, EngineeredProcedure]:
        """
        Streaming Phase 2 — yields text chunks, returns EngineeredProcedure on StopIteration.
        """
        if not self._api_available or not self._client:
            yield "[API unavailable — using fallback procedure]\n"
            return self._fallback_procedure(
                understanding.original_input, context.get("dtcs", [])
            )

        prompt = _build_engineer_prompt(understanding, context, clarification)
        full_text = ""
        try:
            with self._client.messages.stream(
                model=CLAUDE_MODEL,
                max_tokens=2048,
                system=ENGINEER_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                for chunk in stream.text_stream:
                    full_text += chunk
                    yield chunk
        except Exception as e:
            yield f"\n[Stream error: {e}]\n"
            return self._fallback_procedure(
                understanding.original_input, context.get("dtcs", []), error=str(e)
            )

        return self._parse_procedure(full_text)

    # ------------------------------------------------------------------
    # Parse helpers
    # ------------------------------------------------------------------

    def _parse_understanding(
        self, raw_json: str, user_input: str, context: dict
    ) -> ProblemUnderstanding:
        text = raw_json.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:])
            if text.endswith("```"):
                text = text[:-3].strip()

        data = json.loads(text)
        return ProblemUnderstanding(
            symptoms=data.get("symptoms", []),
            suspected_system=data.get("suspected_system", "UNKNOWN"),
            confidence=float(data.get("confidence", 0.6)),
            needs_clarification=bool(data.get("needs_clarification", False)),
            clarifying_question=data.get("clarifying_question", ""),
            data_highlights=data.get("data_highlights", []),
            original_input=user_input,
            dtcs=context.get("dtcs", []),
        )

    def _parse_procedure(self, raw_json: str) -> EngineeredProcedure:
        text = raw_json.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:])
            if text.endswith("```"):
                text = text[:-3].strip()

        data = json.loads(text)

        steps = [
            ProcedureStep(
                step_number=s["step_number"],
                description=s["description"],
                action_type=s["action_type"],
                action_data=s.get("action_data", {}),
                expected_result=s.get("expected_result", ""),
            )
            for s in data.get("steps", [])
        ]

        return EngineeredProcedure(
            title=data.get("title", "Engineered Diagnostic Procedure"),
            steps=steps,
            confidence=float(data.get("confidence", 0.7)),
            reasoning=data.get("reasoning", ""),
            data_requirements=data.get("data_requirements", []),
            safety_notes=data.get("safety_notes", []),
            estimated_time=data.get("estimated_time", "Unknown"),
            engineered=True,
        )

    # ------------------------------------------------------------------
    # Fallbacks
    # ------------------------------------------------------------------

    def _fallback_understanding(
        self, user_input: str, context: dict
    ) -> ProblemUnderstanding:
        dtcs: list[DTC] = context.get("dtcs", [])
        symptoms = [f"Mechanic reports: {user_input}"]
        highlights: list[str] = []

        for d in dtcs:
            symptoms.append(f"Active DTC: {d.code} — {d.description}")
            highlights.append(f"{d.code}: {d.description}")

        # Guess system from DTC prefix
        suspected_system = "UNKNOWN"
        if dtcs:
            code = dtcs[0].code
            prefix_map = {"C": "CHASSIS", "P": "ENGINE/POWERTRAIN", "B": "BODY", "U": "NETWORK"}
            suspected_system = prefix_map.get(code[0].upper(), "UNKNOWN")

        return ProblemUnderstanding(
            symptoms=symptoms,
            suspected_system=suspected_system,
            confidence=0.4,
            needs_clarification=False,
            clarifying_question="",
            data_highlights=highlights,
            original_input=user_input,
            dtcs=dtcs,
        )

    def _fallback_procedure(
        self,
        user_input: str,
        dtcs: list[DTC],
        error: str = "",
    ) -> EngineeredProcedure:
        steps: list[ProcedureStep] = [
            ProcedureStep(
                step_number=1,
                description="Read all active DTCs and record codes",
                action_type="read_pid",
                action_data={"pid": "dtcs"},
                expected_result="DTC list captured",
            ),
            ProcedureStep(
                step_number=2,
                description="Capture live data snapshot (RPM, coolant temp, MAF, O2)",
                action_type="read_pid",
                action_data={"pid": "all"},
                expected_result="Live data recorded",
            ),
            ProcedureStep(
                step_number=3,
                description="Review DTC definitions and correlate with live data",
                action_type="instruct_mechanic",
                action_data={"instruction": "Cross-reference DTC codes with vehicle service manual"},
                expected_result="Root cause identified",
            ),
        ]
        notes = [f"API unavailable{': ' + error if error else ''}. Running basic investigation."]
        if dtcs:
            notes.append(f"Focus on active codes: {', '.join(d.code for d in dtcs)}")

        return EngineeredProcedure(
            title="Basic Diagnostic Investigation",
            steps=steps,
            confidence=0.4,
            reasoning="Fallback procedure — API not available. Manual investigation required.",
            data_requirements=["all_live_pids", "dtcs"],
            safety_notes=notes,
            estimated_time="10-30 min",
            engineered=False,
        )


