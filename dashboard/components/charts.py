import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

PRIORITY_COLORS = {
    "P1": "#DC2626",
    "P2": "#EA580C",
    "P3": "#CA8A04",
    "P4": "#16A34A",
}

STATUS_COLORS = {
    "Aberto": "#DC2626",
    "Em Andamento": "#2563EB",
    "Resolvido": "#16A34A",
}


def _base_layout(fig, title: str = ""):
    fig.update_layout(
        title=title,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", size=13),
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def incidents_by_priority_chart(df: pd.DataFrame) -> go.Figure:
    counts = df["priority"].value_counts().reset_index()
    counts.columns = ["priority", "count"]
    counts = counts.sort_values("priority")
    colors = [PRIORITY_COLORS.get(p, "#6B7280") for p in counts["priority"]]

    fig = go.Figure(go.Pie(
        labels=counts["priority"],
        values=counts["count"],
        hole=0.55,
        marker_colors=colors,
        textinfo="label+percent",
        hovertemplate="<b>%{label}</b><br>%{value} incidentes<br>%{percent}<extra></extra>",
    ))
    return _base_layout(fig, "Distribuição por Prioridade")


def loss_over_time_chart(df: pd.DataFrame, freq: str = "W") -> go.Figure:
    """Perda produtiva acumulada ao longo do tempo — foco em impacto, não volume."""
    df = df.copy()
    df["period"] = pd.to_datetime(df["started_at"]).dt.to_period(freq).dt.start_time
    grouped = df.groupby("period")["production_loss"].sum().reset_index()
    grouped.columns = ["period", "perda"]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=grouped["period"], y=grouped["perda"],
        mode="lines+markers",
        fill="tozeroy",
        fillcolor="rgba(29,78,216,0.12)",
        line=dict(color="#1D4ED8", width=2.5),
        marker=dict(size=7, color="#1D4ED8"),
        hovertemplate="<b>%{x}</b><br>Perda: %{y:,.0f} unidades<extra></extra>",
    ))
    fig.update_layout(yaxis_title="Perda produtiva (unidades)", xaxis_title="")
    return _base_layout(fig, "Perda Produtiva ao Longo do Tempo")


def incidents_by_system_chart(
    df: pd.DataFrame, by: str = "loss", top_n: int = 10, title: str = ""
) -> go.Figure:
    if by == "count":
        agg = df.groupby("system").size().reset_index(name="valor")
        xlabel = "Quantidade de Incidentes"
    else:
        agg = df.groupby("system")["production_loss"].sum().reset_index(name="valor")
        xlabel = "Perda de Produção (unidades)"

    agg = agg.nlargest(top_n, "valor").sort_values("valor")

    fig = px.bar(
        agg, x="valor", y="system", orientation="h",
        color="valor",
        color_continuous_scale=["#DBEAFE", "#1D4ED8"],
        labels={"valor": xlabel, "system": "Sistema"},
    )
    fig.update_coloraxes(showscale=False)
    fig.update_traces(hovertemplate="<b>%{y}</b><br>%{x:,.0f}<extra></extra>")
    chart_title = title or f"Top {top_n} Sistemas — {xlabel}"
    return _base_layout(fig, chart_title)


def incidents_over_time_chart(df: pd.DataFrame, freq: str = "W") -> go.Figure:
    df = df.copy()
    df["period"] = pd.to_datetime(df["started_at"]).dt.to_period(freq).dt.start_time
    grouped = (
        df.groupby(["period", "priority"])
        .size()
        .reset_index(name="count")
    )

    fig = px.bar(
        grouped, x="period", y="count", color="priority",
        color_discrete_map=PRIORITY_COLORS,
        barmode="stack",
        labels={"period": "Período", "count": "Incidentes", "priority": "Prioridade"},
    )
    fig.update_traces(hovertemplate="<b>%{x}</b><br>%{y} incidentes<extra></extra>")
    return _base_layout(fig, "Incidentes ao Longo do Tempo")


def top_impactful_incidents_chart(df: pd.DataFrame, n: int = 10) -> go.Figure:
    top = df.nlargest(n, "production_loss")[
        ["incident_id", "title", "system", "priority", "production_loss"]
    ].copy()
    top["label"] = top["incident_id"] + " — " + top["system"]
    top = top.sort_values("production_loss")
    colors = [PRIORITY_COLORS.get(p, "#6B7280") for p in top["priority"]]

    fig = go.Figure(go.Bar(
        x=top["production_loss"],
        y=top["label"],
        orientation="h",
        marker_color=colors,
        hovertemplate="<b>%{y}</b><br>Perda: %{x:.0f} unidades<extra></extra>",
    ))
    return _base_layout(fig, f"Top {n} Incidentes por Impacto na Produção")


def mttr_by_priority_chart(df: pd.DataFrame) -> go.Figure:
    resolved = df[df["status"] == "Resolvido"].copy()
    if resolved.empty:
        return go.Figure()
    mttr = resolved.groupby("priority")["duration_minutes"].mean().reset_index()
    mttr.columns = ["priority", "mttr"]
    mttr = mttr.sort_values("priority")
    colors = [PRIORITY_COLORS.get(p, "#6B7280") for p in mttr["priority"]]

    fig = go.Figure(go.Bar(
        x=mttr["priority"],
        y=mttr["mttr"],
        marker_color=colors,
        hovertemplate="<b>%{x}</b><br>MTTR: %{y:.0f} min<extra></extra>",
    ))
    fig.update_layout(yaxis_title="Minutos")
    return _base_layout(fig, "MTTR Médio por Prioridade (minutos)")


def heatmap_dow_hour(df: pd.DataFrame) -> go.Figure:
    df = df.copy()
    df["started_at"] = pd.to_datetime(df["started_at"])
    df["dow"] = df["started_at"].dt.day_name()
    df["hour"] = df["started_at"].dt.hour

    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    labels_pt = {"Monday": "Seg", "Tuesday": "Ter", "Wednesday": "Qua",
                 "Thursday": "Qui", "Friday": "Sex", "Saturday": "Sáb", "Sunday": "Dom"}

    pivot = (
        df.groupby(["dow", "hour"])
        .size()
        .unstack(fill_value=0)
        .reindex([d for d in order if d in df["dow"].unique()])
    )
    pivot.index = [labels_pt.get(d, d) for d in pivot.index]

    fig = go.Figure(go.Heatmap(
        z=pivot.values,
        x=[f"{h:02d}h" for h in pivot.columns],
        y=pivot.index,
        colorscale="Blues",
        hovertemplate="<b>%{y} %{x}</b><br>%{z} incidentes<extra></extra>",
    ))
    fig.update_layout(xaxis_title="Hora do dia", yaxis_title="Dia da semana")
    return _base_layout(fig, "Concentração de Incidentes (Dia × Hora)")


def incidents_by_type_chart(df: pd.DataFrame) -> go.Figure:
    agg = df.groupby("incident_type").size().reset_index(name="count").sort_values("count")
    fig = px.bar(
        agg, x="count", y="incident_type", orientation="h",
        color="count",
        color_continuous_scale=["#E0F2FE", "#0369A1"],
        labels={"count": "Quantidade", "incident_type": "Tipo"},
    )
    fig.update_coloraxes(showscale=False)
    return _base_layout(fig, "Incidentes por Tipo")


def status_donut_chart(df: pd.DataFrame) -> go.Figure:
    counts = df["status"].value_counts().reset_index()
    counts.columns = ["status", "count"]
    colors = [STATUS_COLORS.get(s, "#6B7280") for s in counts["status"]]

    fig = go.Figure(go.Pie(
        labels=counts["status"],
        values=counts["count"],
        hole=0.55,
        marker_colors=colors,
        textinfo="label+percent",
    ))
    return _base_layout(fig, "Status dos Incidentes")
