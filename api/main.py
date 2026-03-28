"""
OpenTune Knowledge API — FastAPI application.
Run: uvicorn api.main:app --reload --port 8765
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from api.db import (
    init_db,
    get_all_procedures,
    get_procedure_by_id,
    increment_verified,
    upsert_procedure,
    save_embedding,
)
from api.embeddings import search_procedures, embed_text, build_procedure_text

VERSION = "0.1.0"

app = FastAPI(title="OpenTune Knowledge API", version=VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class SubmitProcedureRequest(BaseModel):
    title: str
    system: str
    make: Optional[str] = ""
    dtc_codes: list[str] = []
    symptoms: list[str] = []
    steps: list[dict] = []
    outcome_summary: Optional[str] = ""
    contributor: Optional[str] = "community"


class VerifyRequest(BaseModel):
    vehicle: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _decode_json_fields(proc: dict) -> dict:
    """Parse JSON string fields back to Python objects for API responses."""
    for field in ("dtc_codes", "symptoms", "steps", "vehicles_confirmed"):
        val = proc.get(field)
        if isinstance(val, str):
            try:
                proc[field] = json.loads(val)
            except Exception:
                proc[field] = []
    proc.pop("embedding", None)
    return proc


def _summary(proc: dict) -> dict:
    """Return a trimmed summary dict (no steps detail)."""
    p = _decode_json_fields(dict(proc))
    return {
        "id": p.get("id"),
        "title": p.get("title"),
        "system": p.get("system"),
        "make": p.get("make"),
        "model": p.get("model"),
        "year_min": p.get("year_min"),
        "year_max": p.get("year_max"),
        "dtc_codes": p.get("dtc_codes"),
        "symptoms": p.get("symptoms"),
        "outcome_summary": p.get("outcome_summary"),
        "verified_count": p.get("verified_count"),
        "confidence": p.get("confidence"),
        "score": p.get("score"),
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    procs = get_all_procedures()
    return {"status": "ok", "procedures_count": len(procs), "version": VERSION}


@app.get("/search")
def search(
    q: str = Query(..., description="Search query"),
    make: Optional[str] = Query(None),
    system: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=100),
):
    procs = get_all_procedures()

    # Pre-filter by make/system if provided
    if make:
        procs = [p for p in procs if (p.get("make") or "").lower() == make.lower()]
    if system:
        procs = [p for p in procs if (p.get("system") or "").lower() == system.lower()]

    if not procs:
        return []

    results = search_procedures(q, procs, top_k=limit)
    return [_summary(r) for r in results]


@app.get("/procedure/{proc_id}")
def get_procedure(proc_id: str):
    proc = get_procedure_by_id(proc_id)
    if not proc:
        raise HTTPException(status_code=404, detail="Procedure not found")
    return _decode_json_fields(proc)


@app.get("/browse")
def browse(
    make: Optional[str] = Query(None),
    system: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    procs = get_all_procedures()

    if make:
        procs = [p for p in procs if (p.get("make") or "").lower() == make.lower()]
    if system:
        procs = [p for p in procs if (p.get("system") or "").lower() == system.lower()]

    return [_summary(p) for p in procs[:limit]]


@app.post("/submit", status_code=201)
def submit_procedure(body: SubmitProcedureRequest):
    now = datetime.now(timezone.utc).isoformat()
    proc_id = str(uuid.uuid4())

    proc = {
        "id": proc_id,
        "title": body.title,
        "system": body.system,
        "make_family": body.make,
        "make": body.make,
        "model": "",
        "year_min": None,
        "year_max": None,
        "dtc_codes": body.dtc_codes,
        "symptoms": body.symptoms,
        "steps": body.steps,
        "outcome_summary": body.outcome_summary,
        "verified_count": 0,
        "vehicles_confirmed": [],
        "confidence": 0.0,
        "contributor": body.contributor,
        "created_at": now,
        "updated_at": now,
        "embedding": None,
    }

    upsert_procedure(proc)

    text = build_procedure_text(proc)
    emb_bytes = embed_text(text)
    save_embedding(proc_id, emb_bytes)

    result = get_procedure_by_id(proc_id)
    return _decode_json_fields(result)


@app.post("/verify/{proc_id}")
def verify_procedure(proc_id: str, body: VerifyRequest):
    updated = increment_verified(proc_id, body.vehicle)
    if not updated:
        raise HTTPException(status_code=404, detail="Procedure not found")
    return _decode_json_fields(updated)


@app.get("/stats")
def stats():
    procs = get_all_procedures()
    total = len(procs)
    verified = sum(1 for p in procs if (p.get("verified_count") or 0) > 0)

    make_counts: dict[str, int] = {}
    system_counts: dict[str, int] = {}
    for p in procs:
        m = p.get("make") or "unknown"
        make_counts[m] = make_counts.get(m, 0) + 1
        s = p.get("system") or "unknown"
        system_counts[s] = system_counts.get(s, 0) + 1

    top_makes = sorted(make_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    top_systems = sorted(system_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "total_procedures": total,
        "verified_procedures": verified,
        "top_makes": [{"make": k, "count": v} for k, v in top_makes],
        "top_systems": [{"system": k, "count": v} for k, v in top_systems],
    }
