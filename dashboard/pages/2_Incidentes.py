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
from app.services.config_service import ConfigService
from app.utils.calculations import format_duration
from dashboard.components.theme import apply_theme, page_header

st.set_page_config(page_title="Incidentes | Gestão", page_icon="🚨", layout="wide")
apply_theme()

page_header("Gestão de Incidentes", "Registre, acompanhe e encerre incidentes operacionais")

PRIORITY_COLORS = {"P1": "#DC2626", "P2": "#EA580C", "P3": "#CA8A04", "P4": "#16A34A"}
STATUS_COLORS = {"Aberto": "#DC2626", "Em Andamento": "#2563EB", "Resolvido": "#16A34A"}


def get_db():
    return get_db_session()


@st.cache_data(ttl=30)
def get_reference_data():
    db = get_db()
    try:
        svc = IncidentService(db)
        cfg_svc = ConfigService(db)
        systems = svc.get_systems()
        types = svc.get_incident_types()
        cfg = cfg_svc.get_production_config()
        return (
            {s.name: s.id for s in systems},
            {t.name: t.id for t in types},
            cfg,
        )
    finally:
        db.close()


systems_map, types_map, cfg = get_reference_data()
systems_list = list(systems_map.keys())
types_list = list(types_map.keys())

# ------------------------------------------------------------------ #
#  Sidebar: Create new incident (session_state — permite botão de IA) #
# ------------------------------------------------------------------ #

st.sidebar.header("➕ Novo Incidente")

# Inicializa defaults na primeira renderização (ou após limpar o form)
_now = datetime.now()
for _k, _v in {
    "ni_system":       systems_list[0] if systems_list else "",
    "ni_type":         types_list[0]   if types_list   else "",
    "ni_priority":     "P1",
    "ni_status":       "Aberto",
    "ni_started_time": _now.time(),
    "ni_ended_time":   _now.time(),
    "ni_has_end":      False,
    "ni_affected":     0,
}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

title       = st.sidebar.text_input("Título *", placeholder="Ex: ERP fora do ar — produção parada", key="ni_title")
description = st.sidebar.text_area("Descrição", height=80, key="ni_desc")


# ── Restante dos campos ───────────────────────────────────────────── #
system_name = st.sidebar.selectbox("Sistema *",    systems_list,                          key="ni_system")
type_name   = st.sidebar.selectbox("Tipo *",       types_list,                            key="ni_type")
priority    = st.sidebar.selectbox("Prioridade *", ["P1", "P2", "P3", "P4"],              key="ni_priority")
status      = st.sidebar.selectbox("Status *",     ["Aberto", "Em Andamento", "Resolvido"], key="ni_status")

started_at_date = st.sidebar.date_input("Data de Início *", key="ni_started_date")
started_time    = st.sidebar.time_input("Hora de Início",    key="ni_started_time")

has_end = st.sidebar.checkbox("Já encerrado?", key="ni_has_end")
if has_end:
    ended_at_date = st.sidebar.date_input("Data Fim", key="ni_ended_date")
    ended_time    = st.sidebar.time_input("Hora Fim",  key="ni_ended_time")
else:
    ended_at_date = None
    ended_time    = None

affected_users = st.sidebar.number_input("Usuários afetados", min_value=0, key="ni_affected")

if st.sidebar.button("Registrar Incidente", use_container_width=True, type="primary"):
    if not title.strip():
        st.sidebar.error("Título é obrigatório.")
    else:
        db = get_db()
        svc = IncidentService(db)
        started_dt = datetime.combine(started_at_date, started_time)
        ended_dt   = datetime.combine(ended_at_date, ended_time) if has_end else None

        svc.create({
            "title":            title.strip(),
            "description":      (description or "").strip(),
            "system_id":        systems_map[system_name],
            "incident_type_id": types_map[type_name],
            "priority":         priority,
            "status":           status,
            "started_at":       started_dt,
            "ended_at":         ended_dt,
            "affected_users":   int(affected_users),
        })
        # Retreina os modelos com o novo dado incluído
        try:
            from app.services.ml_service import train_all
            train_all(svc.get_all({}))
        except Exception:
            pass
        db.close()

        for _k in [k for k in list(st.session_state.keys())
                   if k.startswith("ni_") or k.startswith("_ni_")]:
            del st.session_state[_k]

        st.sidebar.success("Incidente registrado!")
        st.cache_data.clear()
        st.rerun()

# ------------------------------------------------------------------ #
#  Filters                                                             #
# ------------------------------------------------------------------ #

st.subheader("Filtros")
fcol1, fcol2, fcol3, fcol4 = st.columns(4)
with fcol1:
    f_priority = st.multiselect("Prioridade", ["P1", "P2", "P3", "P4"], key="f_p")
with fcol2:
    f_status = st.multiselect("Status", ["Aberto", "Em Andamento", "Resolvido"], key="f_s")
with fcol3:
    f_system = st.multiselect("Sistema", list(systems_map.keys()), key="f_sys")
with fcol4:
    f_search = st.text_input("Buscar no título", key="f_search")

# ------------------------------------------------------------------ #
#  Load & display incidents                                            #
# ------------------------------------------------------------------ #

db = get_db()
svc = IncidentService(db)
filters: dict = {}
if f_priority:
    filters["priority"] = f_priority
if f_status:
    filters["status"] = f_status
if f_system:
    filters["system_id"] = [systems_map[n] for n in f_system]

incidents = svc.get_all(filters)
db.close()

if f_search:
    incidents = [i for i in incidents if f_search.lower() in i.title.lower()]

count_col, csv_col = st.columns([4, 1])
count_col.markdown(f"**{len(incidents)} incidente(s) encontrado(s)**")

with csv_col:
    if incidents:
        rows = []
        for i in incidents:
            rows.append({
                "ID":             i.incident_id,
                "Título":         i.title,
                "Sistema":        i.system.name if i.system else "",
                "Tipo":           i.incident_type.name if i.incident_type else "",
                "Prioridade":     i.priority,
                "Status":         i.status,
                "Início":         i.started_at.strftime("%d/%m/%Y %H:%M"),
                "Encerramento":   i.ended_at.strftime("%d/%m/%Y %H:%M") if i.ended_at else "",
                "Duração (min)":  round(i.duration_minutes or 0, 1),
                "Perda Produção": round(i.production_loss or 0, 1),
                "Usuários":       i.affected_users or 0,
                "Causa Raiz":     i.root_cause or "",
                "Resolução":      i.resolution_notes or "",
            })
        csv_bytes = pd.DataFrame(rows).to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
        st.download_button(
            label="⬇ Exportar CSV",
            data=csv_bytes,
            file_name=f"incidentes_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True,
        )

st.markdown("---")

if not incidents:
    st.info("Nenhum incidente encontrado.")
    st.stop()

# ------------------------------------------------------------------ #
#  Incident cards                                                      #
# ------------------------------------------------------------------ #

for inc in incidents:
    p_color = PRIORITY_COLORS.get(inc.priority, "#6B7280")
    s_color = STATUS_COLORS.get(inc.status, "#374151")
    system_name_disp = inc.system.name if inc.system else "-"
    type_name_disp = inc.incident_type.name if inc.incident_type else "-"
    dur = inc.duration_minutes or 0
    if not inc.ended_at:
        dur = (datetime.now() - inc.started_at).total_seconds() / 60

    with st.container():
        header_col, action_col = st.columns([5, 1])
        with header_col:
            st.markdown(
                f"""
                <div style="display:flex; align-items:center; gap:10px; margin-bottom:4px">
                    <span style="background:{p_color}22;color:{p_color};
                        padding:2px 10px;border-radius:999px;font-size:12px;font-weight:700">
                        {inc.priority}
                    </span>
                    <span style="background:{s_color}22;color:{s_color};
                        padding:2px 10px;border-radius:999px;font-size:12px;font-weight:600">
                        {inc.status}
                    </span>
                    <span style="font-weight:600;font-size:15px">{inc.incident_id}</span>
                    <span style="color:#374151">{inc.title}</span>
                </div>
                <div style="color:#374151;font-size:13px">
                    🖥 {system_name_disp} &nbsp;|&nbsp;
                    🏷 {type_name_disp} &nbsp;|&nbsp;
                    🕒 {inc.started_at.strftime('%d/%m/%Y %H:%M')} &nbsp;|&nbsp;
                    ⏱ {format_duration(dur)} &nbsp;|&nbsp;
                    👥 {inc.affected_users} usuários
                </div>
                """,
                unsafe_allow_html=True,
            )

        with action_col:
            if st.button("Editar", key=f"edit_{inc.incident_id}"):
                for s in ["es", "ep", "et", "erc", "ern", "ehe", "eed", "eet"]:
                    st.session_state.pop(f"{s}_{inc.incident_id}", None)
                st.session_state[f"editing_{inc.incident_id}"] = True

    # Painel de edição inline
    if st.session_state.get(f"editing_{inc.incident_id}"):
        k = inc.incident_id
        st.markdown(f"**Editando {k}**")

        ec1, ec2 = st.columns(2)
        new_status = ec1.selectbox(
            "Status", ["Aberto", "Em Andamento", "Resolvido"],
            index=["Aberto", "Em Andamento", "Resolvido"].index(inc.status),
            key=f"es_{k}",
        )
        new_priority = ec2.selectbox(
            "Prioridade", ["P1", "P2", "P3", "P4"],
            index=["P1", "P2", "P3", "P4"].index(inc.priority),
            key=f"ep_{k}",
        )
        new_title = st.text_input("Título", value=inc.title, key=f"et_{k}")

        new_root_cause = st.text_area("Causa Raiz", value=inc.root_cause or "", key=f"erc_{k}")
        new_resolution = st.text_area("Notas de Resolução", value=inc.resolution_notes or "", key=f"ern_{k}")

        has_end_edit = st.checkbox(
            "Definir data de encerramento",
            value=inc.ended_at is not None,
            key=f"ehe_{k}",
        )
        ec3, ec4 = st.columns(2)
        end_d = ec3.date_input(
            "Data Fim",
            value=(inc.ended_at or datetime.now()).date(),
            key=f"eed_{k}",
            disabled=not has_end_edit,
        )
        end_t = ec4.time_input(
            "Hora Fim",
            value=(inc.ended_at or datetime.now()).time(),
            key=f"eet_{k}",
            disabled=not has_end_edit,
        )
        new_ended_at = datetime.combine(end_d, end_t) if has_end_edit else None

        save_col, cancel_col, del_col = st.columns([2, 2, 1])

        if save_col.button("Salvar", key=f"esave_{k}", use_container_width=True):
            db2 = get_db()
            IncidentService(db2).update(k, {
                "title":            new_title,
                "status":           new_status,
                "priority":         new_priority,
                "root_cause":       new_root_cause,
                "resolution_notes": new_resolution,
                "ended_at":         new_ended_at,
            })
            db2.close()
            st.session_state[f"editing_{k}"] = False
            st.cache_data.clear()
            st.rerun()

        if cancel_col.button("Cancelar", key=f"ecancel_{k}", use_container_width=True):
            for s in ["es", "ep", "et", "erc", "ern", "ehe", "eed", "eet"]:
                st.session_state.pop(f"{s}_{k}", None)
            st.session_state[f"editing_{k}"] = False
            st.rerun()

        if del_col.button("Excluir", key=f"edel_{k}", use_container_width=True):
            db3 = get_db()
            IncidentService(db3).delete(k)
            db3.close()
            st.session_state[f"editing_{k}"] = False
            st.cache_data.clear()
            st.rerun()

    st.markdown(
        "<hr style='margin:8px 0;border:none;border-top:1px solid #F1F5F9'>",
        unsafe_allow_html=True,
    )
