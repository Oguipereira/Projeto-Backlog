import sys
from pathlib import Path
from datetime import datetime

_ROOT = Path(__file__).resolve().parent.parent.parent
_DASH = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_DASH))

import streamlit as st

from app.database import get_db_session
from app.services.incident_service import IncidentService
from app.services.config_service import ConfigService
from app.services.similarity_service import find_similar
from app.services.anomaly_service import detect_anomalies, system_trend
from app.services.sla_predictor import train, predict_risk, is_trained
from app.services.ml_service import train_all, models_status
from app.utils.calculations import format_duration
from dashboard.components.theme import apply_theme, page_header

st.set_page_config(
    page_title="Inteligência | Incidentes",
    page_icon="",
    layout="wide",
)
apply_theme()
page_header(
    "Inteligência de Incidentes",
    "Anomalias, risco de SLA e busca por similaridade",
)

SEVERITY_COLOR = {"moderado": "#CA8A04", "alto": "#EA580C", "crítico": "#DC2626"}
RISK_COLOR     = {"baixo": "#16A34A", "médio": "#CA8A04", "alto": "#EA580C", "crítico": "#DC2626", "sem modelo": "#6B7280"}
PRIO_COLOR     = {"P1": "#DC2626", "P2": "#EA580C", "P3": "#CA8A04", "P4": "#16A34A"}


@st.cache_data(ttl=120)
def load_data():
    db = get_db_session()
    try:
        svc      = IncidentService(db)
        cfg_svc  = ConfigService(db)
        all_incs = svc.get_all()
        open_incs = svc.get_all({"status": ["Aberto", "Em Andamento"]})
        resolved  = svc.get_all({"status": ["Resolvido"]})
        sla_map   = {p: cfg_svc.get_priority_sla(p) for p in ["P1", "P2", "P3", "P4"]}
        return all_incs, open_incs, resolved, sla_map
    finally:
        db.close()


all_incs, open_incs, resolved, sla_map = load_data()

# ── Sidebar: status e treino dos modelos ─────────────────────── #
with st.sidebar:
    st.markdown("### Modelos ML")
    ml_st  = models_status()
    sla_ok = is_trained()

    st.markdown(f"Classificador de prioridade: {'Treinado' if ml_st['priority'] else 'Pendente'}")
    st.markdown(f"Classificador de sistema: {'Treinado' if ml_st['system'] else 'Pendente'}")
    st.markdown(f"Classificador de tipo: {'Treinado' if ml_st['type'] else 'Pendente'}")
    st.markdown(f"Preditor de SLA: {'Treinado' if sla_ok else 'Pendente'}")

    st.divider()
    if st.button("Treinar todos os modelos", use_container_width=True):
        with st.spinner("Treinando..."):
            r_ml  = train_all(all_incs)
            r_sla = train(resolved, sla_map)
        if r_ml.get("status") == "ok":
            st.success(f"Classificadores treinados ({r_ml['count']} registros)")
        else:
            st.warning(f"Dados insuficientes para classificadores ({r_ml.get('count',0)} < {r_ml.get('needed',10)})")
        if r_sla.get("status") == "ok":
            st.success(f"SLA treinado — acurácia {r_sla['accuracy']}%")
        else:
            st.warning(f"Dados insuficientes para SLA ({r_sla.get('samples',0)} < {r_sla.get('needed',20)})")
        st.cache_data.clear()
        st.rerun()


st.markdown("---")

# ── 1. Anomalias ─────────────────────────────────────────────── #
st.subheader("Anomalias por Sistema")
st.caption("Sistemas com volume de incidentes acima do padrão histórico nos últimos 7 dias.")

anomalies = detect_anomalies(all_incs, recent_days=7, z_threshold=2.0)

if not anomalies:
    st.success("Nenhuma anomalia detectada. Todos os sistemas dentro do padrão historico.")
else:
    cols = st.columns(min(len(anomalies), 4))
    for idx, a in enumerate(anomalies[:4]):
        color = SEVERITY_COLOR.get(a["severity"], "#6B7280")
        cols[idx].markdown(
            f"""
            <div style="border:2px solid {color};border-radius:12px;padding:16px;text-align:center">
                <div style="font-size:13px;color:#64748B;font-weight:600">{a['system']}</div>
                <div style="font-size:28px;font-weight:800;color:{color};margin:6px 0">
                    {a['recent_count']}
                </div>
                <div style="font-size:12px;color:#64748B">
                    incidentes (7d)<br>
                    media historica: {a['weekly_avg']}/sem<br>
                    z-score: {a['z_score']}
                </div>
                <div style="margin-top:8px;padding:2px 10px;border-radius:999px;
                    background:{color};color:#fff;font-size:12px;font-weight:700;
                    display:inline-block">{a['severity'].upper()}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if len(anomalies) > 4:
        with st.expander(f"Ver mais {len(anomalies) - 4} sistema(s)"):
            for a in anomalies[4:]:
                color = SEVERITY_COLOR.get(a["severity"], "#6B7280")
                st.markdown(
                    f"**{a['system']}** — {a['recent_count']} incidentes (7d) · "
                    f"média {a['weekly_avg']}/sem · z={a['z_score']} · "
                    f":{color}[{a['severity'].upper()}]"
                )

    # Tendência do sistema mais crítico
    if anomalies:
        top_sys = anomalies[0]["system"]
        trend   = system_trend(all_incs, top_sys, weeks=8)
        if trend:
            import pandas as pd
            import plotly.graph_objects as go
            df_t = pd.DataFrame(trend)
            fig  = go.Figure()
            fig.add_trace(go.Bar(
                x=[r["week_start"].strftime("%d/%m") for r in trend],
                y=[r["count"] for r in trend],
                name="Total",
                marker_color="#3B82F6",
            ))
            fig.add_trace(go.Bar(
                x=[r["week_start"].strftime("%d/%m") for r in trend],
                y=[r["p1_p2"] for r in trend],
                name="P1/P2",
                marker_color="#DC2626",
            ))
            fig.update_layout(
                barmode="overlay",
                title=f"Tendência semanal — {top_sys}",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(size=13),
                margin=dict(l=10, r=10, t=40, b=10),
                legend=dict(orientation="h", y=1.1),
                yaxis_title="Incidentes",
                xaxis_title="Semana",
            )
            st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# ── 2. Risco de SLA ──────────────────────────────────────────── #
st.subheader("Risco de SLA — Incidentes Abertos")

if not is_trained():
    st.info("Modelo SLA nao treinado. Clique em **Treinar todos os modelos** na barra lateral.")
elif not open_incs:
    st.success("Nenhum incidente aberto no momento.")
else:
    risk_rows = []
    for inc in open_incs:
        r       = predict_risk(inc)
        elapsed = (datetime.now() - inc.started_at).total_seconds() / 60
        risk_rows.append({
            "ID":          inc.incident_id,
            "Título":      inc.title[:50] + "…" if len(inc.title) > 50 else inc.title,
            "Sistema":     inc.system.name if inc.system else "-",
            "Prior.":      inc.priority,
            "Status":      inc.status,
            "Decorrido":   format_duration(elapsed),
            "Risco SLA":   r["risk_pct"],
            "Nivel":       r["risk_level"],
        })

    risk_rows.sort(key=lambda x: x["Risco SLA"], reverse=True)

    for row in risk_rows:
        pcolor = PRIO_COLOR.get(row["Prior."], "#6B7280")
        rcolor = RISK_COLOR.get(row["Nivel"], "#6B7280")
        pct    = row["Risco SLA"]
        bar_w  = max(4, pct)

        st.markdown(
            f"""
            <div style="border:1px solid #E2E8F0;border-radius:10px;
                padding:12px 16px;margin-bottom:8px">
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <div>
                        <span style="font-weight:700;color:{pcolor}">{row['Prior.']}</span>
                        &nbsp;
                        <span style="font-weight:600">{row['ID']}</span>
                        &nbsp;·&nbsp;
                        <span style="color:#374151">{row['Título']}</span>
                    </div>
                    <div style="text-align:right;min-width:120px">
                        <span style="font-size:20px;font-weight:800;color:{rcolor}">{pct}%</span>
                        <span style="font-size:12px;color:#64748B;margin-left:4px">{row['Nivel']}</span>
                    </div>
                </div>
                <div style="font-size:12px;color:#64748B;margin:6px 0 4px">
                    {row['Sistema']} &nbsp;·&nbsp; {row['Status']} &nbsp;·&nbsp; {row['Decorrido']}
                </div>
                <div style="background:#E5E7EB;border-radius:999px;height:6px">
                    <div style="width:{bar_w}%;background:{rcolor};height:6px;border-radius:999px"></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown("---")

# ── 3. Busca por Similaridade ─────────────────────────────────── #
st.subheader("Busca por Incidentes Similares")
st.caption("Descreva o incidente atual para encontrar casos parecidos com causa raiz e resolucao.")

col_a, col_b = st.columns([2, 1])
with col_a:
    sim_title = st.text_input("Titulo do incidente", placeholder="Ex: Queda de performance no ERP")
with col_b:
    top_k = st.slider("Resultados", min_value=1, max_value=10, value=5)

sim_desc = st.text_area("Descricao (opcional)", placeholder="Descreva os sintomas observados...", height=80)

if sim_title:
    with st.spinner("Buscando..."):
        similar = find_similar(sim_title, sim_desc or "", resolved, top_k=top_k)

    if not similar:
        st.warning("Nenhum incidente similar encontrado. Tente termos diferentes.")
    else:
        st.markdown(f"**{len(similar)} resultado(s) encontrado(s)**")
        for s in similar:
            pcolor = PRIO_COLOR.get(s["priority"], "#6B7280")
            score  = s["similarity_pct"]
            bar_w  = max(4, score)

            with st.expander(
                f"{s['incident_id']} — {s['title'][:60]}{'…' if len(s['title'])>60 else ''}  ({score}% similar)",
                expanded=(score >= 20),
            ):
                c1, c2, c3 = st.columns(3)
                c1.markdown(f"**Sistema:** {s['system']}")
                c2.markdown(
                    f"**Prioridade:** <span style='color:{pcolor};font-weight:700'>{s['priority']}</span>",
                    unsafe_allow_html=True,
                )
                c3.markdown(f"**Duracao:** {s['duration_formatted']}")

                st.markdown(
                    f"""
                    <div style="background:#E5E7EB;border-radius:999px;height:6px;margin:6px 0 12px">
                        <div style="width:{bar_w}%;background:#1D4ED8;height:6px;border-radius:999px"></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                if s["root_cause"]:
                    st.markdown(f"**Causa raiz:** {s['root_cause']}")
                if s["resolution_notes"]:
                    st.markdown(f"**Resolucao:** {s['resolution_notes']}")
                if not s["root_cause"] and not s["resolution_notes"]:
                    st.caption("Sem causa raiz ou notas de resolucao registradas.")
else:
    st.info("Digite o titulo do incidente acima para iniciar a busca.")
