import re
import io
import pandas as pd
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Optional
from dateutil import parser as dateparser

# ── Normalisation maps ──────────────────────────────────────────────── #

PRIORITY_MAP = {
    "p1": "P1", "1": "P1", "crítico": "P1", "critico": "P1", "urgente": "P1",
    "critical": "P1",
    "p2": "P2", "2": "P2", "alto": "P2", "high": "P2", "grave": "P2",
    "sério": "P2", "serio": "P2",
    "p3": "P3", "3": "P3", "médio": "P3", "medio": "P3", "medium": "P3",
    "moderado": "P3", "media": "P3",
    "p4": "P4", "4": "P4", "baixo": "P4", "low": "P4", "leve": "P4",
    "menor": "P4",
}

STATUS_MAP = {
    "aberto": "Aberto", "open": "Aberto", "novo": "Aberto",
    "new": "Aberto", "pendente": "Aberto",
    "em andamento": "Em Andamento", "andamento": "Em Andamento",
    "in progress": "Em Andamento", "em_andamento": "Em Andamento",
    "working": "Em Andamento", "progress": "Em Andamento",
    "resolvido": "Resolvido", "resolved": "Resolvido", "fechado": "Resolvido",
    "closed": "Resolvido", "concluído": "Resolvido", "concluido": "Resolvido",
    "done": "Resolvido", "finalizado": "Resolvido",
}

# Column header aliases for auto-detection
COLUMN_ALIASES = {
    "title":            ["título", "titulo", "incidente", "nome", "assunto",
                         "ocorrência", "ocorrencia", "title", "chamado", "evento"],
    "started_at":       ["início", "inicio", "data_inicio", "data_abertura",
                         "abertura", "start", "data inicio", "data abertura",
                         "dt_inicio", "dt_abertura", "data_inicio"],
    "started_time":     ["hora_inicio", "hora_abertura", "hora inicio",
                         "hora abertura", "time_start", "hr_inicio"],
    "system":           ["sistema", "system", "aplicação", "aplicacao", "app",
                         "sistema_afetado", "sistema afetado", "aplicativo"],
    "incident_type":    ["tipo", "type", "categoria", "category",
                         "tipo_incidente", "tipo incidente",
                         "classificação", "classificacao", "tipo_ocorrencia"],
    "priority":         ["prioridade", "priority", "severidade", "criticidade",
                         "nivel", "nivel_criticidade", "nivel criticidade", "sla"],
    "status":           ["status", "estado", "situacao", "situação", "estado_atual"],
    "ended_at":         ["fim", "encerramento", "fechamento", "end", "data_fim",
                         "data_encerramento", "data fim", "data encerramento",
                         "dt_fim", "resolução_data", "data_resolucao"],
    "ended_time":       ["hora_fim", "hora_encerramento", "hora fim",
                         "hora encerramento", "time_end", "hr_fim"],
    "duration_minutes": ["duração", "duracao", "duration", "tempo_parado",
                         "downtime", "minutos_parado", "min_parado",
                         "tempo parado", "tempo_indisponivel"],
    "affected_users":   ["usuarios", "users", "afetados", "impactados",
                         "usuarios_afetados", "users_affected", "qtd_usuarios"],
    "root_cause":       ["causa", "causa_raiz", "root_cause", "causa raiz",
                         "motivo", "origem"],
    "resolution_notes": ["notas_resolucao", "resolution_notes", "solução",
                         "solucao", "notas", "resolucao", "como_resolvido"],
    "description":      ["descrição", "descricao", "description", "detalhes",
                         "details", "obs", "observações", "observacoes"],
}

FIELD_LABELS = {
    "title":            "Título *",
    "started_at":       "Data de Início *",
    "started_time":     "Hora de Início",
    "system":           "Sistema *",
    "incident_type":    "Tipo de Incidente *",
    "priority":         "Prioridade *",
    "status":           "Status",
    "ended_at":         "Data de Fim",
    "ended_time":       "Hora de Fim",
    "duration_minutes": "Duração (min)",
    "affected_users":   "Usuários Afetados",
    "root_cause":       "Causa Raiz",
    "resolution_notes": "Notas de Resolução",
    "description":      "Descrição",
}

REQUIRED_FIELDS = {"title", "started_at", "system", "incident_type", "priority"}


# ── Helpers ─────────────────────────────────────────────────────────── #

def _sim(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _safe_isna(v) -> bool:
    try:
        return pd.isna(v)
    except Exception:
        return v is None


def _get_cell(row, col: Optional[str]):
    if not col or col not in row.index:
        return None
    v = row[col]
    return None if _safe_isna(v) else v


# ── Column detection ─────────────────────────────────────────────────── #

def detect_column_mapping(columns: list) -> dict:
    """Auto-maps schema fields to CSV/Excel column names via fuzzy matching."""
    mapping = {}
    used: set = set()
    for field, aliases in COLUMN_ALIASES.items():
        best_col, best_score = None, 0.0
        for col in columns:
            if col in used:
                continue
            col_norm = col.lower().strip().replace("-", " ").replace("_", " ")
            for alias in aliases:
                alias_norm = alias.lower().replace("_", " ")
                # Exact match
                if col_norm == alias_norm:
                    best_col, best_score = col, 1.0
                    break
                score = _sim(col_norm, alias_norm)
                if score > best_score and score >= 0.75:
                    best_score = score
                    best_col = col
            if best_score == 1.0:
                break
        mapping[field] = best_col
        if best_col:
            used.add(best_col)
    return mapping


# ── Value normalisers ────────────────────────────────────────────────── #

def _norm_priority(val) -> Optional[str]:
    if val is None:
        return None
    v = str(val).strip().lower()
    return PRIORITY_MAP.get(v)


def _norm_status(val) -> str:
    if val is None:
        return "Aberto"
    v = str(val).strip().lower()
    return STATUS_MAP.get(v, "Aberto")


def _parse_dt(date_val, time_val=None) -> Optional[datetime]:
    if date_val is None:
        return None
    try:
        if isinstance(date_val, pd.Timestamp):
            dt = date_val.to_pydatetime().replace(tzinfo=None)
        elif isinstance(date_val, datetime):
            dt = date_val.replace(tzinfo=None)
        else:
            dt = dateparser.parse(str(date_val), dayfirst=True)
        if time_val is not None and not _safe_isna(time_val):
            try:
                t = dateparser.parse(str(time_val)).time()
                dt = dt.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
            except Exception:
                pass
        return dt
    except Exception:
        return None


def _parse_duration(val) -> Optional[float]:
    """Returns minutes from various formats: '120', '2h', '2h30m', '2:30'."""
    if val is None or _safe_isna(val):
        return None
    s = str(val).strip().lower()
    try:
        return float(s)
    except ValueError:
        pass
    m = re.match(r"(\d+)\s*h\s*(\d+)\s*m?", s)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    m = re.match(r"(\d+)\s*h", s)
    if m:
        return int(m.group(1)) * 60
    m = re.match(r"(\d+)\s*m(?:in)?", s)
    if m:
        return float(m.group(1))
    m = re.match(r"(\d+):(\d+)", s)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    return None


def _fuzzy_match(name: str, options: list, threshold: float = 0.65) -> Optional[str]:
    if not name or not options:
        return None
    best, best_score = None, 0.0
    for opt in options:
        score = _sim(name.strip().lower(), opt.lower())
        if score > best_score:
            best_score, best = score, opt
    return best if best_score >= threshold else None


# ── Core analysis (no DB writes) ─────────────────────────────────────── #

def analyze_dataframe(
    df: pd.DataFrame,
    col_map: dict,
    existing_systems: list,
    existing_types: list,
) -> tuple:
    """
    Pure analysis pass — no DB writes.
    Returns (valid_rows, error_rows, new_systems, new_types).
    Each valid_row is a dict ready for IncidentService.create().
    """
    new_systems: set = set()
    new_types:   set = set()
    valid_rows:  list = []
    error_rows:  list = []

    for idx, row in df.iterrows():
        errors = []
        result = {}

        def get(field):
            return _get_cell(row, col_map.get(field))

        # Title
        title = get("title")
        if not title:
            errors.append("título ausente")
        else:
            result["title"] = str(title).strip()[:200]

        # started_at
        started_at = _parse_dt(get("started_at"), get("started_time"))
        if not started_at:
            errors.append("data de início inválida ou ausente")
        else:
            result["started_at"] = started_at

        # ended_at (direct or from duration)
        ended_at = _parse_dt(get("ended_at"), get("ended_time"))
        if not ended_at and started_at:
            dur = _parse_duration(get("duration_minutes"))
            if dur:
                ended_at = started_at + timedelta(minutes=dur)
        result["ended_at"] = ended_at

        # Priority
        raw_p = get("priority")
        priority = _norm_priority(str(raw_p)) if raw_p is not None else None
        if not priority:
            errors.append(f"prioridade '{raw_p}' não reconhecida (use P1/P2/P3/P4)")
        else:
            result["priority"] = priority

        # Status
        result["status"] = _norm_status(get("status"))

        # System
        raw_sys = get("system")
        if not raw_sys:
            errors.append("sistema ausente")
        else:
            sys_name = _fuzzy_match(str(raw_sys), existing_systems)
            if sys_name:
                result["_system_name"] = sys_name
            else:
                result["_system_name"] = str(raw_sys).strip()
                new_systems.add(str(raw_sys).strip())

        # Incident type
        raw_type = get("incident_type")
        if not raw_type:
            errors.append("tipo de incidente ausente")
        else:
            type_name = _fuzzy_match(str(raw_type), existing_types)
            if type_name:
                result["_type_name"] = type_name
            else:
                result["_type_name"] = str(raw_type).strip()
                new_types.add(str(raw_type).strip())

        # Optional
        result["description"]      = str(get("description")      or "").strip()
        result["root_cause"]       = str(get("root_cause")       or "").strip()
        result["resolution_notes"] = str(get("resolution_notes") or "").strip()
        try:
            raw_u = get("affected_users")
            result["affected_users"] = int(float(str(raw_u))) if raw_u else 0
        except Exception:
            result["affected_users"] = 0

        if errors:
            error_rows.append({
                "row":    idx + 2,
                "errors": errors,
                "data":   result,
            })
        else:
            valid_rows.append(result)

    return valid_rows, error_rows, sorted(new_systems), sorted(new_types)


# ── Import (DB writes) ────────────────────────────────────────────────── #

def commit_import(valid_rows: list, db) -> dict:
    """
    Resolves system/type names to IDs (creating new ones when needed)
    and bulk-inserts incidents. Returns summary dict.
    """
    from app.services.incident_service import IncidentService

    svc = IncidentService(db)
    systems = {s.name: s.id for s in svc.get_systems(active_only=False)}
    types   = {t.name: t.id for t in svc.get_incident_types(active_only=False)}

    imported = skipped = 0
    for row in valid_rows:
        try:
            sys_name  = row["_system_name"]
            type_name = row["_type_name"]

            if sys_name not in systems:
                ns = svc.create_system(sys_name)
                systems[ns.name] = ns.id

            if type_name not in types:
                nt = svc.create_incident_type(type_name)
                types[nt.name] = nt.id

            payload = {k: v for k, v in row.items() if not k.startswith("_")}
            payload["system_id"]        = systems[sys_name]
            payload["incident_type_id"] = types[type_name]

            svc.create(payload)
            imported += 1
        except Exception:
            skipped += 1

    return {"imported": imported, "skipped": skipped}


# ── File reader ───────────────────────────────────────────────────────── #

def read_file(uploaded_file) -> tuple:
    """
    Reads CSV or Excel. Returns (DataFrame, error_message).
    Tries multiple encodings and separators for CSV.
    """
    name = uploaded_file.name.lower()
    content = uploaded_file.read()

    if name.endswith((".xlsx", ".xls")):
        try:
            df = pd.read_excel(io.BytesIO(content), dtype=str)
            return df, None
        except Exception as e:
            return None, f"Erro ao ler Excel: {e}"

    # CSV — try encodings and separators
    for enc in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
        try:
            text = content.decode(enc)
            sep = ";" if text.count(";") > text.count(",") else ","
            df = pd.read_csv(io.StringIO(text), sep=sep, dtype=str)
            return df, None
        except Exception:
            continue

    return None, "Não foi possível ler o CSV. Verifique a codificação do arquivo."
