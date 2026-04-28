import streamlit as st
from app.utils.calculations import format_duration, format_number


def _hero_card(value: str, label: str, sub: str = "", color: str = "#1D4ED8"):
    st.markdown(
        f"""
        <div style="
            background:linear-gradient(135deg,{color} 0%,{color}CC 100%);
            color:#fff;border-radius:16px;padding:24px 28px;text-align:center;
            box-shadow:0 4px 20px {color}40;
        ">
            <div style="font-size:38px;font-weight:800;letter-spacing:-1px;line-height:1.1">{value}</div>
            <div style="font-size:13px;opacity:.85;margin-top:6px;font-weight:600">{label}</div>
            {"" if not sub else f'<div style="font-size:12px;opacity:.65;margin-top:3px">{sub}</div>'}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_main_kpis(kpis: dict, cfg: dict):
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        _hero_card(
            value=format_number(kpis["total_production_loss"]),
            label="Perda Total de Produção",
            sub=f"Média por incidente: {format_number(kpis['total_production_loss'] / max(kpis['total'], 1))}",
            color="#1D4ED8",
        )
    with col2:
        st.metric("Total de Incidentes", format_number(kpis["total"]))
        st.metric(
            "Em Aberto",
            kpis["open"] + kpis["in_progress"],
            delta=f"{kpis['open'] + kpis['in_progress']} ativo(s)",
            delta_color="inverse" if (kpis["open"] + kpis["in_progress"]) > 0 else "off",
        )
    with col3:
        st.metric("Violações de SLA", kpis["sla_violations"],
                  delta_color="inverse" if kpis["sla_violations"] > 0 else "off")
        st.metric("Resolvidos", kpis["resolved"])

    st.markdown("")

    # ── Secondary row: time + MTTR + resolved ──────────────────────── #
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tempo Total de Parada", format_duration(kpis["total_downtime_minutes"]))
    c2.metric("MTTR Médio", format_duration(kpis["mttr_minutes"]))
    c3.metric("Resolvidos", kpis["resolved"])
    c4.metric("Violações de SLA", kpis["sla_violations"],
              delta_color="inverse" if kpis["sla_violations"] > 0 else "off")


def render_priority_kpis(kpis: dict):
    priority_info = [
        ("P1", "Crítico",  "#DC2626", kpis["p1"]),
        ("P2", "Alto",     "#EA580C", kpis["p2"]),
        ("P3", "Médio",    "#CA8A04", kpis["p3"]),
        ("P4", "Baixo",    "#16A34A", kpis["p4"]),
    ]
    cols = st.columns(4)
    for col, (code, label, color, count) in zip(cols, priority_info):
        pct = round(count / kpis["total"] * 100, 1) if kpis["total"] else 0
        col.markdown(
            f"""
            <div style="background:{color}12;border-left:4px solid {color};
                border-radius:8px;padding:14px 16px;text-align:center;">
                <div style="font-size:30px;font-weight:800;color:{color}">{count}</div>
                <div style="font-size:13px;color:#374151;font-weight:600">{code} — {label}</div>
                <div style="font-size:12px;color:#6B7280">{pct}% do total</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
