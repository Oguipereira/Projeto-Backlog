import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from app.database import get_db_session
from app.services.incident_service import IncidentService
from app.services.impact_service import ImpactService
from app.services.config_service import ConfigService
from app.utils.calculations import format_duration, format_number
from app.auth import require_login, sidebar_user
from dashboard.components.theme import apply_theme, page_header

st.set_page_config(
    page_title="Gestão de Incidentes",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_theme()
require_login()
sidebar_user()

PRIORITY_COLORS = {"P1": "#DC2626", "P2": "#EA580C", "P3": "#CA8A04", "P4": "#16A34A"}
STATUS_COLORS   = {"Aberto": "#DC2626", "Em Andamento": "#2563EB", "Resolvido": "#16A34A"}


@st.cache_data(ttl=60)
def load_home():
    db = get_db_session()
    try:
        svc    = IncidentService(db)
        impact = ImpactService(db)
        cfg_sv = ConfigService(db)

        today       = datetime.utcnow().replace(hour=0, minute=0, second=0)
        month_start = today.replace(day=1)

        all_inc    = svc.get_all()
        today_inc  = svc.get_all({"start_date": today})
        month_inc  = svc.get_all({"start_date": month_start})
        open_inc   = svc.get_all({"status": ["Aberto", "Em Andamento"]})

        kpis = impact.get_kpis(month_inc)
        cfg  = cfg_sv.get_production_config()

        open_rows = []
        for i in open_inc:
            dur = (datetime.utcnow() - i.started_at).total_seconds() / 60
            rate = cfg_sv.get_production_rates()["per_minute"]
            open_rows.append({
                "ID":        i.incident_id,
                "Título":    i.title[:55] + "…" if len(i.title) > 55 else i.title,
                "Sistema":   i.system.name if i.system else "-",
                "Prior.":    i.priority,
                "Status":    i.status,
                "Início":    i.started_at.strftime("%d/%m %H:%M"),
                "Duração":   format_duration(dur),
                "Perda estimada": f"{dur * rate:,.0f}".replace(",", "."),
            })

        return dict(
            total=len(all_inc),
            today=len(today_inc),
            open=len(open_inc),
            kpis=kpis,
            open_rows=open_rows,
            cfg=cfg,
        )
    finally:
        db.close()


# ──────────────────────────────────────────────────────────────────── #
data = load_home()
kpis = data["kpis"]
cfg  = data["cfg"]
currency = cfg.get("currency", "R$")

page_header(
    "Sistema de Gestão de Incidentes",
    f"Atualizado em {datetime.now().strftime('%d/%m/%Y %H:%M')} · Use o menu lateral para navegar",
)
st.markdown("---")

# ── Headline KPIs ────────────────────────────────────────────────── #
st.subheader("Impacto do Mês Atual")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(
        f"""
        <div style="background:linear-gradient(135deg,#1D4ED8,#3B82F6);color:#fff;
            border-radius:14px;padding:22px 24px;text-align:center;
            box-shadow:0 4px 16px #1D4ED840">
            <div style="font-size:34px;font-weight:800">
                {format_number(kpis['total_production_loss'])}
            </div>
            <div style="font-size:13px;opacity:.85;margin-top:4px">
                perda de produção no mês
            </div>
        </div>
        """, unsafe_allow_html=True)
with col2:
    st.metric("Tempo total de parada", format_duration(kpis["total_downtime_minutes"]))
    st.metric("MTTR médio (mês)",      format_duration(kpis["mttr_minutes"]))
with col3:
    st.metric("Incidentes no mês",  kpis["total"])
    st.metric("P1 Críticos",        kpis["p1"],
              delta=" Atenção!" if kpis["p1"] > 0 else "Nenhum",
              delta_color="inverse" if kpis["p1"] > 0 else "off")
with col4:
    st.metric("Violações de SLA",      kpis["sla_violations"],
              delta_color="inverse" if kpis["sla_violations"] > 0 else "off")
    st.metric("Resolvidos no mês",     kpis["resolved"])

st.markdown("---")

# ── Open incidents ───────────────────────────────────────────────── #
open_label = f"Incidentes em Aberto ({data['open']})"
st.subheader(open_label)

if data["open_rows"]:
    df_open = pd.DataFrame(data["open_rows"])

    def _color_p(val):
        c = PRIORITY_COLORS.get(val, "#6B7280")
        return f"color:{c};font-weight:700"

    def _color_s(val):
        c = STATUS_COLORS.get(val, "#374151")
        return f"color:{c};font-weight:600"

    styled = (
        df_open.style
        .applymap(_color_p, subset=["Prior."])
        .applymap(_color_s, subset=["Status"])
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)
else:
    st.success("Nenhum incidente aberto no momento.")

st.markdown("---")

# ── Bottom stats ─────────────────────────────────────────────────── #
c1, c2 = st.columns(2)
c1.metric("Total histórico de incidentes", data["total"])
c2.metric("Registrados hoje",              data["today"])

st.markdown("---")
st.caption("Dashboard · Incidentes · Analíticos · Relatórios · Configurações")
