"""
Fixtures compartilhadas entre todos os testes.

Usa SQLite em memória para isolamento total — nenhum dado real é tocado.
"""
import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# app.database deve ser importado antes de app.models para evitar circular import
# durante init_db() que é chamado no nível do módulo em app/database.py
import app.database  # noqa: F401
from app.models import Base, System, IncidentType


SAMPLE_CONFIG = {
    "production": {
        "work_hours_per_day": 9.0,
        "effective_hours_per_day": 8.0,
        "daily_production_target": 40_000_000.0,
        "currency": "R$",
    },
    "priorities": {
        "P1": {"label": "Crítico", "color": "#DC2626", "sla_minutes": 60},
        "P2": {"label": "Alto",    "color": "#EA580C", "sla_minutes": 240},
        "P3": {"label": "Médio",   "color": "#CA8A04", "sla_minutes": 480},
        "P4": {"label": "Baixo",   "color": "#16A34A", "sla_minutes": 1440},
    },
    "statuses": ["Aberto", "Em Andamento", "Resolvido"],
    "criticality_levels": ["alta", "media", "baixa"],
}


@pytest.fixture()
def db_session():
    """Sessão SQLite em memória; revertida ao final de cada teste."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def config_patch(monkeypatch):
    """Substitui a leitura do settings.json pelo dicionário local."""
    monkeypatch.setattr(
        "app.services.config_service.ConfigService._load_file",
        lambda self: SAMPLE_CONFIG,
    )


@pytest.fixture()
def populated_db(db_session, config_patch):
    """Sessão já com um System e um IncidentType cadastrados."""
    system = System(name="ERP", description="Sistema principal", criticality="alta")
    itype = IncidentType(name="Falha de Rede", description="Conectividade")
    db_session.add_all([system, itype])
    db_session.commit()
    db_session.refresh(system)
    db_session.refresh(itype)
    return {"db": db_session, "system": system, "itype": itype}
