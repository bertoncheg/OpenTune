"""
Vehicle Profiles — persist vehicle data across sessions.
Stored in sessions/vehicle_profiles.json.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from config import SESSION_LOG_DIR


@dataclass
class VehicleProfile:
    vin: str
    nickname: str
    make: str
    model: str
    year: int
    engine: str
    last_seen: str       # ISO-8601
    session_count: int = 0
    notes: str = ""


class VehicleProfileManager:
    """Load/save vehicle profiles from sessions/vehicle_profiles.json."""

    def __init__(self, log_dir: str = SESSION_LOG_DIR) -> None:
        self.profiles_file = Path(log_dir) / "vehicle_profiles.json"
        self.profiles_file.parent.mkdir(parents=True, exist_ok=True)
        self._profiles: dict[str, VehicleProfile] = {}
        self._load()

    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self.profiles_file.exists():
            return
        try:
            data = json.loads(self.profiles_file.read_text(encoding="utf-8"))
            for vin, rec in data.items():
                self._profiles[vin] = VehicleProfile(**rec)
        except Exception:
            self._profiles = {}

    def _save(self) -> None:
        data = {vin: asdict(p) for vin, p in self._profiles.items()}
        self.profiles_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------

    def get_all(self) -> list[VehicleProfile]:
        return sorted(self._profiles.values(), key=lambda p: p.last_seen, reverse=True)

    def get(self, vin: str) -> Optional[VehicleProfile]:
        return self._profiles.get(vin)

    def save_profile(
        self,
        vin: str,
        make: str,
        model: str,
        year: int,
        engine: str,
        nickname: str = "",
    ) -> VehicleProfile:
        existing = self._profiles.get(vin)
        if existing:
            existing.last_seen = datetime.now(timezone.utc).isoformat()
            existing.session_count += 1
            if nickname:
                existing.nickname = nickname
            self._save()
            return existing
        profile = VehicleProfile(
            vin=vin,
            nickname=nickname or f"{year} {make} {model}",
            make=make,
            model=model,
            year=year,
            engine=engine,
            last_seen=datetime.now(timezone.utc).isoformat(),
            session_count=1,
        )
        self._profiles[vin] = profile
        self._save()
        return profile

    def delete_profile(self, vin: str) -> bool:
        if vin in self._profiles:
            del self._profiles[vin]
            self._save()
            return True
        return False

    def update_notes(self, vin: str, notes: str) -> None:
        if vin in self._profiles:
            self._profiles[vin].notes = notes
            self._save()
