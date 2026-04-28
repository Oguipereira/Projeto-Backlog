import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT))

import streamlit as st
import pandas as pd

from app.database import get_db_session
from app.services.activity_service import ActivityService
from app.auth import require_login, sidebar_user
from dashboard.components.theme import apply_theme, page_header

st.set_page_config(page_title="Atividades | Incidentes", page_icon="📋", layout="wide")
apply_theme()
require_login()
sidebar_user()

page_header("Registro de Atividades", "Histórico de acessos e alterações realizadas no sistema")

db = get_db_session()
try:
    logs = ActivityService(db).get_recent(limit=500)
finally:
    db.close()

if not logs:
    st.info("Nenhuma atividade registrada ainda.")
    st.stop()

rows = [
    {
        "Data / Hora":  log.created_at.strftime("%d/%m/%Y %H:%M:%S"),
        "Nome":         log.user_name or log.user_email,
        "E-mail":       log.user_email,
        "Ação":         log.action,
        "Detalhes":     log.details or "",
    }
    for log in logs
]
df = pd.DataFrame(rows)

col1, col2 = st.columns(2)
with col1:
    f_user = st.text_input("Filtrar por usuário ou e-mail")
with col2:
    acoes = ["Todas"] + sorted(df["Ação"].unique().tolist())
    f_action = st.selectbox("Filtrar por ação", acoes)

if f_user:
    mask = (
        df["Nome"].str.contains(f_user, case=False, na=False)
        | df["E-mail"].str.contains(f_user, case=False, na=False)
    )
    df = df[mask]
if f_action != "Todas":
    df = df[df["Ação"] == f_action]

st.markdown(f"**{len(df)} registro(s)**")
st.dataframe(df, use_container_width=True, hide_index=True)
