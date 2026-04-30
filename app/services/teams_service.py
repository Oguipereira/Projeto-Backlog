"""
Envia relatório de incidentes para Microsoft Teams via Incoming Webhook.

O payload usa Adaptive Cards (versão 1.4) — suportado em todos os
clientes Teams modernos sem necessidade de autenticação adicional.

Como configurar o webhook no Teams:
  Canal → ••• → Conectores → Incoming Webhook → Configurar → copiar URL
"""
import requests

_SEVERITY_ICON = {"moderado": "⚠️", "alto": "🟠", "crítico": "🔴"}
_PRIO_ICON     = {"P1": "🔴", "P2": "🟠", "P3": "🟡", "P4": "🟢"}


def _adaptive_card(report: dict) -> dict:
    body = []

    # ── Cabeçalho ──────────────────────────────────────────────── #
    body.append({
        "type": "TextBlock",
        "text": f"📊 Relatório de Incidentes — {report['generated_at']}",
        "weight": "Bolder",
        "size": "Large",
        "wrap": True,
    })

    # ── Resumo executivo ───────────────────────────────────────── #
    body.append({
        "type": "FactSet",
        "spacing": "Medium",
        "facts": [
            {"title": "Incidentes em aberto",  "value": str(report["open_count"])},
            {"title": "Perda total estimada",  "value": report["total_loss_fmt"]},
            {"title": "Anomalias detectadas",  "value": str(len(report["anomalies"]))},
            {"title": "Riscos críticos de SLA","value": str(len(report["sla_critical"]))},
        ],
    })

    # ── Anomalias ──────────────────────────────────────────────── #
    if report["anomalies"]:
        body.append({
            "type": "TextBlock",
            "text": "**Anomalias por Sistema (últimos 7 dias)**",
            "weight": "Bolder",
            "spacing": "Medium",
            "wrap": True,
        })
        for a in report["anomalies"]:
            icon = _SEVERITY_ICON.get(a["severity"], "⚠️")
            body.append({
                "type": "TextBlock",
                "text": (
                    f"{icon} **{a['system']}** — "
                    f"{a['recent_count']} incidentes · "
                    f"z={a['z_score']} · {a['severity'].upper()}"
                ),
                "wrap": True,
                "spacing": "Small",
            })

    # ── Risco de SLA ───────────────────────────────────────────── #
    if report["sla_critical"]:
        body.append({
            "type": "TextBlock",
            "text": "**Risco de SLA — Atenção Imediata**",
            "weight": "Bolder",
            "spacing": "Medium",
            "wrap": True,
        })
        for s in report["sla_critical"]:
            icon = _PRIO_ICON.get(s["priority"], "⚪")
            body.append({
                "type": "TextBlock",
                "text": (
                    f"{icon} {s['incident_id']} · "
                    f"{s['title'][:50]} — "
                    f"**{s['risk_pct']}% de risco** ({s['risk_level']})"
                ),
                "wrap": True,
                "spacing": "Small",
            })

    # ── Maiores perdas ─────────────────────────────────────────── #
    if report["top_losses"]:
        body.append({
            "type": "TextBlock",
            "text": "**Maiores Perdas Estimadas**",
            "weight": "Bolder",
            "spacing": "Medium",
            "wrap": True,
        })
        for row in report["top_losses"]:
            icon = _PRIO_ICON.get(row["priority"], "⚪")
            title = row["title"][:48] + "…" if len(row["title"]) > 48 else row["title"]
            body.append({
                "type": "TextBlock",
                "text": (
                    f"{icon} {row['incident_id']} · {title} — "
                    f"**{row['loss_fmt']}** ({row['elapsed_fmt']} em aberto)"
                ),
                "wrap": True,
                "spacing": "Small",
            })

    # ── Rodapé ─────────────────────────────────────────────────── #
    body.append({
        "type": "TextBlock",
        "text": "_Gerado automaticamente pelo Sistema de Gestão de Incidentes._",
        "isSubtle": True,
        "spacing": "Large",
        "wrap": True,
    })

    return {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": body,
                },
            }
        ],
    }


def send_to_teams(webhook_url: str, report: dict, timeout: int = 10) -> dict:
    """
    Envia o relatório para um canal Teams via Incoming Webhook.

    Retorna:
      {"status": "ok"}
      {"status": "error", "message": str}
    """
    if not webhook_url or not webhook_url.startswith("https://"):
        return {"status": "error", "message": "URL do webhook inválida ou não configurada."}

    payload = _adaptive_card(report)

    try:
        resp = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=timeout,
        )
        if resp.status_code in (200, 202):
            return {"status": "ok"}
        return {
            "status": "error",
            "message": f"Teams retornou HTTP {resp.status_code}: {resp.text[:300]}",
        }
    except requests.exceptions.Timeout:
        return {"status": "error", "message": "Timeout ao conectar com o Teams (10s)."}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": str(e)}
