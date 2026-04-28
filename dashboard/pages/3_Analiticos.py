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
from dashboard.components.theme import apply_theme, page_header
from dashboard.components.charts import (
    mttr_by_priority_chart,
    heatmap_dow_hour,
    top_impactful_incidents_chart,
    loss_over_time_chart,
    incidents_by_system_chart,
)
from dashboard.components.filters import render_period_filter

st.set_page_config(page_title="Analíticos | Incidentes", page_icon="📈", layout="wide")
apply_theme()

page_header("Análise Estratégica de Impacto", "Qual sistema está custando mais? Por que não batemos a meta?")


@st.cache_data(ttl=120)
def load(start: datetime, end: datetime):
    db = get_db_session()
    try:
        svc    = IncidentService(db)
        impact = ImpactService(db)
        cfg_sv = ConfigService(db)
        incs   = svc.get_all({"start_date": start, "end_date": end})
        kpis   = impact.get_kpis(incs)
        cfg    = cfg_sv.get_production_config()
        prios  = cfg_sv.get_priorities()

        rows = []
        for i in incs:
            ended = i.ended_at or datetime.utcnow()
            dur = (ended - i.started_at).total_seconds() / 60
            rows.append({
                "incident_id":   i.incident_id,
                "title":         i.title,
                "system":        i.system.name if i.system else "-",
                "incident_type": i.incident_type.name if i.incident_type else "-",
                "priority":      i.priority,
                "status":        i.status,
                "started_at":    i.started_at,
                "ended_at":      i.ended_at,
                "duration_minutes": i.duration_minutes or dur,
                "production_loss":  i.production_loss or 0,
                "affected_users":   i.affected_users or 0,
            })
        return pd.DataFrame(rows) if rows else pd.DataFrame(), kpis, cfg, prios
    finally:
        db.close()


start, end = render_period_filter("analytics")
df, kpis, cfg, prios = load(start, end)

if df.empty:
    st.warning("Nenhum dado encontrado para o período selecionado.")
    st.stop()

daily_target = cfg.get("daily_production_target", 1000)
eff_hours    = cfg.get("effective_hours_per_day", 8)

st.markdown("---")

# ─── 1. Meta vs Realidade ─────────────────────────────────────────── #
st.subheader(" Meta de Produção vs Realidade")

days_in_period = max(1, (end - start).days + 1)
target_period  = daily_target * days_in_period
total_loss     = kpis["total_production_loss"]
impact_pct     = round(total_loss / target_period * 100, 2) if target_period else 0
eff            = max(0, 100 - impact_pct)
bar_color      = "#16A34A" if eff >= 95 else "#CA8A04" if eff >= 85 else "#DC2626"

mc1, mc2, mc3 = st.columns(3)
mc1.metric("Meta do Período",       format_number(target_period))
mc2.metric(
    "Perda por Incidentes",
    format_number(total_loss),
    delta=f"-{impact_pct}% da meta",
    delta_color="inverse",
)
mc3.metric("Eficiência no Período", f"{eff:.1f}%",
           delta_color="inverse" if eff < 95 else "normal")

st.markdown(
    f"""
    <div style="margin:12px 0 4px">
        <div style="display:flex;justify-content:space-between;font-size:13px;color:#374151">
            <span>Eficiência produtiva no período</span>
            <span style="font-weight:700;color:{bar_color}">{eff:.1f}%</span>
        </div>
        <div style="background:#E5E7EB;border-radius:999px;height:14px;margin-top:6px">
            <div style="width:{eff}%;background:{bar_color};height:14px;
                border-radius:999px;transition:width .5s"></div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown("---")

# ─── 2. Perda ao longo do tempo ───────────────────────────────────── #
st.subheader("Perda Produtiva ao Longo do Tempo")
freq_label = st.radio("Agrupar por:", ["Semana", "Mês"], horizontal=True, key="an_freq")
st.plotly_chart(
    loss_over_time_chart(df, freq="W" if freq_label == "Semana" else "M"),
    use_container_width=True,
)
st.markdown("---")

# ─── 3. Ranking de sistemas por PERDA ─────────────────────────────── #
st.subheader("Sistemas que Mais Custam à Empresa")
col_a, col_b = st.columns(2)
with col_a:
    st.plotly_chart(
        incidents_by_system_chart(df, by="loss",  title="Ranking por Perda Produtiva"),
        use_container_width=True,
    )
with col_b:
    st.plotly_chart(
        incidents_by_system_chart(df, by="count", title="Ranking por Frequência"),
        use_container_width=True,
    )

# System detail table — ordered by production loss
sys_agg = (
    df.groupby("system")
    .agg(
        Incidentes=("incident_id", "count"),
        P1=("priority", lambda x: (x == "P1").sum()),
        Downtime=("duration_minutes", "sum"),
        Perda_Producao=("production_loss", "sum"),
    )
    .sort_values("Perda_Producao", ascending=False)
    .reset_index()
)
sys_agg["Downtime"]       = sys_agg["Downtime"].apply(format_duration)
sys_agg["Perda_Producao"] = sys_agg["Perda_Producao"].apply(
    lambda x: f"{x:,.0f}".replace(",", ".")
)
sys_agg.columns = ["Sistema", "Incidentes", "P1", "Downtime", "Perda de Produção"]
st.dataframe(sys_agg, use_container_width=True, hide_index=True)
st.markdown("---")

# ─── 4. Top incidentes mais caros ─────────────────────────────────── #
st.subheader("🔥 Incidentes Mais Caros (Top 10)")
st.plotly_chart(top_impactful_incidents_chart(df, n=10), use_container_width=True)

with st.expander("Ver tabela detalhada"):
    top10 = (
        df.nlargest(10, "production_loss")
        [[
            "incident_id", "title", "system", "priority", "status",
            "duration_minutes", "production_loss", "affected_users",
        ]]
        .copy()
    )
    top10["duration_minutes"] = top10["duration_minutes"].apply(format_duration)
    top10["production_loss"]  = top10["production_loss"].apply(
        lambda x: f"{x:,.0f}".replace(",", ".")
    )
    top10.columns = [
        "ID", "Título", "Sistema", "Prior.", "Status",
        "Duração", "Perda de Produção", "Usuários",
    ]
    st.dataframe(top10, use_container_width=True, hide_index=True)

st.markdown("---")

# ─── 5. MTTR e SLA ───────────────────────────────────────────────── #
st.subheader("MTTR e Conformidade de SLA")
cc1, cc2 = st.columns(2)
with cc1:
    st.plotly_chart(mttr_by_priority_chart(df), use_container_width=True)
with cc2:
    sla_rows = []
    for p in ["P1", "P2", "P3", "P4"]:
        p_df   = df[df["priority"] == p]
        sla_m  = prios.get(p, {}).get("sla_minutes", 9999)
        if p_df.empty:
            continue
        viols  = int((p_df["duration_minutes"] > sla_m).sum())
        comp   = round((1 - viols / len(p_df)) * 100, 1)
        sla_rows.append({
            "Prioridade": p, "SLA (min)": sla_m,
            "Total": len(p_df), "Violações": viols,
            "Conformidade": f"{comp}%",
        })
    if sla_rows:
        st.dataframe(pd.DataFrame(sla_rows), use_container_width=True, hide_index=True)

st.markdown("---")

# ─── 6. Heatmap ──────────────────────────────────────────────────── #
st.subheader(" Quando os Incidentes Mais Ocorrem?")
st.plotly_chart(heatmap_dow_hour(df), use_container_width=True)
st.caption("Identifique horários críticos e planeje janelas de manutenção preventiva.")
