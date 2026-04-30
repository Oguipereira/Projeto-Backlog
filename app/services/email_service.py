"""
Envia relatório executivo de incidentes por e-mail via SMTP.

Suporta Gmail (porta 587/TLS) e Outlook/Exchange corporativo.
Para Gmail: use uma App Password (não a senha da conta).
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List

from app.utils.calculations import format_number

_PRIO_COLOR = {"P1": "#DC2626", "P2": "#EA580C", "P3": "#CA8A04", "P4": "#16A34A"}
_SEV_COLOR  = {"moderado": "#CA8A04", "alto": "#EA580C", "crítico": "#DC2626"}
_RISK_COLOR = {"médio": "#CA8A04", "alto": "#EA580C", "crítico": "#DC2626"}


def _fmt(value: float) -> str:
    return f"R$ {format_number(value)}"


def _projection_row(label: str, extra_minutes: float, current_loss: float,
                    rate_per_min: float, open_count: int) -> str:
    projected = current_loss + (rate_per_min * extra_minutes * open_count)
    delta     = rate_per_min * extra_minutes * open_count
    return f"""
    <tr>
      <td style="padding:8px 12px;color:#374151;border-bottom:1px solid #F3F4F6">{label}</td>
      <td style="padding:8px 12px;text-align:right;font-weight:600;color:#DC2626;
                 border-bottom:1px solid #F3F4F6">{_fmt(projected)}</td>
      <td style="padding:8px 12px;text-align:right;color:#6B7280;font-size:13px;
                 border-bottom:1px solid #F3F4F6">+{_fmt(delta)}</td>
    </tr>"""


def build_html(report: dict) -> str:
    rate    = report["rate_per_minute"]
    n_open  = report["open_count"]
    loss    = report["total_loss"]
    per_h   = report["rate_per_hour"]
    per_d   = report["rate_per_day"]

    # ── Seção: projeção de perdas ──────────────────────────────── #
    proj_rows = (
        _projection_row("Agora (acumulado)",   0,    loss, rate, 1)
        + _projection_row("+1 hora",           60,   loss, rate, n_open)
        + _projection_row("+4 horas",          240,  loss, rate, n_open)
        + _projection_row("+8 horas",          480,  loss, rate, n_open)
        + _projection_row("+24 horas",         1440, loss, rate, n_open)
    )

    # ── Seção: top perdas por incidente ────────────────────────── #
    loss_rows_html = ""
    for row in report["top_losses"]:
        pc  = _PRIO_COLOR.get(row["priority"], "#6B7280")
        add1h = row["loss"] + rate * 60
        loss_rows_html += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #F3F4F6">
            <span style="color:{pc};font-weight:700">{row['priority']}</span>
            &nbsp;<strong>{row['incident_id']}</strong>
          </td>
          <td style="padding:8px 12px;border-bottom:1px solid #F3F4F6;max-width:220px;
                     overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
            {row['title'][:55]}{'…' if len(row['title'])>55 else ''}
          </td>
          <td style="padding:8px 12px;text-align:center;color:#6B7280;
                     border-bottom:1px solid #F3F4F6">{row['elapsed_fmt']}</td>
          <td style="padding:8px 12px;text-align:right;font-weight:700;color:#DC2626;
                     border-bottom:1px solid #F3F4F6">{row['loss_fmt']}</td>
          <td style="padding:8px 12px;text-align:right;color:#EA580C;
                     border-bottom:1px solid #F3F4F6">{_fmt(add1h)}</td>
        </tr>"""

    # ── Seção: anomalias ───────────────────────────────────────── #
    anomaly_html = ""
    for a in report["anomalies"]:
        sc = _SEV_COLOR.get(a["severity"], "#6B7280")
        anomaly_html += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #F3F4F6;font-weight:600">
            {a['system']}
          </td>
          <td style="padding:8px 12px;text-align:center;border-bottom:1px solid #F3F4F6">
            {a['recent_count']}
          </td>
          <td style="padding:8px 12px;text-align:center;border-bottom:1px solid #F3F4F6;color:#6B7280">
            {a['weekly_avg']}
          </td>
          <td style="padding:8px 12px;text-align:center;border-bottom:1px solid #F3F4F6;
                     font-weight:700;color:{sc}">{a['z_score']}</td>
          <td style="padding:8px 12px;text-align:center;border-bottom:1px solid #F3F4F6">
            <span style="background:{sc};color:#fff;padding:2px 10px;border-radius:999px;
                         font-size:12px;font-weight:700">{a['severity'].upper()}</span>
          </td>
        </tr>"""
    if not anomaly_html:
        anomaly_html = """<tr><td colspan="5" style="padding:12px;text-align:center;
            color:#16A34A">Nenhuma anomalia detectada nos últimos 7 dias.</td></tr>"""

    # ── Seção: risco de SLA ────────────────────────────────────── #
    sla_html = ""
    for s in report["sla_critical"]:
        pc = _PRIO_COLOR.get(s["priority"], "#6B7280")
        rc = _RISK_COLOR.get(s["risk_level"], "#6B7280")
        sla_html += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #F3F4F6">
            <span style="color:{pc};font-weight:700">{s['priority']}</span>
            &nbsp;<strong>{s['incident_id']}</strong>
          </td>
          <td style="padding:8px 12px;border-bottom:1px solid #F3F4F6">
            {s['title'][:55]}{'…' if len(s['title'])>55 else ''}
          </td>
          <td style="padding:8px 12px;text-align:center;font-weight:700;color:{rc};
                     border-bottom:1px solid #F3F4F6">{s['risk_pct']}%</td>
          <td style="padding:8px 12px;text-align:center;border-bottom:1px solid #F3F4F6">
            <span style="background:{rc};color:#fff;padding:2px 10px;border-radius:999px;
                         font-size:12px;font-weight:700">{s['risk_level'].upper()}</span>
          </td>
        </tr>"""
    if not sla_html:
        sla_html = """<tr><td colspan="4" style="padding:12px;text-align:center;
            color:#16A34A">Nenhum incidente com risco alto ou crítico de SLA.</td></tr>"""

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>Relatório de Incidentes</title>
</head>
<body style="margin:0;padding:0;background:#F8FAFC;font-family:Arial,sans-serif;color:#1E293B">
<table width="100%" cellpadding="0" cellspacing="0"
       style="max-width:720px;margin:32px auto;background:#fff;
              border-radius:12px;overflow:hidden;
              box-shadow:0 2px 12px rgba(0,0,0,.08)">

  <!-- Header -->
  <tr>
    <td style="background:linear-gradient(135deg,#1E3A5F,#1D4ED8);
               padding:28px 32px;color:#fff">
      <p style="margin:0;font-size:13px;opacity:.8;letter-spacing:.5px">
        RELATÓRIO EXECUTIVO
      </p>
      <h1 style="margin:6px 0 4px;font-size:22px">
        Gestão de Incidentes
      </h1>
      <p style="margin:0;font-size:13px;opacity:.75">
        Gerado em {report['generated_at']}
      </p>
    </td>
  </tr>

  <tr><td style="padding:28px 32px">

    <!-- Resumo executivo -->
    <h2 style="margin:0 0 16px;font-size:15px;text-transform:uppercase;
               letter-spacing:.5px;color:#64748B">Resumo Executivo</h2>
    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:28px">
      <tr>
        <td style="width:25%;padding:16px;background:#FEF2F2;border-radius:8px;
                   text-align:center;margin:4px">
          <div style="font-size:28px;font-weight:800;color:#DC2626">{n_open}</div>
          <div style="font-size:12px;color:#6B7280;margin-top:4px">Incidentes Abertos</div>
        </td>
        <td style="width:4%"></td>
        <td style="width:25%;padding:16px;background:#FFF7ED;border-radius:8px;text-align:center">
          <div style="font-size:22px;font-weight:800;color:#EA580C">{_fmt(loss)}</div>
          <div style="font-size:12px;color:#6B7280;margin-top:4px">Perda Total Acumulada</div>
        </td>
        <td style="width:4%"></td>
        <td style="width:25%;padding:16px;background:#FEFCE8;border-radius:8px;text-align:center">
          <div style="font-size:28px;font-weight:800;color:#CA8A04">{len(report['anomalies'])}</div>
          <div style="font-size:12px;color:#6B7280;margin-top:4px">Anomalias Detectadas</div>
        </td>
        <td style="width:4%"></td>
        <td style="width:25%;padding:16px;background:#FEF2F2;border-radius:8px;text-align:center">
          <div style="font-size:28px;font-weight:800;color:#DC2626">{len(report['sla_critical'])}</div>
          <div style="font-size:12px;color:#6B7280;margin-top:4px">Riscos Críticos de SLA</div>
        </td>
      </tr>
    </table>

    <!-- Destaque: expectativa de perda -->
    <div style="background:#FEF2F2;border-left:4px solid #DC2626;
                border-radius:8px;padding:20px 24px;margin-bottom:28px">
      <h2 style="margin:0 0 6px;font-size:15px;color:#DC2626">
        Expectativa de Perda de Producao
      </h2>
      <p style="margin:0 0 16px;font-size:13px;color:#6B7280">
        Se os {n_open} incidente(s) em aberto permanecerem sem resolucao,
        a perda estimada acumulada sera:
      </p>
      <table width="100%" cellpadding="0" cellspacing="0"
             style="background:#fff;border-radius:8px;overflow:hidden">
        <thead>
          <tr style="background:#FEE2E2">
            <th style="padding:10px 12px;text-align:left;font-size:13px;
                       color:#374151">Horizonte</th>
            <th style="padding:10px 12px;text-align:right;font-size:13px;
                       color:#374151">Perda Total Estimada</th>
            <th style="padding:10px 12px;text-align:right;font-size:13px;
                       color:#374151">Adicional</th>
          </tr>
        </thead>
        <tbody>{proj_rows}</tbody>
      </table>
      <p style="margin:12px 0 0;font-size:12px;color:#9CA3AF">
        Taxa de producao: {_fmt(per_h)}/hora &nbsp;|&nbsp;
        {_fmt(per_d)}/dia &nbsp;|&nbsp;
        {_fmt(rate * 60)}/hora por incidente
      </p>
    </div>

    <!-- Top perdas por incidente -->
    <h2 style="margin:0 0 12px;font-size:15px;text-transform:uppercase;
               letter-spacing:.5px;color:#64748B">Top 5 Maiores Perdas</h2>
    <table width="100%" cellpadding="0" cellspacing="0"
           style="margin-bottom:28px;border:1px solid #E2E8F0;border-radius:8px;
                  overflow:hidden">
      <thead>
        <tr style="background:#F8FAFC">
          <th style="padding:10px 12px;text-align:left;font-size:13px;color:#374151">Incidente</th>
          <th style="padding:10px 12px;text-align:left;font-size:13px;color:#374151">Titulo</th>
          <th style="padding:10px 12px;text-align:center;font-size:13px;color:#374151">Aberto ha</th>
          <th style="padding:10px 12px;text-align:right;font-size:13px;color:#374151">Perda Atual</th>
          <th style="padding:10px 12px;text-align:right;font-size:13px;color:#374151">Em +1h</th>
        </tr>
      </thead>
      <tbody>{loss_rows_html}</tbody>
    </table>

    <!-- Anomalias -->
    <h2 style="margin:0 0 12px;font-size:15px;text-transform:uppercase;
               letter-spacing:.5px;color:#64748B">Anomalias por Sistema (ultimos 7 dias)</h2>
    <table width="100%" cellpadding="0" cellspacing="0"
           style="margin-bottom:28px;border:1px solid #E2E8F0;border-radius:8px;
                  overflow:hidden">
      <thead>
        <tr style="background:#F8FAFC">
          <th style="padding:10px 12px;text-align:left;font-size:13px;color:#374151">Sistema</th>
          <th style="padding:10px 12px;text-align:center;font-size:13px;color:#374151">Recentes</th>
          <th style="padding:10px 12px;text-align:center;font-size:13px;color:#374151">Media Hist.</th>
          <th style="padding:10px 12px;text-align:center;font-size:13px;color:#374151">Z-Score</th>
          <th style="padding:10px 12px;text-align:center;font-size:13px;color:#374151">Severidade</th>
        </tr>
      </thead>
      <tbody>{anomaly_html}</tbody>
    </table>

    <!-- Risco de SLA -->
    <h2 style="margin:0 0 12px;font-size:15px;text-transform:uppercase;
               letter-spacing:.5px;color:#64748B">Risco de SLA - Atencao Imediata</h2>
    <table width="100%" cellpadding="0" cellspacing="0"
           style="margin-bottom:28px;border:1px solid #E2E8F0;border-radius:8px;
                  overflow:hidden">
      <thead>
        <tr style="background:#F8FAFC">
          <th style="padding:10px 12px;text-align:left;font-size:13px;color:#374151">Incidente</th>
          <th style="padding:10px 12px;text-align:left;font-size:13px;color:#374151">Titulo</th>
          <th style="padding:10px 12px;text-align:center;font-size:13px;color:#374151">Risco</th>
          <th style="padding:10px 12px;text-align:center;font-size:13px;color:#374151">Nivel</th>
        </tr>
      </thead>
      <tbody>{sla_html}</tbody>
    </table>

  </td></tr>

  <!-- Footer -->
  <tr>
    <td style="background:#F8FAFC;padding:20px 32px;border-top:1px solid #E2E8F0;
               text-align:center;color:#9CA3AF;font-size:12px">
      Gerado automaticamente pelo Sistema de Gestao de Incidentes.<br/>
      Este e-mail e confidencial e destinado exclusivamente a lideranca.
    </td>
  </tr>

</table>
</body>
</html>"""


def send_email(
    smtp_host: str,
    smtp_port: int,
    username: str,
    password: str,
    from_addr: str,
    to_addrs: List[str],
    report: dict,
    timeout: int = 15,
) -> dict:
    """
    Envia o relatório HTML por e-mail via SMTP com TLS.

    Retorna {"status": "ok"} ou {"status": "error", "message": str}.
    """
    if not smtp_host or not username or not password:
        return {"status": "error", "message": "Configuracoes SMTP incompletas."}
    if not to_addrs:
        return {"status": "error", "message": "Nenhum destinatario informado."}

    subject = f"[Incidentes] Relatorio Executivo — {report['generated_at']}"
    html    = build_html(report)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = from_addr or username
    msg["To"]      = ", ".join(to_addrs)
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=timeout) as server:
            server.ehlo()
            server.starttls()
            server.login(username, password)
            server.sendmail(from_addr or username, to_addrs, msg.as_string())
        return {"status": "ok"}
    except smtplib.SMTPAuthenticationError:
        return {"status": "error", "message": "Falha de autenticacao SMTP. Verifique usuario e senha."}
    except smtplib.SMTPException as e:
        return {"status": "error", "message": f"Erro SMTP: {e}"}
    except OSError as e:
        return {"status": "error", "message": f"Erro de conexao: {e}"}
