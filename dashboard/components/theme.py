from pathlib import Path
import streamlit as st

_ASSETS = Path(__file__).resolve().parent.parent.parent / "assets"
LOGO_PATH = str(_ASSETS / "logo.jpg")

CORPORATE_CSS = """
<style>
/* ══════════════════════════════════════════════════════════
   BASE: forçar modo claro e texto escuro em tudo
   ══════════════════════════════════════════════════════════ */
:root { color-scheme: light; }
body, .stApp {
    color: #0F172A !important;
    background-color: #FFFFFF;
}

/* Todos os elementos de texto herdam a cor escura do body */
p, span, div, h1, h2, h3, h4, h5, h6,
label, li, td, th, button, a,
input, textarea, select,
[data-baseweb="select"] span,
[data-baseweb="select"] div,
[data-baseweb="input"] *,
[data-testid="stWidgetLabel"] *,
[data-testid="stMarkdownContainer"] * { color: #0F172A !important; }

/* ══════════════════════════════════════════════════════════
   SIDEBAR — sobrescreve tudo com texto claro sobre azul escuro
   ══════════════════════════════════════════════════════════ */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1E3A5F 0%, #1D4ED8 100%) !important;
    border-right: 1px solid #1E40AF;
}
[data-testid="stSidebar"] *:not(input):not(textarea):not([data-baseweb="input"] *):not([data-baseweb="select"] span):not([data-baseweb="select"] div) {
    color: #F0F7FF !important;
}

/* Sidebar — inputs com fundo branco e texto escuro */
[data-testid="stSidebar"] input,
[data-testid="stSidebar"] textarea {
    color: #1E293B !important;
    background: rgba(255,255,255,0.92) !important;
}
[data-testid="stSidebar"] [data-baseweb="input"],
[data-testid="stSidebar"] [data-baseweb="textarea"] {
    background: rgba(255,255,255,0.92) !important;
}
[data-testid="stSidebar"] [data-baseweb="input"] * { color: #1E293B !important; }
[data-testid="stSidebar"] [data-baseweb="select"] > div:first-child {
    background: rgba(255,255,255,0.92) !important;
}
[data-testid="stSidebar"] [data-baseweb="select"] span,
[data-testid="stSidebar"] [data-baseweb="select"] div[class*="singleValue"],
[data-testid="stSidebar"] [data-baseweb="select"] div[class*="placeholder"] {
    color: #1E293B !important;
}

/* ══════════════════════════════════════════════════════════
   LOGO na sidebar
   ══════════════════════════════════════════════════════════ */
[data-testid="stLogo"] {
    background: #FFFFFF;
    border-radius: 10px;
    padding: 6px 10px;
    margin: 8px 12px;
}

/* ── Page header bar ──────────────────────────────────── */
.page-header {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 14px 20px;
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    margin-bottom: 20px;
}
.page-header img {
    height: 44px;
    width: auto;
    object-fit: contain;
}
.page-header .title   { font-size: 20px; font-weight: 700; color: #1E3A5F; }
.page-header .caption { font-size: 12px; color: #64748B; margin-top: 2px; }

/* ── Metrics ──────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 16px 20px;
}
[data-testid="stMetricLabel"]  { color: #64748B !important; font-size: 13px !important; }
[data-testid="stMetricValue"]  { color: #1E3A5F !important; font-weight: 700 !important; }

/* ── Big KPI card ─────────────────────────────────────── */
.kpi-hero {
    background: linear-gradient(135deg, #1D4ED8 0%, #2563EB 100%);
    color: #FFFFFF;
    border-radius: 16px;
    padding: 28px 32px;
    text-align: center;
}
.kpi-hero .value  { font-size: 42px; font-weight: 800; letter-spacing: -1px; }
.kpi-hero .label  { font-size: 14px; opacity: .85; margin-top: 4px; }
.kpi-hero .sub    { font-size: 13px; opacity: .70; margin-top: 2px; }

/* ── Priority badges ──────────────────────────────────── */
.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 700;
}

/* ── Dividers ─────────────────────────────────────────── */
hr { border: none; border-top: 1px solid #E2E8F0; margin: 20px 0; }

/* ── Print ────────────────────────────────────────────── */
@media print {
    [data-testid="stSidebar"]    { display: none !important; }
    [data-testid="stHeader"]     { display: none !important; }
    [data-testid="stToolbar"]    { display: none !important; }
    [data-testid="stDecoration"] { display: none !important; }
    footer                        { display: none !important; }
    .no-print                     { display: none !important; }
    .stButton                     { display: none !important; }
    .main .block-container        { padding: 0 !important; }
}
</style>
"""


def apply_theme():
    st.markdown(CORPORATE_CSS, unsafe_allow_html=True)
    # Logo nativo do Streamlit — aparece no topo-esquerdo da sidebar
    if Path(LOGO_PATH).exists():
        st.logo(LOGO_PATH)


def page_header(title: str, caption: str = ""):
    """Barra de cabeçalho com logo + título usada em todas as páginas."""
    import base64
    logo_b64 = ""
    if Path(LOGO_PATH).exists():
        with open(LOGO_PATH, "rb") as f:
            logo_b64 = base64.b64encode(f.read()).decode()

    logo_html = (
        f'<img src="data:image/jpeg;base64,{logo_b64}" />'
        if logo_b64 else ""
    )
    caption_html = (
        f'<div class="caption">{caption}</div>' if caption else ""
    )
    st.markdown(
        f"""
        <div class="page-header">
            {logo_html}
            <div>
                <div class="title">{title}</div>
                {caption_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
