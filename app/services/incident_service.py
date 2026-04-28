from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload

from app.models import Incident, System, IncidentType
from app.services.config_service import ConfigService
from app.utils.calculations import calculate_duration_minutes, calculate_production_loss


class IncidentService:
    def __init__(self, db: Session):
        self.db = db
        self._cfg = ConfigService(db)

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _next_incident_id(self) -> str:
        last = self.db.query(Incident).order_by(Incident.id.desc()).first()
        if last and last.incident_id:
            try:
                num = int(last.incident_id.split("-")[1]) + 1
            except (IndexError, ValueError):
                num = self.db.query(Incident).count() + 1
        else:
            num = 1
        return f"INC-{num:04d}"

    def _update_impact(self, incident: Incident):
        if incident.ended_at and incident.started_at:
            rates = self._cfg.get_production_rates()
            duration = calculate_duration_minutes(incident.started_at, incident.ended_at)
            incident.duration_minutes = round(duration, 2)
            incident.production_loss = calculate_production_loss(duration, rates["per_minute"])

    def _base_query(self):
        return self.db.query(Incident).options(
            joinedload(Incident.system),
            joinedload(Incident.incident_type),
        )

    # ------------------------------------------------------------------ #
    #  Incident CRUD                                                       #
    # ------------------------------------------------------------------ #

    def create(self, data: dict) -> Incident:
        incident = Incident(incident_id=self._next_incident_id(), **data)
        self._update_impact(incident)
        self.db.add(incident)
        self.db.commit()
        self.db.refresh(incident)
        return incident

    def update(self, incident_id: str, data: dict) -> Optional[Incident]:
        incident = self.get_by_id(incident_id)
        if not incident:
            return None
        for key, value in data.items():
            setattr(incident, key, value)
        if data.get("status") == "Resolvido" and not incident.ended_at:
            incident.ended_at = datetime.utcnow()
        self._update_impact(incident)
        incident.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(incident)
        return incident

    def delete(self, incident_id: str) -> bool:
        incident = self.get_by_id(incident_id)
        if not incident:
            return False
        self.db.delete(incident)
        self.db.commit()
        return True

    def get_by_id(self, incident_id: str) -> Optional[Incident]:
        return (
            self._base_query()
            .filter(Incident.incident_id == incident_id)
            .first()
        )

    def get_all(self, filters: Optional[dict] = None) -> List[Incident]:
        q = self._base_query()
        if filters:
            if filters.get("status"):
                q = q.filter(Incident.status.in_(filters["status"]))
            if filters.get("priority"):
                q = q.filter(Incident.priority.in_(filters["priority"]))
            if filters.get("system_id"):
                ids = filters["system_id"]
                if isinstance(ids, list):
                    q = q.filter(Incident.system_id.in_(ids))
                else:
                    q = q.filter(Incident.system_id == ids)
            if filters.get("incident_type_id"):
                ids = filters["incident_type_id"]
                if isinstance(ids, list):
                    q = q.filter(Incident.incident_type_id.in_(ids))
                else:
                    q = q.filter(Incident.incident_type_id == ids)
            if filters.get("start_date"):
                q = q.filter(Incident.started_at >= filters["start_date"])
            if filters.get("end_date"):
                q = q.filter(Incident.started_at <= filters["end_date"])
        return q.order_by(Incident.started_at.desc()).all()

    # ------------------------------------------------------------------ #
    #  Systems                                                             #
    # ------------------------------------------------------------------ #

    def get_systems(self, active_only: bool = True) -> List[System]:
        q = self.db.query(System)
        if active_only:
            q = q.filter(System.active.is_(True))
        return q.order_by(System.name).all()

    def create_system(self, name: str, description: str = "", criticality: str = "media") -> System:
        system = System(name=name, description=description, criticality=criticality)
        self.db.add(system)
        self.db.commit()
        self.db.refresh(system)
        return system

    def update_system(self, system_id: int, data: dict) -> Optional[System]:
        system = self.db.query(System).filter(System.id == system_id).first()
        if not system:
            return None
        for key, value in data.items():
            setattr(system, key, value)
        self.db.commit()
        self.db.refresh(system)
        return system

    def delete_system(self, system_id: int) -> tuple:
        """Soft-delete if the system has incidents; hard-delete otherwise."""
        system = self.db.query(System).filter(System.id == system_id).first()
        if not system:
            return False, "Sistema não encontrado."
        incident_count = (
            self.db.query(Incident).filter(Incident.system_id == system_id).count()
        )
        if incident_count > 0:
            system.active = False
            self.db.commit()
            return True, (
                f"Sistema desativado. {incident_count} incidente(s) histórico(s) preservado(s)."
            )
        self.db.delete(system)
        self.db.commit()
        return True, "Sistema excluído permanentemente."

    # ------------------------------------------------------------------ #
    #  Incident types                                                      #
    # ------------------------------------------------------------------ #

    def get_incident_types(self, active_only: bool = True) -> List[IncidentType]:
        q = self.db.query(IncidentType)
        if active_only:
            q = q.filter(IncidentType.active.is_(True))
        return q.order_by(IncidentType.name).all()

    def create_incident_type(self, name: str, description: str = "") -> IncidentType:
        itype = IncidentType(name=name, description=description)
        self.db.add(itype)
        self.db.commit()
        self.db.refresh(itype)
        return itype

    def update_incident_type(self, type_id: int, data: dict) -> Optional[IncidentType]:
        itype = self.db.query(IncidentType).filter(IncidentType.id == type_id).first()
        if not itype:
            return None
        for key, value in data.items():
            setattr(itype, key, value)
        self.db.commit()
        self.db.refresh(itype)
        return itype

    def delete_incident_type(self, type_id: int) -> tuple:
        itype = self.db.query(IncidentType).filter(IncidentType.id == type_id).first()
        if not itype:
            return False, "Tipo não encontrado."
        incident_count = self.db.query(Incident).filter(Incident.incident_type_id == type_id).count()
        if incident_count > 0:
            itype.active = False
            self.db.commit()
            return True, f"Tipo desativado. {incident_count} incidente(s) histórico(s) preservado(s)."
        self.db.delete(itype)
        self.db.commit()
        return True, "Tipo excluído permanentemente."
