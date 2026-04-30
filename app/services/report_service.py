"""
Monta o payload de relatório executivo para envio à liderança.

Agrega dados de incidentes abertos, perdas estimadas, anomalias
e riscos de SLA em um dicionário estruturado pronto para ser
formatado por qualquer canal de saída (Teams, e-mail, etc).
"""
from datetime import datetime
from typing import List

from app.models import Incident
from app.services.anomaly_service import detect_anomalies
from app.services.sla_predictor import is_trained, predict_risk
from app.utils.calculations import calculate_production_loss, format_duration, format_number


def build_report(
    all_incs: List[Incident],
    open_incs: List[Incident],
    prod_rates: dict,
    top_n: int = 5,
) -> dict:
    """
    Retorna dicionário estruturado com dados para o relatório de liderança.

    Campos retornados:
      generated_at   — timestamp de geração
      open_count     — total de incidentes abertos
      total_loss_fmt — perda total formatada em R$
      top_losses     — lista dos top_n incidentes por perda (desc)
      anomalies      — sistemas anômalos (últimos 7 dias)
      sla_critical   — incidentes com risco SLA alto ou crítico
    """
    rate = prod_rates["per_minute"]
    now  = datetime.now()

    loss_rows = []
    for inc in open_incs:
        elapsed = (now - inc.started_at).total_seconds() / 60
        loss    = calculate_production_loss(elapsed, rate)
        loss_rows.append({
            "incident_id":  inc.incident_id,
            "title":        inc.title,
            "priority":     inc.priority,
            "system":       inc.system.name if inc.system else "-",
            "status":       inc.status,
            "elapsed_fmt":  format_duration(elapsed),
            "loss":         loss,
            "loss_fmt":     f"R$ {format_number(loss)}",
        })
    loss_rows.sort(key=lambda x: x["loss"], reverse=True)

    total_loss = sum(r["loss"] for r in loss_rows)

    anomalies = detect_anomalies(all_incs, recent_days=7, z_threshold=2.0)

    sla_critical = []
    if is_trained():
        for inc in open_incs:
            risk = predict_risk(inc)
            if risk["risk_level"] in ("alto", "crítico"):
                sla_critical.append({
                    "incident_id": inc.incident_id,
                    "title":       inc.title,
                    "priority":    inc.priority,
                    "risk_pct":    risk["risk_pct"],
                    "risk_level":  risk["risk_level"],
                })
        sla_critical.sort(key=lambda x: x["risk_pct"], reverse=True)

    return {
        "generated_at":   now.strftime("%d/%m/%Y %H:%M"),
        "open_count":     len(open_incs),
        "total_loss":     total_loss,
        "total_loss_fmt": f"R$ {format_number(total_loss)}",
        "top_losses":     loss_rows[:top_n],
        "anomalies":      anomalies[:4],
        "sla_critical":   sla_critical[:5],
    }
