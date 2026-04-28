import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
_DASH = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_DASH))

import streamlit as st
import pandas as pd
from datetime import datetime

from app.database import get_db_session
from app.services.incident_service import IncidentService
from app.services.impact_service import ImpactService
from app.services.config_service import ConfigService
from app.utils.calculations import format_duration, format_number
from app.utils.pdf_generator import generate_report_pdf
from app.auth import require_login, sidebar_user
from dashboard.components.theme import apply_theme, page_header
from dashboard.components.charts import loss_over_time_chart
from dashboard.components.filters import render_period_filter

st.set_page_config(
    page_title="Relatório Executivo | Incidentes",
    page_icon="",
    layout="wide",
)
apply_theme()
require_login()
sidebar_user()

st.markdown("""
<style>
.report-kpi-big {
    background: #1D4ED8; color: white;
    border-radius: 14px; padding: 20px 24px; text-align: center;
}
.report-kpi-big .val { font-size: 36px; font-weight: 800; letter-spacing: -1px; }
.report-kpi-big .lbl { font-size: 12px; opacity: .80; margin-top: 4px; }
.report-kpi-sec {
    background: #F1F5F9; border: 1px solid #E2E8F0;
    border-radius: 12px; padding: 14px 18px; text-align: center;
}
.report-kpi-sec .val { font-size: 24px; font-weight: 700; color: #1E3A5F; }
.report-kpi-sec .lbl { font-size: 12px; color: #64748B; margin-top: 2px; }
.section-title {
    font-size: 14px; font-weight: 700; color: #1E3A5F;
    text-transform: uppercase; letter-spacing: .5px;
    border-bottom: 2px solid #1D4ED8; padding-bottom: 6px; margin: 16px 0 10px;
}
</style>
""", unsafe_allow_html=True)


# ─── Data ─────────────────────────────────────────────────────────── #

@st.cache_data(ttl=120)
def load_report(start: datetime, end: datetime):
    db = get_db_session()
    try:
        svc    = IncidentService(db)
        impact = ImpactService(db)
        cfg_sv = ConfigService(db)
        incs   = svc.get_all({"start_date": start, "end_date": end})
        kpis   = impact.get_kpis(incs)
        cfg    = cfg_sv.get_production_config()
        rows   = []
        for i in incs:
            rows.append({
                "incident_id":      i.incident_id,
                "title":            i.title,
                "system":           i.system.name if i.system else "-",
                "incident_type":    i.incident_type.name if i.incident_type else "-",
                "priority":         i.priority,
                "status":           i.status,
                "started_at":       i.started_at,
                "ended_at":         i.ended_at,
                "duration_minutes": i.duration_minutes or 0,
                "production_loss":  i.production_loss or 0,
                "affected_users":   i.affected_users or 0,
            })
        return pd.DataFrame(rows) if rows else pd.DataFrame(), kpis, cfg
    finally:
        db.close()


# ─── Header + period ──────────────────────────────────────────────── #
page_header("Relatório Executivo", "Visão consolidada para apresentação e compartilhamento")

start, end = render_period_filter("report")
df, kpis, cfg = load_report(start, end)

if df.empty:
    st.info("Nenhum dado para o período selecionado.")
    st.stop()

target   = cfg.get("daily_production_target", 1000)

days          = max(1, (end - start).days + 1)
target_period = target * days
impact_pct    = round(kpis["total_production_loss"] / target_period * 100, 2) if target_period else 0

# ─── Botão de download PDF ────────────────────────────────────────── #
st.markdown("---")
dl_col, csv_col, info_col = st.columns([2, 2, 4])
with dl_col:
    with st.spinner("Preparando PDF..."):
        pdf_bytes = generate_report_pdf(df, kpis, cfg, start, end)
    filename = f"relatorio_incidentes_{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}.pdf"
    st.download_button(
        label="⬇ Baixar PDF",
        data=pdf_bytes,
        file_name=filename,
        mime="application/pdf",
        use_container_width=True,
    )
with csv_col:
    csv_export = df.copy()
    csv_export.columns = [c.replace("_", " ").title() for c in csv_export.columns]
    csv_bytes = csv_export.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
    st.download_button(
        label="⬇ Exportar CSV",
        data=csv_bytes,
        file_name=f"incidentes_{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}.csv",
        mime="text/csv",
        use_container_width=True,
    )
with info_col:
    st.info(
        f"PDF: KPIs · Top 5 sistemas · Top 5 incidentes · Distribuição por prioridade · "
        f"{len(df)} incidentes. CSV: dados brutos do período para análise no Excel."
    )

st.markdown("---")

# ═══════════════════════════════════════════════════════════════════ #
#  Preview na tela (para referência visual)                           #
# ═══════════════════════════════════════════════════════════════════ #

# ── Header visual ─────────────────────────────────────────────────── #
st.markdown(
    f"""
    <div style="background:linear-gradient(135deg,#1E3A5F,#1D4ED8);color:#fff;
        border-radius:14px;padding:24px 32px;margin-bottom:16px">
        <div style="font-size:11px;opacity:.65;text-transform:uppercase;letter-spacing:1px">
            Relatório Executivo
        </div>
        <div style="font-size:22px;font-weight:800;margin-top:4px">
            Gestão de Incidentes — Impacto na Produção
        </div>
        <div style="font-size:13px;opacity:.75;margin-top:4px">
            {start.strftime('%d/%m/%Y')} a {end.strftime('%d/%m/%Y')} · {days} dias ·
            Meta: {format_number(target_period)}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── KPIs hero ─────────────────────────────────────────────────────── #
k1, k2, k3, k4 = st.columns(4)
eff = round(100 - impact_pct, 1)
eff_color = "#16A34A" if eff >= 95 else "#CA8A04" if eff >= 85 else "#DC2626"

k1.markdown(f"""<div class="report-kpi-big">
    <div class="val">{format_number(kpis['total_production_loss'])}</div>
    <div class="lbl">Perda de Produção</div></div>""", unsafe_allow_html=True)
k2.markdown(f"""<div class="report-kpi-sec">
    <div class="val" style="color:{eff_color}">{eff}%</div>
    <div class="lbl">Eficiência no período</div></div>""", unsafe_allow_html=True)
k3.markdown(f"""<div class="report-kpi-sec">
    <div class="val">{format_duration(kpis['total_downtime_minutes'])}</div>
    <div class="lbl">Downtime total</div></div>""", unsafe_allow_html=True)
k4.markdown(f"""<div class="report-kpi-sec">
    <div class="val">{kpis['total']}</div>
    <div class="lbl">Total de Incidentes</div></div>""", unsafe_allow_html=True)

st.markdown("")
s1, s2, s3, s4, s5 = st.columns(5)
for col, lbl, val in [
    (s1, "Total Incidentes",  kpis["total"]),
    (s2, "P1 Críticos",       kpis["p1"]),
    (s3, "P2 Altos",          kpis["p2"]),
    (s4, "Violações de SLA",  kpis["sla_violations"]),
    (s5, "MTTR Médio",        format_duration(kpis["mttr_minutes"])),
]:
    col.markdown(f"""<div class="report-kpi-sec">
        <div class="val">{val}</div>
        <div class="lbl">{lbl}</div></div>""", unsafe_allow_html=True)

st.markdown("")

# ── Gráfico + tabelas ─────────────────────────────────────────────── #
left, right = st.columns([3, 2])

with left:
    st.markdown('<div class="section-title">Perda Produtiva ao Longo do Tempo</div>',
                unsafe_allow_html=True)
    st.plotly_chart(loss_over_time_chart(df, freq="W"), use_container_width=True)

with right:
    st.markdown('<div class="section-title">Top 5 Sistemas por Impacto</div>',
                unsafe_allow_html=True)
    sys5 = (
        df.groupby("system")["production_loss"].sum()
        .nlargest(5).reset_index()
        .rename(columns={"system": "Sistema", "production_loss": "Perda de Produção"})
    )
    sys5["Perda de Produção"] = sys5["Perda de Produção"].apply(
        lambda x: f"{x:,.0f}".replace(",", ".")
    )
    st.dataframe(sys5, use_container_width=True, hide_index=True)

    st.markdown('<div class="section-title">Top 5 Incidentes Mais Caros</div>',
                unsafe_allow_html=True)
    inc5 = df.nlargest(5, "production_loss")[
        ["incident_id", "title", "system", "priority", "production_loss"]
    ].copy()
    inc5["title"]           = inc5["title"].str[:35] + "…"
    inc5["production_loss"] = inc5["production_loss"].apply(
        lambda x: f"{x:,.0f}".replace(",", ".")
    )
    inc5.columns = ["ID", "Título", "Sistema", "P.", "Perda de Produção"]
    st.dataframe(inc5, use_container_width=True, hide_index=True)

# ── Prioridades ────────────────────────────────────────────────────── #
st.markdown('<div class="section-title">Distribuição por Prioridade</div>',
            unsafe_allow_html=True)
PRIORITY_COLORS = {"P1":"#DC2626","P2":"#EA580C","P3":"#CA8A04","P4":"#16A34A"}
pc1, pc2, pc3, pc4 = st.columns(4)
for col, (p, lbl, cnt) in zip(
    [pc1, pc2, pc3, pc4],
    [("P1","Crítico",kpis["p1"]),("P2","Alto",kpis["p2"]),
     ("P3","Médio",kpis["p3"]),("P4","Baixo",kpis["p4"])],
):
    c = PRIORITY_COLORS[p]
    p_loss = df[df["priority"] == p]["production_loss"].sum()
    pct    = round(p_loss / max(kpis["total_production_loss"], 1) * 100, 1)
    col.markdown(
        f"""<div style="border-left:4px solid {c};background:{c}10;
            border-radius:0 10px 10px 0;padding:12px 16px">
            <div style="font-size:26px;font-weight:800;color:{c}">{cnt}</div>
            <div style="font-size:12px;font-weight:700;color:#374151">{p} — {lbl}</div>
            <div style="font-size:12px;color:#6B7280">{pct}% da perda total</div>
        </div>""",
        unsafe_allow_html=True,
    )
