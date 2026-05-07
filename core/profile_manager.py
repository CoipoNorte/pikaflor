from __future__ import annotations

import json
from pathlib import Path


class ProfileManager:
    def __init__(self) -> None:
        self.base_dir = Path.home() / ".picaflor"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.profile_file = self.base_dir / "profiles.json"

    def _load_all(self) -> dict:
        if not self.profile_file.exists():
            return {}
        try:
            return json.loads(self.profile_file.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            return {}

    def _save_all(self, data: dict) -> None:
        self.profile_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def list_profiles(self) -> list[str]:
        data = self._load_all()
        return sorted(data.keys())

    def get_profile(self, name: str) -> dict | None:
        data = self._load_all()
        return data.get(name)

    def save_profile(self, name: str, payload: dict) -> None:
        data = self._load_all()
        data[name] = payload
        self._save_all(data)

    def delete_profile(self, name: str) -> bool:
        data = self._load_all()
        if name not in data:
            return False
        del data[name]
        self._save_all(data)
        return True