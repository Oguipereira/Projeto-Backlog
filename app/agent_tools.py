"""
Ferramentas de ML expostas no formato tool-use da Claude API.

Cada função tem assinatura simples (tipos primitivos) e retorna dict —
pronto para ser registrado como tool quando a integração Claude API ocorrer.

Uso futuro:
    tools = [find_similar_tool, predict_sla_risk_tool, detect_anomalies_tool]
    client.messages.create(..., tools=tools)
"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.services.anomaly_service import detect_anomalies, system_trend
from app.services.incident_service import IncidentService
from app.services.similarity_service import find_similar
from app.services.sla_predictor import is_trained, predict_risk


# ── Tool 1: buscar incidentes similares ───────────────────────── #

FIND_SIMILAR_SCHEMA = {
    "name": "find_similar_incidents",
    "description": (
        "Busca incidentes passados similares ao texto fornecido. "
        "Útil para sugerir causa raiz e resolução com base no histórico."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "title":       {"type": "string", "description": "Título do incidente atual"},
            "description": {"type": "string", "description": "Descrição do incidente atual"},
            "top_k":       {"type": "integer", "description": "Número de resultados (padrão 5)", "default": 5},
        },
        "required": ["title"],
    },
}


def find_similar_incidents(
    title: str,
    description: str = "",
    top_k: int = 5,
    db: Optional[Session] = None,
) -> dict:
    if db is None:
        from app.database import get_db_session
        db = get_db_session()

    svc       = IncidentService(db)
    resolved  = svc.get_all({"status": ["Resolvido"]})
    similar   = find_similar(title, description, resolved, top_k=top_k)

    return {
        "query":   {"title": title, "description": description},
        "results": similar,
        "count":   len(similar),
    }


# ── Tool 2: prever risco de SLA ───────────────────────────────── #

PREDICT_SLA_RISK_SCHEMA = {
    "name": "predict_sla_risk",
    "description": (
        "Prevê a probabilidade de um incidente aberto violar o SLA "
        "com base em prioridade, sistema, tipo e tempo decorrido."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "incident_id": {"type": "string", "description": "ID do incidente (ex: INC-0042)"},
        },
        "required": ["incident_id"],
    },
}


def predict_sla_risk(incident_id: str, db: Optional[Session] = None) -> dict:
    if db is None:
        from app.database import get_db_session
        db = get_db_session()

    if not is_trained():
        return {"error": "Modelo SLA não treinado. Execute o retreinamento primeiro."}

    svc      = IncidentService(db)
    incident = svc.get_by_id(incident_id)
    if not incident:
        return {"error": f"Incidente {incident_id} não encontrado."}

    risk = predict_risk(incident)
    return {
        "incident_id": incident_id,
        "priority":    incident.priority,
        "system":      incident.system.name if incident.system else "-",
        "elapsed_min": round((datetime.now() - incident.started_at).total_seconds() / 60, 1),
        **risk,
    }


# ── Tool 3: detectar anomalias ────────────────────────────────── #

DETECT_ANOMALIES_SCHEMA = {
    "name": "detect_anomalies",
    "description": (
        "Identifica sistemas com volume anômalo de incidentes "
        "comparado à média histórica via z-score."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "recent_days":  {"type": "integer", "description": "Janela recente em dias (padrão 7)"},
            "z_threshold":  {"type": "number",  "description": "Sensibilidade — desvios-padrão (padrão 2.0)"},
        },
        "required": [],
    },
}


def detect_system_anomalies(
    recent_days: int = 7,
    z_threshold: float = 2.0,
    db: Optional[Session] = None,
) -> dict:
    if db is None:
        from app.database import get_db_session
        db = get_db_session()

    svc       = IncidentService(db)
    incidents = svc.get_all()
    anomalies = detect_anomalies(incidents, recent_days=recent_days, z_threshold=z_threshold)

    return {
        "period_days": recent_days,
        "anomalies":   anomalies,
        "count":       len(anomalies),
        "has_critical": any(a["severity"] == "crítico" for a in anomalies),
    }


# ── Registro completo de tools para Claude API ────────────────── #

ALL_TOOLS = [
    FIND_SIMILAR_SCHEMA,
    PREDICT_SLA_RISK_SCHEMA,
    DETECT_ANOMALIES_SCHEMA,
]

TOOL_HANDLERS = {
    "find_similar_incidents": find_similar_incidents,
    "predict_sla_risk":       predict_sla_risk,
    "detect_anomalies":       detect_system_anomalies,
}
