"""
SQLite wrapper for the OpenTune Knowledge Base.
DB file: opentune_kb.db at project root.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional

# Project root is one level up from this file
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "opentune_kb.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS procedures (
                id                TEXT PRIMARY KEY,
                title             TEXT,
                system            TEXT,
                make_family       TEXT,
                make              TEXT,
                model             TEXT,
                year_min          INTEGER,
                year_max          INTEGER,
                dtc_codes         TEXT DEFAULT '[]',
                symptoms          TEXT DEFAULT '[]',
                steps             TEXT DEFAULT '[]',
                outcome_summary   TEXT,
                verified_count    INTEGER DEFAULT 0,
                vehicles_confirmed TEXT DEFAULT '[]',
                confidence        REAL DEFAULT 0.0,
                contributor       TEXT DEFAULT 'opentune_seed',
                created_at        TEXT,
                updated_at        TEXT,
                embedding         BLOB
            )
        """)
        conn.commit()


def upsert_procedure(data: dict) -> None:
    fields = [
        "id", "title", "system", "make_family", "make", "model",
        "year_min", "year_max", "dtc_codes", "symptoms", "steps",
        "outcome_summary", "verified_count", "vehicles_confirmed",
        "confidence", "contributor", "created_at", "updated_at", "embedding",
    ]
    # Serialize list/dict fields to JSON strings
    for field in ("dtc_codes", "symptoms", "steps", "vehicles_confirmed"):
        if field in data and not isinstance(data[field], str):
            data[field] = json.dumps(data[field])

    placeholders = ", ".join(f":{f}" for f in fields)
    cols = ", ".join(fields)
    update_set = ", ".join(
        f"{f}=excluded.{f}"
        for f in fields
        if f != "id"
    )
    sql = f"""
        INSERT INTO procedures ({cols}) VALUES ({placeholders})
        ON CONFLICT(id) DO UPDATE SET {update_set}
    """
    row = {f: data.get(f) for f in fields}
    with get_connection() as conn:
        conn.execute(sql, row)
        conn.commit()


def get_all_procedures() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM procedures").fetchall()
    return [dict(r) for r in rows]


def get_procedure_by_id(proc_id: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM procedures WHERE id=?", (proc_id,)
        ).fetchone()
    return dict(row) if row else None


def increment_verified(proc_id: str, vehicle_str: str) -> Optional[dict]:
    proc = get_procedure_by_id(proc_id)
    if not proc:
        return None
    confirmed = json.loads(proc.get("vehicles_confirmed") or "[]")
    if vehicle_str not in confirmed:
        confirmed.append(vehicle_str)
    with get_connection() as conn:
        conn.execute(
            """UPDATE procedures
               SET verified_count = verified_count + 1,
                   vehicles_confirmed = ?,
                   updated_at = datetime('now')
               WHERE id = ?""",
            (json.dumps(confirmed), proc_id),
        )
        conn.commit()
    return get_procedure_by_id(proc_id)


def save_embedding(proc_id: str, embedding_bytes: bytes) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE procedures SET embedding=? WHERE id=?",
            (embedding_bytes, proc_id),
        )
        conn.commit()

# ---------------------------------------------------------------------------
# Services directory
# ---------------------------------------------------------------------------

def init_services_table() -> None:
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS services (
                id           TEXT PRIMARY KEY,
                name         TEXT NOT NULL,
                service_type TEXT DEFAULT 'shop',
                city         TEXT NOT NULL,
                state        TEXT,
                country      TEXT DEFAULT 'US',
                specialties  TEXT,
                description  TEXT,
                website      TEXT,
                phone        TEXT,
                email        TEXT,
                verified     INTEGER DEFAULT 0,
                created_at   TEXT
            )
        """)
        conn.commit()


def get_all_services(service_type: str = None, specialty: str = None) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM services ORDER BY verified DESC, created_at DESC").fetchall()
    results = [dict(r) for r in rows]
    if service_type:
        results = [s for s in results if s.get("service_type") == service_type]
    if specialty:
        results = [s for s in results if specialty.lower() in (s.get("specialties") or "").lower()]
    return results


def upsert_service(data: dict) -> None:
    fields = ["id","name","service_type","city","state","country","specialties","description","website","phone","email","verified","created_at"]
    placeholders = ", ".join(f":{f}" for f in fields)
    cols = ", ".join(fields)
    update_set = ", ".join(f"{f}=excluded.{f}" for f in fields if f != "id")
    sql = f"INSERT INTO services ({cols}) VALUES ({placeholders}) ON CONFLICT(id) DO UPDATE SET {update_set}"
    row = {f: data.get(f) for f in fields}
    with get_connection() as conn:
        conn.execute(sql, row)
        conn.commit()
