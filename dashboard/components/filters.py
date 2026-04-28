from datetime import datetime, date, timedelta
import streamlit as st


PERIOD_OPTIONS = {
    "Hoje":             0,
    "Últimos 7 dias":   7,
    "Últimos 30 dias":  30,
    "Últimos 90 dias":  90,
    "Últimos 6 meses":  180,
    "Último ano":       365,
    "Personalizado":    -1,
}


def render_period_filter(key_prefix: str = "filter") -> tuple[datetime, datetime]:
    col1, col2 = st.columns([2, 3])
    with col1:
        period = st.selectbox(
            "Período",
            list(PERIOD_OPTIONS.keys()),
            index=2,
            key=f"{key_prefix}_period",
        )
    days = PERIOD_OPTIONS[period]
    today = date.today()

    if days == 0:
        start = datetime.combine(today, datetime.min.time())
        end = datetime.combine(today, datetime.max.time())
    elif days > 0:
        start = datetime.combine(today - timedelta(days=days), datetime.min.time())
        end = datetime.combine(today, datetime.max.time())
    else:
        with col2:
            c1, c2 = st.columns(2)
            start_d = c1.date_input("De", value=today - timedelta(days=30), key=f"{key_prefix}_start")
            end_d = c2.date_input("Até", value=today, key=f"{key_prefix}_end")
        start = datetime.combine(start_d, datetime.min.time())
        end = datetime.combine(end_d, datetime.max.time())

    return start, end


def render_sidebar_filters(systems: list, types: list) -> dict:
    st.sidebar.header("Filtros")

    priority_opts = ["P1", "P2", "P3", "P4"]
    selected_priorities = st.sidebar.multiselect(
        "Prioridade", priority_opts, default=priority_opts, key="sb_priority"
    )

    status_opts = ["Aberto", "Em Andamento", "Resolvido"]
    selected_status = st.sidebar.multiselect(
        "Status", status_opts, default=status_opts, key="sb_status"
    )

    system_names = {s.name: s.id for s in systems}
    selected_sys_names = st.sidebar.multiselect(
        "Sistema", list(system_names.keys()), key="sb_system"
    )
    selected_system_ids = [system_names[n] for n in selected_sys_names] if selected_sys_names else None

    type_names = {t.name: t.id for t in types}
    selected_type_names = st.sidebar.multiselect(
        "Tipo de Incidente", list(type_names.keys()), key="sb_type"
    )
    selected_type_ids = [type_names[n] for n in selected_type_names] if selected_type_names else None

    return {
        "priority": selected_priorities or None,
        "status": selected_status or None,
        "system_id": selected_system_ids,
        "incident_type_id": selected_type_ids,
    }
