"""Customer LTV — RFM analysis, BG/NBD predictions, segment breakdown."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
from app import get_loader, render_sidebar
from dashboard.charts import rfm_scatter, ltv_segment_bar, p_alive_histogram

render_sidebar()

st.markdown("# 💎 Customer LTV")
st.markdown(
    "<p style='color:#4e6278;margin-top:-8px;'>BG/NBD + Gamma-Gamma lifetime value predictions</p>",
    unsafe_allow_html=True,
)
st.markdown("<br>", unsafe_allow_html=True)

loader = get_loader()
rfm = loader.customer_rfm()

# ── RFM KPIs ──────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Unique Customers", f"{len(rfm):,}")
c2.metric("Repeat Buyers", f"{(rfm['frequency_repeat'] > 0).sum():,}")
c3.metric("Repeat Rate", f"{(rfm['frequency_repeat'] > 0).mean():.1%}")
c4.metric("Median Spend", f"R$ {rfm['total_spend'].median():.2f}")
c5.metric("Avg Order Value", f"R$ {rfm['monetary_mean'].mean():.2f}")

st.markdown("<br>", unsafe_allow_html=True)

# ── RFM scatter ───────────────────────────────────────────────────────────────
col_l, col_r = st.columns(2)
with col_l:
    st.plotly_chart(rfm_scatter(rfm), use_container_width=True)
with col_r:
    import plotly.graph_objects as go

    fig = go.Figure(
        go.Histogram(
            x=rfm["total_spend"].clip(0, 2000),
            nbinsx=40,
            marker_color="#b388ff",
            marker_opacity=0.8,
        )
    )
    fig.update_layout(
        title="Total Spend Distribution (clipped R$2k)",
        paper_bgcolor="#0f1923",
        plot_bgcolor="#0f1923",
        font=dict(family="Space Mono", color="#4e6278", size=10),
        margin=dict(t=40, b=20, l=10, r=10),
        height=380,
        xaxis=dict(showgrid=False, title="Total Spend (R$)"),
        yaxis=dict(showgrid=True, gridcolor="#1e2d3d"),
    )
    median_spend = rfm["total_spend"].median()
    fig.add_vline(
        x=median_spend,
        line_color="#ffab40",
        line_dash="dash",
        annotation_text=f"Median R${median_spend:.0f}",
        annotation_font_color="#ffab40",
    )
    st.plotly_chart(fig, use_container_width=True)

# ── BG/NBD predictions ────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    '<div class="section-header">BG/NBD + Gamma-Gamma Predictions</div>', unsafe_allow_html=True
)

run_model = st.button("▶  Run LTV Model", type="primary")

if run_model or "ltv_predictions" in st.session_state:
    if run_model:
        with st.spinner("Fitting BG/NBD + Gamma-Gamma… (~30 seconds)"):
            from ml.customer_ltv_model import CustomerLTVModel
            import mlflow

            mlflow.set_tracking_uri("http://localhost:5000")
            mlflow.set_experiment("olist/customer-ltv")
            model = CustomerLTVModel()
            preds = model.train_and_predict(rfm, predict_days=[90, 365])
            st.session_state["ltv_predictions"] = preds
            st.session_state["ltv_segment_summary"] = model.segment_summary(preds)
        st.success("Model trained ✓")

    preds = st.session_state["ltv_predictions"]
    seg_sum = st.session_state["ltv_segment_summary"]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Median P(Alive)", f"{preds['p_alive'].median():.1%}")
    m2.metric("Median LTV 90d", f"R$ {preds['predicted_ltv_90d'].median():.2f}")
    m3.metric("Median LTV 365d", f"R$ {preds['predicted_ltv_365d'].median():.2f}")
    m4.metric("Platinum Customers", f"{(preds['ltv_segment'] == 'Platinum').sum():,}")

    st.markdown("<br>", unsafe_allow_html=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.plotly_chart(p_alive_histogram(preds), use_container_width=True)
    with col_b:
        st.plotly_chart(ltv_segment_bar(seg_sum), use_container_width=True)

    st.markdown('<div class="section-header">Segment Summary</div>', unsafe_allow_html=True)
    seg_display = seg_sum.copy()
    seg_display["avg_ltv_365d"] = seg_display["avg_ltv_365d"].apply(lambda x: f"R$ {x:.2f}")
    seg_display["total_predicted_revenue"] = seg_display["total_predicted_revenue"].apply(
        lambda x: f"R$ {x:,.0f}"
    )
    seg_display["avg_p_alive"] = seg_display["avg_p_alive"].apply(lambda x: f"{x:.1%}")
    seg_display["avg_purchases_90d"] = seg_display["avg_purchases_90d"].apply(lambda x: f"{x:.2f}")
    st.dataframe(
        seg_display.rename(
            columns={
                "ltv_segment": "Segment",
                "customer_count": "Customers",
                "avg_p_alive": "Avg P(Alive)",
                "avg_ltv_365d": "Avg LTV 365d",
                "total_predicted_revenue": "Total Predicted Revenue",
                "avg_purchases_90d": "Avg Purchases (90d)",
            }
        ),
        hide_index=True,
        use_container_width=True,
    )
else:
    st.info(
        "Click **▶ Run LTV Model** to fit BG/NBD + Gamma-Gamma on the customer base. Takes ~30 seconds."
    )
