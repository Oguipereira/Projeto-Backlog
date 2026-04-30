"""
Testes unitários para similarity_service.

Usa objetos mock — sem DB — para testar a lógica TF-IDF
de forma isolada e determinística.
"""
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import pytest

import app.database  # noqa: F401 — resolve circular import
from app.services.similarity_service import find_similar

random.seed(42)


# ── Mocks ─────────────────────────────────────────────────────── #

@dataclass
class _Sys:
    name: str

@dataclass
class _Inc:
    incident_id: str
    title: str
    description: str = ""
    priority: str = "P3"
    status: str = "Resolvido"
    system: Optional[_Sys] = None
    duration_minutes: Optional[float] = 30.0
    root_cause: str = ""
    resolution_notes: str = ""


_TITLES = [
    "Queda de performance no ERP",
    "Falha de conectividade na rede",
    "Sistema de estoque indisponível",
    "Timeout na integração SAP",
    "Erro no módulo de relatórios",
    "Lentidão no acesso ao banco de dados",
    "Parada total do servidor de produção",
    "Falha no backup automático",
    "Erro de autenticação no portal",
    "Sistema de e-mail fora do ar",
]


def _make_candidates(n: int = 10) -> list:
    return [
        _Inc(
            incident_id=f"INC-{i:04d}",
            title=_TITLES[i % len(_TITLES)],
            description=f"Detalhes do incidente {i}",
            system=_Sys("ERP"),
            root_cause=f"Causa {i}",
            resolution_notes=f"Resolução {i}",
        )
        for i in range(n)
    ]


# ── Testes ────────────────────────────────────────────────────── #

class TestFindSimilarEntrada:
    def test_lista_vazia_retorna_vazio(self):
        assert find_similar("falha no sistema", "", []) == []

    def test_query_vazia_nao_levanta_excecao(self):
        result = find_similar("", "", _make_candidates(5))
        assert isinstance(result, list)

    def test_retorna_no_maximo_top_k(self):
        result = find_similar("falha de conectividade", "", _make_candidates(10), top_k=3)
        assert len(result) <= 3

    def test_top_k_maior_que_candidatos_ok(self):
        result = find_similar("erro", "", _make_candidates(3), top_k=10)
        assert len(result) <= 3


class TestFindSimilarOrdemEScore:
    def test_resultados_ordenados_por_score_decrescente(self):
        result = find_similar("falha de conectividade na rede", "", _make_candidates(10), top_k=5)
        for i in range(len(result) - 1):
            assert result[i]["similarity_score"] >= result[i + 1]["similarity_score"]

    def test_similarity_score_entre_0_e_1(self):
        result = find_similar("lentidão no sistema", "", _make_candidates(10), top_k=10)
        for r in result:
            assert 0.0 <= r["similarity_score"] <= 1.0

    def test_similarity_pct_entre_0_e_100(self):
        result = find_similar("queda de performance", "", _make_candidates(10), top_k=10)
        for r in result:
            assert 0 <= r["similarity_pct"] <= 100

    def test_similarity_score_e_pct_consistentes(self):
        result = find_similar("timeout integração", "", _make_candidates(10), top_k=5)
        for r in result:
            assert r["similarity_pct"] == int(round(r["similarity_score"] * 100))

    def test_min_score_exclui_irrelevantes(self):
        candidatos = [_Inc(f"INC-{i}", f"zyx qwerty asdf {i}", system=_Sys("X")) for i in range(5)]
        result = find_similar("performance network latency", "", candidatos, min_score=0.99)
        assert result == []


class TestFindSimilarCampos:
    def test_campos_obrigatorios_presentes(self):
        result = find_similar("lentidão", "", _make_candidates(5), top_k=3)
        campos = {"incident_id", "title", "system", "priority", "status",
                  "duration_formatted", "root_cause", "resolution_notes",
                  "similarity_score", "similarity_pct"}
        for r in result:
            assert campos.issubset(r.keys())

    def test_incidente_sem_root_cause_retorna_string_vazia(self):
        candidatos = [_Inc("INC-0001", "Falha de rede", system=_Sys("ERP"), root_cause="")]
        result = find_similar("falha de rede", "", candidatos)
        if result:
            assert result[0]["root_cause"] == ""

    def test_incidente_sem_resolution_retorna_string_vazia(self):
        candidatos = [_Inc("INC-0001", "Erro no portal", system=_Sys("ERP"), resolution_notes="")]
        result = find_similar("erro no portal", "", candidatos)
        if result:
            assert result[0]["resolution_notes"] == ""

    def test_similarity_score_e_float(self):
        result = find_similar("timeout", "", _make_candidates(5), top_k=5)
        for r in result:
            assert isinstance(r["similarity_score"], float)

    def test_similarity_pct_e_inteiro(self):
        result = find_similar("timeout", "", _make_candidates(5), top_k=5)
        for r in result:
            assert isinstance(r["similarity_pct"], int)

    def test_busca_com_titulo_e_descricao(self):
        result = find_similar("sistema", "banco de dados lentidão timeout", _make_candidates(10))
        assert isinstance(result, list)
