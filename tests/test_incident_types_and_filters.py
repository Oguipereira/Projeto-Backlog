"""
Testes adicionais para IncidentService:
  - CRUD completo de tipos de incidente
  - Update e delete de sistemas
  - Filtros avançados (system_id, incident_type_id, end_date, active_only)
  - Branch de incident_id malformado em _next_incident_id
"""
from datetime import datetime

import pytest

from app.models import Incident, IncidentType, System
from app.services.incident_service import IncidentService


def _base_data(system_id: int, type_id: int, **kw) -> dict:
    data = {
        "title": "Incidente",
        "system_id": system_id,
        "incident_type_id": type_id,
        "priority": "P3",
        "status": "Aberto",
        "started_at": datetime(2024, 6, 1, 8, 0),
        "created_by": "teste",
    }
    data.update(kw)
    return data


# ------------------------------------------------------------------ #
#  Tipos de incidente                                                 #
# ------------------------------------------------------------------ #

class TestIncidentTypes:
    def test_cria_tipo(self, db_session, config_patch):
        svc = IncidentService(db_session)
        t = svc.create_incident_type("Hardware", "Falha física")
        assert t.id is not None
        assert t.name == "Hardware"

    def test_get_tipos_ativos(self, db_session, config_patch):
        svc = IncidentService(db_session)
        svc.create_incident_type("Rede")
        svc.create_incident_type("Software")
        assert len(svc.get_incident_types()) == 2

    def test_get_tipos_inclui_inativos(self, db_session, config_patch):
        svc = IncidentService(db_session)
        t = svc.create_incident_type("Antigo")
        t.active = False
        db_session.commit()
        assert len(svc.get_incident_types(active_only=False)) == 1
        assert len(svc.get_incident_types(active_only=True)) == 0

    def test_atualiza_tipo(self, db_session, config_patch):
        svc = IncidentService(db_session)
        t = svc.create_incident_type("Rede")
        updated = svc.update_incident_type(t.id, {"name": "Conectividade"})
        assert updated.name == "Conectividade"

    def test_atualiza_tipo_inexistente_retorna_none(self, db_session, config_patch):
        svc = IncidentService(db_session)
        assert svc.update_incident_type(9999, {"name": "x"}) is None

    def test_hard_delete_tipo_sem_incidentes(self, db_session, config_patch):
        svc = IncidentService(db_session)
        t = svc.create_incident_type("Temporário")
        ok, msg = svc.delete_incident_type(t.id)
        assert ok is True
        assert "permanentemente" in msg.lower()

    def test_soft_delete_tipo_com_incidentes(self, populated_db):
        db, system, itype = populated_db["db"], populated_db["system"], populated_db["itype"]
        svc = IncidentService(db)
        svc.create(_base_data(system.id, itype.id))
        ok, msg = svc.delete_incident_type(itype.id)
        assert ok is True
        assert "desativado" in msg.lower()
        t = db.query(IncidentType).filter_by(id=itype.id).first()
        assert t.active is False

    def test_delete_tipo_inexistente_retorna_false(self, db_session, config_patch):
        svc = IncidentService(db_session)
        ok, msg = svc.delete_incident_type(9999)
        assert ok is False
        assert "não encontrado" in msg.lower()


# ------------------------------------------------------------------ #
#  Update e delete de sistemas                                        #
# ------------------------------------------------------------------ #

class TestSystemUpdates:
    def test_atualiza_sistema(self, db_session, config_patch):
        svc = IncidentService(db_session)
        s = svc.create_system("CRM")
        updated = svc.update_system(s.id, {"description": "Novo desc", "criticality": "alta"})
        assert updated.description == "Novo desc"
        assert updated.criticality == "alta"

    def test_atualiza_sistema_inexistente_retorna_none(self, db_session, config_patch):
        svc = IncidentService(db_session)
        assert svc.update_system(9999, {"name": "x"}) is None

    def test_delete_sistema_inexistente_retorna_false(self, db_session, config_patch):
        svc = IncidentService(db_session)
        ok, msg = svc.delete_system(9999)
        assert ok is False
        assert "não encontrado" in msg.lower()

    def test_get_systems_inclui_inativos(self, db_session, config_patch):
        svc = IncidentService(db_session)
        s = svc.create_system("Legado")
        s.active = False
        db_session.commit()
        assert len(svc.get_systems(active_only=False)) == 1
        assert len(svc.get_systems(active_only=True)) == 0


# ------------------------------------------------------------------ #
#  Filtros avançados em get_all                                       #
# ------------------------------------------------------------------ #

class TestGetAllFilters:
    def test_filtro_system_id_lista(self, populated_db):
        db, system, itype = populated_db["db"], populated_db["system"], populated_db["itype"]
        svc = IncidentService(db)
        svc.create(_base_data(system.id, itype.id))
        resultado = svc.get_all(filters={"system_id": [system.id]})
        assert len(resultado) == 1

    def test_filtro_system_id_escalar(self, populated_db):
        db, system, itype = populated_db["db"], populated_db["system"], populated_db["itype"]
        svc = IncidentService(db)
        svc.create(_base_data(system.id, itype.id))
        resultado = svc.get_all(filters={"system_id": system.id})
        assert len(resultado) == 1

    def test_filtro_incident_type_id_lista(self, populated_db):
        db, system, itype = populated_db["db"], populated_db["system"], populated_db["itype"]
        svc = IncidentService(db)
        svc.create(_base_data(system.id, itype.id))
        resultado = svc.get_all(filters={"incident_type_id": [itype.id]})
        assert len(resultado) == 1

    def test_filtro_incident_type_id_escalar(self, populated_db):
        db, system, itype = populated_db["db"], populated_db["system"], populated_db["itype"]
        svc = IncidentService(db)
        svc.create(_base_data(system.id, itype.id))
        resultado = svc.get_all(filters={"incident_type_id": itype.id})
        assert len(resultado) == 1

    def test_filtro_end_date(self, populated_db):
        db, system, itype = populated_db["db"], populated_db["system"], populated_db["itype"]
        svc = IncidentService(db)
        svc.create(_base_data(system.id, itype.id, started_at=datetime(2024, 1, 15, 8, 0)))
        svc.create(_base_data(system.id, itype.id, started_at=datetime(2024, 6, 15, 8, 0)))
        anteriores = svc.get_all(filters={"end_date": datetime(2024, 3, 1)})
        assert len(anteriores) == 1
        assert anteriores[0].started_at.month == 1

    def test_filtro_combinado_status_e_prioridade(self, populated_db):
        db, system, itype = populated_db["db"], populated_db["system"], populated_db["itype"]
        svc = IncidentService(db)
        svc.create(_base_data(system.id, itype.id, status="Aberto", priority="P1"))
        svc.create(_base_data(system.id, itype.id, status="Aberto", priority="P3"))
        svc.create(_base_data(system.id, itype.id, status="Resolvido", priority="P1"))
        resultado = svc.get_all(filters={"status": ["Aberto"], "priority": ["P1"]})
        assert len(resultado) == 1


# ------------------------------------------------------------------ #
#  Branch de incident_id malformado                                   #
# ------------------------------------------------------------------ #

class TestNextIncidentIdMalformed:
    def test_id_malformado_usa_contagem(self, db_session, config_patch):
        """Se o último incident_id não segue o padrão INC-NNNN, usa count()+1."""
        svc = IncidentService(db_session)
        system = System(name="S", criticality="media")
        itype = IncidentType(name="T")
        db_session.add_all([system, itype])
        db_session.commit()

        # Insere diretamente um incidente com ID malformado
        bad = Incident(
            incident_id="MALFORMADO",
            title="Ruim",
            system_id=system.id,
            incident_type_id=itype.id,
            priority="P4",
            status="Aberto",
            started_at=datetime(2024, 1, 1, 8, 0),
        )
        db_session.add(bad)
        db_session.commit()

        # O próximo ID deve ser gerado via count, não via split
        novo = svc.create({
            "title": "Novo",
            "system_id": system.id,
            "incident_type_id": itype.id,
            "priority": "P4",
            "status": "Aberto",
            "started_at": datetime(2024, 1, 2, 8, 0),
        })
        # count() = 2, portanto INC-0002
        assert novo.incident_id == "INC-0002"
