"""
Performance: ML service — treino e predição conforme volume cresce.

Usa objetos mock (sem DB) para isolar a camada de ML pura.
Modelos salvos em diretório temporário para não sobrescrever os reais.
"""
import time
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from unittest.mock import patch

import pytest

import app.database  # noqa: F401
import app.services.ml_service as ml

random.seed(2)

# ── Limites aceitáveis ─────────────────────────────────────────── #
LIMIT_TRAIN_50    = 3.0    # s
LIMIT_TRAIN_200   = 8.0    # s
LIMIT_PREDICT     = 0.150  # s — inclui cold start (joblib.load por chamada)
LIMIT_STATUS      = 0.010  # s


# ── Objetos mock ───────────────────────────────────────────────── #

@dataclass
class _Sys:
    name: str

@dataclass
class _Type:
    name: str

@dataclass
class _Inc:
    title: str
    description: str
    priority: str
    system: Optional[_Sys]
    incident_type: Optional[_Type]


SYSTEMS  = ["ERP", "CRM", "WMS", "Portal de Vendas", "MES"]
TYPES    = ["Falha de Rede", "Lentidão", "Falha de Hardware", "Erro de Config"]
PRIOS    = ["P1", "P2", "P3", "P4"]
P_W      = [0.07, 0.18, 0.42, 0.33]

TITLES = [
    "Parada total do sistema",
    "Lentidão crítica detectada",
    "Falha de conectividade",
    "Erro em processamento batch",
    "Timeout em integração",
    "Queda de desempenho no módulo",
    "Sistema indisponível para usuários",
    "Erros intermitentes no módulo de relatórios",
]


def _make_incidents(n: int) -> list:
    incs = []
    for i in range(n):
        p = random.choices(PRIOS, weights=P_W)[0]
        incs.append(_Inc(
            title=f"{random.choice(TITLES)} #{i}",
            description=f"Incidente no sistema {random.choice(SYSTEMS)}. Detalhes do problema #{i}.",
            priority=p,
            system=_Sys(random.choice(SYSTEMS)),
            incident_type=_Type(random.choice(TYPES)),
        ))
    return incs


# ── Fixtures ───────────────────────────────────────────────────── #

@pytest.fixture(scope="module")
def incidents_50():  return _make_incidents(50)

@pytest.fixture(scope="module")
def incidents_100(): return _make_incidents(100)

@pytest.fixture(scope="module")
def incidents_200(): return _make_incidents(200)

@pytest.fixture()
def tmp_models(tmp_path):
    """Redireciona MODELS_DIR para pasta temporária."""
    with patch.object(ml, "MODELS_DIR", tmp_path):
        yield tmp_path


# ── Benchmarks: train_all ─────────────────────────────────────── #

def test_train_50(benchmark, incidents_50, tmp_models):
    result = benchmark(ml.train_all, incidents_50)
    assert result["status"] == "ok"
    assert result["count"] == 50


def test_train_100(benchmark, incidents_100, tmp_models):
    result = benchmark(ml.train_all, incidents_100)
    assert result["status"] == "ok"
    assert result["count"] == 100


def test_train_200(benchmark, incidents_200, tmp_models):
    result = benchmark(ml.train_all, incidents_200)
    assert result["status"] == "ok"
    assert result["count"] == 200


def test_train_insuficiente_retorna_rapidamente(benchmark, tmp_models):
    poucos = _make_incidents(5)
    result = benchmark(ml.train_all, poucos)
    assert result["status"] == "insufficient_data"


# ── Benchmarks: suggest_classification ───────────────────────── #

def test_predict_sem_modelos_retorna_vazio(benchmark, tmp_models):
    result = benchmark(ml.suggest_classification, "Sistema fora do ar", "Erro crítico")
    assert isinstance(result, dict)


def test_predict_com_modelo_treinado(benchmark, incidents_100, tmp_models):
    ml.train_all(incidents_100)
    result = benchmark(ml.suggest_classification, "Queda de desempenho no ERP", "Lentidão severa")
    assert "priority" in result
    assert "priority_confidence" in result


# ── Benchmarks: models_status ────────────────────────────────── #

def test_models_status_sem_modelos(benchmark, tmp_models):
    result = benchmark(ml.models_status)
    assert all(v is False for v in result.values())


def test_models_status_com_modelos(benchmark, incidents_100, tmp_models):
    ml.train_all(incidents_100)
    result = benchmark(ml.models_status)
    assert result["priority"] is True


# ── Limites rígidos ────────────────────────────────────────────── #

def test_train_50_dentro_do_limite(incidents_50, tmp_models):
    t0 = time.perf_counter()
    ml.train_all(incidents_50)
    elapsed = time.perf_counter() - t0
    assert elapsed < LIMIT_TRAIN_50, \
        f"train_all(50) levou {elapsed:.2f}s — limite {LIMIT_TRAIN_50}s"


def test_train_200_dentro_do_limite(incidents_200, tmp_models):
    t0 = time.perf_counter()
    ml.train_all(incidents_200)
    elapsed = time.perf_counter() - t0
    assert elapsed < LIMIT_TRAIN_200, \
        f"train_all(200) levou {elapsed:.2f}s — limite {LIMIT_TRAIN_200}s"


def test_predict_dentro_do_limite(incidents_100, tmp_models):
    ml.train_all(incidents_100)
    t0 = time.perf_counter()
    ml.suggest_classification("Parada total do ERP", "Sistema indisponível")
    elapsed = time.perf_counter() - t0
    assert elapsed < LIMIT_PREDICT, \
        f"suggest_classification levou {elapsed*1000:.1f}ms — limite {LIMIT_PREDICT*1000:.0f}ms"


def test_status_dentro_do_limite(tmp_models):
    t0 = time.perf_counter()
    ml.models_status()
    assert time.perf_counter() - t0 < LIMIT_STATUS, \
        f"models_status excedeu {LIMIT_STATUS*1000:.0f}ms"
