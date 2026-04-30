import json
from datetime import datetime
from pathlib import Path
from typing import Any
from sqlalchemy.orm import Session

from app.models import Configuration
from app.utils.calculations import get_production_rates

CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "settings.json"


class ConfigService:
    def __init__(self, db: Session):
        self.db = db
        self._file = self._load_file()

    def _load_file(self) -> dict:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)

    def _save_file(self):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self._file, f, indent=2, ensure_ascii=False)


    def get_production_config(self) -> dict:
        base = self._file["production"].copy()
        overrides = (
            self.db.query(Configuration)
            .filter(Configuration.category == "production")
            .all()
        )
        for rec in overrides:
            short_key = rec.key.replace("production.", "", 1)
            if short_key in base:
                try:
                    base[short_key] = type(base[short_key])(rec.value)
                except (ValueError, TypeError):
                    pass
        return base

    def get_production_rates(self) -> dict:
        cfg = self.get_production_config()
        return get_production_rates(
            cfg["daily_production_target"],
            cfg["effective_hours_per_day"],
        )

    def save_production_config(self, updates: dict):
        for key, value in updates.items():
            full_key = f"production.{key}"
            rec = (
                self.db.query(Configuration)
                .filter(Configuration.key == full_key)
                .first()
            )
            if rec:
                rec.value = str(value)
                rec.updated_at = datetime.now()
            else:
                self.db.add(Configuration(key=full_key, value=str(value), category="production"))
            self._file["production"][key] = value
        self.db.commit()
        self._save_file()

    # ------------------------------------------------------------------ #
    #  Priority / status helpers                                           #
    # ------------------------------------------------------------------ #

    def get_priorities(self) -> dict:
        return self._file.get("priorities", {})

    def get_statuses(self) -> list:
        return self._file.get("statuses", ["Aberto", "Em Andamento", "Resolvido"])

    def get_priority_color(self, priority: str) -> str:
        return self._file["priorities"].get(priority, {}).get("color", "#6B7280")

    def get_priority_sla(self, priority: str) -> int:
        return self._file["priorities"].get(priority, {}).get("sla_minutes", 9999)
