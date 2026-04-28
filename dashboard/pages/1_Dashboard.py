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
from dashboard.components.theme import apply_theme, page_header
from dashboard.components.kpis import render_main_kpis, render_priority_kpis
from dashboard.components.charts import (
    incidents_by_priority_chart,
    incidents_by_system_chart,
    incidents_over_time_chart,
    top_impactful_incidents_chart,
    status_donut_chart,
    incidents_by_type_chart,
    loss_over_time_chart,
)
from dashboard.components.filters import render_period_filter, render_sidebar_filters

st.set_page_config(page_title="Dashboard | Incidentes", page_icon="📊", layout="wide")
apply_theme()

page_header("Dashboard Executivo", "Análise de impacto produtivo por período")


# ─── helpers ──────────────────────────────────────────────────────── #

@st.cache_data(ttl=120)
def load_data(start, end, priority, status, system_id, type_id):
    db = get_db_session()
    try:
        svc    = IncidentService(db)
        impact = ImpactService(db)
        cfg_sv = ConfigService(db)

        filters = {"start_date": start, "end_date": end}
        if priority:  filters["priority"]           = list(priority)
        if status:    filters["status"]             = list(status)
        if system_id: filters["system_id"]          = list(system_id)
        if type_id:   filters["incident_type_id"]   = list(type_id)

        incidents = svc.get_all(filters)
        kpis      = impact.get_kpis(incidents)
        cfg       = cfg_sv.get_production_config()

        rows = []
        for i in incidents:
            rows.append({
                "incident_id":    i.incident_id,
                "title":          i.title,
                "system":         i.system.name if i.system else "-",
                "incident_type":  i.incident_type.name if i.incident_type else "-",
                "priority":       i.priority,
                "status":         i.status,
                "started_at":     i.started_at,
                "ended_at":       i.ended_at,
                "duration_minutes": i.duration_minutes or 0,
                "production_loss":  i.production_loss or 0,
                "affected_users":   i.affected_users or 0,
            })
        return pd.DataFrame(rows), kpis, cfg
    finally:
        db.close()


def get_ref():
    db = get_db_session()
    try:
        svc = IncidentService(db)
        return svc.get_systems(), svc.get_incident_types()
    finally:
        db.close()


# ─── Filters ──────────────────────────────────────────────────────── #
systems, types = get_ref()
sb_filters = render_sidebar_filters(systems, types)
start, end = render_period_filter("dash")

st.caption(f"Período: {start.strftime('%d/%m/%Y')} → {end.strftime('%d/%m/%Y')}")
st.markdown("---")

df, kpis, cfg = load_data(
    start, end,
    tuple(sb_filters["priority"])          if sb_filters["priority"]          else None,
    tuple(sb_filters["status"])            if sb_filters["status"]            else None,
    tuple(sb_filters["system_id"])         if sb_filters["system_id"]         else None,
    tuple(sb_filters["incident_type_id"])  if sb_filters["incident_type_id"]  else None,
)

if df.empty:
    st.info("Nenhum incidente encontrado para os filtros selecionados.")
    st.stop()

# ─── KPIs ─────────────────────────────────────────────────────────── #
render_main_kpis(kpis, cfg)
st.markdown("")
render_priority_kpis(kpis)
st.markdown("---")

# ─── Row 1: Loss over time + Priority pie ─────────────────────────── #
col1, col2 = st.columns([3, 2])
with col1:
    freq = st.radio("Agrupar por:", ["Semana", "Mês"], horizontal=True, key="r1_freq")
    st.plotly_chart(
        loss_over_time_chart(df, freq="W" if freq == "Semana" else "M"),
        use_container_width=True,
    )
with col2:
    st.plotly_chart(incidents_by_priority_chart(df), use_container_width=True)

# ─── Row 2: Systems ranking (loss) + Type breakdown ───────────────── #
col3, col4 = st.columns(2)
with col3:
    # Default: ranked by production loss
    st.plotly_chart(
        incidents_by_system_chart(df, by="loss", title="Sistemas por Perda Produtiva"),
        use_container_width=True,
    )
with col4:
    st.plotly_chart(top_impactful_incidents_chart(df), use_container_width=True)

# ─── Row 3: Type + Status ─────────────────────────────────────────── #
col5, col6 = st.columns(2)
with col5:
    st.plotly_chart(incidents_by_type_chart(df), use_container_width=True)
with col6:
    st.plotly_chart(status_donut_chart(df), use_container_width=True)

# ─── Raw data / export ────────────────────────────────────────────── #
st.markdown("---")
with st.expander("Ver dados brutos"):
    export_df = (
        df.sort_values("production_loss", ascending=False)
        .rename(columns={
            "incident_id": "ID", "title": "Título", "system": "Sistema",
            "incident_type": "Tipo", "priority": "Prioridade", "status": "Status",
            "started_at": "Início", "ended_at": "Fim",
            "duration_minutes": "Duração (min)",
            "production_loss": "Perda Produtiva",
            "affected_users": "Usuários Afetados",
        })
    )
    st.dataframe(export_df, use_container_width=True, hide_index=True)
    csv = export_df.to_csv(index=False).encode("utf-8")
    st.download_button(" Exportar CSV (ordenado por perda)", csv,
                       "incidentes_por_impacto.csv", "text/csv")
