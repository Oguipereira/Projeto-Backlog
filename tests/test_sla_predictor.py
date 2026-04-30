"""
Testes unitários para sla_predictor.

Modelos salvos em diretório temporário para não sobrescrever
o modelo real em data/models/sla_risk.pkl.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from unittest.mock import patch

import pytest

import app.database  # noqa: F401
import app.services.sla_predictor as sla_mod

SLA_MAP = {"P1": 60, "P2": 240, "P3": 480, "P4": 1440}
_PRIO_CYCLE = ["P1", "P2", "P3", "P4"]


# ── Mocks ─────────────────────────────────────────────────────── #

@dataclass
class _Sys:
    name: str

@dataclass
class _Type:
    name: str

@dataclass
class _Inc:
    incident_id: str
    priority: str = "P3"
    system: Optional[_Sys] = None
    incident_type: Optional[_Type] = None
    started_at: datetime = field(default_factory=datetime.now)
    ended_at: Optional[datetime] = None
    duration_minutes: Optional[float] = None
    title: str = "Incidente teste"
    description: str = ""


def _make_inc(idx: int, priority: str = "P3", duration_min: Optional[float] = 30.0) -> _Inc:
    now = datetime.now() - timedelta(days=idx)
    ended = (now + timedelta(minutes=duration_min)) if duration_min is not None else None
    return _Inc(
        incident_id=f"INC-{idx:04d}",
        priority=priority,
        system=_Sys("ERP"),
        incident_type=_Type("Falha de Rede"),
        started_at=now,
        ended_at=ended,
        duration_minutes=duration_min,
    )


def _make_training_set(n: int) -> list:
    """Gera n incidentes resolvidos alternando violação/cumprimento de SLA."""
    result = []
    for i in range(n):
        p = _PRIO_CYCLE[i % 4]
        sla = SLA_MAP[p]
        dur = sla * 0.5 if i % 2 == 0 else sla * 1.5
        result.append(_make_inc(i, priority=p, duration_min=dur))
    return result


# ── Fixture de isolamento ──────────────────────────────────────── #

@pytest.fixture(autouse=True)
def isolated_model(tmp_path):
    """Redireciona MODEL_PATH para pasta temporária em todos os testes."""
    tmp_model = tmp_path / "sla_risk.pkl"
    with patch.object(sla_mod, "MODEL_PATH", tmp_model):
        sla_mod._cache.clear()
        yield tmp_model
        sla_mod._cache.clear()


# ── is_trained ────────────────────────────────────────────────── #

def test_is_trained_sem_arquivo_retorna_false():
    assert sla_mod.is_trained() is False


def test_is_trained_apos_treino_retorna_true():
    sla_mod.train(_make_training_set(40), SLA_MAP)
    assert sla_mod.is_trained() is True


# ── train ─────────────────────────────────────────────────────── #

def test_train_insuficiente_retorna_insufficient_data():
    result = sla_mod.train(_make_training_set(5), SLA_MAP)
    assert result["status"] == "insufficient_data"
    assert "samples" in result
    assert result["samples"] < sla_mod.MIN_SAMPLES


def test_train_suficiente_retorna_ok():
    result = sla_mod.train(_make_training_set(40), SLA_MAP)
    assert result["status"] == "ok"
    assert "accuracy" in result
    assert "samples" in result


def test_train_accuracy_entre_0_e_100():
    result = sla_mod.train(_make_training_set(40), SLA_MAP)
    assert 0.0 <= result["accuracy"] <= 100.0


def test_train_samples_correto():
    result = sla_mod.train(_make_training_set(40), SLA_MAP)
    assert result["samples"] == 40


def test_train_ignora_incidentes_sem_ended_at():
    candidatos = _make_training_set(40)
    for inc in candidatos[:20]:
        inc.ended_at = None
        inc.duration_minutes = None
    result = sla_mod.train(candidatos, SLA_MAP)
    assert result["status"] == "ok"
    assert result["samples"] == 20


def test_train_todos_sem_ended_at_retorna_insuficiente():
    candidatos = _make_training_set(40)
    for inc in candidatos:
        inc.ended_at = None
        inc.duration_minutes = None
    result = sla_mod.train(candidatos, SLA_MAP)
    assert result["status"] == "insufficient_data"


# ── predict_risk ──────────────────────────────────────────────── #

def test_predict_sem_modelo_retorna_sem_modelo():
    inc = _make_inc(0, priority="P1")
    result = sla_mod.predict_risk(inc)
    assert result["risk_level"] == "sem modelo"
    assert result["model_ready"] is False
    assert result["risk_pct"] == 0


def test_predict_campos_obrigatorios():
    sla_mod.train(_make_training_set(40), SLA_MAP)
    result = sla_mod.predict_risk(_make_inc(0, priority="P2"))
    assert {"risk_pct", "risk_level", "model_ready"}.issubset(result.keys())


def test_predict_risk_pct_entre_0_e_100():
    sla_mod.train(_make_training_set(40), SLA_MAP)
    for p in _PRIO_CYCLE:
        result = sla_mod.predict_risk(_make_inc(0, priority=p))
        assert 0 <= result["risk_pct"] <= 100


def test_predict_risk_level_valor_valido():
    sla_mod.train(_make_training_set(40), SLA_MAP)
    niveis = {"baixo", "médio", "alto", "crítico"}
    for p in _PRIO_CYCLE:
        result = sla_mod.predict_risk(_make_inc(0, priority=p))
        assert result["risk_level"] in niveis


def test_predict_model_ready_true_apos_treino():
    sla_mod.train(_make_training_set(40), SLA_MAP)
    result = sla_mod.predict_risk(_make_inc(0, priority="P1"))
    assert result["model_ready"] is True


def test_predict_usa_cache_na_segunda_chamada():
    sla_mod.train(_make_training_set(40), SLA_MAP)
    inc = _make_inc(0, priority="P3")
    sla_mod.predict_risk(inc)          # carrega modelo → popula cache
    assert "model" in sla_mod._cache
    sla_mod.predict_risk(inc)          # usa cache — não deve levantar exceção
