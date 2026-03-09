"""ML Predictions — Delivery delay model inference."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import plotly.graph_objects as go
import streamlit as st

from app import get_loader, html_table, render_sidebar
from dashboard.charts import AMBER, DARK, GOLD, GREEN, MUTED, ORANGE, RED, _apply

render_sidebar()

st.markdown("# 🤖 ML Predictions")
st.markdown("<p style='color:#6B5B00;margin-top:-8px;'>Delivery delay risk scoring — LightGBM classifier</p>",
            unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

loader = get_loader()
df     = loader.order_features()
deliv  = df[df["order_status"] == "delivered"].dropna(subset=["is_late"])

c1, c2, c3 = st.columns(3)
c1.metric("Training Orders", f"{len(deliv):,}")
c2.metric("Late Orders",     f"{deliv['is_late'].sum():,}")
c3.metric("Late Rate",       f"{deliv['is_late'].mean():.1%}")

st.markdown("---")
st.markdown('<div class="section-header">Delay Risk Scoring</div>', unsafe_allow_html=True)

run_model = st.button("▶  Run Delay Model", type="primary")

if run_model or "delay_predictions" in st.session_state:
    if run_model:
        with st.spinner("Training LightGBM delay classifier… (~30 seconds)"):
            from ml.delivery_delay_model import DeliveryDelayModel
            model = DeliveryDelayModel()
            preds = model.train_and_predict(deliv)
            st.session_state["delay_predictions"] = preds
            st.session_state["delay_model"]       = model
        st.success("Model trained ✓")

    preds = st.session_state["delay_predictions"]
    model = st.session_state["delay_model"]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("AUC-ROC",          f"{model.metrics.get('auc_roc', 0):.3f}")
    m2.metric("Precision",        f"{model.metrics.get('precision', 0):.3f}")
    m3.metric("Recall",           f"{model.metrics.get('recall', 0):.3f}")
    m4.metric("High-Risk Orders", f"{(preds['delay_risk_score'] > 0.5).sum():,}")

    st.markdown("<br>", unsafe_allow_html=True)
    col_a, col_b = st.columns(2)

    with col_a:
        fig = go.Figure(go.Histogram(
            x=preds["delay_risk_score"], nbinsx=40,
            marker_color=AMBER, marker_opacity=0.85,
        ))
        fig.add_vline(x=0.5, line_color=RED, line_dash="dash",
                      annotation_text="Risk threshold 0.5",
                      annotation_font_color=RED)
        st.plotly_chart(_apply(fig, "Delay Risk Score Distribution"), use_container_width=True)

    with col_b:
        imp     = model.top_features(n=12)
        fig_imp = go.Figure(go.Bar(
            x=imp["importance"], y=imp["feature"], orientation="h",
            marker_color=GOLD, marker_opacity=0.9,
        ))
        fig_imp.update_yaxes(categoryorder="total ascending")
        st.plotly_chart(_apply(fig_imp, "Feature Importance", height=380), use_container_width=True)

    st.markdown("---")
    st.markdown('<div class="section-header">High-Risk Orders</div>', unsafe_allow_html=True)
    high_risk = (
        preds[preds["delay_risk_score"] > 0.5]
        .sort_values("delay_risk_score", ascending=False)
        .head(200)
    )
    if len(high_risk) > 0:
        cols_show = [c for c in ["order_id","customer_state","main_category",
                                  "delay_risk_score","actual_days","is_late"] if c in high_risk.columns]
        display = high_risk[cols_show].copy()
        if "delay_risk_score" in display.columns:
            display["delay_risk_score"] = display["delay_risk_score"].apply(lambda x: f"{x:.3f}")
        html_table(display, height=300)
else:
    st.info("Click **▶ Run Delay Model** to score delivery risk. Takes ~30 seconds.")
