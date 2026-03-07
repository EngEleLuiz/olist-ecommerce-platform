"""ML Predictions — live delivery delay prediction for individual orders."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from app import get_loader, render_sidebar

render_sidebar()

st.markdown("# 🤖 ML Predictions")
st.markdown("<p style='color:#4e6278;margin-top:-8px;'>Live delivery delay prediction — enter an order and get an instant risk score</p>",
            unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

loader = get_loader()
df     = loader.order_features()

# ── Model status ──────────────────────────────────────────────────────────────
col_status = st.columns(3)
for col, (name, desc) in zip(col_status, [
    ("Delivery Delay", "XGBoost · AUC ~0.78"),
    ("Customer LTV",   "BG/NBD + Gamma-Gamma"),
    ("Demand Forecast","LightGBM · 4-week"),
]):
    with col:
        st.markdown(f"""
        <div class="metric-card">
          <div class="metric-label">{name}</div>
          <div class="metric-value" style="font-size:1rem; color:#00e676;">● READY</div>
          <div class="metric-delta flat">{desc}</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Live delay prediction form ─────────────────────────────────────────────────
st.markdown("## Delivery Delay Risk — Order Simulator")
st.markdown("<p style='color:#4e6278;'>Simulate an order and get real-time delay probability from the XGBoost model.</p>",
            unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

col_l, col_r = st.columns([1, 1])

with col_l:
    st.markdown('<div class="section-header">Order Parameters</div>', unsafe_allow_html=True)
    item_count        = st.slider("Number of items",        1, 10, 2)
    total_price       = st.slider("Order value (R$)",       20.0, 1000.0, 120.0, step=10.0)
    total_freight     = st.slider("Freight value (R$)",     5.0, 150.0, 25.0, step=5.0)
    estimated_days    = st.slider("Estimated delivery days",5, 40, 15)
    max_installments  = st.slider("Payment installments",   1, 12, 1)
    purchase_month    = st.selectbox("Purchase month", list(range(1, 13)),
                                      format_func=lambda x: [
                                          "Jan","Feb","Mar","Apr","May","Jun",
                                          "Jul","Aug","Sep","Oct","Nov","Dec"][x-1])
    purchase_hour     = st.slider("Purchase hour", 0, 23, 14)
    purchase_dow      = st.selectbox("Day of week",
                                      [0,1,2,3,4,5,6],
                                      format_func=lambda x: ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][x])

with col_r:
    st.markdown('<div class="section-header">Order Context</div>', unsafe_allow_html=True)

    states = sorted(df["customer_state"].dropna().unique().tolist())
    customer_state = st.selectbox("Customer state", states,
                                   index=states.index("SP") if "SP" in states else 0)

    regions = {"SP":"Sudeste","RJ":"Sudeste","MG":"Sudeste","ES":"Sudeste",
               "RS":"Sul","PR":"Sul","SC":"Sul","BA":"Nordeste","PE":"Nordeste",
               "CE":"Nordeste","AM":"Norte","PA":"Norte","DF":"Centro-Oeste"}
    customer_region = regions.get(customer_state, "Sudeste")

    cats = sorted(df["main_category"].dropna().unique().tolist())
    main_category = st.selectbox("Product category", cats)

    payment_types = ["credit_card", "boleto", "voucher", "debit_card"]
    main_payment_type = st.selectbox("Payment type", payment_types)

    distinct_sellers   = st.slider("Distinct sellers", 1, 5, 1)
    avg_product_weight = st.slider("Avg product weight (g)", 50, 5000, 500, step=50)

    st.markdown("<br>", unsafe_allow_html=True)
    predict_btn = st.button("▶  Predict Delay Risk", type="primary", use_container_width=True)

# ── Prediction result ─────────────────────────────────────────────────────────
if predict_btn:
    freight_ratio     = total_freight / total_price if total_price > 0 else 0
    is_peak_season    = 1 if purchase_month in [11, 12] else 0
    is_weekend        = 1 if purchase_dow in [5, 6] else 0

    # State-level avg late rate from data
    state_lr = (
        df[df["customer_state"] == customer_state]["is_late"].mean()
        if customer_state in df["customer_state"].values else 0.1
    )

    order_df = pd.DataFrame([{
        "order_id":                "simulated",
        "order_purchase_timestamp": pd.Timestamp.now(),
        "order_status":            "delivered",
        "purchase_month":          purchase_month,
        "purchase_dow":            purchase_dow,
        "purchase_hour":           purchase_hour,
        "item_count":              item_count,
        "total_price":             total_price,
        "total_freight":           total_freight,
        "freight_ratio":           freight_ratio,
        "max_installments":        max_installments,
        "estimated_days":          estimated_days,
        "distinct_sellers":        distinct_sellers,
        "avg_product_weight_g":    avg_product_weight,
        "is_peak_season":          is_peak_season,
        "is_weekend_purchase":     is_weekend,
        "state_seller_late_rate":  state_lr,
        "main_category":           main_category,
        "main_payment_type":       main_payment_type,
        "customer_state":          customer_state,
        "customer_region":         customer_region,
        "is_late":                 0,
    }])

    with st.spinner("Running model…"):
        from ml.delivery_delay_model import DeliveryDelayModel
        model = DeliveryDelayModel(n_trials=15)
        model.train(df[df["order_status"] == "delivered"].dropna(subset=["is_late"]))
        result = model.predict(order_df)

    prob   = float(result["delay_probability"].iloc[0])
    is_late_pred = int(result["predicted_late"].iloc[0])

    st.markdown("---")
    st.markdown("## Prediction Result")

    risk_color = "#ff4444" if prob > 0.5 else "#ffab40" if prob > 0.25 else "#00e676"
    risk_label = "HIGH RISK" if prob > 0.5 else "MEDIUM RISK" if prob > 0.25 else "LOW RISK"

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""
        <div class="metric-card">
          <div class="metric-label">Delay Probability</div>
          <div class="metric-value" style="color:{risk_color}; font-size:2.5rem;">{prob:.1%}</div>
          <div class="metric-delta" style="color:{risk_color};">● {risk_label}</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="metric-card">
          <div class="metric-label">Prediction</div>
          <div class="metric-value" style="font-size:1.5rem;">
            {'⚠ LATE' if is_late_pred else '✓ ON TIME'}
          </div>
          <div class="metric-delta flat">Threshold: {model.threshold:.2f}</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="metric-card">
          <div class="metric-label">Freight Ratio</div>
          <div class="metric-value" style="font-size:1.5rem;">{freight_ratio:.1%}</div>
          <div class="metric-delta flat">R$ {total_freight:.0f} / R$ {total_price:.0f}</div>
        </div>
        """, unsafe_allow_html=True)

    # Gauge chart
    st.markdown("<br>", unsafe_allow_html=True)
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=prob * 100,
        number={"suffix": "%", "font": {"family": "Space Mono", "color": risk_color, "size": 32}},
        gauge={
            "axis":    {"range": [0, 100], "tickcolor": "#4e6278",
                        "tickfont": {"family": "Space Mono", "size": 9}},
            "bar":     {"color": risk_color, "thickness": 0.25},
            "bgcolor": "#0f1923",
            "bordercolor": "#1e2d3d",
            "steps": [
                {"range": [0, 25],  "color": "#00e67615"},
                {"range": [25, 50], "color": "#ffab4015"},
                {"range": [50, 100],"color": "#ff444415"},
            ],
            "threshold": {"line": {"color": risk_color, "width": 3},
                          "thickness": 0.8, "value": prob * 100},
        },
        title={"text": "Delay Risk Score", "font": {"family": "Space Mono",
                                                      "color": "#4e6278", "size": 12}},
    ))
    fig_gauge.update_layout(
        paper_bgcolor="#0f1923", font=dict(color="#4e6278"),
        height=300, margin=dict(t=30, b=0, l=30, r=30),
    )
    st.plotly_chart(fig_gauge, use_container_width=True)

    # Top features
    st.markdown('<div class="section-header">Top Delay Risk Factors</div>',
                unsafe_allow_html=True)
    top_feat = model.top_features(n=8)
    fig_feat = go.Figure(go.Bar(
        x=top_feat["importance"], y=top_feat["feature"],
        orientation="h", marker_color=risk_color, marker_opacity=0.8,
    ))
    fig_feat.update_layout(
        paper_bgcolor="#0f1923", plot_bgcolor="#0f1923",
        font=dict(family="Space Mono", color="#4e6278", size=10),
        margin=dict(t=10,b=20,l=10,r=10), height=300,
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=False, categoryorder="total ascending"),
    )
    st.plotly_chart(fig_feat, use_container_width=True)
