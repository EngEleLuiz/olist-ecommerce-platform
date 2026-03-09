"""Shared Plotly chart builders — Olist gold/amber palette."""

from __future__ import annotations
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

GOLD   = "#FFD400"
YELLOW = "#FFC300"
AMBER  = "#FF8C00"
ORANGE = "#FF5F00"
DARK   = "#2D2000"
MUTED  = "#6B5B00"
RED    = "#CC2200"
GREEN  = "#2D7A00"

PALETTE = [GOLD, AMBER, ORANGE, YELLOW, "#E6B800", "#FF4500", "#FFE066", "#FF6B35"]


def _rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


BASE = dict(
    paper_bgcolor="#FFFFFF",
    plot_bgcolor="#FFFDF5",
    font=dict(family="Inter, Arial, sans-serif", color=DARK, size=11),
    xaxis=dict(showgrid=False, color=MUTED, linecolor="#F0E8C8", linewidth=1),
    yaxis=dict(showgrid=True, gridcolor="#F0E8C8", color=MUTED),
    margin=dict(t=48, b=24, l=12, r=12),
    legend=dict(bgcolor="#FFFFFF", bordercolor="#F0E8C8", borderwidth=1,
                font=dict(size=11, color=DARK)),
    coloraxis_colorbar=dict(
        tickfont=dict(color=DARK),
        title=dict(font=dict(color=DARK)),
    ),
)


def _apply(fig: go.Figure, title: str = "", height: int = 380) -> go.Figure:
    fig.update_layout(
        **BASE,
        title=dict(text=title, font=dict(size=13, color=DARK, family="Inter, Arial, sans-serif")),
        height=height,
    )
    return fig


def monthly_volume_bar(df: pd.DataFrame, title: str = "Monthly Order Volume") -> go.Figure:
    monthly = (
        df.groupby("purchase_ym")
        .agg(orders=("order_id", "count"), gmv=("payment_value", "sum"))
        .reset_index()
    )
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.6, 0.4], vertical_spacing=0.06)
    fig.add_trace(go.Bar(x=monthly["purchase_ym"], y=monthly["orders"],
                         marker_color=GOLD, marker_opacity=0.9, name="Orders"), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=monthly["purchase_ym"], y=monthly["gmv"],
        fill="tozeroy", fillcolor=_rgba(AMBER, 0.15),
        line=dict(color=AMBER, width=2), name="GMV",
    ), row=2, col=1)
    fig = _apply(fig, title, height=420)
    fig.update_yaxes(showgrid=True, gridcolor="#F0E8C8")
    return fig


def state_bar(df: pd.DataFrame, metric: str = "gmv",
              title: str = "GMV by State", top_n: int = 15) -> go.Figure:
    col_map = {"gmv": "payment_value", "order_count": "order_id", "payment_value": "payment_value"}
    col = col_map.get(metric, "payment_value")
    agg_fn = "count" if col == "order_id" else "sum"
    agg = (
        df.groupby("customer_state")[col].agg(agg_fn)
        .sort_values(ascending=True).tail(top_n)
    )
    colors = [GOLD] * (len(agg) - 1) + [ORANGE]
    fig = go.Figure(go.Bar(
        x=agg.values, y=agg.index, orientation="h",
        marker_color=colors, marker_opacity=0.9,
    ))
    return _apply(fig, title, height=400)


def category_treemap(df: pd.DataFrame, title: str = "GMV by Category") -> go.Figure:
    cat = (
        df.groupby("main_category")
        .agg(gmv=("payment_value", "sum"), orders=("order_id", "count"))
        .reset_index()
    )
    fig = px.treemap(
        cat, path=["main_category"], values="gmv",
        color="orders", color_continuous_scale=["#FFF3B0", "#FFD400", "#FF5F00"],
    )
    fig.update_traces(textfont=dict(family="Inter, Arial, sans-serif", size=11),
                      marker=dict(cornerradius=4))
    return _apply(fig, title, height=420)


def delay_histogram(df: pd.DataFrame, title: str = "Delivery Delay Distribution") -> go.Figure:
    delivered = df[df["order_status"] == "delivered"].dropna(subset=["delay_days"])
    fig = go.Figure(go.Histogram(
        x=delivered["delay_days"].clip(0, 30),
        nbinsx=30, marker_color=AMBER, marker_opacity=0.85,
    ))
    fig.add_vline(x=0, line_color=GREEN, line_dash="dash",
                  annotation_text="On time", annotation_font_color=GREEN)
    fig.add_vline(x=delivered["delay_days"].median(),
                  line_color=RED, line_dash="dash",
                  annotation_text=f"Median {delivered['delay_days'].median():.1f}d",
                  annotation_font_color=RED)
    return _apply(fig, title)


def late_rate_by_state(df: pd.DataFrame, title: str = "Late Rate by State") -> go.Figure:
    state_lr = (
        df[df["order_status"] == "delivered"]
        .groupby("customer_state")["is_late"].mean()
        .sort_values(ascending=True)
    )
    colors = [RED if v > 0.15 else AMBER if v > 0.08 else GREEN for v in state_lr.values]
    fig = go.Figure(go.Bar(
        x=state_lr.values * 100, y=state_lr.index,
        orientation="h", marker_color=colors, marker_opacity=0.85,
    ))
    fig.add_vline(x=state_lr.mean() * 100, line_color=GOLD, line_dash="dash",
                  annotation_text=f"Avg {state_lr.mean():.1%}", annotation_font_color=DARK)
    return _apply(fig, title, height=500)


def estimated_vs_actual(df: pd.DataFrame, title: str = "Estimated vs Actual Delivery") -> go.Figure:
    sample = (
        df[df["order_status"] == "delivered"]
        .dropna(subset=["estimated_days", "actual_days"])
        .sample(min(4000, len(df)), random_state=42)
    )
    fig = go.Figure(go.Scattergl(
        x=sample["estimated_days"], y=sample["actual_days"],
        mode="markers",
        marker=dict(size=3, color=AMBER, opacity=0.3),
        name="Orders",
    ))
    lim = max(sample["estimated_days"].max(), sample["actual_days"].max())
    fig.add_trace(go.Scatter(x=[0, lim], y=[0, lim],
                             mode="lines", line=dict(color=GREEN, dash="dash", width=1.5),
                             name="On time line"))
    fig.update_xaxes(title_text="Estimated Days")
    fig.update_yaxes(title_text="Actual Days")
    return _apply(fig, title)


def sla_donut(df: pd.DataFrame, title: str = "Delivery SLA Breakdown") -> go.Figure:
    delivered = df[df["order_status"] == "delivered"].dropna(subset=["delay_days"])
    bands = {
        "On Time":       (delivered["delay_days"] == 0).sum(),
        "1-3 days late": ((delivered["delay_days"] >= 1) & (delivered["delay_days"] <= 3)).sum(),
        "4-7 days late": ((delivered["delay_days"] >= 4) & (delivered["delay_days"] <= 7)).sum(),
        "8+ days late":  (delivered["delay_days"] > 7).sum(),
    }
    fig = go.Figure(go.Pie(
        labels=list(bands.keys()), values=list(bands.values()),
        hole=0.6, marker_colors=[GREEN, YELLOW, AMBER, RED],
        textfont=dict(family="Inter, Arial, sans-serif", size=11, color=DARK),
    ))
    return _apply(fig, title, height=340)


def rfm_scatter(rfm: pd.DataFrame, title: str = "RFM - Recency vs Frequency") -> go.Figure:
    sample = rfm.sample(min(5000, len(rfm)), random_state=42)
    fig = go.Figure(go.Scattergl(
        x=sample["recency_days"], y=sample["frequency"],
        mode="markers",
        marker=dict(size=4, color=sample["total_spend"],
                    colorscale=[[0, "#FFF3B0"], [0.5, "#FFD400"], [1, "#FF5F00"]],
                    opacity=0.6,
                    colorbar=dict(title="Spend R$")),
    ))
    fig.update_xaxes(title_text="Recency (days)", autorange="reversed")
    fig.update_yaxes(title_text="Purchase Frequency")
    return _apply(fig, title)


def ltv_segment_bar(segment_df: pd.DataFrame, title: str = "LTV Segments") -> go.Figure:
    colors = {"Platinum": ORANGE, "Gold": GOLD, "Silver": YELLOW, "Bronze": "#C8A000"}
    fig = go.Figure()
    for _, row in segment_df.iterrows():
        fig.add_trace(go.Bar(
            x=[row["ltv_segment"]], y=[row["total_predicted_revenue"]],
            name=row["ltv_segment"],
            marker_color=colors.get(row["ltv_segment"], GOLD),
        ))
    fig.update_layout(barmode="group", showlegend=False)
    return _apply(fig, title)


def p_alive_histogram(predictions: pd.DataFrame,
                      title: str = "P(Alive) Distribution") -> go.Figure:
    fig = go.Figure(go.Histogram(
        x=predictions["p_alive"], nbinsx=40,
        marker_color=GOLD, marker_opacity=0.85,
    ))
    fig.add_vline(x=0.5, line_color=ORANGE, line_dash="dash",
                  annotation_text="50%", annotation_font_color=ORANGE)
    return _apply(fig, title)


def forecast_band(hist, fcast, state, category, title="") -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=hist["week_start"], y=hist["order_count"],
        name="Historical", line=dict(color=GOLD, width=2),
    ))
    if len(fcast) > 0:
        fig.add_trace(go.Scatter(
            x=fcast["forecast_date"], y=fcast["forecast_p50"],
            name="Forecast p50", line=dict(color=ORANGE, width=2, dash="dash"),
        ))
        fig.add_trace(go.Scatter(
            x=pd.concat([fcast["forecast_date"], fcast["forecast_date"].iloc[::-1]]),
            y=pd.concat([fcast["forecast_p90"], fcast["forecast_p10"].iloc[::-1]]),
            fill="toself", fillcolor=_rgba(AMBER, 0.20),
            line=dict(color="rgba(0,0,0,0)"), name="p10-p90",
        ))
    title = title or f"Demand Forecast - {state} x {category}"
    fig.update_xaxes(title_text="Week")
    fig.update_yaxes(title_text="Orders")
    return _apply(fig, title, height=400)


def review_score_bar(df: pd.DataFrame, title: str = "Review Score Distribution") -> go.Figure:
    counts = df["review_score"].value_counts().sort_index()
    colors = [RED, AMBER, YELLOW, GOLD, GREEN]
    fig = go.Figure(go.Bar(
        x=counts.index, y=counts.values,
        marker_color=colors, marker_opacity=0.9,
        text=counts.values, textposition="outside",
        textfont=dict(family="Inter, Arial, sans-serif", size=10, color=DARK),
    ))
    fig.update_xaxes(title_text="Score", tickvals=[1, 2, 3, 4, 5])
    return _apply(fig, title, height=320)
