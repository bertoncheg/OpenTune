"""
Seed the OpenTune Knowledge Base from knowledge/ JSON files.

Run: python -m api.seed
"""
from __future__ import annotations

import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"

from api.db import init_db, upsert_procedure, save_embedding
from api.embeddings import embed_text, build_procedure_text


def _parse_dtc_codes(symptoms: list) -> list[str]:
    """Extract DTC-like codes (P####, C####, B####, U####) from symptom strings."""
    dtcs = []
    pattern = re.compile(r'\b[PCBU]\d{4}\b', re.IGNORECASE)
    for s in symptoms:
        dtcs.extend(pattern.findall(str(s)))
    return list(set(dtcs))


def _parse_makes_from_vehicles(vehicles: list[str]) -> tuple[str, str, str]:
    """Parse make_family, make, model from strings like '2019 Toyota Camry'."""
    makes = []
    models = []
    for v in vehicles:
        parts = v.strip().split()
        # Skip leading year token
        if parts and parts[0].isdigit():
            parts = parts[1:]
        if len(parts) >= 1:
            makes.append(parts[0])
        if len(parts) >= 2:
            models.append(" ".join(parts[1:]))

    make = makes[0] if makes else ""
    model = models[0] if models else ""
    # make_family = brand family (same as make for now)
    make_family = make
    return make_family, make, model


def _normalize_steps(raw_steps: list) -> list[dict]:
    """Normalize steps to [{step_number, description}]."""
    normalized = []
    for i, s in enumerate(raw_steps, 1):
        if isinstance(s, dict):
            desc = s.get("description") or s.get("desc") or str(s)
            num = s.get("step_number") or s.get("step") or i
            normalized.append({"step_number": int(num), "description": desc})
        else:
            normalized.append({"step_number": i, "description": str(s)})
    return normalized


def parse_knowledge_file(path: Path) -> dict:
    """Flexibly parse a knowledge JSON file into procedure schema."""
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    now = datetime.now(timezone.utc).isoformat()

    # Support both spec schema and actual seed schema
    title = (
        raw.get("title")
        or raw.get("service_type")
        or path.stem.replace("_", " ").title()
    )

    system = raw.get("system") or path.parent.name

    # Symptoms
    symptoms = (
        raw.get("symptoms")
        or raw.get("common_symptoms")
        or []
    )

    # Steps — handle nested technical_solution or flat steps[]
    raw_steps = raw.get("steps") or []
    if not raw_steps:
        tech = raw.get("technical_solution") or {}
        raw_steps = tech.get("procedure_steps") or tech.get("steps") or []

    steps = _normalize_steps(raw_steps)

    # Vehicles
    vehicles_seen = (
        raw.get("vehicles_seen")
        or raw.get("applicable_makes")  # may be a list of make strings
        or []
    )
    make_family, make, model = _parse_makes_from_vehicles(vehicles_seen)

    # Override model if applicable_models present
    applicable_models = raw.get("applicable_models") or []
    if applicable_models:
        model = applicable_models[0] if isinstance(applicable_models[0], str) else model

    # Year range
    year_range = raw.get("year_range") or {}
    year_min = year_range.get("min") if year_range else None
    year_max = year_range.get("max") if year_range else None

    # DTC codes
    dtc_codes = raw.get("dtc_codes") or _parse_dtc_codes(symptoms)

    # Outcome
    outcome_summary = (
        raw.get("outcome")
        or raw.get("outcome_summary")
        or raw.get("physical_solution")
        or ""
    )

    # Confidence from success_rate
    confidence = float(raw.get("success_rate") or raw.get("confidence") or 0.0)

    # Stable ID: use procedure_id from file or generate uuid5 from path
    proc_id = raw.get("procedure_id") or str(
        uuid.uuid5(uuid.NAMESPACE_URL, str(path.relative_to(PROJECT_ROOT)))
    )

    return {
        "id": proc_id,
        "title": title,
        "system": system,
        "make_family": make_family,
        "make": make,
        "model": model,
        "year_min": year_min,
        "year_max": year_max,
        "dtc_codes": dtc_codes,
        "symptoms": symptoms,
        "steps": steps,
        "outcome_summary": outcome_summary,
        "verified_count": int(raw.get("total_cases") or 0),
        "vehicles_confirmed": vehicles_seen,
        "confidence": confidence,
        "contributor": raw.get("contributor") or "opentune_seed",
        "created_at": raw.get("last_updated") or now,
        "updated_at": now,
        "embedding": None,
    }


def seed() -> None:
    print("Initializing database...")
    init_db()

    json_files = list(KNOWLEDGE_DIR.rglob("*.json"))
    if not json_files:
        print(f"No JSON files found in {KNOWLEDGE_DIR}")
        sys.exit(1)

    print(f"Found {len(json_files)} knowledge file(s). Seeding...\n")

    for path in json_files:
        rel = path.relative_to(PROJECT_ROOT)
        try:
            proc = parse_knowledge_file(path)
            upsert_procedure(proc)

            text = build_procedure_text(proc)
            emb_bytes = embed_text(text)
            save_embedding(proc["id"], emb_bytes)

            print(f"  [OK] {rel}  ->  {proc['title']}")
        except Exception as exc:
            print(f"  [ERR] {rel}: {exc}")

    print(f"\nSeed complete. {len(json_files)} procedure(s) loaded.")


if __name__ == "__main__":
    seed()
