"""Olist E-Commerce Intelligence Dashboard — single-page tab navigation."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="Olist Intelligence",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
OLIST_CSS = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

  html, body, [data-testid="stAppViewContainer"], section[data-testid="stMain"] {
    background-color: #FFFDF5 !important;
    color: #000000 !important;
    font-family: 'Inter', sans-serif !important;
  }

  /* Hide sidebar toggle and sidebar entirely */
  [data-testid="stSidebar"]          { display: none !important; }
  [data-testid="collapsedControl"]   { display: none !important; }

  /* ── TOP NAV BAR ─────────────────────────────────────────── */
  .olist-topbar {
    display: flex;
    align-items: center;
    background: #2D2000;
    padding: 0 28px;
    height: 56px;
    position: sticky;
    top: 0;
    z-index: 999;
    border-bottom: 3px solid #FFD400;
    margin-bottom: 24px;
    border-radius: 8px;
  }
  .olist-topbar-brand {
    font-size: 1.05rem;
    font-weight: 700;
    color: #FFD400;
    margin-right: 36px;
    white-space: nowrap;
    letter-spacing: 0.02em;
  }
  .olist-topbar-brand span {
    color: #A89000;
    font-weight: 400;
    font-size: 0.78rem;
    margin-left: 8px;
  }

  /* ── TABS ────────────────────────────────────────────────── */
  .stTabs [data-baseweb="tab-list"] {
    background: #2D2000 !important;
    border-radius: 8px 8px 0 0 !important;
    padding: 0 8px !important;
    gap: 2px !important;
    border-bottom: 3px solid #FFD400 !important;
  }
  .stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: #A89000 !important;
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    padding: 12px 20px !important;
    border-radius: 6px 6px 0 0 !important;
    border: none !important;
    white-space: nowrap !important;
    font-family: 'Inter', sans-serif !important;
  }
  .stTabs [data-baseweb="tab"]:hover {
    background: #3D2E00 !important;
    color: #FFD400 !important;
  }
  .stTabs [aria-selected="true"] {
    background: #FFD400 !important;
    color: #2D2000 !important;
    font-weight: 700 !important;
  }
  .stTabs [data-baseweb="tab-panel"] {
    background: #FFFDF5 !important;
    padding-top: 16px !important;
  }
  /* Hide default tab highlight underline */
  .stTabs [data-baseweb="tab-highlight"] { display: none !important; }
  .stTabs [data-baseweb="tab-border"]    { display: none !important; }

  /* ── METRICS ─────────────────────────────────────────────── */
  div[data-testid="stMetric"] {
    background: #FFFFFF !important;
    border: 1px solid #F0E8C8 !important;
    border-top: 3px solid #FFD400 !important;
    border-radius: 8px !important;
    padding: 16px 20px !important;
  }
  div[data-testid="stMetric"] label {
    font-size: 0.72rem !important;
    color: #6B5B00 !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600 !important;
  }
  div[data-testid="stMetric"] [data-testid="stMetricValue"] {
    font-size: 1.55rem !important;
    font-weight: 700 !important;
    color: #000000 !important;
  }

  /* ── MISC ────────────────────────────────────────────────── */
  .section-header {
    font-size: 0.72rem;
    color: #6B5B00;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-weight: 700;
    border-bottom: 2px solid #FFD400;
    padding-bottom: 6px;
    margin-bottom: 16px;
  }
  h1, h2, h3 {
    font-family: 'Inter', sans-serif !important;
    color: #000000 !important;
    font-weight: 700 !important;
  }
  .stPlotlyChart {
    border: 1px solid #F0E8C8 !important;
    border-radius: 8px !important;
  }
  #MainMenu, footer, header { visibility: hidden; }
  .block-container { padding-top: 1rem !important; max-width: 1200px !important; }
</style>
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner="Carregando dados Olist…")
def get_loader():
    from data_loader import OlistLoader
    return OlistLoader()


def html_table(df, height: int = 400) -> None:
    """Render a DataFrame as a gold-palette HTML table."""
    thead_bg = "#2D2000"
    thead_fg = "#FFD400"
    row_even  = "#FFFFFF"
    row_odd   = "#FFFDF5"
    border    = "#F0E8C8"

    cols = "".join(
        f"<th style='padding:8px 14px;text-align:left;font-size:0.78rem;"
        f"letter-spacing:0.06em;text-transform:uppercase;white-space:nowrap;"
        f"color:{thead_fg};'>{c}</th>"
        for c in df.columns
    )
    rows = ""
    for i, (_, row) in enumerate(df.iterrows()):
        bg = row_even if i % 2 == 0 else row_odd
        cells = "".join(
            f"<td style='padding:7px 14px;font-size:0.82rem;"
            f"border-bottom:1px solid {border};white-space:nowrap;"
            f"color:#000000;'>{v}</td>"
            for v in row.values
        )
        rows += f"<tr style='background:{bg};'>{cells}</tr>"

    html = f"""
    <div style='overflow:auto;max-height:{height}px;border:1px solid {border};border-radius:8px;'>
      <table style='border-collapse:collapse;width:100%;font-family:Inter,Arial,sans-serif;'>
        <thead>
          <tr style='background:{thead_bg};position:sticky;top:0;z-index:1;'>{cols}</tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>"""
    st.markdown(html, unsafe_allow_html=True)


def inject_css():
    st.markdown(OLIST_CSS, unsafe_allow_html=True)


# ── Top brand bar ─────────────────────────────────────────────────────────────

def render_topbar():
    inject_css()
    use_duckdb = os.getenv("USE_DUCKDB", "true").lower() == "true"
    badge = "● Local CSV" if use_duckdb else "● Redshift Live"
    st.markdown(f"""
    <div class="olist-topbar">
      <div class="olist-topbar-brand">
        🛒 Olist Intelligence <span>Brazilian E-Commerce Analytics</span>
      </div>
      <div style="margin-left:auto;font-size:0.72rem;background:#FFF3B0;
                  color:#6B5B00;padding:3px 12px;border-radius:12px;
                  border:1px solid #FFD400;font-weight:600;">{badge}</div>
    </div>
    """, unsafe_allow_html=True)


# ── Page renderers ────────────────────────────────────────────────────────────

def page_home(loader):
    import plotly.graph_objects as go
    df = loader.order_features()

    st.markdown("## 🏠 Olist E-Commerce Intelligence")
    st.markdown("<p style='color:#6B5B00;margin-top:-8px;'>Análise de mercado brasileiro — 100k pedidos reais · 27 estados · 3 modelos ML</p>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    delivered = df[df["order_status"] == "delivered"]
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Pedidos",    f"{len(df):,}")
    c2.metric("GMV",              f"R$ {df['payment_value'].sum():,.0f}")
    c3.metric("Ticket Médio",     f"R$ {df['payment_value'].mean():.2f}")
    c4.metric("Taxa de Atraso",   f"{(delivered['is_late']==1).mean():.1%}")
    c5.metric("Review Médio",     f"{df['review_score'].mean():.2f} ⭐")

    st.markdown("<br>", unsafe_allow_html=True)
    col_l, col_r = st.columns([3, 2])
    with col_l:
        monthly = (df.groupby("purchase_ym")
                   .agg(orders=("order_id","count"), gmv=("payment_value","sum"))
                   .reset_index())
        fig = go.Figure(go.Bar(x=monthly["purchase_ym"], y=monthly["orders"],
                               marker_color="#FFD400", marker_opacity=0.9, name="Pedidos"))
        fig.update_layout(title="Volume Mensal de Pedidos", height=300,
                          paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFDF5",
                          font=dict(family="Inter", color="#000000", size=11),
                          margin=dict(t=40,b=20,l=10,r=10),
                          xaxis=dict(showgrid=False, tickfont=dict(color="#000000")),
                          yaxis=dict(showgrid=True, gridcolor="#F0E8C8", tickfont=dict(color="#000000")))
        st.plotly_chart(fig, use_container_width=True)
    with col_r:
        st.markdown('<div class="section-header">Top Estados por GMV</div>', unsafe_allow_html=True)
        top = (df.groupby("customer_state")
               .agg(gmv=("payment_value","sum"), orders=("order_id","count"),
                    late_rate=("is_late","mean"))
               .sort_values("gmv", ascending=False).head(8).reset_index())
        top["gmv_fmt"]  = top["gmv"].apply(lambda x: f"R$ {x:,.0f}")
        top["late_fmt"] = top["late_rate"].apply(lambda x: f"{x:.1%}")
        html_table(top[["customer_state","gmv_fmt","orders","late_fmt"]].rename(
            columns={"customer_state":"Estado","gmv_fmt":"GMV","orders":"Pedidos","late_fmt":"Atraso"}
        ), height=280)


def page_market(loader):
    from dashboard.charts import monthly_volume_bar, state_bar, category_treemap, review_score_bar
    df = loader.order_features()

    st.markdown("## 📊 Market Overview")
    st.markdown("<p style='color:#6B5B00;margin-top:-8px;'>Receita, volume e distribuição geográfica</p>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("GMV Total",        f"R$ {df['payment_value'].sum():,.0f}")
    c2.metric("Total Pedidos",    f"{len(df):,}")
    c3.metric("Ticket Médio",     f"R$ {df['payment_value'].mean():.2f}")
    c4.metric("Clientes Únicos",  f"{df['customer_unique_id'].nunique():,}")
    c5.metric("Estados Ativos",   f"{df['customer_state'].nunique()}")

    st.markdown("<br>", unsafe_allow_html=True)
    st.plotly_chart(monthly_volume_bar(df), use_container_width=True)

    col_l, col_r = st.columns(2)
    with col_l:
        metric = st.selectbox("Métrica por Estado", ["gmv","order_count"],
                              format_func=lambda x: {"gmv":"GMV","order_count":"Pedidos"}[x])
        st.plotly_chart(state_bar(df, metric=metric,
                                   title=f"{'GMV' if metric=='gmv' else 'Pedidos'} por Estado"),
                        use_container_width=True)
    with col_r:
        st.plotly_chart(category_treemap(df), use_container_width=True)

    st.markdown("---")
    state_df = (df.groupby("customer_state")
                .agg(gmv=("payment_value","sum"), orders=("order_id","count"),
                     late_rate=("is_late","mean"), avg_review=("review_score","mean"))
                .sort_values("gmv", ascending=False).reset_index())
    state_df["gmv_share"] = (state_df["gmv"]/state_df["gmv"].sum()*100).round(1)
    state_df["gmv"]       = state_df["gmv"].apply(lambda x: f"R$ {x:,.0f}")
    state_df["late_rate"] = state_df["late_rate"].apply(lambda x: f"{x:.1%}")
    state_df["avg_review"]= state_df["avg_review"].apply(lambda x: f"{x:.2f} ⭐")
    state_df["gmv_share"] = state_df["gmv_share"].apply(lambda x: f"{x}%")
    html_table(state_df.rename(columns={"customer_state":"Estado","gmv":"GMV",
               "orders":"Pedidos","late_rate":"Atraso","avg_review":"Review","gmv_share":"Share"}))

    col_a, col_b = st.columns([1,2])
    with col_a:
        st.plotly_chart(review_score_bar(df), use_container_width=True)
    with col_b:
        cat_df = (df.groupby("main_category")
                  .agg(gmv=("payment_value","sum"), orders=("order_id","count"),
                       late_rate=("is_late","mean"), avg_review=("review_score","mean"))
                  .sort_values("gmv", ascending=False).head(15).reset_index())
        cat_df["gmv"]       = cat_df["gmv"].apply(lambda x: f"R$ {x:,.0f}")
        cat_df["late_rate"] = cat_df["late_rate"].apply(lambda x: f"{x:.1%}")
        cat_df["avg_review"]= cat_df["avg_review"].apply(lambda x: f"{x:.2f}")
        html_table(cat_df.rename(columns={"main_category":"Categoria","gmv":"GMV",
                   "orders":"Pedidos","late_rate":"Atraso","avg_review":"Review"}), height=350)


def page_delivery(loader):
    from dashboard.charts import delay_histogram, estimated_vs_actual, late_rate_by_state, sla_donut
    df = loader.order_features()
    deliv = df[df["order_status"] == "delivered"]

    st.markdown("## 🚚 Delivery Performance")
    st.markdown("<p style='color:#6B5B00;margin-top:-8px;'>SLA, distribuição de atrasos e análise por estado</p>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    on_time = (deliv["is_late"]==0).mean()
    late    = (deliv["is_late"]==1).mean()
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Pedidos Entregues", f"{len(deliv):,}")
    c2.metric("No Prazo",          f"{on_time:.1%}")
    c3.metric("Taxa de Atraso",    f"{late:.1%}")
    c4.metric("Atraso Médio",      f"{deliv['delay_days'].mean():.1f} dias")
    c5.metric("Entrega Média",     f"{deliv['actual_days'].mean():.1f} dias")

    st.markdown("<br>", unsafe_allow_html=True)
    col_l, col_r = st.columns(2)
    with col_l:
        st.plotly_chart(delay_histogram(df), use_container_width=True)
    with col_r:
        st.plotly_chart(sla_donut(df), use_container_width=True)
    st.plotly_chart(late_rate_by_state(df), use_container_width=True)
    st.plotly_chart(estimated_vs_actual(df), use_container_width=True)


def page_ltv(loader):
    import plotly.graph_objects as go
    import numpy as np
    from dashboard.charts import AMBER, DARK, GOLD, ORANGE, _apply, _rgba, ltv_segment_bar, p_alive_histogram, rfm_scatter

    rfm = loader.customer_rfm()

    st.markdown("## 💎 Customer LTV")
    st.markdown("<p style='color:#6B5B00;margin-top:-8px;'>BG/NBD + Gamma-Gamma lifetime value predictions</p>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Clientes Únicos",  f"{len(rfm):,}")
    c2.metric("Compradores Recorrentes", f"{(rfm['frequency_repeat']>0).sum():,}")
    c3.metric("Taxa de Recompra", f"{(rfm['frequency_repeat']>0).mean():.1%}")
    c4.metric("Gasto Mediano",    f"R$ {rfm['total_spend'].median():.2f}")
    c5.metric("Ticket Médio",     f"R$ {rfm['monetary_mean'].mean():.2f}")

    st.markdown("<br>", unsafe_allow_html=True)
    col_l, col_r = st.columns(2)
    with col_l:
        st.plotly_chart(rfm_scatter(rfm), use_container_width=True)
    with col_r:
        fig = go.Figure(go.Histogram(x=rfm["total_spend"].clip(0,2000), nbinsx=40,
                                      marker_color=AMBER, marker_opacity=0.85))
        med = rfm["total_spend"].median()
        fig.add_vline(x=med, line_color=ORANGE, line_dash="dash",
                      annotation_text=f"Mediana R${med:.0f}", annotation_font_color=ORANGE)
        fig.update_xaxes(title_text="Gasto Total (R$)", tickfont=dict(color="#000000"))
        fig.update_yaxes(tickfont=dict(color="#000000"))
        st.plotly_chart(_apply(fig, "Distribuição de Gasto Total"), use_container_width=True)

    st.markdown("---")
    st.markdown('<div class="section-header">BG/NBD + Gamma-Gamma Predictions</div>', unsafe_allow_html=True)
    run_model = st.button("▶  Run LTV Model", type="primary")

    if run_model or "ltv_predictions" in st.session_state:
        if run_model:
            with st.spinner("Fitting BG/NBD + Gamma-Gamma… (~30 seconds)"):
                try:
                    from ml.customer_ltv_model import CustomerLTVModel
                    # Hard cap at 2000 rows — protects 1GB RAM on t3.micro
                    rfm_fit = rfm[rfm["frequency_repeat"] > 0].head(2000).copy()
                    if len(rfm_fit) < 10:
                        st.error("Not enough repeat buyers to fit model.")
                        st.stop()
                    model = CustomerLTVModel()
                    preds = model.train_and_predict(rfm_fit, predict_days=[90, 365])
                    st.session_state["ltv_predictions"]     = preds
                    st.session_state["ltv_segment_summary"] = model.segment_summary(preds)
                    st.success("Model trained ✓")
                except MemoryError:
                    st.error("Out of memory. The server has 1GB RAM — try again after a few seconds.")
                    st.stop()
                except Exception as e:
                    st.error(f"Model error: {e}")
                    st.stop()

        preds   = st.session_state["ltv_predictions"]
        seg_sum = st.session_state["ltv_segment_summary"]

        m1,m2,m3,m4 = st.columns(4)
        m1.metric("P(Alive) Mediana",   f"{preds['p_alive'].median():.1%}")
        m2.metric("LTV Mediano 90d",    f"R$ {preds['predicted_ltv_90d'].median():.2f}")
        m3.metric("LTV Mediano 365d",   f"R$ {preds['predicted_ltv_365d'].median():.2f}")
        m4.metric("Clientes Platinum",  f"{(preds['ltv_segment']=='Platinum').sum():,}")

        st.markdown("<br>", unsafe_allow_html=True)
        col_a, col_b = st.columns(2)
        with col_a:
            st.plotly_chart(p_alive_histogram(preds), use_container_width=True)
        with col_b:
            st.plotly_chart(ltv_segment_bar(seg_sum), use_container_width=True)

        seg_d = seg_sum.copy()
        seg_d["avg_ltv_365d"]            = seg_d["avg_ltv_365d"].apply(lambda x: f"R$ {x:.2f}")
        seg_d["total_predicted_revenue"] = seg_d["total_predicted_revenue"].apply(lambda x: f"R$ {x:,.0f}")
        seg_d["avg_p_alive"]             = seg_d["avg_p_alive"].apply(lambda x: f"{x:.1%}")
        seg_d["avg_purchases_90d"]       = seg_d["avg_purchases_90d"].apply(lambda x: f"{x:.2f}")
        html_table(seg_d.rename(columns={"ltv_segment":"Segmento","customer_count":"Clientes",
            "avg_p_alive":"P(Alive) Médio","avg_ltv_365d":"LTV Médio 365d",
            "total_predicted_revenue":"Receita Prevista","avg_purchases_90d":"Compras (90d)"}))
    else:
        st.info("Clique em **▶ Run LTV Model** para ajustar o BG/NBD + Gamma-Gamma. ~30 segundos.")


def page_forecast(loader):
    import plotly.graph_objects as go
    from dashboard.charts import GOLD, AMBER, _apply, _rgba, forecast_band

    demand = loader.demand_series()
    national  = demand.groupby("week_start")["order_count"].sum().reset_index()
    peak_week = national.loc[national["order_count"].idxmax()]

    st.markdown("## 📈 Demand Forecast")
    st.markdown("<p style='color:#6B5B00;margin-top:-8px;'>LightGBM 4 semanas à frente com bandas p10/p50/p90</p>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Semanas",       f"{demand['week_start'].nunique()}")
    c2.metric("Estados×Cats",  f"{demand.groupby(['customer_state','category']).ngroups:,}")
    c3.metric("Semana Pico",   str(peak_week["week_start"].date()))
    c4.metric("Pico Pedidos",  f"{peak_week['order_count']:,.0f}")

    st.markdown("<br>", unsafe_allow_html=True)
    fig_nat = go.Figure()
    fig_nat.add_trace(go.Scatter(x=national["week_start"], y=national["order_count"],
                                  fill="tozeroy", fillcolor=_rgba(AMBER,0.15),
                                  line=dict(color=GOLD,width=2), name="Pedidos Semanais"))
    fig_nat.update_xaxes(title_text="Semana", tickfont=dict(color="#000000"))
    fig_nat.update_yaxes(title_text="Pedidos", tickfont=dict(color="#000000"))
    st.plotly_chart(_apply(fig_nat, "Volume Nacional Semanal", height=300), use_container_width=True)

    st.markdown("---")
    top_states_list = sorted(demand.groupby("customer_state")["order_count"].sum().nlargest(10).index.tolist())
    top_cats_list   = sorted(demand.groupby("category")["order_count"].sum().nlargest(10).index.tolist())
    st.info("⚡ Forecast roda sobre top 10 estados × top 10 categorias para proteger a memória do servidor (~60s)")

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        sel_state = st.selectbox("Estado", top_states_list,
                                  index=top_states_list.index("SP") if "SP" in top_states_list else 0)
    with col_f2:
        sel_cat = st.selectbox("Categoria", top_cats_list,
                                index=top_cats_list.index("health_beauty") if "health_beauty" in top_cats_list else 0)

    if st.button("▶  Run Forecast", type="primary") or "forecast_results" in st.session_state:
        if "forecast_results" not in st.session_state:
            with st.spinner("Treinando LightGBM… (~60 segundos)"):
                from ml.demand_forecast_model import DemandForecastModel
                demand_fit = demand[demand["customer_state"].isin(top_states_list) &
                                    demand["category"].isin(top_cats_list)].copy()
                model = DemandForecastModel(forecast_horizon=4, n_splits=3)
                forecast = model.train_and_forecast(demand_fit)
                st.session_state["forecast_results"] = forecast
                st.session_state["forecast_model"]   = model
            st.success("Forecast completo ✓")

        forecast = st.session_state["forecast_results"]
        model    = st.session_state["forecast_model"]
        hist     = demand[(demand["customer_state"]==sel_state) & (demand["category"]==sel_cat)]
        fcast    = forecast[(forecast["customer_state"]==sel_state) & (forecast["category"]==sel_cat)]

        if len(hist) == 0:
            st.warning(f"Sem dados históricos para {sel_state} × {sel_cat}")
        else:
            st.plotly_chart(forecast_band(hist, fcast, sel_state, sel_cat), use_container_width=True)
            if len(fcast) > 0:
                fd = fcast[["forecast_date","forecast_week","forecast_p10","forecast_p50","forecast_p90"]].copy()
                for c in ["forecast_p10","forecast_p50","forecast_p90"]:
                    fd[c] = fd[c].round(0).astype(int)
                html_table(fd.rename(columns={"forecast_date":"Data","forecast_week":"Semana",
                    "forecast_p10":"P10","forecast_p50":"P50","forecast_p90":"P90"}))

        imp = model.top_features(quantile="p50", n=12)
        fig_imp = go.Figure(go.Bar(x=imp["importance"], y=imp["feature"], orientation="h",
                                    marker_color=GOLD, marker_opacity=0.9))
        fig_imp.update_yaxes(categoryorder="total ascending", tickfont=dict(color="#000000"))
        fig_imp.update_xaxes(tickfont=dict(color="#000000"))
        st.plotly_chart(_apply(fig_imp, "Feature Importance (p50)", height=380), use_container_width=True)
    else:
        st.info("Clique em **▶ Run Forecast** para gerar previsão de 4 semanas. ~60 segundos.")


def page_ml(loader):
    import plotly.graph_objects as go
    from dashboard.charts import AMBER, GOLD, RED, _apply

    df    = loader.order_features()
    deliv = df[df["order_status"] == "delivered"].dropna(subset=["is_late"])

    st.markdown("## 🤖 ML Predictions")
    st.markdown("<p style='color:#6B5B00;margin-top:-8px;'>Classificador de risco de atraso — LightGBM</p>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    c1,c2,c3 = st.columns(3)
    c1.metric("Pedidos de Treino", f"{len(deliv):,}")
    c2.metric("Pedidos Atrasados", f"{(deliv['is_late']==1).sum():,}")
    c3.metric("Taxa de Atraso",    f"{(deliv['is_late']==1).mean():.1%}")

    st.markdown("---")
    st.info("⚡ O modelo usa amostra de até 20.000 pedidos para proteger a memória do servidor.")

    if st.button("▶  Run Delay Model", type="primary") or "delay_predictions" in st.session_state:
        if "delay_predictions" not in st.session_state:
            with st.spinner("Treinando classificador LightGBM… (~30 segundos)"):
                from ml.delivery_delay_model import DeliveryDelayModel
                # Cap at 20k rows to protect t3.micro RAM
                deliv_fit = deliv.sample(min(20000, len(deliv)), random_state=42)
                model = DeliveryDelayModel()
                preds = model.train_and_predict(deliv_fit)
                st.session_state["delay_predictions"] = preds
                st.session_state["delay_model"]       = model
            st.success("Modelo treinado ✓")

        preds = st.session_state["delay_predictions"]
        model = st.session_state["delay_model"]

        m1,m2,m3,m4 = st.columns(4)
        m1.metric("AUC-ROC",          f"{model.metrics.get('auc_roc',0):.3f}")
        m2.metric("Precision",        f"{model.metrics.get('precision',0):.3f}")
        m3.metric("Recall",           f"{model.metrics.get('recall',0):.3f}")
        m4.metric("Alto Risco",       f"{(preds['delay_risk_score']>0.5).sum():,}")

        st.markdown("<br>", unsafe_allow_html=True)
        col_a, col_b = st.columns(2)
        with col_a:
            fig = go.Figure(go.Histogram(x=preds["delay_risk_score"], nbinsx=40,
                                          marker_color=AMBER, marker_opacity=0.85))
            fig.add_vline(x=0.5, line_color=RED, line_dash="dash",
                          annotation_text="Threshold 0.5", annotation_font_color=RED)
            fig.update_xaxes(tickfont=dict(color="#000000"))
            fig.update_yaxes(tickfont=dict(color="#000000"))
            st.plotly_chart(_apply(fig, "Distribuição do Score de Risco"), use_container_width=True)
        with col_b:
            imp = model.top_features(n=12)
            fig_imp = go.Figure(go.Bar(x=imp["importance"], y=imp["feature"], orientation="h",
                                        marker_color=GOLD, marker_opacity=0.9))
            fig_imp.update_yaxes(categoryorder="total ascending", tickfont=dict(color="#000000"))
            fig_imp.update_xaxes(tickfont=dict(color="#000000"))
            st.plotly_chart(_apply(fig_imp, "Feature Importance", height=380), use_container_width=True)

        high_risk = (preds[preds["delay_risk_score"]>0.5]
                     .sort_values("delay_risk_score", ascending=False).head(200))
        if len(high_risk) > 0:
            cols_show = [c for c in ["order_id","customer_state","main_category",
                                      "delay_risk_score","actual_days","is_late"]
                         if c in high_risk.columns]
            d = high_risk[cols_show].copy()
            if "delay_risk_score" in d.columns:
                d["delay_risk_score"] = d["delay_risk_score"].apply(lambda x: f"{x:.3f}")
            html_table(d, height=300)
    else:
        st.info("Clique em **▶ Run Delay Model** para calcular scores de risco. ~30 segundos.")


# ── Main — render tabs ────────────────────────────────────────────────────────

render_topbar()
loader = get_loader()

tabs = st.tabs(["🏠  Home", "📊  Market Overview", "🚚  Delivery", "💎  Customer LTV", "📈  Forecast", "🤖  ML Predictions"])

with tabs[0]: page_home(loader)
with tabs[1]: page_market(loader)
with tabs[2]: page_delivery(loader)
with tabs[3]: page_ltv(loader)
with tabs[4]: page_forecast(loader)
with tabs[5]: page_ml(loader)
