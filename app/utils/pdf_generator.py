"""Geração de relatório executivo em PDF usando fpdf2."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
from fpdf import FPDF

_LOGO_PATH = Path(__file__).resolve().parent.parent.parent / "assets" / "logo.jpg"

# ── Paleta ────────────────────────────────────────────────────────── #
BLUE_DARK   = (30,  58,  95)
BLUE_MID    = (29,  78,  216)
PURPLE      = (124, 58,  237)
GRAY_BG     = (248, 250, 252)
GRAY_BORDER = (226, 232, 240)
GRAY_TEXT   = (100, 116, 139)
WHITE       = (255, 255, 255)
BLACK       = (15,  23,  42)

P_COLORS = {
    "P1": (220, 38,  38),
    "P2": (234, 88,  12),
    "P3": (202, 138, 4),
    "P4": (22,  163, 74),
}


def _fmt_dur(minutes: float) -> str:
    if minutes < 60:
        return f"{int(minutes)}min"
    h, m = int(minutes // 60), int(minutes % 60)
    return f"{h}h{m:02d}min" if m else f"{h}h"


def _safe(text: str, max_len: int = 999) -> str:
    """Trunca e garante compatibilidade latin-1 (substitui chars fora do range)."""
    text = (
        str(text)[:max_len]
        .replace("-", "-")   # em dash
        .replace("–", "-")   # en dash
        .replace("…", "...")  # ellipsis
        .replace("’", "'")   # right single quote
        .replace("“", '"')   # left double quote
        .replace("”", '"')   # right double quote
    )
    return text.encode("latin-1", "replace").decode("latin-1")


# ── Classe base ───────────────────────────────────────────────────── #

class _PDF(FPDF):
    def __init__(self):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_margins(14, 14, 14)
        self.set_auto_page_break(auto=True, margin=14)

    def footer(self):
        self.set_y(-11)
        self.set_font("helvetica", "I", 7.5)
        self.set_text_color(*GRAY_TEXT)
        self.cell(
            0, 6,
            f"Sistema de Gestao de Incidentes  |  Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            align="C",
        )
        self.set_text_color(*BLACK)


# ── Funções de desenho ────────────────────────────────────────────── #

def _header_bar(pdf: _PDF, title: str, subtitle: str):
    """Faixa azul no topo com logo + título."""
    pdf.set_fill_color(*BLUE_MID)
    pdf.rect(0, 0, 210, 30, "F")

    x_text = 16
    logo_h = 22

    if _LOGO_PATH.exists():
        try:
            pdf.image(str(_LOGO_PATH), x=14, y=4, h=logo_h)
            x_text = 52
        except Exception:
            pass

    pdf.set_font("helvetica", "B", 15)
    pdf.set_text_color(*WHITE)
    pdf.set_xy(x_text, 7)
    pdf.cell(0, 8, _safe(title))

    pdf.set_font("helvetica", "", 8.5)
    pdf.set_xy(x_text, 16)
    pdf.cell(0, 5, _safe(subtitle))

    pdf.set_text_color(*BLACK)
    pdf.set_y(34)


def _kpi_box(pdf: _PDF, x: float, y: float, w: float, h: float,
             value: str, label: str, color: tuple):
    """Caixa KPI com fundo colorido."""
    pdf.set_fill_color(*color)
    pdf.rect(x, y, w, h, "F")
    # valor
    pdf.set_font("helvetica", "B", 13)
    pdf.set_text_color(*WHITE)
    pdf.set_xy(x + 2, y + 2)
    pdf.cell(w - 4, 7, _safe(value, 20), align="C")
    # rótulo
    pdf.set_font("helvetica", "", 6.5)
    pdf.set_xy(x + 2, y + 9)
    pdf.cell(w - 4, 4, _safe(label), align="C")
    pdf.set_text_color(*BLACK)


def _sec_kpi(pdf: _PDF, x: float, y: float, w: float, h: float,
             value: str, label: str):
    """Caixa KPI secundária (fundo cinza)."""
    pdf.set_fill_color(*GRAY_BG)
    pdf.set_draw_color(*GRAY_BORDER)
    pdf.rect(x, y, w, h, "FD")
    pdf.set_font("helvetica", "B", 11)
    pdf.set_text_color(*BLUE_DARK)
    pdf.set_xy(x + 1, y + 1)
    pdf.cell(w - 2, 6, _safe(value, 16), align="C")
    pdf.set_font("helvetica", "", 6.5)
    pdf.set_text_color(*GRAY_TEXT)
    pdf.set_xy(x + 1, y + 7)
    pdf.cell(w - 2, 3.5, _safe(label), align="C")
    pdf.set_text_color(*BLACK)


def _section_title(pdf: _PDF, text: str):
    pdf.set_font("helvetica", "B", 8)
    pdf.set_text_color(*GRAY_TEXT)
    pdf.cell(0, 5, _safe(text.upper()), ln=True)
    pdf.set_draw_color(*BLUE_MID)
    pdf.set_line_width(0.4)
    x = pdf.get_x()
    y = pdf.get_y()
    pdf.line(x, y, x + 182, y)
    pdf.set_line_width(0.2)
    pdf.set_draw_color(*GRAY_BORDER)
    pdf.ln(3)
    pdf.set_text_color(*BLACK)


def _table(pdf: _PDF, x: float, y: float, w: float,
           headers: list[str], rows: list[list], col_ratios: list[float] | None = None):
    """Tabela simples com cabeçalho escuro e linhas alternadas."""
    n = len(headers)
    ratios = col_ratios or ([1 / n] * n)
    col_ws = [w * r for r in ratios]
    row_h = 5.5

    # Cabeçalho
    pdf.set_fill_color(*BLUE_DARK)
    pdf.set_text_color(*WHITE)
    pdf.set_font("helvetica", "B", 7.5)
    cx = x
    for i, h in enumerate(headers):
        pdf.set_xy(cx, y)
        pdf.cell(col_ws[i], row_h, _safe(h), fill=True)
        cx += col_ws[i]
    y += row_h

    # Linhas de dados
    pdf.set_font("helvetica", "", 7.5)
    for j, row in enumerate(rows):
        if j % 2 == 0:
            pdf.set_fill_color(*GRAY_BG)
        else:
            pdf.set_fill_color(*WHITE)
        pdf.set_text_color(*BLACK)
        cx = x
        for i, cell in enumerate(row):
            pdf.set_xy(cx, y)
            pdf.cell(col_ws[i], row_h, _safe(str(cell), 30), fill=True)
            cx += col_ws[i]
        y += row_h

    # Linha inferior
    pdf.set_draw_color(*GRAY_BORDER)
    pdf.line(x, y, x + w, y)
    return y + 1


# ── Função pública ────────────────────────────────────────────────── #

def generate_report_pdf(
    df: pd.DataFrame,
    kpis: dict,
    cfg: dict,
    start: datetime,
    end: datetime,
) -> bytes:
    daily_target = cfg.get("daily_production_target", 1000)

    days          = max(1, (end - start).days + 1)
    target_period = daily_target * days
    impact_pct    = round(kpis["total_production_loss"] / target_period * 100, 2) if target_period else 0
    efficiency    = round(100 - impact_pct, 1)
    eff_color     = (22, 163, 74) if efficiency >= 95 else (202, 138, 4) if efficiency >= 85 else (220, 38, 38)

    pdf = _PDF()
    pdf.add_page()

    # ── Cabeçalho ──────────────────────────────────────────────────── #
    period_str = (
        f"Periodo: {start.strftime('%d/%m/%Y')} a {end.strftime('%d/%m/%Y')}"
        f"  |  {days} dias  |  Meta: {daily_target:,.0f}/dia"
    )
    _header_bar(pdf, "Relatorio Executivo - Impacto na Producao", period_str)

    # ── KPIs principais (4 caixas coloridas) ──────────────────────── #
    _section_title(pdf, "Indicadores Principais")
    bw, bh, gap = 42, 17, 2.5
    y0 = pdf.get_y()
    _kpi_box(pdf, 14,          y0, bw, bh, f"{kpis['total_production_loss']:,.0f}".replace(",", "."), "Perda de Producao", BLUE_MID)
    _kpi_box(pdf, 14+bw+gap,   y0, bw, bh, f"{efficiency}%",    "Eficiencia no Periodo", eff_color)
    _kpi_box(pdf, 14+2*(bw+gap), y0, bw, bh, str(kpis["total"]), "Total de Incidentes",  BLUE_DARK)
    _kpi_box(pdf, 14+3*(bw+gap), y0, bw, bh, str(kpis["sla_violations"]), "Violacoes de SLA", (220, 38, 38))
    pdf.set_y(y0 + bh + 3)

    # ── KPIs secundários (8 menores) ──────────────────────────────── #
    sec_data = [
        (str(kpis["p1"]),  "P1 Criticos"),
        (str(kpis["p2"]),  "P2 Altos"),
        (str(kpis["resolved"]), "Resolvidos"),
        (str(kpis["open"] + kpis["in_progress"]), "Em Aberto"),
        (_fmt_dur(kpis["mttr_minutes"]),       "MTTR Medio"),
        (_fmt_dur(kpis["total_downtime_minutes"]), "Downtime Total"),
        (str(kpis["sla_violations"]),          "Violacoes SLA"),
        (str(days),                            "Dias no Periodo"),
    ]
    sw, sh, sgap = (182 / 4) - 1, 12, 1.5
    y1 = pdf.get_y()
    for i, (val, lbl) in enumerate(sec_data):
        col, row = i % 4, i // 4
        _sec_kpi(pdf, 14 + col * (sw + sgap), y1 + row * (sh + 1.5), sw, sh, val, lbl)
    pdf.set_y(y1 + 2 * (sh + 1.5) + 4)

    # ── Tabelas (lado a lado) ─────────────────────────────────────── #
    _section_title(pdf, "Rankings por Impacto Produtivo")
    tw = 88
    yt = pdf.get_y()

    # Esquerda: Top 5 sistemas
    pdf.set_font("helvetica", "B", 8)
    pdf.set_text_color(*GRAY_TEXT)
    pdf.set_xy(14, yt)
    pdf.cell(tw, 5, "TOP 5 SISTEMAS - PERDA PRODUTIVA", ln=False)

    sys5 = (
        df.groupby("system")["production_loss"]
        .sum().nlargest(5).reset_index()
    )
    sys_rows = [
        [row["system"][:24], f"{row['production_loss']:,.0f}".replace(",", ".")]
        for _, row in sys5.iterrows()
    ]
    y_end_left = _table(pdf, 14, yt + 6, tw,
                        ["Sistema", "Perda de Producao"],
                        sys_rows,
                        col_ratios=[0.62, 0.38])

    # Direita: Top 5 incidentes
    pdf.set_font("helvetica", "B", 8)
    pdf.set_text_color(*GRAY_TEXT)
    pdf.set_xy(14 + tw + 6, yt)
    pdf.cell(tw, 5, "TOP 5 INCIDENTES - MAIS IMPACTANTES", ln=False)

    inc5 = df.nlargest(5, "production_loss")[
        ["incident_id", "system", "priority", "production_loss"]
    ]
    inc_rows = [
        [row["incident_id"],
         row["system"][:14],
         row["priority"],
         f"{row['production_loss']:,.0f}".replace(",", ".")]
        for _, row in inc5.iterrows()
    ]
    y_end_right = _table(pdf, 14 + tw + 6, yt + 6, tw,
                         ["ID", "Sistema", "P.", "Perda de Producao"],
                         inc_rows,
                         col_ratios=[0.22, 0.38, 0.12, 0.28])

    pdf.set_y(max(y_end_left, y_end_right) + 4)
    pdf.set_text_color(*BLACK)

    # ── Distribuição por prioridade ────────────────────────────────── #
    _section_title(pdf, "Distribuicao por Prioridade - Participacao na Perda Total")
    pw = (182 / 4) - 1.5
    ph = 18
    yp = pdf.get_y()
    for i, (code, label) in enumerate([("P1","Critico"),("P2","Alto"),("P3","Medio"),("P4","Baixo")]):
        color = P_COLORS[code]
        count = kpis[f"p{i+1}"]
        p_loss = df[df["priority"] == code]["production_loss"].sum()
        pct = round(p_loss / max(kpis["total_production_loss"], 1) * 100, 1)
        xp = 14 + i * (pw + 2)

        # Borda colorida à esquerda
        pdf.set_fill_color(*color)
        pdf.rect(xp, yp, 3, ph, "F")

        # Fundo claro
        light = tuple(min(255, c + 200) for c in color)
        pdf.set_fill_color(*light)
        pdf.rect(xp + 3, yp, pw - 3, ph, "F")

        # Número grande
        pdf.set_font("helvetica", "B", 16)
        pdf.set_text_color(*color)
        pdf.set_xy(xp + 5, yp + 1)
        pdf.cell(pw - 7, 8, str(count))

        # Rótulo
        pdf.set_font("helvetica", "B", 7)
        pdf.set_text_color(*BLUE_DARK)
        pdf.set_xy(xp + 5, yp + 9)
        pdf.cell(pw - 7, 4, f"{code} - {label}")

        # Percentual
        pdf.set_font("helvetica", "", 6.5)
        pdf.set_text_color(*GRAY_TEXT)
        pdf.set_xy(xp + 5, yp + 13)
        pdf.cell(pw - 7, 4, f"{pct}% da perda total")

    pdf.set_text_color(*BLACK)
    pdf.set_y(yp + ph + 4)

    # ── Tabela completa de incidentes ─────────────────────────────── #
    if not df.empty:
        pdf.add_page()
        _section_title(pdf, "Lista Completa de Incidentes - Ordenado por Perda Produtiva")

        all_rows = []
        for _, row in df.sort_values("production_loss", ascending=False).iterrows():
            all_rows.append([
                row["incident_id"],
                row["title"][:28],
                row["system"][:16],
                row["priority"],
                row["status"][:12],
                _fmt_dur(row["duration_minutes"]),
                f"{row['production_loss']:,.0f}".replace(",", "."),
            ])

        _table(
            pdf, 14, pdf.get_y(), 182,
            ["ID", "Titulo", "Sistema", "P.", "Status", "Duracao", "Perda de Producao"],
            all_rows,
            col_ratios=[0.10, 0.25, 0.17, 0.06, 0.13, 0.11, 0.18],
        )

    return bytes(pdf.output())
