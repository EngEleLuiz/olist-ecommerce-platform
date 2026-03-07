"""Delivery Performance — late rates, delay analysis, SLA breakdown."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
from app import get_loader, render_sidebar
from dashboard.charts import (
    delay_histogram, late_rate_by_state, estimated_vs_actual, sla_donut,
)

render_sidebar()

st.markdown("# 🚚 Delivery Performance")
st.markdown("<p style='color:#4e6278;margin-top:-8px;'>On-time rates, delay patterns and SLA compliance</p>",
            unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

loader   = get_loader()
df       = loader.order_features()
delivered= df[df["order_status"] == "delivered"].dropna(subset=["delay_days"])

# ── KPIs ──────────────────────────────────────────────────────────────────────
late_rate    = delivered["is_late"].mean()
avg_delay    = delivered["delay_days"].mean()
median_delay = delivered["delay_days"].median()
on_time_pct  = 1 - late_rate
p95_delay    = delivered["delay_days"].quantile(0.95)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("On-Time Rate",     f"{on_time_pct:.1%}")
c2.metric("Late Rate",        f"{late_rate:.1%}")
c3.metric("Avg Delay",        f"{avg_delay:.1f} days")
c4.metric("Median Delay",     f"{median_delay:.1f} days")
c5.metric("P95 Delay",        f"{p95_delay:.0f} days")

st.markdown("<br>", unsafe_allow_html=True)

# ── Top row charts ─────────────────────────────────────────────────────────────
col_l, col_r = st.columns(2)
with col_l:
    st.plotly_chart(delay_histogram(df), use_container_width=True)
with col_r:
    st.plotly_chart(sla_donut(df), use_container_width=True)

# ── Geography ─────────────────────────────────────────────────────────────────
st.markdown("---")
col_a, col_b = st.columns(2)
with col_a:
    st.plotly_chart(late_rate_by_state(df), use_container_width=True)
with col_b:
    st.plotly_chart(estimated_vs_actual(df), use_container_width=True)

# ── Filters — drill-down by state / category ─────────────────────────────────
st.markdown("---")
st.markdown('<div class="section-header">Drill-Down</div>', unsafe_allow_html=True)

col_f1, col_f2 = st.columns(2)
with col_f1:
    states = ["All"] + sorted(df["customer_state"].dropna().unique().tolist())
    sel_state = st.selectbox("Filter by State", states)
with col_f2:
    cats = ["All"] + sorted(df["main_category"].dropna().unique().tolist())
    sel_cat = st.selectbox("Filter by Category", cats)

filtered = delivered.copy()
if sel_state != "All":
    filtered = filtered[filtered["customer_state"] == sel_state]
if sel_cat != "All":
    filtered = filtered[filtered["main_category"] == sel_cat]

if len(filtered) == 0:
    st.warning("No data for selected filters.")
else:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Orders",        f"{len(filtered):,}")
    m2.metric("Late Rate",     f"{filtered['is_late'].mean():.1%}")
    m3.metric("Avg Delay",     f"{filtered['delay_days'].mean():.1f}d")
    m4.metric("Avg Review",    f"{filtered['review_score'].mean():.2f} ⭐")

    # Monthly trend for selection
    import plotly.graph_objects as go
    monthly_late = (
        filtered.groupby("purchase_ym")
        .agg(late_rate=("is_late","mean"), orders=("order_id","count"))
        .reset_index()
    )
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=monthly_late["purchase_ym"], y=monthly_late["late_rate"] * 100,
        mode="lines+markers", line=dict(color="#ffab40", width=2),
        name="Late Rate %",
    ))
    fig.update_layout(
        title=f"Monthly Late Rate — {sel_state} / {sel_cat}",
        paper_bgcolor="#0f1923", plot_bgcolor="#0f1923",
        font=dict(family="Space Mono", color="#4e6278", size=10),
        margin=dict(t=40,b=20,l=10,r=10), height=300,
        xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor="#1e2d3d"),
    )
    fig.add_hline(y=filtered["is_late"].mean() * 100,
                  line_dash="dash", line_color="#40c4ff",
                  annotation_text=f"Avg {filtered['is_late'].mean():.1%}",
                  annotation_font_color="#40c4ff")
    st.plotly_chart(fig, use_container_width=True)
