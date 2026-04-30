"""
Performance: import service com DataFrames de 100, 500 e 1000 linhas.

Mede detect_column_mapping, analyze_dataframe e commit_import.
"""
import io
import random
import time

import pandas as pd
import pytest

import app.database  # noqa: F401
from app.services.import_service import analyze_dataframe, commit_import, detect_column_mapping, read_file

random.seed(1)

# ── Limites aceitáveis ─────────────────────────────────────────── #
LIMIT_DETECT_MAP    = 0.010   # s — detecção de colunas
LIMIT_ANALYZE_100   = 0.300   # s
LIMIT_ANALYZE_500   = 1.000   # s
LIMIT_ANALYZE_1000  = 2.000   # s
LIMIT_READ_CSV_1000 = 0.500   # s


# ── Helpers ────────────────────────────────────────────────────── #

SYSTEMS = ["ERP", "CRM", "WMS", "Portal de Vendas", "MES"]
TYPES   = ["Falha de Rede", "Lentidão", "Falha de Hardware", "Erro de Configuração"]
PRIOS   = ["P1", "P2", "P3", "P4"]
P_W     = [0.07, 0.18, 0.42, 0.33]


def _make_df(n: int) -> pd.DataFrame:
    rows = []
    base = pd.Timestamp("2024-01-01 08:00")
    for i in range(n):
        rows.append({
            "título":     f"Incidente {i:05d}",
            "início":     base + pd.Timedelta(hours=i * 2),
            "sistema":    random.choice(SYSTEMS),
            "tipo":       random.choice(TYPES),
            "prioridade": random.choices(PRIOS, weights=P_W)[0],
            "status":     "resolvido",
            "afetados":   str(random.randint(1, 300)),
        })
    return pd.DataFrame(rows)


def _col_map() -> dict:
    return {
        "title":            "título",
        "started_at":       "início",
        "started_time":     None,
        "ended_at":         None,
        "ended_time":       None,
        "system":           "sistema",
        "incident_type":    "tipo",
        "priority":         "prioridade",
        "status":           "status",
        "duration_minutes": None,
        "affected_users":   "afetados",
        "root_cause":       None,
        "resolution_notes": None,
        "description":      None,
    }


def _make_csv_bytes(n: int) -> bytes:
    df = _make_df(n)
    df["início"] = df["início"].dt.strftime("%d/%m/%Y %H:%M")
    buf = io.StringIO()
    df.to_csv(buf, index=False, sep=";")
    return buf.getvalue().encode("utf-8")


class _FakeFile:
    def __init__(self, name, content):
        self.name = name
        self._content = content

    def read(self):
        return self._content


# ── Fixtures ───────────────────────────────────────────────────── #

@pytest.fixture(scope="module")
def df_100():  return _make_df(100)

@pytest.fixture(scope="module")
def df_500():  return _make_df(500)

@pytest.fixture(scope="module")
def df_1000(): return _make_df(1000)


# ── Benchmarks: detect_column_mapping ─────────────────────────── #

def test_detect_map_7_colunas(benchmark):
    cols   = ["título", "início", "sistema", "tipo", "prioridade", "status", "afetados"]
    result = benchmark(detect_column_mapping, cols)
    assert result["title"] == "título"


def test_detect_map_20_colunas(benchmark):
    extras = [f"coluna_extra_{i}" for i in range(13)]
    cols   = ["título", "início", "sistema", "tipo", "prioridade", "status", "afetados"] + extras
    result = benchmark(detect_column_mapping, cols)
    assert result["title"] == "título"


# ── Benchmarks: analyze_dataframe ─────────────────────────────── #

def test_analyze_100(benchmark, df_100):
    valid, errors, _, _ = benchmark(analyze_dataframe, df_100, _col_map(), SYSTEMS, TYPES)
    assert len(valid) + len(errors) == 100


def test_analyze_500(benchmark, df_500):
    valid, errors, _, _ = benchmark(analyze_dataframe, df_500, _col_map(), SYSTEMS, TYPES)
    assert len(valid) + len(errors) == 500


def test_analyze_1000(benchmark, df_1000):
    valid, errors, _, _ = benchmark(analyze_dataframe, df_1000, _col_map(), SYSTEMS, TYPES)
    assert len(valid) + len(errors) == 1000


# ── Benchmarks: read_file (CSV) ───────────────────────────────── #

def test_read_csv_100(benchmark):
    f      = _FakeFile("dados.csv", _make_csv_bytes(100))
    df, e  = benchmark(read_file, f)
    assert e is None and len(df) == 100


def test_read_csv_500(benchmark):
    f      = _FakeFile("dados.csv", _make_csv_bytes(500))
    df, e  = benchmark(read_file, f)
    assert e is None and len(df) == 500


def test_read_csv_1000(benchmark):
    f      = _FakeFile("dados.csv", _make_csv_bytes(1000))
    df, e  = benchmark(read_file, f)
    assert e is None and len(df) == 1000


# ── Benchmarks: commit_import ─────────────────────────────────── #

def test_commit_import_100(benchmark, populated_db):
    db, system, itype = populated_db["db"], populated_db["system"], populated_db["itype"]
    df = _make_df(100)
    valid, _, _, _ = analyze_dataframe(df, _col_map(), [system.name], [itype.name])

    def _run():
        return commit_import(valid, db)

    result = benchmark(_run)
    assert result["imported"] > 0


# ── Limites rígidos ────────────────────────────────────────────── #

def test_detect_map_dentro_do_limite():
    cols = ["título", "início", "sistema", "tipo", "prioridade", "status", "afetados"]
    t0   = time.perf_counter()
    detect_column_mapping(cols)
    assert time.perf_counter() - t0 < LIMIT_DETECT_MAP, \
        f"detect_column_mapping excedeu {LIMIT_DETECT_MAP*1000:.0f}ms"


def test_analyze_100_dentro_do_limite(df_100):
    t0 = time.perf_counter()
    analyze_dataframe(df_100, _col_map(), SYSTEMS, TYPES)
    assert time.perf_counter() - t0 < LIMIT_ANALYZE_100, \
        f"analyze_dataframe(100) excedeu {LIMIT_ANALYZE_100*1000:.0f}ms"


def test_analyze_1000_dentro_do_limite(df_1000):
    t0 = time.perf_counter()
    analyze_dataframe(df_1000, _col_map(), SYSTEMS, TYPES)
    assert time.perf_counter() - t0 < LIMIT_ANALYZE_1000, \
        f"analyze_dataframe(1000) excedeu {LIMIT_ANALYZE_1000*1000:.0f}ms"


def test_read_csv_1000_dentro_do_limite():
    f  = _FakeFile("dados.csv", _make_csv_bytes(1000))
    t0 = time.perf_counter()
    read_file(f)
    assert time.perf_counter() - t0 < LIMIT_READ_CSV_1000, \
        f"read_file(1000 linhas CSV) excedeu {LIMIT_READ_CSV_1000*1000:.0f}ms"
