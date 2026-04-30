"""
Testes para import_service.py.

Cobre: normalização de valores, detecção de colunas, parsing de datas/duração,
análise de DataFrame e commit no banco. Sem arquivos reais — usa DataFrames
e objetos de arquivo criados em memória.
"""
import io
from datetime import datetime

import pandas as pd
import pytest

import app.database  # noqa: F401 — evita circular import
from app.services.import_service import (
    _fuzzy_match,
    _norm_priority,
    _norm_status,
    _parse_dt,
    _parse_duration,
    _safe_isna,
    analyze_dataframe,
    commit_import,
    detect_column_mapping,
    read_file,
)


# ------------------------------------------------------------------ #
#  _norm_priority                                                     #
# ------------------------------------------------------------------ #

class TestNormPriority:
    @pytest.mark.parametrize("raw,expected", [
        ("P1", "P1"), ("p1", "P1"), ("1", "P1"),
        ("crítico", "P1"), ("critico", "P1"), ("urgente", "P1"), ("critical", "P1"),
        ("P2", "P2"), ("alto", "P2"), ("high", "P2"), ("grave", "P2"),
        ("P3", "P3"), ("médio", "P3"), ("medio", "P3"), ("medium", "P3"),
        ("P4", "P4"), ("baixo", "P4"), ("low", "P4"), ("leve", "P4"),
    ])
    def test_mapeamentos_conhecidos(self, raw, expected):
        assert _norm_priority(raw) == expected

    def test_valor_desconhecido_retorna_none(self):
        assert _norm_priority("urgentíssimo") is None

    def test_none_retorna_none(self):
        assert _norm_priority(None) is None

    def test_strip_de_espacos(self):
        assert _norm_priority("  P1  ") == "P1"


# ------------------------------------------------------------------ #
#  _norm_status                                                       #
# ------------------------------------------------------------------ #

class TestNormStatus:
    @pytest.mark.parametrize("raw,expected", [
        ("aberto",       "Aberto"),
        ("open",         "Aberto"),
        ("novo",         "Aberto"),
        ("pendente",     "Aberto"),
        ("em andamento", "Em Andamento"),
        ("in progress",  "Em Andamento"),
        ("working",      "Em Andamento"),
        ("resolvido",    "Resolvido"),
        ("resolved",     "Resolvido"),
        ("closed",       "Resolvido"),
        ("done",         "Resolvido"),
        ("finalizado",   "Resolvido"),
    ])
    def test_mapeamentos_conhecidos(self, raw, expected):
        assert _norm_status(raw) == expected

    def test_valor_desconhecido_usa_aberto_como_fallback(self):
        assert _norm_status("qualquer_coisa") == "Aberto"

    def test_none_retorna_aberto(self):
        assert _norm_status(None) == "Aberto"


# ------------------------------------------------------------------ #
#  _parse_duration                                                    #
# ------------------------------------------------------------------ #

class TestParseDuration:
    @pytest.mark.parametrize("raw,expected", [
        ("120",    120.0),
        ("90.5",   90.5),
        ("2h",     120.0),
        ("2h30m",  150.0),
        ("2h 30m", 150.0),
        ("1:30",    90.0),
        ("45min",   45.0),
        ("45m",     45.0),
    ])
    def test_formatos_válidos(self, raw, expected):
        assert _parse_duration(raw) == expected

    def test_none_retorna_none(self):
        assert _parse_duration(None) is None

    def test_texto_inválido_retorna_none(self):
        assert _parse_duration("não é duração") is None

    def test_nan_retorna_none(self):
        assert _parse_duration(float("nan")) is None


# ------------------------------------------------------------------ #
#  _parse_dt                                                          #
# ------------------------------------------------------------------ #

class TestParseDt:
    def test_string_br_dia_mês_ano(self):
        result = _parse_dt("15/03/2024")
        assert result == datetime(2024, 3, 15)

    def test_string_formato_br(self):
        # dayfirst=True: "01/06/2024" → dia=01, mês=06 → 1 de junho
        result = _parse_dt("01/06/2024")
        assert result == datetime(2024, 6, 1)

    def test_pandas_timestamp(self):
        ts = pd.Timestamp("2024-06-01 08:30:00")
        result = _parse_dt(ts)
        assert result == datetime(2024, 6, 1, 8, 30, 0)

    def test_datetime_nativo(self):
        dt = datetime(2024, 6, 1, 9, 0)
        assert _parse_dt(dt) == dt

    def test_none_retorna_none(self):
        assert _parse_dt(None) is None

    def test_string_invalida_retorna_none(self):
        assert _parse_dt("não é data") is None

    def test_combina_data_e_hora(self):
        result = _parse_dt("2024-06-01", "14:30")
        assert result.hour == 14
        assert result.minute == 30

    def test_hora_inválida_usa_hora_da_data(self):
        result = _parse_dt("2024-06-01 08:00", "hora_errada")
        assert result is not None  # data ainda é válida


# ------------------------------------------------------------------ #
#  _fuzzy_match                                                       #
# ------------------------------------------------------------------ #

class TestFuzzyMatch:
    def test_match_exato(self):
        assert _fuzzy_match("ERP", ["ERP", "CRM", "SAP"]) == "ERP"

    def test_match_aproximado(self):
        result = _fuzzy_match("Falha de Rede", ["Falha Rede", "Queda Energia"])
        assert result == "Falha Rede"

    def test_sem_match_retorna_none(self):
        assert _fuzzy_match("xyz123abc", ["ERP", "CRM"]) is None

    def test_lista_vazia_retorna_none(self):
        assert _fuzzy_match("ERP", []) is None

    def test_nome_vazio_retorna_none(self):
        assert _fuzzy_match("", ["ERP"]) is None


# ------------------------------------------------------------------ #
#  detect_column_mapping                                              #
# ------------------------------------------------------------------ #

class TestDetectColumnMapping:
    def test_nomes_exatos_em_português(self):
        cols = ["título", "início", "sistema", "tipo", "prioridade"]
        mapping = detect_column_mapping(cols)
        assert mapping["title"]         == "título"
        assert mapping["started_at"]    == "início"
        assert mapping["system"]        == "sistema"
        assert mapping["incident_type"] == "tipo"
        assert mapping["priority"]      == "prioridade"

    def test_nomes_em_inglês(self):
        cols = ["title", "start", "system", "type", "priority", "status"]
        mapping = detect_column_mapping(cols)
        assert mapping["title"]    == "title"
        assert mapping["system"]   == "system"
        assert mapping["priority"] == "priority"

    def test_coluna_ausente_mapeia_none(self):
        mapping = detect_column_mapping(["título"])
        assert mapping["started_at"] is None

    def test_cada_coluna_usada_uma_única_vez(self):
        cols = ["título", "título"]  # duplicata
        mapping = detect_column_mapping(cols)
        # O mesmo valor de coluna não deve aparecer duas vezes
        used = [v for v in mapping.values() if v is not None]
        assert len(used) == len(set(used))

    def test_alias_variante(self):
        mapping = detect_column_mapping(["chamado", "abertura", "sistema"])
        assert mapping["title"]      == "chamado"
        assert mapping["started_at"] == "abertura"


# ------------------------------------------------------------------ #
#  analyze_dataframe                                                  #
# ------------------------------------------------------------------ #

def _make_df(**cols) -> pd.DataFrame:
    """Cria um DataFrame de uma linha a partir de colunas nomeadas."""
    return pd.DataFrame([cols])


def _base_col_map() -> dict:
    return {
        "title":         "título",
        "started_at":    "início",
        "started_time":  None,
        "ended_at":      "fim",
        "ended_time":    None,
        "system":        "sistema",
        "incident_type": "tipo",
        "priority":      "prioridade",
        "status":        "status",
        "duration_minutes": None,
        "affected_users":   "afetados",
        "root_cause":       None,
        "resolution_notes": None,
        "description":      None,
    }


SYSTEMS = ["ERP", "CRM"]
TYPES   = ["Falha de Rede", "Lentidão"]


class TestAnalyzeDataframe:
    def test_linha_válida_completa(self):
        df = _make_df(
            título="Queda do sistema",
            início="2024-06-01",
            fim="2024-06-01 10:00",
            sistema="ERP",
            tipo="Falha de Rede",
            prioridade="P1",
            status="resolvido",
            afetados="100",
        )
        valid, errors, new_sys, new_types = analyze_dataframe(df, _base_col_map(), SYSTEMS, TYPES)
        assert len(valid) == 1
        assert len(errors) == 0
        assert valid[0]["title"] == "Queda do sistema"
        assert valid[0]["priority"] == "P1"
        assert valid[0]["status"] == "Resolvido"

    def test_título_ausente_gera_erro(self):
        df = _make_df(
            título=None,
            início="2024-06-01",
            sistema="ERP",
            tipo="Falha de Rede",
            prioridade="P1",
        )
        valid, errors, _, _ = analyze_dataframe(df, _base_col_map(), SYSTEMS, TYPES)
        assert len(valid) == 0
        assert any("título" in e for e in errors[0]["errors"])

    def test_data_inválida_gera_erro(self):
        df = _make_df(
            título="Incidente",
            início="não é data",
            sistema="ERP",
            tipo="Falha de Rede",
            prioridade="P1",
        )
        _, errors, _, _ = analyze_dataframe(df, _base_col_map(), SYSTEMS, TYPES)
        assert any("início" in e for e in errors[0]["errors"])

    def test_prioridade_inválida_gera_erro(self):
        df = _make_df(
            título="Incidente",
            início="2024-06-01",
            sistema="ERP",
            tipo="Falha de Rede",
            prioridade="P9",
        )
        _, errors, _, _ = analyze_dataframe(df, _base_col_map(), SYSTEMS, TYPES)
        assert any("prioridade" in e for e in errors[0]["errors"])

    def test_sistema_desconhecido_vai_para_new_systems(self):
        df = _make_df(
            título="Incidente",
            início="2024-06-01",
            sistema="SAP",
            tipo="Falha de Rede",
            prioridade="P2",
        )
        valid, _, new_sys, _ = analyze_dataframe(df, _base_col_map(), SYSTEMS, TYPES)
        assert "SAP" in new_sys
        assert valid[0]["_system_name"] == "SAP"

    def test_tipo_desconhecido_vai_para_new_types(self):
        df = _make_df(
            título="Incidente",
            início="2024-06-01",
            sistema="ERP",
            tipo="Falha Elétrica",
            prioridade="P3",
        )
        valid, _, _, new_types = analyze_dataframe(df, _base_col_map(), SYSTEMS, TYPES)
        assert "Falha Elétrica" in new_types

    def test_ended_at_derivado_de_duration_minutes(self):
        col_map = _base_col_map()
        col_map["duration_minutes"] = "duração"
        col_map["ended_at"] = None
        # Usa pd.Timestamp para evitar ambiguidade do dayfirst
        df = pd.DataFrame([{
            "título":  "Incidente",
            "início":  pd.Timestamp("2024-06-01 08:00"),
            "sistema": "ERP",
            "tipo":    "Falha de Rede",
            "prioridade": "P2",
            "duração": "60",
        }])
        valid, errors, _, _ = analyze_dataframe(df, col_map, SYSTEMS, TYPES)
        assert len(valid) == 1
        assert valid[0]["ended_at"] == datetime(2024, 6, 1, 9, 0)

    def test_affected_users_convertido_para_int(self):
        df = _make_df(
            título="Incidente",
            início="2024-06-01",
            sistema="ERP",
            tipo="Falha de Rede",
            prioridade="P1",
            afetados="250",
        )
        valid, _, _, _ = analyze_dataframe(df, _base_col_map(), SYSTEMS, TYPES)
        assert valid[0]["affected_users"] == 250

    def test_affected_users_inválido_usa_zero(self):
        df = _make_df(
            título="Incidente",
            início="2024-06-01",
            sistema="ERP",
            tipo="Falha de Rede",
            prioridade="P1",
            afetados="abc",
        )
        valid, _, _, _ = analyze_dataframe(df, _base_col_map(), SYSTEMS, TYPES)
        assert valid[0]["affected_users"] == 0

    def test_múltiplas_linhas_válidas_e_inválidas(self):
        df = pd.DataFrame([
            {"título": "Inc 1", "início": "2024-06-01", "sistema": "ERP",
             "tipo": "Falha de Rede", "prioridade": "P1"},
            {"título": None,    "início": "2024-06-02", "sistema": "ERP",
             "tipo": "Falha de Rede", "prioridade": "P2"},
        ])
        valid, errors, _, _ = analyze_dataframe(df, _base_col_map(), SYSTEMS, TYPES)
        assert len(valid) == 1
        assert len(errors) == 1
        assert errors[0]["row"] == 3  # linha 2 do df → row = idx+2


# ------------------------------------------------------------------ #
#  commit_import                                                      #
# ------------------------------------------------------------------ #

class TestCommitImport:
    def test_importa_linhas_válidas(self, populated_db):
        db, system, itype = populated_db["db"], populated_db["system"], populated_db["itype"]
        rows = [{
            "title":            "Incidente importado",
            "started_at":       datetime(2024, 6, 1, 8, 0),
            "ended_at":         datetime(2024, 6, 1, 9, 0),
            "priority":         "P2",
            "status":           "Resolvido",
            "description":      "",
            "root_cause":       "",
            "resolution_notes": "",
            "affected_users":   10,
            "_system_name":     system.name,
            "_type_name":       itype.name,
        }]
        result = commit_import(rows, db)
        assert result["imported"] == 1
        assert result["skipped"] == 0

    def test_cria_sistema_novo_durante_import(self, populated_db):
        db, _, itype = populated_db["db"], populated_db["system"], populated_db["itype"]
        rows = [{
            "title":            "Inc com sistema novo",
            "started_at":       datetime(2024, 6, 1, 8, 0),
            "ended_at":         None,
            "priority":         "P3",
            "status":           "Aberto",
            "description":      "",
            "root_cause":       "",
            "resolution_notes": "",
            "affected_users":   0,
            "_system_name":     "SAP_NOVO",
            "_type_name":       itype.name,
        }]
        result = commit_import(rows, db)
        assert result["imported"] == 1
        from app.services.incident_service import IncidentService
        sistemas = IncidentService(db).get_systems(active_only=False)
        assert any(s.name == "SAP_NOVO" for s in sistemas)

    def test_cria_tipo_novo_durante_import(self, populated_db):
        db, system, _ = populated_db["db"], populated_db["system"], populated_db["itype"]
        rows = [{
            "title":            "Inc com tipo novo",
            "started_at":       datetime(2024, 6, 1, 8, 0),
            "ended_at":         None,
            "priority":         "P4",
            "status":           "Aberto",
            "description":      "",
            "root_cause":       "",
            "resolution_notes": "",
            "affected_users":   0,
            "_system_name":     system.name,
            "_type_name":       "Tipo Inédito",
        }]
        result = commit_import(rows, db)
        assert result["imported"] == 1
        from app.services.incident_service import IncidentService
        tipos = IncidentService(db).get_incident_types(active_only=False)
        assert any(t.name == "Tipo Inédito" for t in tipos)

    def test_lista_vazia_retorna_zeros(self, populated_db):
        result = commit_import([], populated_db["db"])
        assert result == {"imported": 0, "skipped": 0}


# ------------------------------------------------------------------ #
#  read_file                                                          #
# ------------------------------------------------------------------ #

class _FakeFile:
    """Simula o objeto de arquivo do Streamlit."""
    def __init__(self, name: str, content: bytes):
        self.name = name
        self._content = content

    def read(self) -> bytes:
        return self._content


class TestReadFile:
    def test_csv_vírgula(self):
        csv = "título,início,sistema\nQueda,2024-06-01,ERP\n"
        f = _FakeFile("dados.csv", csv.encode("utf-8"))
        df, err = read_file(f)
        assert err is None
        assert len(df) == 1
        assert "título" in df.columns

    def test_csv_ponto_e_vírgula(self):
        csv = "título;início;sistema\nQueda;2024-06-01;ERP\n"
        f = _FakeFile("dados.csv", csv.encode("utf-8"))
        df, err = read_file(f)
        assert err is None
        assert len(df) == 1

    def test_csv_latin1(self):
        csv = "título;início\nQueda;2024-06-01\n"
        f = _FakeFile("dados.csv", csv.encode("latin-1"))
        df, err = read_file(f)
        assert err is None

    def test_excel(self):
        import io as _io
        buf = _io.BytesIO()
        pd.DataFrame([{"título": "Queda", "início": "2024-06-01"}]).to_excel(buf, index=False)
        f = _FakeFile("dados.xlsx", buf.getvalue())
        df, err = read_file(f)
        assert err is None
        assert len(df) == 1

    def test_csv_sem_conteúdo_lê_dataframe_vazio(self):
        # latin-1 decodifica qualquer byte, então CSVs nunca falham por encoding.
        # Um CSV só com cabeçalho produz DataFrame vazio (sem erro).
        csv = "título;início;sistema\n"
        f = _FakeFile("dados.csv", csv.encode("utf-8"))
        df, err = read_file(f)
        assert err is None
        assert len(df) == 0

    def test_excel_corrompido_retorna_erro(self):
        f = _FakeFile("dados.xlsx", b"nao e um excel valido")
        df, err = read_file(f)
        assert err is not None
