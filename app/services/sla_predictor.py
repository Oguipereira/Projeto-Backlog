"""
Preditor de risco de violação de SLA.

Treina um RandomForest com incidentes resolvidos e prevê
probabilidade de violação para incidentes abertos.
"""
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder

from app.models import Incident

MODEL_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "models" / "sla_risk.pkl"
MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

MIN_SAMPLES = 20

_PRIORITY_ORDER = {"P1": 0, "P2": 1, "P3": 2, "P4": 3}

_cache: dict = {}


def _features(inc: Incident, elapsed_minutes: Optional[float] = None) -> list:
    p  = _PRIORITY_ORDER.get(inc.priority, 2)
    s  = hash(inc.system.name if inc.system else "") % 100
    t  = hash(inc.incident_type.name if inc.incident_type else "") % 100
    el = elapsed_minutes if elapsed_minutes is not None else (
        (datetime.now() - inc.started_at).total_seconds() / 60
    )
    return [p, s, t, el]


def train(resolved_incidents: List[Incident], sla_map: dict) -> dict:
    """
    Treina o modelo com incidentes resolvidos.

    sla_map: {"P1": 60, "P2": 240, ...} — minutos por prioridade.
    Retorna {"status": "ok"|"insufficient_data", "samples": int, "accuracy": float}.
    """
    eligible = [
        i for i in resolved_incidents
        if i.ended_at and i.started_at and i.duration_minutes is not None
    ]

    if len(eligible) < MIN_SAMPLES:
        return {"status": "insufficient_data", "samples": len(eligible), "needed": MIN_SAMPLES}

    X, y = [], []
    for inc in eligible:
        sla     = sla_map.get(inc.priority, 9999)
        violated = int(inc.duration_minutes > sla)
        X.append(_features(inc, inc.duration_minutes))
        y.append(violated)

    clf = RandomForestClassifier(n_estimators=100, random_state=42, class_weight="balanced")
    clf.fit(X, y)

    joblib.dump(clf, MODEL_PATH)
    _cache.clear()

    correct = sum(
        int(clf.predict([x])[0]) == label
        for x, label in zip(X, y)
    )
    accuracy = round(correct / len(y) * 100, 1)

    return {"status": "ok", "samples": len(eligible), "accuracy": accuracy}


def predict_risk(incident: Incident) -> dict:
    """
    Retorna probabilidade de violação de SLA para um incidente aberto.

    {
      "risk_pct":    int   — 0 a 100,
      "risk_level":  str   — "baixo" | "médio" | "alto" | "crítico",
      "model_ready": bool,
    }
    """
    if not MODEL_PATH.exists():
        return {"risk_pct": 0, "risk_level": "sem modelo", "model_ready": False}

    clf = _cache.get("model")
    if clf is None:
        clf = joblib.load(MODEL_PATH)
        _cache["model"] = clf

    elapsed  = (datetime.now() - incident.started_at).total_seconds() / 60
    features = [_features(incident, elapsed)]
    prob     = clf.predict_proba(features)[0]

    # prob[1] = probabilidade de violar; garante que o modelo tem classe 1
    risk_pct = int(round(prob[1] * 100)) if len(prob) > 1 else 0

    if risk_pct < 30:
        level = "baixo"
    elif risk_pct < 60:
        level = "médio"
    elif risk_pct < 85:
        level = "alto"
    else:
        level = "crítico"

    return {"risk_pct": risk_pct, "risk_level": level, "model_ready": True}


def is_trained() -> bool:
    return MODEL_PATH.exists()
