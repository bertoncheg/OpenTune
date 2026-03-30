"""
OpenTune Knowledge API â€” FastAPI application.
Run: uvicorn api.main:app --reload --port 8765
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
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


# ---------------------------------------------------------------------------
# Web Dashboard (Jinja2 templates)
# ---------------------------------------------------------------------------
import re as _re
from fastapi import Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

_WEB_DIR = Path(__file__).parent.parent / "web"
app.mount("/static", StaticFiles(directory=str(_WEB_DIR / "static")), name="static")
_templates = Jinja2Templates(directory=str(_WEB_DIR / "templates"))

from api.db import get_all_services, upsert_service, init_services_table

import uuid as _uuid
from datetime import datetime as _dt, timezone as _tz


@app.on_event("startup")
def startup_services():
    init_services_table()


def _nav(page: str) -> str:
    return page


# â”€â”€ Home / Dashboard â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.get("/", response_class=HTMLResponse)
def web_index(request: Request):
    st = stats()
    procs = get_all_procedures()
    services = get_all_services()
    st["total_services"] = len(services)
    recent = [_summary(p) for p in procs[-6:]][::-1]
    return _templates.TemplateResponse(request=request, name="index.html", context={"active": "home",
        "stats": st, "recent": recent
    })


# â”€â”€ Browse / Search â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.get("/browse", response_class=HTMLResponse)
def web_browse(request: Request, q: str = "", make: str = "", system: str = ""):
    procs = get_all_procedures()
    all_makes = sorted(set(p.get("make") or "" for p in procs if p.get("make")))
    all_systems = sorted(set(p.get("system") or "" for p in procs if p.get("system")))

    if q:
        filtered = [p for p in procs if (make == "" or (p.get("make") or "").lower() == make.lower()) and (system == "" or (p.get("system") or "").lower() == system.lower())]
        results = search_procedures(q, filtered if filtered else procs, top_k=50)
    else:
        results = [p for p in procs if (make == "" or (p.get("make") or "").lower() == make.lower()) and (system == "" or (p.get("system") or "").lower() == system.lower())]

    summaries = [_summary(p) for p in results]
    return _templates.TemplateResponse(request=request, name="browse.html", context={"active": "browse",
        "procedures": summaries,
        "query": q, "makes": all_makes, "systems": all_systems,
        "selected_make": make, "selected_system": system
    })


# â”€â”€ Procedure Detail â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.get("/procedure/{proc_id}", response_class=HTMLResponse)
def web_procedure(request: Request, proc_id: str):
    proc = get_procedure_by_id(proc_id)
    if not proc:
        return HTMLResponse("<h1>Not found</h1>", status_code=404)
    proc = _decode_json_fields(proc)
    return _templates.TemplateResponse(request=request, name="procedure.html", context={"active": "browse",
        "procedure": proc, "verify_success": False
    })


@app.post("/procedure/{proc_id}/verify", response_class=HTMLResponse)
def web_verify(request: Request, proc_id: str, vehicle: str = Form("")):
    increment_verified(proc_id, vehicle)
    proc = get_procedure_by_id(proc_id)
    if not proc:
        return HTMLResponse("<h1>Not found</h1>", status_code=404)
    proc = _decode_json_fields(proc)
    return _templates.TemplateResponse(request=request, name="procedure.html", context={"active": "browse",
        "procedure": proc, "verify_success": True
    })


# â”€â”€ Submit Procedure â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.get("/submit", response_class=HTMLResponse)
def web_submit_get(request: Request):
    return _templates.TemplateResponse(request=request, name="submit.html", context={"active": "submit",
        "success": False, "error": None
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
        return _templates.TemplateResponse(request=request, name="submit.html", context={"active": "submit",
            "success": False, "error": "Title, system, and steps are required."
        })

    def _split(s):
        return [x.strip() for x in s.split(",") if x.strip()]

    def _parse_steps(raw):
        lines = [l.strip() for l in raw.splitlines() if l.strip()]
        steps = []
        for line in lines:
            clean = _re.sub(r"^\d+[\.\)]\s*", "", line)
            steps.append({"action": clean})
        return steps

    now = _dt.now(_tz.utc).isoformat()
    proc_id = str(_uuid.uuid4())
    proc = {
        "id": proc_id, "title": title, "system": system,
        "make_family": make, "make": make, "model": "",
        "year_min": None, "year_max": None,
        "dtc_codes": _split(dtc_codes),
        "symptoms": _split(symptoms),
        "steps": _parse_steps(steps_text),
        "outcome_summary": outcome_summary,
        "verified_count": 0, "vehicles_confirmed": [],
        "confidence": 0.0,
        "contributor": contributor or "community",
        "created_at": now, "updated_at": now, "embedding": None,
    }
    upsert_procedure(proc)
    try:
        from api.embeddings import build_procedure_text, embed_text
        from api.db import save_embedding
        save_embedding(proc_id, embed_text(build_procedure_text(proc)))
    except Exception:
        pass
    return _templates.TemplateResponse(request=request, name="submit.html", context={"active": "submit",
        "success": True, "error": None
    })


# â”€â”€ Services Directory â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.get("/services", response_class=HTMLResponse)
def web_services(request: Request, q: str = "", specialty: str = "", service_type: str = ""):
    svcs = get_all_services(service_type=service_type or None, specialty=specialty or None)
    if q:
        ql = q.lower()
        svcs = [s for s in svcs if ql in (s.get("name") or "").lower()
                or ql in (s.get("city") or "").lower()
                or ql in (s.get("description") or "").lower()
                or ql in (s.get("specialties") or "").lower()]
    all_specialties = sorted(set(
        sp.strip()
        for s in get_all_services()
        for sp in (s.get("specialties") or "").split(",")
        if sp.strip()
    ))
    return _templates.TemplateResponse(request=request, name="services.html", context={"active": "services",
        "services": svcs, "query": q,
        "specialties": all_specialties,
        "selected_specialty": specialty,
        "selected_type": service_type,
    })


@app.get("/services/register", response_class=HTMLResponse)
def web_register_get(request: Request):
    return _templates.TemplateResponse(request=request, name="register_service.html", context={"active": "services",
        "success": False, "error": None
    })


@app.post("/services/register", response_class=HTMLResponse)
def web_register_post(
    request: Request,
    name: str = Form(""),
    service_type: str = Form("shop"),
    city: str = Form(""),
    state: str = Form(""),
    country: str = Form("US"),
    specialties: str = Form(""),
    description: str = Form(""),
    website: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
):
    if not name or not city:
        return _templates.TemplateResponse(request=request, name="register_service.html", context={"active": "services",
            "success": False, "error": "Name and city are required."
        })
    svc = {
        "id": str(_uuid.uuid4()), "name": name,
        "service_type": service_type, "city": city, "state": state,
        "country": country or "US", "specialties": specialties,
        "description": description, "website": website,
        "phone": phone, "email": email, "verified": 0,
        "created_at": _dt.now(_tz.utc).isoformat(),
    }
    upsert_service(svc)
    return _templates.TemplateResponse(request=request, name="register_service.html", context={"active": "services",
        "success": True, "error": None
    })


# â”€â”€ API stats endpoint alias â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.get("/api/stats")
def api_stats():
    return stats()



