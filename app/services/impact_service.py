from datetime import datetime
from typing import List
from sqlalchemy.orm import Session

from app.models import Incident
from app.services.config_service import ConfigService
from app.utils.calculations import (
    calculate_duration_minutes,
    calculate_production_loss,
    format_duration,
)


class ImpactService:
    def __init__(self, db: Session):
        self.db = db
        self._cfg = ConfigService(db)

    def calculate_incident_impact(self, incident: Incident) -> dict:
        rates = self._cfg.get_production_rates()
        cfg = self._cfg.get_production_config()
        ended = incident.ended_at or datetime.now()
        duration = calculate_duration_minutes(incident.started_at, ended)
        loss = calculate_production_loss(duration, rates["per_minute"])
        effective_minutes = cfg["effective_hours_per_day"] * 60
        sla = self._cfg.get_priority_sla(incident.priority)
        return {
            "incident_id": incident.incident_id,
            "duration_minutes": round(duration, 2),
            "duration_formatted": format_duration(duration),
            "production_loss": round(loss, 2),
            "impact_pct": round((duration / effective_minutes) * 100, 2),
            "is_open": incident.ended_at is None,
            "sla_violated": duration > sla,
        }

    def get_kpis(self, incidents: List[Incident]) -> dict:
        empty = {
            "total": 0, "open": 0, "in_progress": 0, "resolved": 0,
            "p1": 0, "p2": 0, "p3": 0, "p4": 0,
            "total_downtime_minutes": 0.0,
            "total_downtime_formatted": "0min",
            "total_production_loss": 0.0,
            "avg_duration_minutes": 0.0,
            "mttr_minutes": 0.0,
            "sla_violations": 0,
        }
        if not incidents:
            return empty

        rates = self._cfg.get_production_rates()
        cfg = self._cfg.get_production_config()

        total_minutes = 0.0
        resolved_minutes = 0.0
        resolved_count = 0
        sla_violations = 0

        for inc in incidents:
            ended = inc.ended_at or datetime.now()
            dur = calculate_duration_minutes(inc.started_at, ended)
            total_minutes += dur
            if inc.status == "Resolvido" and inc.ended_at:
                resolved_minutes += dur
                resolved_count += 1
            sla = self._cfg.get_priority_sla(inc.priority)
            if dur > sla:
                sla_violations += 1

        total = len(incidents)
        total_loss = total_minutes * rates["per_minute"]

        return {
            "total": total,
            "open": sum(1 for i in incidents if i.status == "Aberto"),
            "in_progress": sum(1 for i in incidents if i.status == "Em Andamento"),
            "resolved": sum(1 for i in incidents if i.status == "Resolvido"),
            "p1": sum(1 for i in incidents if i.priority == "P1"),
            "p2": sum(1 for i in incidents if i.priority == "P2"),
            "p3": sum(1 for i in incidents if i.priority == "P3"),
            "p4": sum(1 for i in incidents if i.priority == "P4"),
            "total_downtime_minutes": round(total_minutes, 2),
            "total_downtime_formatted": format_duration(total_minutes),
            "total_production_loss": round(total_loss, 2),
            "avg_duration_minutes": round(total_minutes / total, 2) if total else 0.0,
            "mttr_minutes": round(resolved_minutes / resolved_count, 2) if resolved_count else 0.0,
            "sla_violations": sla_violations,
        }

    def recalculate_all(self):
        rates = self._cfg.get_production_rates()
        for inc in self.db.query(Incident).all():
            if inc.ended_at and inc.started_at:
                dur = calculate_duration_minutes(inc.started_at, inc.ended_at)
                inc.duration_minutes = round(dur, 2)
                inc.production_loss = round(dur * rates["per_minute"], 2)
        self.db.commit()
