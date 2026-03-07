"""Demand Forecast — LightGBM weekly forecast by state and category."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
from app import get_loader, render_sidebar
from dashboard.charts import forecast_band

render_sidebar()

st.markdown("# 📈 Demand Forecast")
st.markdown("<p style='color:#4e6278;margin-top:-8px;'>LightGBM 4-week-ahead forecast with p10/p50/p90 uncertainty bands</p>",
            unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

loader = get_loader()
demand = loader.demand_series()

# ── National overview ─────────────────────────────────────────────────────────
national = demand.groupby("week_start")["order_count"].sum().reset_index()
peak_week = national.loc[national["order_count"].idxmax()]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Weeks",      f"{demand['week_start'].nunique()}")
c2.metric("States × Cats",    f"{demand.groupby(['customer_state','category']).ngroups:,}")
c3.metric("Peak Week",        str(peak_week["week_start"].date()))
c4.metric("Peak Orders",      f"{peak_week['order_count']:,.0f}")

st.markdown("<br>", unsafe_allow_html=True)

# ── National volume chart ─────────────────────────────────────────────────────
import plotly.graph_objects as go

fig_national = go.Figure()
fig_national.add_trace(go.Scatter(
    x=national["week_start"], y=national["order_count"],
    fill="tozeroy", fillcolor="#40c4ff18",
    line=dict(color="#40c4ff", width=1.5), name="Weekly Orders",
))
fig_national.update_layout(
    title="National Weekly Order Volume",
    paper_bgcolor="#0f1923", plot_bgcolor="#0f1923",
    font=dict(family="Space Mono", color="#4e6278", size=10),
    margin=dict(t=40,b=20,l=10,r=10), height=300,
    xaxis=dict(showgrid=False),
    yaxis=dict(showgrid=True, gridcolor="#1e2d3d"),
)
st.plotly_chart(fig_national, use_container_width=True)

# ── Forecast section ──────────────────────────────────────────────────────────
st.markdown("---")
st.markdown('<div class="section-header">4-Week Forecast</div>', unsafe_allow_html=True)

col_f1, col_f2 = st.columns(2)
with col_f1:
    states = sorted(demand["customer_state"].unique().tolist())
    sel_state = st.selectbox("State", states, index=states.index("SP") if "SP" in states else 0)
with col_f2:
    cats = sorted(demand["category"].unique().tolist())
    sel_cat = st.selectbox("Category", cats,
                            index=cats.index("health_beauty") if "health_beauty" in cats else 0)

run_forecast = st.button("▶  Run Forecast", type="primary")

if run_forecast or "forecast_results" in st.session_state:
    if run_forecast:
        with st.spinner("Training LightGBM… (~60 seconds)"):
            from ml.demand_forecast_model import DemandForecastModel
            import mlflow
            mlflow.set_tracking_uri("http://localhost:5000")
            mlflow.set_experiment("olist/demand-forecast")
            model = DemandForecastModel(forecast_horizon=4, n_splits=5)
            forecast = model.train_and_forecast(demand)
            st.session_state["forecast_results"] = forecast
            st.session_state["forecast_model"]   = model
        st.success("Forecast complete ✓")

    forecast = st.session_state["forecast_results"]
    model    = st.session_state["forecast_model"]

    hist  = demand[(demand["customer_state"] == sel_state) & (demand["category"] == sel_cat)]
    fcast = forecast[(forecast["customer_state"] == sel_state) & (forecast["category"] == sel_cat)]

    if len(hist) == 0:
        st.warning(f"No historical data for {sel_state} × {sel_cat}")
    else:
        st.plotly_chart(
            forecast_band(hist, fcast, sel_state, sel_cat),
            use_container_width=True,
        )

        if len(fcast) > 0:
            st.markdown('<div class="section-header">Forecast Values</div>',
                        unsafe_allow_html=True)
            fcast_display = fcast[["forecast_date","forecast_week",
                                    "forecast_p10","forecast_p50","forecast_p90"]].copy()
            for col in ["forecast_p10","forecast_p50","forecast_p90"]:
                fcast_display[col] = fcast_display[col].round(0).astype(int)
            st.dataframe(fcast_display.rename(columns={
                "forecast_date":"Date","forecast_week":"Week",
                "forecast_p10":"P10","forecast_p50":"P50 (median)","forecast_p90":"P90",
            }), hide_index=True, use_container_width=True)

    # Feature importance
    st.markdown("---")
    st.markdown('<div class="section-header">Feature Importance (p50 model)</div>',
                unsafe_allow_html=True)
    imp = model.top_features(quantile="p50", n=12)
    fig_imp = go.Figure(go.Bar(
        x=imp["importance"], y=imp["feature"], orientation="h",
        marker_color="#40c4ff", marker_opacity=0.8,
    ))
    fig_imp.update_layout(
        paper_bgcolor="#0f1923", plot_bgcolor="#0f1923",
        font=dict(family="Space Mono", color="#4e6278", size=10),
        margin=dict(t=20,b=20,l=10,r=10), height=380,
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=False, categoryorder="total ascending"),
    )
    st.plotly_chart(fig_imp, use_container_width=True)

else:
    st.info("Click **▶ Run Forecast** to generate the 4-week-ahead forecast. Takes ~60 seconds.")
