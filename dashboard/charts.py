"""Shared Plotly chart builders for the Olist dashboard.

All charts share DARK_LAYOUT so the visual language is consistent
across every page. Import the builder you need, call it, pass the
result to st.plotly_chart().
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── Shared layout ─────────────────────────────────────────────────────────────
DARK = dict(
    paper_bgcolor="#0f1923",
    plot_bgcolor="#0f1923",
    font=dict(family="Space Mono", color="#4e6278", size=10),
    xaxis=dict(showgrid=False, color="#4e6278", linecolor="#1e2d3d"),
    yaxis=dict(showgrid=True, gridcolor="#1e2d3d", color="#4e6278"),
    margin=dict(t=48, b=20, l=10, r=10),
    legend=dict(bgcolor="#0f1923", bordercolor="#1e2d3d", borderwidth=1,
                font=dict(size=10, color="#4e6278")),
    coloraxis_colorbar=dict(tickfont=dict(color="#4e6278"), title=dict(font=dict(color="#4e6278"))),
)

BLUE   = "#40c4ff"
GREEN  = "#00e676"
RED    = "#ff4444"
AMBER  = "#ffab40"
GOLD   = "#ffd740"
PURPLE = "#b388ff"

PALETTE = [BLUE, GREEN, AMBER, RED, GOLD, PURPLE,
           "#80deea", "#a5d6a7", "#ffe082", "#ef9a9a"]


def _apply(fig: go.Figure, title: str = "", height: int = 380) -> go.Figure:
    fig.update_layout(**DARK, title=dict(text=title, font=dict(size=12, color="#cdd6e0")),
                      height=height)
    return fig


# ── Volume ────────────────────────────────────────────────────────────────────

def monthly_volume_bar(df: pd.DataFrame, title: str = "Monthly Order Volume") -> go.Figure:
    monthly = (
        df.groupby("purchase_ym")
        .agg(orders=("order_id", "count"), gmv=("payment_value", "sum"))
        .reset_index()
    )
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.6, 0.4], vertical_spacing=0.04)
    fig.add_trace(go.Bar(x=monthly["purchase_ym"], y=monthly["orders"],
                         marker_color=BLUE, marker_opacity=0.85, name="Orders"), row=1, col=1)
    fig.add_trace(go.Scatter(x=monthly["purchase_ym"], y=monthly["gmv"],
                             fill="tozeroy", fillcolor=f"{GREEN}22",
                             line=dict(color=GREEN, width=1.5), name="GMV"), row=2, col=1)
    fig = _apply(fig, title, height=420)
    fig.update_yaxes(showgrid=True, gridcolor="#1e2d3d")
    return fig


def state_bar(df: pd.DataFrame, metric: str = "gmv",
              title: str = "GMV by State", top_n: int = 15) -> go.Figure:
    agg = (
        df.groupby("customer_state")[metric].sum()
        .sort_values(ascending=True).tail(top_n)
    )
    color = [BLUE] * (len(agg) - 1) + [GOLD]
    fig = go.Figure(go.Bar(
        x=agg.values, y=agg.index, orientation="h",
        marker_color=color, marker_opacity=0.85,
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
        color="orders", color_continuous_scale="Blues",
    )
    fig.update_traces(textfont=dict(family="Space Mono", size=10),
                      marker=dict(cornerradius=4))
    return _apply(fig, title, height=420)


# ── Delivery ──────────────────────────────────────────────────────────────────

def delay_histogram(df: pd.DataFrame, title: str = "Delivery Delay Distribution") -> go.Figure:
    delivered = df[df["order_status"] == "delivered"].dropna(subset=["delay_days"])
    fig = go.Figure(go.Histogram(
        x=delivered["delay_days"].clip(0, 30),
        nbinsx=30, marker_color=AMBER, marker_opacity=0.8,
    ))
    fig.add_vline(x=0,   line_color=GREEN, line_dash="dash",
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
    fig.add_vline(x=state_lr.mean() * 100, line_color=BLUE, line_dash="dash",
                  annotation_text=f"Avg {state_lr.mean():.1%}", annotation_font_color=BLUE)
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
        marker=dict(size=3, color=BLUE, opacity=0.3),
        name="Orders",
    ))
    lim = max(sample["estimated_days"].max(), sample["actual_days"].max())
    fig.add_trace(go.Scatter(x=[0, lim], y=[0, lim],
                             mode="lines", line=dict(color=GREEN, dash="dash", width=1),
                             name="On time line"))
    fig.update_xaxes(title_text="Estimated Days")
    fig.update_yaxes(title_text="Actual Days")
    return _apply(fig, title)


def sla_donut(df: pd.DataFrame, title: str = "Delivery SLA Breakdown") -> go.Figure:
    delivered = df[df["order_status"] == "delivered"].dropna(subset=["delay_days"])
    bands = {
        "On Time":       (delivered["delay_days"] == 0).sum(),
        "1–3 days late": ((delivered["delay_days"] >= 1) & (delivered["delay_days"] <= 3)).sum(),
        "4–7 days late": ((delivered["delay_days"] >= 4) & (delivered["delay_days"] <= 7)).sum(),
        "8+ days late":  (delivered["delay_days"] > 7).sum(),
    }
    fig = go.Figure(go.Pie(
        labels=list(bands.keys()), values=list(bands.values()),
        hole=0.6, marker_colors=[GREEN, AMBER, RED, "#880000"],
        textfont=dict(family="Space Mono", size=9),
    ))
    return _apply(fig, title, height=340)


# ── LTV & RFM ─────────────────────────────────────────────────────────────────

def rfm_scatter(rfm: pd.DataFrame, title: str = "RFM — Recency vs Frequency") -> go.Figure:
    sample = rfm.sample(min(5000, len(rfm)), random_state=42)
    fig = go.Figure(go.Scattergl(
        x=sample["recency_days"], y=sample["frequency"],
        mode="markers",
        marker=dict(size=3, color=sample["total_spend"],
                    colorscale="Blues", opacity=0.5,
                    colorbar=dict(title="Spend R$")),
    ))
    fig.update_xaxes(title_text="Recency (days)", autorange="reversed")
    fig.update_yaxes(title_text="Purchase Frequency")
    return _apply(fig, title)


def ltv_segment_bar(segment_df: pd.DataFrame,
                    title: str = "LTV Segments") -> go.Figure:
    colors = {"Platinum": GOLD, "Gold": AMBER, "Silver": BLUE, "Bronze": "#78909c"}
    fig = go.Figure()
    for _, row in segment_df.iterrows():
        fig.add_trace(go.Bar(
            x=[row["ltv_segment"]], y=[row["total_predicted_revenue"]],
            name=row["ltv_segment"],
            marker_color=colors.get(row["ltv_segment"], BLUE),
        ))
    fig.update_layout(barmode="group", showlegend=False)
    return _apply(fig, title)


def p_alive_histogram(predictions: pd.DataFrame,
                      title: str = "P(Alive) Distribution") -> go.Figure:
    fig = go.Figure(go.Histogram(
        x=predictions["p_alive"], nbinsx=40,
        marker_color=GREEN, marker_opacity=0.8,
    ))
    fig.add_vline(x=0.5, line_color=AMBER, line_dash="dash",
                  annotation_text="50%", annotation_font_color=AMBER)
    return _apply(fig, title)


# ── Demand forecast ───────────────────────────────────────────────────────────

def forecast_band(
    hist: pd.DataFrame,
    fcast: pd.DataFrame,
    state: str,
    category: str,
    title: str = "",
) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=hist["week_start"], y=hist["order_count"],
        name="Historical", line=dict(color=BLUE, width=1.5),
    ))
    if len(fcast) > 0:
        fig.add_trace(go.Scatter(
            x=fcast["forecast_date"], y=fcast["forecast_p50"],
            name="Forecast p50", line=dict(color=AMBER, width=2, dash="dash"),
        ))
        fig.add_trace(go.Scatter(
            x=pd.concat([fcast["forecast_date"], fcast["forecast_date"].iloc[::-1]]),
            y=pd.concat([fcast["forecast_p90"], fcast["forecast_p10"].iloc[::-1]]),
            fill="toself", fillcolor=f"{AMBER}20",
            line=dict(color="rgba(0,0,0,0)"), name="p10–p90",
        ))
    title = title or f"Demand Forecast — {state} × {category}"
    fig.update_xaxes(title_text="Week")
    fig.update_yaxes(title_text="Orders")
    return _apply(fig, title, height=400)


def review_score_bar(df: pd.DataFrame, title: str = "Review Score Distribution") -> go.Figure:
    counts = df["review_score"].value_counts().sort_index()
    colors = [RED, RED, AMBER, BLUE, GREEN]
    fig = go.Figure(go.Bar(
        x=counts.index, y=counts.values,
        marker_color=colors, marker_opacity=0.85,
        text=counts.values, textposition="outside",
        textfont=dict(family="Space Mono", size=9, color="#cdd6e0"),
    ))
    fig.update_xaxes(title_text="Score", tickvals=[1, 2, 3, 4, 5])
    return _apply(fig, title, height=320)
