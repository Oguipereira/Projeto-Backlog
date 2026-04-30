"""Testes de integração para ImpactService (KPIs e cálculo de impacto)."""
from datetime import datetime

import pytest

from app.models import Incident
from app.services.impact_service import ImpactService
from app.services.incident_service import IncidentService


def _create_incident(svc: IncidentService, system_id: int, type_id: int, **kwargs) -> Incident:
    defaults = {
        "title": "Incidente teste",
        "system_id": system_id,
        "incident_type_id": type_id,
        "priority": "P2",
        "status": "Aberto",
        "started_at": datetime(2024, 6, 1, 8, 0),
        "created_by": "teste",
    }
    defaults.update(kwargs)
    return svc.create(defaults)


class TestCalculateIncidentImpact:
    def test_duração_calculada_corretamente(self, populated_db):
        db, system, itype = populated_db["db"], populated_db["system"], populated_db["itype"]
        inc_svc = IncidentService(db)
        imp_svc = ImpactService(db)
        start = datetime(2024, 6, 1, 8, 0)
        end   = datetime(2024, 6, 1, 9, 0)
        inc = _create_incident(inc_svc, system.id, itype.id, started_at=start, ended_at=end)
        impact = imp_svc.calculate_incident_impact(inc)
        assert impact["duration_minutes"] == 60.0

    def test_perda_producao_positiva(self, populated_db):
        db, system, itype = populated_db["db"], populated_db["system"], populated_db["itype"]
        inc_svc = IncidentService(db)
        imp_svc = ImpactService(db)
        start = datetime(2024, 6, 1, 8, 0)
        end   = datetime(2024, 6, 1, 9, 0)
        inc = _create_incident(inc_svc, system.id, itype.id, started_at=start, ended_at=end)
        impact = imp_svc.calculate_incident_impact(inc)
        assert impact["production_loss"] > 0

    def test_sla_violado_p1_longo(self, populated_db):
        db, system, itype = populated_db["db"], populated_db["system"], populated_db["itype"]
        inc_svc = IncidentService(db)
        imp_svc = ImpactService(db)
        # SLA do P1 = 60 min; incidente durou 2h
        start = datetime(2024, 6, 1, 8, 0)
        end   = datetime(2024, 6, 1, 10, 0)
        inc = _create_incident(inc_svc, system.id, itype.id,
                               priority="P1", started_at=start, ended_at=end)
        impact = imp_svc.calculate_incident_impact(inc)
        assert impact["sla_violated"] is True

    def test_sla_nao_violado_p1_curto(self, populated_db):
        db, system, itype = populated_db["db"], populated_db["system"], populated_db["itype"]
        inc_svc = IncidentService(db)
        imp_svc = ImpactService(db)
        # SLA do P1 = 60 min; incidente durou 30 min
        start = datetime(2024, 6, 1, 8, 0)
        end   = datetime(2024, 6, 1, 8, 30)
        inc = _create_incident(inc_svc, system.id, itype.id,
                               priority="P1", started_at=start, ended_at=end)
        impact = imp_svc.calculate_incident_impact(inc)
        assert impact["sla_violated"] is False

    def test_incidente_aberto_marcado_como_aberto(self, populated_db):
        db, system, itype = populated_db["db"], populated_db["system"], populated_db["itype"]
        inc_svc = IncidentService(db)
        imp_svc = ImpactService(db)
        inc = _create_incident(inc_svc, system.id, itype.id)
        impact = imp_svc.calculate_incident_impact(inc)
        assert impact["is_open"] is True


class TestGetKPIs:
    def test_sem_incidentes_retorna_zeros(self, populated_db):
        db = populated_db["db"]
        imp_svc = ImpactService(db)
        kpis = imp_svc.get_kpis([])
        assert kpis["total"] == 0
        assert kpis["total_downtime_minutes"] == 0.0

    def test_contagem_por_status(self, populated_db):
        db, system, itype = populated_db["db"], populated_db["system"], populated_db["itype"]
        inc_svc = IncidentService(db)
        imp_svc = ImpactService(db)
        _create_incident(inc_svc, system.id, itype.id, status="Aberto")
        _create_incident(inc_svc, system.id, itype.id, status="Em Andamento")
        _create_incident(inc_svc, system.id, itype.id, status="Resolvido",
                         ended_at=datetime(2024, 6, 1, 9, 0))
        incidents = inc_svc.get_all()
        kpis = imp_svc.get_kpis(incidents)
        assert kpis["total"] == 3
        assert kpis["open"] == 1
        assert kpis["in_progress"] == 1
        assert kpis["resolved"] == 1

    def test_contagem_por_prioridade(self, populated_db):
        db, system, itype = populated_db["db"], populated_db["system"], populated_db["itype"]
        inc_svc = IncidentService(db)
        imp_svc = ImpactService(db)
        _create_incident(inc_svc, system.id, itype.id, priority="P1")
        _create_incident(inc_svc, system.id, itype.id, priority="P1")
        _create_incident(inc_svc, system.id, itype.id, priority="P3")
        incidents = inc_svc.get_all()
        kpis = imp_svc.get_kpis(incidents)
        assert kpis["p1"] == 2
        assert kpis["p3"] == 1

    def test_mttr_calculado_para_resolvidos(self, populated_db):
        db, system, itype = populated_db["db"], populated_db["system"], populated_db["itype"]
        inc_svc = IncidentService(db)
        imp_svc = ImpactService(db)
        start = datetime(2024, 6, 1, 8, 0)
        end   = datetime(2024, 6, 1, 10, 0)  # 120 min
        _create_incident(inc_svc, system.id, itype.id,
                         status="Resolvido", started_at=start, ended_at=end)
        incidents = inc_svc.get_all()
        kpis = imp_svc.get_kpis(incidents)
        assert kpis["mttr_minutes"] == pytest.approx(120.0, abs=0.1)

    def test_sla_violations_contabilizadas(self, populated_db):
        db, system, itype = populated_db["db"], populated_db["system"], populated_db["itype"]
        inc_svc = IncidentService(db)
        imp_svc = ImpactService(db)
        # P1 SLA = 60 min — 2h viola
        start = datetime(2024, 6, 1, 8, 0)
        end   = datetime(2024, 6, 1, 10, 0)
        _create_incident(inc_svc, system.id, itype.id,
                         priority="P1", status="Resolvido", started_at=start, ended_at=end)
        incidents = inc_svc.get_all()
        kpis = imp_svc.get_kpis(incidents)
        assert kpis["sla_violations"] == 1
