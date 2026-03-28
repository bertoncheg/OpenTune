"""
Session Logger — JSONL dataset funnel.

Every diagnostic session is logged as a line of JSON to sessions/YYYYMMDD.jsonl
This file IS the dataset that can feed future OBDAgent training.

Schema per line:
{
  "timestamp": "ISO-8601",
  "session_id": "uuid4",
  "vin": "...",
  "vehicle": "YYYY Make Model",
  "user_input": "mechanic's plain English problem",
  "procedure_engineered": true/false,
  "procedure_title": "...",
  "steps_executed": [ { "step": 1, "description": "...", "status": "ok|fail|skip" } ],
  "outcome": "fixed | not_fixed | unknown",
  "notes": "...",
  "live_data_snapshot": { ... },
  "dtcs": [ {"code": "P0300", "description": "...", "ecu": "ECM"} ],
  "ai_reasoning": "...",
  "confidence": 0.0-1.0
}

Procedure history is stored in sessions/procedure_history.jsonl:
{
  "timestamp": "ISO-8601",
  "vin": "...",
  "vehicle": "...",
  "procedure": "...",
  "outcome": "fixed|not_fixed|unknown",
  "notes": "...",
  "duration_seconds": 0
}
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from config import SESSION_LOG_DIR
from core.connection import DTC, LiveData


class SessionLogger:
    def __init__(self, log_dir: str = SESSION_LOG_DIR):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = str(uuid.uuid4())
        self._log_file = self.log_dir / f"{datetime.now(timezone.utc).strftime('%Y%m%d')}.jsonl"

    def log(
        self,
        *,
        vin: str,
        vehicle: str,
        user_input: str,
        procedure_engineered: bool,
        procedure_title: str,
        steps_executed: list[dict],
        outcome: str,
        notes: str = "",
        live_data_snapshot: Optional[dict] = None,
        dtcs: Optional[list[DTC]] = None,
        ai_reasoning: str = "",
        confidence: float = 0.0,
    ) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": self.session_id,
            "vin": vin,
            "vehicle": vehicle,
            "user_input": user_input,
            "procedure_engineered": procedure_engineered,
            "procedure_title": procedure_title,
            "steps_executed": steps_executed,
            "outcome": outcome,
            "notes": notes,
            "live_data_snapshot": live_data_snapshot or {},
            "dtcs": [
                {"code": d.code, "description": d.description, "ecu": d.ecu}
                for d in (dtcs or [])
            ],
            "ai_reasoning": ai_reasoning,
            "confidence": confidence,
        }
        with open(self._log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    def log_file_path(self) -> str:
        return str(self._log_file)

    def log_procedure(
        self,
        *,
        vin: str,
        vehicle: str,
        procedure: str,
        outcome: str,
        notes: str = "",
        duration_seconds: int = 0,
    ) -> None:
        """Append one record to sessions/procedure_history.jsonl."""
        proc_log = self.log_dir / "procedure_history.jsonl"
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "vin": vin,
            "vehicle": vehicle,
            "procedure": procedure,
            "outcome": outcome,
            "notes": notes,
            "duration_seconds": duration_seconds,
        }
        with open(proc_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    def read_procedure_history(self, vin: Optional[str] = None) -> list[dict]:
        """Read procedure history, optionally filtered by VIN."""
        proc_log = self.log_dir / "procedure_history.jsonl"
        if not proc_log.exists():
            return []
        records: list[dict] = []
        try:
            for line in proc_log.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    rec = json.loads(line)
                    if vin is None or rec.get("vin") == vin:
                        records.append(rec)
        except Exception:
            pass
        return records
