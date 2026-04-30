"""Testes de integração para IncidentService (CRUD completo)."""
from datetime import datetime, timedelta

import pytest

from app.services.incident_service import IncidentService


def make_incident_data(system_id: int, type_id: int, **overrides) -> dict:
    base = {
        "title": "Falha no login",
        "description": "Usuários não conseguem autenticar",
        "system_id": system_id,
        "incident_type_id": type_id,
        "priority": "P2",
        "status": "Aberto",
        "started_at": datetime(2024, 6, 1, 8, 0),
        "affected_users": 50,
        "created_by": "teste",
    }
    base.update(overrides)
    return base


# ------------------------------------------------------------------ #
#  Criação                                                            #
# ------------------------------------------------------------------ #

class TestCreateIncident:
    def test_cria_com_id_sequencial(self, populated_db):
        db, system, itype = populated_db["db"], populated_db["system"], populated_db["itype"]
        svc = IncidentService(db)
        inc = svc.create(make_incident_data(system.id, itype.id))
        assert inc.incident_id == "INC-0001"

    def test_segundo_incidente_incrementa_id(self, populated_db):
        db, system, itype = populated_db["db"], populated_db["system"], populated_db["itype"]
        svc = IncidentService(db)
        svc.create(make_incident_data(system.id, itype.id))
        inc2 = svc.create(make_incident_data(system.id, itype.id, title="Segundo"))
        assert inc2.incident_id == "INC-0002"

    def test_calcula_duracao_quando_tem_fim(self, populated_db):
        db, system, itype = populated_db["db"], populated_db["system"], populated_db["itype"]
        svc = IncidentService(db)
        start = datetime(2024, 6, 1, 8, 0)
        end   = datetime(2024, 6, 1, 9, 30)
        inc = svc.create(make_incident_data(system.id, itype.id, started_at=start, ended_at=end))
        assert inc.duration_minutes == 90.0

    def test_duracao_nula_sem_fim(self, populated_db):
        db, system, itype = populated_db["db"], populated_db["system"], populated_db["itype"]
        svc = IncidentService(db)
        inc = svc.create(make_incident_data(system.id, itype.id))
        assert inc.ended_at is None
        assert inc.duration_minutes is None


# ------------------------------------------------------------------ #
#  Leitura                                                            #
# ------------------------------------------------------------------ #

class TestGetIncident:
    def test_get_by_id_existente(self, populated_db):
        db, system, itype = populated_db["db"], populated_db["system"], populated_db["itype"]
        svc = IncidentService(db)
        created = svc.create(make_incident_data(system.id, itype.id))
        found = svc.get_by_id(created.incident_id)
        assert found is not None
        assert found.incident_id == created.incident_id

    def test_get_by_id_inexistente(self, populated_db):
        svc = IncidentService(populated_db["db"])
        assert svc.get_by_id("INC-9999") is None

    def test_get_all_retorna_lista(self, populated_db):
        db, system, itype = populated_db["db"], populated_db["system"], populated_db["itype"]
        svc = IncidentService(db)
        svc.create(make_incident_data(system.id, itype.id))
        svc.create(make_incident_data(system.id, itype.id, title="Outro"))
        assert len(svc.get_all()) == 2

    def test_filtro_por_status(self, populated_db):
        db, system, itype = populated_db["db"], populated_db["system"], populated_db["itype"]
        svc = IncidentService(db)
        svc.create(make_incident_data(system.id, itype.id, status="Aberto"))
        svc.create(make_incident_data(system.id, itype.id, status="Resolvido"))
        abertos = svc.get_all(filters={"status": ["Aberto"]})
        assert len(abertos) == 1
        assert abertos[0].status == "Aberto"

    def test_filtro_por_prioridade(self, populated_db):
        db, system, itype = populated_db["db"], populated_db["system"], populated_db["itype"]
        svc = IncidentService(db)
        svc.create(make_incident_data(system.id, itype.id, priority="P1"))
        svc.create(make_incident_data(system.id, itype.id, priority="P3"))
        p1 = svc.get_all(filters={"priority": ["P1"]})
        assert len(p1) == 1
        assert p1[0].priority == "P1"

    def test_filtro_por_data(self, populated_db):
        db, system, itype = populated_db["db"], populated_db["system"], populated_db["itype"]
        svc = IncidentService(db)
        svc.create(make_incident_data(system.id, itype.id, started_at=datetime(2024, 1, 1, 8, 0)))
        svc.create(make_incident_data(system.id, itype.id, started_at=datetime(2024, 6, 1, 8, 0)))
        recentes = svc.get_all(filters={"start_date": datetime(2024, 3, 1)})
        assert len(recentes) == 1


# ------------------------------------------------------------------ #
#  Atualização                                                        #
# ------------------------------------------------------------------ #

class TestUpdateIncident:
    def test_atualiza_titulo(self, populated_db):
        db, system, itype = populated_db["db"], populated_db["system"], populated_db["itype"]
        svc = IncidentService(db)
        inc = svc.create(make_incident_data(system.id, itype.id))
        updated = svc.update(inc.incident_id, {"title": "Novo título"})
        assert updated.title == "Novo título"

    def test_resolve_define_ended_at(self, populated_db):
        db, system, itype = populated_db["db"], populated_db["system"], populated_db["itype"]
        svc = IncidentService(db)
        inc = svc.create(make_incident_data(system.id, itype.id))
        updated = svc.update(inc.incident_id, {"status": "Resolvido"})
        assert updated.ended_at is not None
        assert updated.status == "Resolvido"

    def test_update_inexistente_retorna_none(self, populated_db):
        svc = IncidentService(populated_db["db"])
        assert svc.update("INC-9999", {"title": "x"}) is None


# ------------------------------------------------------------------ #
#  Exclusão                                                           #
# ------------------------------------------------------------------ #

class TestDeleteIncident:
    def test_deleta_existente(self, populated_db):
        db, system, itype = populated_db["db"], populated_db["system"], populated_db["itype"]
        svc = IncidentService(db)
        inc = svc.create(make_incident_data(system.id, itype.id))
        assert svc.delete(inc.incident_id) is True
        assert svc.get_by_id(inc.incident_id) is None

    def test_deleta_inexistente_retorna_false(self, populated_db):
        svc = IncidentService(populated_db["db"])
        assert svc.delete("INC-9999") is False


# ------------------------------------------------------------------ #
#  Sistemas                                                           #
# ------------------------------------------------------------------ #

class TestSystems:
    def test_cria_sistema(self, db_session, config_patch):
        svc = IncidentService(db_session)
        s = svc.create_system("CRM", criticality="media")
        assert s.id is not None
        assert s.name == "CRM"

    def test_soft_delete_com_incidentes(self, populated_db):
        db, system, itype = populated_db["db"], populated_db["system"], populated_db["itype"]
        svc = IncidentService(db)
        svc.create(make_incident_data(system.id, itype.id))
        ok, msg = svc.delete_system(system.id)
        assert ok is True
        assert "desativado" in msg.lower()
        # Sistema continua na base, apenas inativo
        from app.models import System
        s = db.query(System).filter_by(id=system.id).first()
        assert s.active is False

    def test_hard_delete_sem_incidentes(self, db_session, config_patch):
        svc = IncidentService(db_session)
        s = svc.create_system("Temporário")
        ok, msg = svc.delete_system(s.id)
        assert ok is True
        assert "permanentemente" in msg.lower()
