import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
from app.database import get_db_session
from app.services.incident_service import IncidentService
from app.services.impact_service import ImpactService
from app.services.config_service import ConfigService
from dashboard.components.theme import apply_theme, page_header

st.set_page_config(page_title="Configurações | Incidentes", page_icon="⚙️", layout="wide")
apply_theme()

page_header("Configurações do Sistema", "Parâmetros de produção, sistemas e tipos de incidente")

CRIT_COLORS = {"alta": "#DC2626", "media": "#CA8A04", "baixa": "#16A34A"}


def get_db():
    return get_db_session()


# ─── 1. Parâmetros de Produção ────────────────────────────────────── #
st.subheader(" Parâmetros de Produção")
st.caption("Altere os valores abaixo sem precisar modificar código. KPIs recalculados automaticamente.")

db = get_db()
cfg_svc = ConfigService(db)
cur = cfg_svc.get_production_config()
db.close()

with st.form("prod_config_form"):
    c1, c2 = st.columns(2)
    work_h   = c1.number_input("Horas de trabalho por dia",          min_value=1.0, max_value=24.0, value=float(cur["work_hours_per_day"]),        step=0.5)
    eff_h    = c2.number_input("Horas úteis (descontando pausas)",    min_value=1.0, max_value=24.0, value=float(cur["effective_hours_per_day"]),   step=0.5)
    target   = c1.number_input("Meta de produção diária",             min_value=1.0,                 value=float(cur["daily_production_target"]))
    currency = c2.text_input("Moeda",                                                                value=cur["currency"])

    eff_min   = eff_h * 60
    r_hour    = round(target / eff_h,   2)
    r_min     = round(target / eff_min, 4)
    st.info(
        f"**Taxas:** {r_hour}/h · {r_min}/min"
    )
    saved = st.form_submit_button(" Salvar Configurações de Produção", use_container_width=True)

if saved:
    db2 = get_db()
    ConfigService(db2).save_production_config({
        "work_hours_per_day":      work_h,
        "effective_hours_per_day": eff_h,
        "daily_production_target": target,
        "currency":                currency,
    })
    db2.close()
    st.success("Configurações salvas!")
    st.cache_data.clear()

if st.button(" Recalcular Impacto de Todos os Incidentes"):
    db3 = get_db()
    ImpactService(db3).recalculate_all()
    db3.close()
    st.success("Recálculo concluído. Todos os incidentes foram atualizados.")
    st.cache_data.clear()

st.markdown("---")

# ─── 2. Sistemas (CRUD completo) ─────────────────────────────────── #
st.subheader(" Sistemas Cadastrados")
st.caption("Excluir um sistema com histórico o **desativa** (dados preservados). Sem histórico: exclusão permanente.")

# Add system
with st.expander("➕ Adicionar novo sistema"):
    with st.form("add_system"):
        n1, n2, n3 = st.columns([2, 3, 1])
        s_name = n1.text_input("Nome *")
        s_desc = n2.text_input("Descrição")
        s_crit = n3.selectbox("Criticidade", ["alta", "media", "baixa"])
        if st.form_submit_button("Adicionar", use_container_width=True):
            if s_name.strip():
                db4 = get_db()
                IncidentService(db4).create_system(s_name.strip(), s_desc.strip(), s_crit)
                db4.close()
                st.success(f"Sistema '{s_name}' adicionado!")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error("Nome é obrigatório.")

# List + edit + delete
db5 = get_db()
systems = IncidentService(db5).get_systems(active_only=False)
db5.close()

for s in systems:
    cc = CRIT_COLORS.get(s.criticality, "#6B7280")
    active_badge = (
        '<span style="color:#16A34A;font-weight:600;font-size:12px">● Ativo</span>'
        if s.active else
        '<span style="color:#9CA3AF;font-weight:600;font-size:12px">○ Inativo</span>'
    )

    col_info, col_edit, col_del = st.columns([6, 1, 1])
    with col_info:
        st.markdown(
            f"""
            <div style="display:flex;align-items:center;gap:12px;padding:10px 0;
                        border-bottom:1px solid #F1F5F9">
                {active_badge}
                <span style="font-weight:700;min-width:180px">{s.name}</span>
                <span style="background:{cc}15;color:{cc};padding:1px 8px;
                    border-radius:999px;font-size:11px;font-weight:700">
                    {s.criticality.upper()}
                </span>
                <span style="color:#6B7280;font-size:13px;flex:1">{s.description}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_edit:
        if st.button("✏️", key=f"edit_s_{s.id}", help="Editar sistema"):
            st.session_state[f"editing_sys_{s.id}"] = True

    with col_del:
        if st.button("🗑️", key=f"del_s_{s.id}", help="Excluir / desativar"):
            st.session_state[f"confirm_del_sys_{s.id}"] = True

    # Confirm delete
    if st.session_state.get(f"confirm_del_sys_{s.id}"):
        st.warning(
            f"Confirmar exclusão de **{s.name}**? "
            "Se houver incidentes, o sistema será desativado (não apagado)."
        )
        yes_col, no_col = st.columns(2)
        if yes_col.button("✅ Confirmar", key=f"yes_del_{s.id}"):
            db6 = get_db()
            ok, msg = IncidentService(db6).delete_system(s.id)
            db6.close()
            st.session_state[f"confirm_del_sys_{s.id}"] = False
            if ok:
                st.success(msg)
            else:
                st.error(msg)
            st.cache_data.clear()
            st.rerun()
        if no_col.button("❌ Cancelar", key=f"no_del_{s.id}"):
            st.session_state[f"confirm_del_sys_{s.id}"] = False
            st.rerun()

    # Inline edit form
    if st.session_state.get(f"editing_sys_{s.id}"):
        with st.form(f"edit_sys_{s.id}"):
            st.markdown(f"**Editando: {s.name}**")
            e1, e2, e3, e4 = st.columns([2, 3, 1, 1])
            new_name  = e1.text_input("Nome",        value=s.name)
            new_desc  = e2.text_input("Descrição",   value=s.description or "")
            new_crit  = e3.selectbox("Criticidade",  ["alta", "media", "baixa"],
                                     index=["alta", "media", "baixa"].index(s.criticality))
            new_active = e4.checkbox("Ativo",        value=s.active)
            sv, cn = st.columns(2)
            if sv.form_submit_button("Salvar", use_container_width=True):
                db7 = get_db()
                IncidentService(db7).update_system(s.id, {
                    "name": new_name, "description": new_desc,
                    "criticality": new_crit, "active": new_active,
                })
                db7.close()
                st.session_state[f"editing_sys_{s.id}"] = False
                st.cache_data.clear()
                st.rerun()
            if cn.form_submit_button("Cancelar", use_container_width=True):
                st.session_state[f"editing_sys_{s.id}"] = False
                st.rerun()

st.markdown("---")

# ─── 3. Tipos de Incidente ────────────────────────────────────────── #
st.subheader(" Tipos de Incidente")

with st.expander("➕ Adicionar tipo"):
    with st.form("add_type"):
        t1, t2 = st.columns([2, 4])
        t_name = t1.text_input("Nome *")
        t_desc = t2.text_input("Descrição")
        if st.form_submit_button("Adicionar", use_container_width=True):
            if t_name.strip():
                db8 = get_db()
                IncidentService(db8).create_incident_type(t_name.strip(), t_desc.strip())
                db8.close()
                st.success(f"Tipo '{t_name}' adicionado!")
                st.rerun()
            else:
                st.error("Nome é obrigatório.")

db9 = get_db()
types = IncidentService(db9).get_incident_types(active_only=False)
db9.close()

st.caption("Excluir um tipo com histórico o **desativa** (dados preservados). Sem histórico: exclusão permanente.")

for t in types:
    active_badge = (
        '<span style="color:#16A34A;font-weight:600;font-size:12px">● Ativo</span>'
        if t.active else
        '<span style="color:#9CA3AF;font-weight:600;font-size:12px">○ Inativo</span>'
    )

    col_info, col_edit, col_del = st.columns([6, 1, 1])
    with col_info:
        st.markdown(
            f"""
            <div style="display:flex;align-items:center;gap:12px;padding:10px 0;
                        border-bottom:1px solid #F1F5F9">
                {active_badge}
                <span style="font-weight:700;min-width:200px">{t.name}</span>
                <span style="color:#6B7280;font-size:13px;flex:1">{t.description}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_edit:
        if st.button("✏️", key=f"edit_t_{t.id}", help="Editar tipo"):
            st.session_state[f"editing_type_{t.id}"] = True

    with col_del:
        if st.button("🗑️", key=f"del_t_{t.id}", help="Excluir / desativar"):
            st.session_state[f"confirm_del_type_{t.id}"] = True

    if st.session_state.get(f"confirm_del_type_{t.id}"):
        st.warning(
            f"Confirmar exclusão de **{t.name}**? "
            "Se houver incidentes vinculados, o tipo será desativado (não apagado)."
        )
        yes_col, no_col = st.columns(2)
        if yes_col.button("✅ Confirmar", key=f"yes_del_t_{t.id}"):
            db_d = get_db()
            ok, msg = IncidentService(db_d).delete_incident_type(t.id)
            db_d.close()
            st.session_state[f"confirm_del_type_{t.id}"] = False
            st.success(msg) if ok else st.error(msg)
            st.cache_data.clear()
            st.rerun()
        if no_col.button("❌ Cancelar", key=f"no_del_t_{t.id}"):
            st.session_state[f"confirm_del_type_{t.id}"] = False
            st.rerun()

    if st.session_state.get(f"editing_type_{t.id}"):
        with st.form(f"edit_type_{t.id}"):
            st.markdown(f"**Editando: {t.name}**")
            e1, e2, e3 = st.columns([2, 4, 1])
            new_tname  = e1.text_input("Nome",       value=t.name)
            new_tdesc  = e2.text_input("Descrição",  value=t.description or "")
            new_active = e3.checkbox("Ativo",        value=t.active)
            sv, cn = st.columns(2)
            if sv.form_submit_button("Salvar", use_container_width=True):
                db_e = get_db()
                IncidentService(db_e).update_incident_type(t.id, {
                    "name": new_tname, "description": new_tdesc, "active": new_active,
                })
                db_e.close()
                st.session_state[f"editing_type_{t.id}"] = False
                st.cache_data.clear()
                st.rerun()
            if cn.form_submit_button("Cancelar", use_container_width=True):
                st.session_state[f"editing_type_{t.id}"] = False
                st.rerun()

st.markdown("---")

with st.expander("ℹ️ Sobre o sistema"):
    st.markdown("""
    **Sistema de Gestão de Incidentes Corporativos**

    | Componente | Tecnologia |
    |---|---|
    | Banco de dados | SQLite (`data/incidents.db`) |
    | ORM | SQLAlchemy 2.0 |
    | Dashboard | Streamlit + Plotly |
    | Configuração | `config/settings.json` |

    Para migrar para **PostgreSQL**, altere `DATABASE_URL` em `app/database.py`.
    """)
