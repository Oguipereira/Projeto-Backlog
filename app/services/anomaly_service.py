"""
Detecção de anomalias por sistema via z-score.

Compara o volume de incidentes recentes de cada sistema
contra sua média histórica. Sem modelo treinado — é stateless.
"""
from datetime import datetime, timedelta
from typing import List

from app.models import Incident


def detect_anomalies(
    incidents: List[Incident],
    recent_days: int = 7,
    z_threshold: float = 2.0,
    min_history_weeks: int = 4,
) -> List[dict]:
    """
    Retorna sistemas com volume anômalo de incidentes no período recente.

    Parâmetros:
      recent_days        — janela "recente" para comparação (padrão: 7 dias)
      z_threshold        — desvios-padrão para considerar anomalia (padrão: 2.0)
      min_history_weeks  — semanas mínimas de histórico para calcular baseline

    Cada resultado:
      {
        "system":         str,
        "recent_count":   int,
        "weekly_avg":     float,
        "weekly_std":     float,
        "z_score":        float,
        "severity":       "moderado" | "alto" | "crítico",
      }
    """
    if not incidents:
        return []

    now        = datetime.now()
    cutoff     = now - timedelta(days=recent_days)
    history_start = now - timedelta(weeks=min_history_weeks)

    # Agrupa incidentes por sistema
    by_system: dict = {}
    for inc in incidents:
        name = inc.system.name if inc.system else "Desconhecido"
        by_system.setdefault(name, []).append(inc)

    anomalies = []

    for system, incs in by_system.items():
        historical = [i for i in incs if i.started_at >= history_start and i.started_at < cutoff]
        recent     = [i for i in incs if i.started_at >= cutoff]

        if len(historical) == 0:
            continue

        # Divide histórico em janelas de recent_days para calcular baseline
        total_days    = (cutoff - history_start).days or 1
        n_windows     = max(1, total_days // recent_days)
        weekly_counts = []

        for w in range(n_windows):
            w_start = history_start + timedelta(days=w * recent_days)
            w_end   = w_start + timedelta(days=recent_days)
            cnt     = sum(1 for i in historical if w_start <= i.started_at < w_end)
            weekly_counts.append(cnt)

        avg = sum(weekly_counts) / len(weekly_counts)
        variance = sum((c - avg) ** 2 for c in weekly_counts) / len(weekly_counts)
        std = variance ** 0.5

        if std == 0:
            # Sem variação histórica — só alerta se recente for o dobro
            if len(recent) >= avg * 2 and len(recent) > 0:
                z = 3.0
            else:
                continue
        else:
            z = (len(recent) - avg) / std

        if z < z_threshold:
            continue

        if z < 3.0:
            severity = "moderado"
        elif z < 4.0:
            severity = "alto"
        else:
            severity = "crítico"

        anomalies.append({
            "system":       system,
            "recent_count": len(recent),
            "weekly_avg":   round(avg, 1),
            "weekly_std":   round(std, 2),
            "z_score":      round(z, 2),
            "severity":     severity,
        })

    return sorted(anomalies, key=lambda x: x["z_score"], reverse=True)


def system_trend(
    incidents: List[Incident],
    system_name: str,
    weeks: int = 8,
) -> List[dict]:
    """
    Retorna volume semanal de incidentes de um sistema para análise de tendência.

    [{"week_start": datetime, "count": int, "p1_p2": int}, ...]
    """
    now   = datetime.now()
    incs  = [i for i in incidents if (i.system.name if i.system else "") == system_name]
    result = []

    for w in range(weeks - 1, -1, -1):
        w_start = now - timedelta(weeks=w + 1)
        w_end   = now - timedelta(weeks=w)
        week_incs = [i for i in incs if w_start <= i.started_at < w_end]
        result.append({
            "week_start": w_start,
            "count":      len(week_incs),
            "p1_p2":      sum(1 for i in week_incs if i.priority in ("P1", "P2")),
        })

    return result
