"""
OpenTune Knowledge API + Web Dashboard
Run: python -m uvicorn api.main:app --port 8765
"""
from __future__ import annotations

import json
import re as _re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
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

_WEB_DIR = Path(__file__).parent.parent / "web"
app.mount("/static", StaticFiles(directory=str(_WEB_DIR / "static")), name="static")
_templates = Jinja2Templates(directory=str(_WEB_DIR / "templates"))


@app.on_event("startup")
def startup():
    init_db()


# ---------------------------------------------------------------------------
# Pydantic models
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

def _decode(proc: dict) -> dict:
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
    p = _decode(dict(proc))
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
    }


def _db_stats() -> dict:
    procs = get_all_procedures()
    total = len(procs)
    verified = sum(1 for p in procs if (p.get("verified_count") or 0) > 0)
    make_counts: dict[str, int] = {}
    system_counts: dict[str, int] = {}
    for p in procs:
        m = p.get("make") or "Universal"
        make_counts[m] = make_counts.get(m, 0) + 1
        s = p.get("system") or "Other"
        system_counts[s] = system_counts.get(s, 0) + 1
    top_makes = [{"make": k, "count": v} for k, v in sorted(make_counts.items(), key=lambda x: -x[1])[:5]]
    top_systems = [{"system": k, "count": v} for k, v in sorted(system_counts.items(), key=lambda x: -x[1])[:5]]
    return {
        "total_procedures": total,
        "verified_procedures": verified,
        "top_makes": top_makes,
        "top_systems": top_systems,
    }


# ---------------------------------------------------------------------------
# JSON API  (all under /api/)
# ---------------------------------------------------------------------------

@app.get("/api/health")
def api_health():
    procs = get_all_procedures()
    return {"status": "ok", "procedures": len(procs), "version": VERSION}


@app.get("/api/stats")
def api_stats():
    return _db_stats()


@app.get("/api/search")
def api_search(
    q: str = Query(...),
    make: Optional[str] = Query(None),
    system: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=100),
):
    procs = get_all_procedures()
    if make:
        procs = [p for p in procs if (p.get("make") or "").lower() == make.lower()]
    if system:
        procs = [p for p in procs if (p.get("system") or "").lower() == system.lower()]
    results = search_procedures(q, procs or get_all_procedures(), top_k=limit)
    return [_summary(r) for r in results]


@app.get("/api/browse")
def api_browse(
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


@app.get("/api/procedure/{proc_id}")
def api_get_procedure(proc_id: str):
    proc = get_procedure_by_id(proc_id)
    if not proc:
        raise HTTPException(status_code=404, detail="Not found")
    return _decode(proc)


@app.post("/api/submit", status_code=201)
def api_submit(body: SubmitProcedureRequest):
    now = datetime.now(timezone.utc).isoformat()
    proc_id = str(uuid.uuid4())
    proc = {
        "id": proc_id, "title": body.title, "system": body.system,
        "make_family": body.make, "make": body.make, "model": "",
        "year_min": None, "year_max": None,
        "dtc_codes": body.dtc_codes, "symptoms": body.symptoms,
        "steps": body.steps, "outcome_summary": body.outcome_summary,
        "verified_count": 0, "vehicles_confirmed": [], "confidence": 0.0,
        "contributor": body.contributor, "created_at": now, "updated_at": now, "embedding": None,
    }
    upsert_procedure(proc)
    save_embedding(proc_id, embed_text(build_procedure_text(proc)))
    return _decode(get_procedure_by_id(proc_id))


@app.post("/api/verify/{proc_id}")
def api_verify(proc_id: str, body: VerifyRequest):
    updated = increment_verified(proc_id, body.vehicle)
    if not updated:
        raise HTTPException(status_code=404, detail="Not found")
    return _decode(updated)


# ---------------------------------------------------------------------------
# Web Dashboard
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def web_index(request: Request):
    st = _db_stats()
    procs = get_all_procedures()
    recent = [_summary(p) for p in reversed(procs[-6:])]
    return _templates.TemplateResponse(request=request, name="index.html", context={
        "active": "home", "stats": st, "recent": recent,
    })


@app.get("/browse", response_class=HTMLResponse)
def web_browse(request: Request, q: str = "", make: str = "", system: str = ""):
    procs = get_all_procedures()
    all_makes = sorted(set(p.get("make") or "" for p in procs if p.get("make")))
    all_systems = sorted(set(p.get("system") or "" for p in procs if p.get("system")))

    if q:
        pool = [p for p in procs
                if (not make or (p.get("make") or "").lower() == make.lower())
                and (not system or (p.get("system") or "").lower() == system.lower())]
        results = search_procedures(q, pool or procs, top_k=50)
    else:
        results = [p for p in procs
                   if (not make or (p.get("make") or "").lower() == make.lower())
                   and (not system or (p.get("system") or "").lower() == system.lower())]

    return _templates.TemplateResponse(request=request, name="browse.html", context={
        "active": "browse", "procedures": [_summary(p) for p in results],
        "query": q, "makes": all_makes, "systems": all_systems,
        "selected_make": make, "selected_system": system,
    })


@app.get("/procedure/{proc_id}", response_class=HTMLResponse)
def web_procedure(request: Request, proc_id: str):
    proc = get_procedure_by_id(proc_id)
    if not proc:
        return HTMLResponse("<h1>Not found</h1>", status_code=404)
    return _templates.TemplateResponse(request=request, name="procedure.html", context={
        "active": "browse", "procedure": _decode(proc), "verify_success": False,
    })


@app.post("/procedure/{proc_id}/verify", response_class=HTMLResponse)
def web_verify(request: Request, proc_id: str, vehicle: str = Form("")):
    increment_verified(proc_id, vehicle)
    proc = get_procedure_by_id(proc_id)
    if not proc:
        return HTMLResponse("<h1>Not found</h1>", status_code=404)
    return _templates.TemplateResponse(request=request, name="procedure.html", context={
        "active": "browse", "procedure": _decode(proc), "verify_success": True,
    })


@app.get("/submit", response_class=HTMLResponse)
def web_submit_get(request: Request):
    return _templates.TemplateResponse(request=request, name="submit.html", context={
        "active": "submit", "success": False, "error": None,
    })


@app.post("/submit", response_class=HTMLResponse)
def web_submit_post(
    request: Request,
    title: str = Form(""),
    system: str = Form(""),
    make: str = Form(""),
    dtc_codes: str = Form(""),
    symptoms: str = Form(""),
    steps_text: str = Form(""),
    outcome_summary: str = Form(""),
    contributor: str = Form("community"),
):
    if not title or not system or not steps_text:
        return _templates.TemplateResponse(request=request, name="submit.html", context={
            "active": "submit", "success": False,
            "error": "Title, system, and steps are required.",
        })

    def _split(s): return [x.strip() for x in s.split(",") if x.strip()]
    def _parse_steps(raw):
        return [{"action": _re.sub(r"^\d+[\.\)]\s*", "", l.strip())}
                for l in raw.splitlines() if l.strip()]

    now = datetime.now(timezone.utc).isoformat()
    proc_id = str(uuid.uuid4())
    proc = {
        "id": proc_id, "title": title, "system": system,
        "make_family": make, "make": make, "model": "",
        "year_min": None, "year_max": None,
        "dtc_codes": _split(dtc_codes), "symptoms": _split(symptoms),
        "steps": _parse_steps(steps_text), "outcome_summary": outcome_summary,
        "verified_count": 0, "vehicles_confirmed": [], "confidence": 0.0,
        "contributor": contributor or "community",
        "created_at": now, "updated_at": now, "embedding": None,
    }
    upsert_procedure(proc)
    try:
        save_embedding(proc_id, embed_text(build_procedure_text(proc)))
    except Exception:
        pass
    return _templates.TemplateResponse(request=request, name="submit.html", context={
        "active": "submit", "success": True, "error": None,
    })


# ---------------------------------------------------------------------------
# Services Directory  (knowledge engine map)
# ---------------------------------------------------------------------------

_SYSTEM_DESC = {
    "Engine": "Misfires, sensors, timing, fuel delivery, idle issues",
    "Transmission": "Shift behavior, solenoids, fluid codes, TCM faults",
    "Brakes": "ABS, pad wear, caliper, master cylinder, EPB",
    "Suspension": "Ride height, struts, control arms, KDSS, alignment",
    "Electrical": "Wiring, fuses, grounds, CAN bus, module communication",
    "HVAC": "A/C, heater core, blend doors, refrigerant, compressor",
    "Exhaust / Emissions": "Catalytic converter, O2 sensors, EGR, EVAP",
    "Fuel System": "Injectors, pump, pressure, direct injection",
    "Steering": "EPS, rack, angle sensor calibration, SAS reset",
    "Body / Lighting": "BCM, exterior lights, door modules",
    "TPMS": "Sensor registration, relearn, pressure monitoring",
    "ABS / Traction": "Wheel speed sensors, ABS module, stability control",
    "Hybrid / EV": "HV battery, inverter, regen braking, charging",
    "Reference": "PID maps, ECU specs, wiring diagrams, lookup tables",
}


@app.get("/services", response_class=HTMLResponse)
def web_services(request: Request):
    procs = get_all_procedures()

    system_map: dict[str, list] = {}
    for p in procs:
        s = p.get("system") or "Other"
        system_map.setdefault(s, []).append(p)

    categories = []
    for sys_name, sys_procs in sorted(system_map.items(), key=lambda x: -len(x[1])):
        dtcs = []
        for p in sys_procs:
            codes = p.get("dtc_codes")
            if isinstance(codes, str):
                try: codes = json.loads(codes)
                except: codes = []
            dtcs.extend(codes or [])
        dtcs = list(dict.fromkeys(dtcs))
        categories.append({
            "system": sys_name,
            "count": len(sys_procs),
            "description": _SYSTEM_DESC.get(sys_name, "Diagnostic procedures and repair guides"),
            "dtcs": dtcs,
        })

    make_map: dict[str, int] = {}
    for p in procs:
        m = p.get("make") or ""
        if m:
            make_map[m] = make_map.get(m, 0) + 1
    makes = [{"make": k, "count": v} for k, v in sorted(make_map.items(), key=lambda x: -x[1])]

    top_verified = sorted(
        [_summary(p) for p in procs if (p.get("verified_count") or 0) > 0],
        key=lambda x: x.get("verified_count") or 0, reverse=True
    )[:6]
    recent = [_summary(p) for p in reversed(procs[-6:])]

    return _templates.TemplateResponse(request=request, name="services.html", context={
        "active": "services", "categories": categories, "makes": makes,
        "top_verified": top_verified, "recent": recent,
    })
