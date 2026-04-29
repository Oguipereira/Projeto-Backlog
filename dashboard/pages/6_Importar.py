import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
from datetime import datetime

from app.database import get_db_session
from app.services.incident_service import IncidentService
from app.services.import_service import (
    read_file, detect_column_mapping, analyze_dataframe,
    commit_import, FIELD_LABELS,
)
from dashboard.components.theme import apply_theme, page_header

st.set_page_config(page_title="Importar Dados | Gestão", page_icon="📥", layout="wide")
apply_theme()

page_header(
    "Importar Dados Históricos",
    "Importe incidentes de planilhas Excel ou CSV — o sistema normaliza automaticamente",
)

# ── Upload ───────────────────────────────────────────────────────────── #
uploaded = st.file_uploader(
    "Selecione um arquivo CSV ou Excel",
    type=["csv", "xlsx", "xls"],
)

if not uploaded:
    with st.expander("ℹ️ Como preparar o arquivo"):
        st.markdown("""
O sistema reconhece automaticamente variações de nomes de colunas e normaliza
os dados antes de importar. As colunas obrigatórias são **título**, **data de início**,
**sistema**, **tipo** e **prioridade**.

| Campo | Exemplos de cabeçalho aceitos |
|---|---|
| Título | `título`, `incidente`, `chamado`, `assunto` |
| Data de Início | `início`, `data_inicio`, `abertura`, `start` |
| Hora de Início | `hora_inicio`, `hora_abertura` |
| Sistema | `sistema`, `aplicação`, `app` |
| Tipo | `tipo`, `categoria`, `classificação` |
| Prioridade | `prioridade`, `criticidade` · valores: `P1/P2/P3/P4`, `1–4`, `crítico/alto/médio/baixo` |
| Status | `status`, `estado` · valores: `aberto/em andamento/resolvido` |
| Data de Fim | `fim`, `encerramento`, `data_fim` |
| Duração (min) | `duração`, `tempo_parado`, `downtime` · formatos: `120`, `2h`, `2h30m`, `2:30` |
| Usuários afetados | `usuarios`, `afetados`, `impactados` |
| Causa Raiz | `causa`, `causa_raiz` |
| Notas de Resolução | `resolução`, `solução`, `notas` |
        """)
    st.stop()

# ── Read file ────────────────────────────────────────────────────────── #
df_raw, read_err = read_file(uploaded)
if read_err:
    st.error(read_err)
    st.stop()

df_raw = df_raw.dropna(how="all")
df_raw.columns = [str(c).strip() for c in df_raw.columns]

st.success(f"Arquivo lido: **{len(df_raw)} linhas** · **{len(df_raw.columns)} colunas**")

with st.expander("👁 Preview dos dados brutos (primeiras 8 linhas)"):
    st.dataframe(df_raw.head(8), use_container_width=True)

st.markdown("---")

# ── Column mapping UI ────────────────────────────────────────────────── #
st.subheader("Mapeamento de Colunas")
st.caption("Detectado automaticamente. Ajuste se necessário — campos com * são obrigatórios.")

auto_map = detect_column_mapping(list(df_raw.columns))
options  = ["(ignorar coluna)"] + list(df_raw.columns)
col_map  = {}

c1, c2 = st.columns(2)
for i, (field, label) in enumerate(FIELD_LABELS.items()):
    detected  = auto_map.get(field)
    default_i = options.index(detected) if detected in options else 0
    selected  = (c1 if i % 2 == 0 else c2).selectbox(
        label, options, index=default_i, key=f"cm_{field}"
    )
    col_map[field] = None if selected == "(ignorar coluna)" else selected

st.markdown("---")

# ── Analysis ─────────────────────────────────────────────────────────── #
if st.button("Analisar e Validar", type="primary", use_container_width=True):
    db = get_db_session()
    try:
        svc = IncidentService(db)
        existing_systems = [s.name for s in svc.get_systems(active_only=False)]
        existing_types   = [t.name for t in svc.get_incident_types(active_only=False)]
    finally:
        db.close()

    with st.spinner("Normalizando dados..."):
        valid, errors, new_sys, new_types = analyze_dataframe(
            df_raw, col_map, existing_systems, existing_types
        )

    st.session_state["imp_valid"]    = valid
    st.session_state["imp_errors"]   = errors
    st.session_state["imp_new_sys"]  = new_sys
    st.session_state["imp_new_type"] = new_types

if "imp_valid" not in st.session_state:
    st.stop()

valid    = st.session_state["imp_valid"]
errors   = st.session_state["imp_errors"]
new_sys  = st.session_state["imp_new_sys"]
new_type = st.session_state["imp_new_type"]

# ── Results ──────────────────────────────────────────────────────────── #
m1, m2, m3 = st.columns(3)
m1.metric("Registros válidos",       len(valid))
m2.metric("Registros com problemas", len(errors))
m3.metric("Novos sistemas/tipos",    len(new_sys) + len(new_type))

if new_sys or new_type:
    with st.expander("🆕 Sistemas e tipos que serão criados automaticamente"):
        if new_sys:
            st.markdown("**Sistemas novos:** " + " · ".join(f"`{s}`" for s in new_sys))
        if new_type:
            st.markdown("**Tipos novos:** " + " · ".join(f"`{t}`" for t in new_type))

if valid:
    with st.expander(f"✅ Preview — primeiros {min(8, len(valid))} registros válidos"):
        rows_preview = []
        for r in valid[:8]:
            rows_preview.append({
                "Título":     (r.get("title") or "")[:50],
                "Início":     r["started_at"].strftime("%d/%m/%Y %H:%M") if r.get("started_at") else "—",
                "Fim":        r["ended_at"].strftime("%d/%m/%Y %H:%M")   if r.get("ended_at")   else "—",
                "Sistema":    r.get("_system_name", "—"),
                "Tipo":       r.get("_type_name",   "—"),
                "Prioridade": r.get("priority",     "—"),
                "Status":     r.get("status",       "—"),
            })
        st.dataframe(pd.DataFrame(rows_preview), use_container_width=True, hide_index=True)

if errors:
    with st.expander(f"⚠️ Registros com problemas — {len(errors)} linha(s)"):
        for er in errors[:30]:
            st.markdown(
                f"**Linha {er['row']}**: {'; '.join(er['errors'])}"
            )
        if len(errors) > 30:
            st.caption(f"… e mais {len(errors) - 30} com problemas.")

# ── Import ───────────────────────────────────────────────────────────── #
if valid:
    st.markdown("---")
    st.info(
        f"**{len(valid)} registros** serão importados. "
        f"{len(errors)} linha(s) com problemas serão ignoradas."
    )
    if st.button(
        f"Importar {len(valid)} registros",
        type="primary",
        use_container_width=True,
    ):
        with st.spinner("Importando..."):
            db = get_db_session()
            try:
                result = commit_import(valid, db)
            finally:
                db.close()

        st.success(
            f"Importação concluída: **{result['imported']} importados**"
            + (f", {result['skipped']} ignorados." if result["skipped"] else ".")
        )
        for k in ["imp_valid", "imp_errors", "imp_new_sys", "imp_new_type"]:
            st.session_state.pop(k, None)
        st.cache_data.clear()
else:
    st.warning("Nenhum registro válido para importar. Revise o mapeamento de colunas.")
