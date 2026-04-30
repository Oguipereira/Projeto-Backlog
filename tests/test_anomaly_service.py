"""
Testes unitários para anomaly_service.

Usa objetos mock com datas controladas para garantir resultados
determinísticos na detecção de anomalias por z-score.
"""
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import pytest

import app.database  # noqa: F401
from app.services.anomaly_service import detect_anomalies, system_trend

random.seed(99)


# ── Mocks ─────────────────────────────────────────────────────── #

@dataclass
class _Sys:
    name: str

@dataclass
class _Inc:
    incident_id: str
    started_at: datetime
    priority: str = "P3"
    system: Optional[_Sys] = None


def _make_inc(idx: int, system: str, started_at: datetime, priority: str = "P3") -> _Inc:
    return _Inc(
        incident_id=f"INC-{idx:04d}",
        started_at=started_at,
        priority=priority,
        system=_Sys(system),
    )


def _make_history(
    system: str,
    n_historical: int,
    n_recent: int,
    history_weeks: int = 8,
    recent_days: int = 7,
    seed: int = 0,
) -> list:
    """
    Gera incidentes históricos distribuídos uniformemente nas últimas
    history_weeks semanas (exceto o período recente) + n_recent incidentes
    nos últimos recent_days dias.
    """
    rng = random.Random(seed)
    now = datetime.now()
    history_start = now - timedelta(weeks=history_weeks)
    history_end = now - timedelta(days=recent_days)
    span = (history_end - history_start).total_seconds()

    incs = []
    for i in range(n_historical):
        offset = rng.uniform(0, span)
        incs.append(_make_inc(i, system, history_start + timedelta(seconds=offset)))

    for j in range(n_recent):
        offset = rng.uniform(1, recent_days * 86400 - 1)
        incs.append(_make_inc(n_historical + j, system, now - timedelta(seconds=offset)))

    return incs


# ── detect_anomalies ──────────────────────────────────────────── #

class TestDetectAnomalies:
    def test_lista_vazia_retorna_vazio(self):
        assert detect_anomalies([]) == []

    def test_detecta_anomalia_volume_alto(self):
        # 8 históricos (≈1/semana) vs 20 recentes → z alto
        incs = _make_history("SistemaX", n_historical=8, n_recent=20, seed=1)
        result = detect_anomalies(incs, recent_days=7, z_threshold=2.0)
        assert any(a["system"] == "SistemaX" for a in result)

    def test_nao_detecta_anomalia_volume_normal(self):
        # Histórico e recente equivalentes → sem anomalia
        incs = _make_history("SistemaY", n_historical=16, n_recent=2, seed=2)
        result = detect_anomalies(incs, recent_days=7, z_threshold=2.0)
        assert not any(a["system"] == "SistemaY" for a in result)

    def test_resultado_ordenado_por_z_score_decrescente(self):
        incs = (
            _make_history("A", n_historical=8, n_recent=30, seed=3)
            + _make_history("B", n_historical=8, n_recent=15, seed=4)
        )
        result = detect_anomalies(incs, z_threshold=1.0)
        for i in range(len(result) - 1):
            assert result[i]["z_score"] >= result[i + 1]["z_score"]

    def test_campos_obrigatorios_presentes(self):
        incs = _make_history("C", n_historical=8, n_recent=20, seed=5)
        result = detect_anomalies(incs, z_threshold=1.0)
        campos = {"system", "recent_count", "weekly_avg", "weekly_std", "z_score", "severity"}
        for a in result:
            assert campos.issubset(a.keys())

    def test_severity_valores_validos(self):
        incs = _make_history("D", n_historical=8, n_recent=25, seed=6)
        result = detect_anomalies(incs, z_threshold=1.0)
        validos = {"moderado", "alto", "crítico"}
        for a in result:
            assert a["severity"] in validos

    def test_z_score_acima_do_threshold(self):
        threshold = 2.0
        incs = _make_history("E", n_historical=8, n_recent=20, seed=7)
        result = detect_anomalies(incs, z_threshold=threshold)
        for a in result:
            assert a["z_score"] >= threshold

    def test_sistema_sem_historico_ignorado(self):
        # Incidentes só no período recente → sem baseline → não gera anomalia
        now = datetime.now()
        incs = [_make_inc(i, "Novo", now - timedelta(hours=i + 1)) for i in range(5)]
        result = detect_anomalies(incs, recent_days=7, min_history_weeks=4)
        assert not any(a["system"] == "Novo" for a in result)

    def test_multissistemas_detecta_apenas_anomalos(self):
        incs = (
            _make_history("Anomalo", n_historical=8, n_recent=25, seed=8)
            + _make_history("Normal", n_historical=16, n_recent=2, seed=9)
        )
        result = detect_anomalies(incs, z_threshold=2.0)
        sistemas = [a["system"] for a in result]
        assert "Anomalo" in sistemas
        assert "Normal" not in sistemas

    def test_sistema_historico_constante_alerta_se_dobro(self):
        # Z-score infinito quando std=0 e recente >= 2x média → usa z=3.0 hardcoded
        now = datetime.now()
        incs = []
        for w in range(1, 9):
            incs.append(_make_inc(w, "Estavel", now - timedelta(weeks=w, days=1)))
        for j in range(10):
            incs.append(_make_inc(100 + j, "Estavel", now - timedelta(hours=j + 1)))
        result = detect_anomalies(incs, recent_days=7, z_threshold=2.0)
        assert any(a["system"] == "Estavel" for a in result)

    def test_recent_count_correto(self):
        incs = _make_history("F", n_historical=8, n_recent=15, seed=10)
        result = detect_anomalies(incs, z_threshold=1.0)
        r = next((a for a in result if a["system"] == "F"), None)
        if r:
            assert r["recent_count"] == 15

    def test_weekly_avg_positivo(self):
        incs = _make_history("G", n_historical=12, n_recent=20, seed=11)
        result = detect_anomalies(incs, z_threshold=1.0)
        for a in result:
            assert a["weekly_avg"] > 0


# ── system_trend ──────────────────────────────────────────────── #

class TestSystemTrend:
    def test_retorna_exatamente_n_semanas(self):
        incs = [_make_inc(i, "ERP", datetime.now() - timedelta(days=i)) for i in range(10)]
        assert len(system_trend(incs, "ERP", weeks=8)) == 8

    def test_retorna_1_semana(self):
        incs = [_make_inc(0, "ERP", datetime.now() - timedelta(days=1))]
        assert len(system_trend(incs, "ERP", weeks=1)) == 1

    def test_campos_obrigatorios(self):
        incs = [_make_inc(0, "ERP", datetime.now() - timedelta(days=1))]
        for entry in system_trend(incs, "ERP", weeks=4):
            assert {"week_start", "count", "p1_p2"}.issubset(entry.keys())

    def test_sistema_inexistente_retorna_zeros(self):
        incs = [_make_inc(0, "ERP", datetime.now() - timedelta(days=1))]
        result = system_trend(incs, "Fantasma", weeks=4)
        assert all(r["count"] == 0 for r in result)
        assert all(r["p1_p2"] == 0 for r in result)

    def test_total_count_bate_com_incidentes(self):
        now = datetime.now()
        incs = [_make_inc(i, "CRM", now - timedelta(days=i + 1)) for i in range(6)]
        result = system_trend(incs, "CRM", weeks=4)
        assert sum(r["count"] for r in result) == 6

    def test_p1_p2_conta_apenas_alta_prioridade(self):
        now = datetime.now()
        incs = [
            _make_inc(0, "MES", now - timedelta(days=1), priority="P1"),
            _make_inc(1, "MES", now - timedelta(days=1), priority="P2"),
            _make_inc(2, "MES", now - timedelta(days=1), priority="P3"),
            _make_inc(3, "MES", now - timedelta(days=1), priority="P4"),
        ]
        result = system_trend(incs, "MES", weeks=2)
        assert sum(r["p1_p2"] for r in result) == 2

    def test_week_start_e_datetime(self):
        incs = [_make_inc(0, "ERP", datetime.now() - timedelta(days=1))]
        result = system_trend(incs, "ERP", weeks=4)
        for entry in result:
            assert isinstance(entry["week_start"], datetime)

    def test_semanas_em_ordem_cronologica(self):
        incs = [_make_inc(i, "WMS", datetime.now() - timedelta(days=i)) for i in range(14)]
        result = system_trend(incs, "WMS", weeks=4)
        for i in range(len(result) - 1):
            assert result[i]["week_start"] < result[i + 1]["week_start"]
