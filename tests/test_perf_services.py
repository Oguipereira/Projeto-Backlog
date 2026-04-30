"""
Performance: queries e serviços com volume controlado.

Usa SQLite in-memory para resultados reproduzíveis.
Testa get_all, filtros, KPIs e cálculo de impacto
com 100, 500 e 1000 incidentes.
"""
import time
import random
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.database  # noqa: F401
from app.models import Base, System, IncidentType
from app.services.incident_service import IncidentService
from app.services.impact_service import ImpactService

random.seed(0)

# ── Limites aceitáveis ─────────────────────────────────────────── #
LIMIT_GET_ALL_100   = 0.150   # s
LIMIT_GET_ALL_500   = 0.500   # s
LIMIT_GET_ALL_1000  = 1.000   # s
LIMIT_KPIS_100      = 0.100   # s
LIMIT_KPIS_500      = 0.400   # s
LIMIT_KPIS_1000     = 0.800   # s
LIMIT_FILTERS       = 0.200   # s


# ── Fixtures ───────────────────────────────────────────────────── #

def _build_session(n_incidents: int):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    system = System(name="ERP", criticality="alta")
    itype  = IncidentType(name="Falha de Rede")
    db.add_all([system, itype])
    db.commit()

    priorities = ["P1", "P2", "P3", "P4"]
    statuses   = ["Aberto", "Em Andamento", "Resolvido"]
    p_w        = [0.08, 0.20, 0.40, 0.32]
    s_w        = [0.05, 0.05, 0.90]
    base_time  = datetime(2024, 1, 1, 8, 0)

    svc = IncidentService(db)
    for i in range(n_incidents):
        priority = random.choices(priorities, weights=p_w)[0]
        status   = random.choices(statuses, weights=s_w)[0]
        started  = base_time + timedelta(hours=i * 3)
        ended    = started + timedelta(minutes=random.randint(10, 300)) if status == "Resolvido" else None
        svc.create({
            "title":            f"Incidente {i:05d}",
            "system_id":        system.id,
            "incident_type_id": itype.id,
            "priority":         priority,
            "status":           status,
            "started_at":       started,
            "ended_at":         ended,
            "affected_users":   random.randint(1, 200),
        })

    return db


@pytest.fixture(scope="module")
def session_100():
    db = _build_session(100)
    yield db
    db.close()


@pytest.fixture(scope="module")
def session_500():
    db = _build_session(500)
    yield db
    db.close()


@pytest.fixture(scope="module")
def session_1000():
    db = _build_session(1000)
    yield db
    db.close()


# ── Benchmarks: get_all ────────────────────────────────────────── #

def test_get_all_100(benchmark, session_100):
    svc = IncidentService(session_100)
    result = benchmark(svc.get_all)
    assert len(result) == 100


def test_get_all_500(benchmark, session_500):
    svc = IncidentService(session_500)
    result = benchmark(svc.get_all)
    assert len(result) == 500


def test_get_all_1000(benchmark, session_1000):
    svc = IncidentService(session_1000)
    result = benchmark(svc.get_all)
    assert len(result) == 1000


# ── Benchmarks: filtros ────────────────────────────────────────── #

def test_filtro_status_500(benchmark, session_500):
    svc    = IncidentService(session_500)
    result = benchmark(svc.get_all, {"status": ["Resolvido"]})
    assert all(i.status == "Resolvido" for i in result)


def test_filtro_prioridade_500(benchmark, session_500):
    svc    = IncidentService(session_500)
    result = benchmark(svc.get_all, {"priority": ["P1", "P2"]})
    assert all(i.priority in ("P1", "P2") for i in result)


def test_filtro_data_500(benchmark, session_500):
    svc    = IncidentService(session_500)
    start  = datetime(2024, 6, 1)
    result = benchmark(svc.get_all, {"start_date": start})
    assert all(i.started_at >= start for i in result)


# ── Benchmarks: KPIs ──────────────────────────────────────────── #

def test_kpis_100(benchmark, session_100):
    svc    = IncidentService(session_100)
    impact = ImpactService(session_100)
    incs   = svc.get_all()
    result = benchmark(impact.get_kpis, incs)
    assert result["total"] == 100


def test_kpis_500(benchmark, session_500):
    svc    = IncidentService(session_500)
    impact = ImpactService(session_500)
    incs   = svc.get_all()
    result = benchmark(impact.get_kpis, incs)
    assert result["total"] == 500


def test_kpis_1000(benchmark, session_1000):
    svc    = IncidentService(session_1000)
    impact = ImpactService(session_1000)
    incs   = svc.get_all()
    result = benchmark(impact.get_kpis, incs)
    assert result["total"] == 1000


# ── Limites rígidos (sem benchmark, com assert de tempo) ──────── #

def test_get_all_100_dentro_do_limite(session_100):
    svc = IncidentService(session_100)
    t0  = time.perf_counter()
    svc.get_all()
    assert time.perf_counter() - t0 < LIMIT_GET_ALL_100, \
        f"get_all(100) excedeu {LIMIT_GET_ALL_100*1000:.0f}ms"


def test_get_all_500_dentro_do_limite(session_500):
    svc = IncidentService(session_500)
    t0  = time.perf_counter()
    svc.get_all()
    assert time.perf_counter() - t0 < LIMIT_GET_ALL_500, \
        f"get_all(500) excedeu {LIMIT_GET_ALL_500*1000:.0f}ms"


def test_get_all_1000_dentro_do_limite(session_1000):
    svc = IncidentService(session_1000)
    t0  = time.perf_counter()
    svc.get_all()
    assert time.perf_counter() - t0 < LIMIT_GET_ALL_1000, \
        f"get_all(1000) excedeu {LIMIT_GET_ALL_1000*1000:.0f}ms"


def test_kpis_1000_dentro_do_limite(session_1000):
    svc    = IncidentService(session_1000)
    impact = ImpactService(session_1000)
    incs   = svc.get_all()
    t0     = time.perf_counter()
    impact.get_kpis(incs)
    assert time.perf_counter() - t0 < LIMIT_KPIS_1000, \
        f"get_kpis(1000) excedeu {LIMIT_KPIS_1000*1000:.0f}ms"
