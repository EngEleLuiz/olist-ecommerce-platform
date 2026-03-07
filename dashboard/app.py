"""Olist E-Commerce Intelligence Dashboard.

Entry point — run with:
    streamlit run dashboard/app.py

Works immediately with just the CSVs in data/ — no Docker, no AWS needed.
Shows SIMULATION badge when reading from local files, LIVE when on Redshift.
"""

import os
import sys
from pathlib import Path

# Allow imports from project root (data_loader, ml/)
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Olist Intelligence",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS — dark Brazilian market aesthetic ───────────────────────────────
st.markdown(
    """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600&display=swap');

  :root {
    --bg:       #080e14;
    --surface:  #0f1923;
    --border:   #1e2d3d;
    --text:     #cdd6e0;
    --muted:    #4e6278;
    --green:    #00e676;
    --red:      #ff4444;
    --amber:    #ffab40;
    --blue:     #40c4ff;
    --gold:     #ffd740;
    --mono:     'Space Mono', monospace;
    --sans:     'DM Sans', sans-serif;
  }

  html, body, [data-testid="stAppViewContainer"] {
    background-color: var(--bg) !important;
    color: var(--text) !important;
    font-family: var(--sans) !important;
  }

  [data-testid="stSidebar"] {
    background-color: var(--surface) !important;
    border-right: 1px solid var(--border) !important;
  }

  [data-testid="stSidebar"] * { color: var(--text) !important; }

  h1, h2, h3 {
    font-family: var(--mono) !important;
    color: #e8f0f8 !important;
    letter-spacing: -0.02em;
  }

  .metric-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 20px 24px;
    position: relative;
    overflow: hidden;
  }
  .metric-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, var(--blue), var(--green));
  }
  .metric-label {
    font-family: var(--mono);
    font-size: 0.68rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin-bottom: 6px;
  }
  .metric-value {
    font-family: var(--mono);
    font-size: 1.75rem;
    font-weight: 700;
    color: #e8f0f8;
    line-height: 1;
  }
  .metric-delta {
    font-family: var(--mono);
    font-size: 0.75rem;
    margin-top: 6px;
  }
  .metric-delta.up   { color: var(--green); }
  .metric-delta.down { color: var(--red); }
  .metric-delta.flat { color: var(--muted); }

  .badge {
    display: inline-block;
    font-family: var(--mono);
    font-size: 0.65rem;
    padding: 2px 8px;
    border-radius: 3px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-weight: 700;
  }
  .badge-live       { background: #00e67620; color: var(--green); border: 1px solid var(--green); }
  .badge-simulation { background: #ffab4020; color: var(--amber); border: 1px solid var(--amber); }
  .badge-late       { background: #ff444420; color: var(--red);   border: 1px solid var(--red);   }
  .badge-ontime     { background: #00e67620; color: var(--green); border: 1px solid var(--green); }
  .badge-gold       { background: #ffd74020; color: var(--gold);  border: 1px solid var(--gold);  }

  div[data-testid="stMetric"] {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    padding: 16px 20px !important;
  }
  div[data-testid="stMetric"] label {
    font-family: var(--mono) !important;
    font-size: 0.68rem !important;
    color: var(--muted) !important;
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }
  div[data-testid="stMetric"] [data-testid="stMetricValue"] {
    font-family: var(--mono) !important;
    font-size: 1.5rem !important;
    color: #e8f0f8 !important;
  }

  div[data-testid="stSelectbox"] label,
  div[data-testid="stMultiSelect"] label {
    font-family: var(--mono) !important;
    font-size: 0.7rem !important;
    color: var(--muted) !important;
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }

  .section-header {
    font-family: var(--mono);
    font-size: 0.7rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.15em;
    border-bottom: 1px solid var(--border);
    padding-bottom: 6px;
    margin-bottom: 16px;
  }

  [data-testid="stDataFrame"] {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
  }

  .stTabs [data-baseweb="tab-list"] {
    background: var(--surface) !important;
    border-bottom: 1px solid var(--border) !important;
    gap: 0 !important;
  }
  .stTabs [data-baseweb="tab"] {
    font-family: var(--mono) !important;
    font-size: 0.72rem !important;
    color: var(--muted) !important;
    background: transparent !important;
    padding: 10px 20px !important;
  }
  .stTabs [aria-selected="true"] {
    color: var(--blue) !important;
    border-bottom: 2px solid var(--blue) !important;
  }

  .stPlotlyChart { border: 1px solid var(--border) !important; border-radius: 8px !important; }
  .stAlert       { border-radius: 6px !important; }

  /* Hide Streamlit branding */
  #MainMenu, footer, header { visibility: hidden; }
  .block-container { padding-top: 1.5rem !important; }
</style>
""",
    unsafe_allow_html=True,
)


# ── Data loader (cached at session level) ─────────────────────────────────────
@st.cache_resource(show_spinner="Loading Olist dataset…")
def get_loader():
    from data_loader import OlistLoader

    return OlistLoader()


# ── Sidebar ───────────────────────────────────────────────────────────────────
def render_sidebar():
    use_duckdb = os.getenv("USE_DUCKDB", "true").lower() == "true"

    with st.sidebar:
        st.markdown(
            """
        <div style="padding: 8px 0 20px;">
          <div style="font-family: 'Space Mono', monospace; font-size: 1.1rem;
                      color: #e8f0f8; font-weight: 700; letter-spacing: -0.02em;">
            🛒 OLIST<br>
            <span style="color: #4e6278; font-size: 0.75rem; font-weight: 400;">
              Intelligence Platform
            </span>
          </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

        badge_cls = "badge-simulation" if use_duckdb else "badge-live"
        badge_txt = "● LOCAL CSV" if use_duckdb else "● REDSHIFT"
        st.markdown(f'<span class="badge {badge_cls}">{badge_txt}</span>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown('<div class="section-header">Navigation</div>', unsafe_allow_html=True)
        st.page_link("app.py", label="🏠  Home", icon=None)
        st.page_link("pages/01_market_overview.py", label="📊  Market Overview")
        st.page_link("pages/02_delivery_performance.py", label="🚚  Delivery Performance")
        st.page_link("pages/03_customer_ltv.py", label="💎  Customer LTV")
        st.page_link("pages/04_demand_forecast.py", label="📈  Demand Forecast")
        st.page_link("pages/05_ml_predictions.py", label="🤖  ML Predictions")

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="section-header">Dataset</div>', unsafe_allow_html=True)

        loader = get_loader()
        summary = loader.summary()
        st.markdown(
            f"""
        <div style="font-family: 'Space Mono', monospace; font-size: 0.7rem; color: #4e6278; line-height: 2;">
          ORDERS &nbsp;&nbsp; <span style="color: #cdd6e0;">{summary["total_orders"]:,}</span><br>
          DELIVERED &nbsp; <span style="color: #cdd6e0;">{summary["delivered"]:,}</span><br>
          FROM &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; <span style="color: #cdd6e0;">{summary["date_range"][0]}</span><br>
          TO &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; <span style="color: #cdd6e0;">{summary["date_range"][1]}</span><br>
          FILES &nbsp;&nbsp;&nbsp;&nbsp; <span style="color: #cdd6e0;">{summary["files_loaded"]}/9</span>
        </div>
        """,
            unsafe_allow_html=True,
        )


# ── Home page ─────────────────────────────────────────────────────────────────
def render_home():
    loader = get_loader()
    df = loader.order_features()

    st.markdown("# Olist E-Commerce Intelligence")
    st.markdown(
        "<p style='color: #4e6278; font-family: DM Sans; font-size: 1rem; margin-top: -8px;'>"
        "Brazilian market analytics — 100k real orders · 27 states · 3 ML models"
        "</p>",
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    delivered = df[df["order_status"] == "delivered"]

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("Total Orders", f"{len(df):,}")
    with c2:
        st.metric("GMV", f"R$ {df['payment_value'].sum():,.0f}")
    with c3:
        st.metric("Avg Order Value", f"R$ {df['payment_value'].mean():,.2f}")
    with c4:
        st.metric("Late Rate", f"{delivered['is_late'].mean():.1%}")
    with c5:
        st.metric("Avg Review", f"{df['review_score'].mean():.2f} ⭐")

    st.markdown("<br>", unsafe_allow_html=True)

    col_left, col_right = st.columns([3, 2])
    with col_left:
        import plotly.graph_objects as go

        monthly = (
            df.groupby("purchase_ym")
            .agg(orders=("order_id", "count"), gmv=("payment_value", "sum"))
            .reset_index()
        )
        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=monthly["purchase_ym"],
                y=monthly["orders"],
                marker_color="#40c4ff",
                marker_opacity=0.8,
                name="Orders",
            )
        )
        fig.update_layout(
            title="Monthly Order Volume",
            height=300,
            paper_bgcolor="#0f1923",
            plot_bgcolor="#0f1923",
            font=dict(family="Space Mono", color="#4e6278", size=10),
            margin=dict(t=40, b=20, l=10, r=10),
            xaxis=dict(showgrid=False, color="#4e6278"),
            yaxis=dict(showgrid=True, gridcolor="#1e2d3d", color="#4e6278"),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.markdown('<div class="section-header">Top States by GMV</div>', unsafe_allow_html=True)
        top_states = (
            df.groupby("customer_state")
            .agg(
                gmv=("payment_value", "sum"),
                orders=("order_id", "count"),
                late_rate=("is_late", "mean"),
            )
            .sort_values("gmv", ascending=False)
            .head(8)
            .reset_index()
        )
        top_states["gmv_fmt"] = top_states["gmv"].apply(lambda x: f"R$ {x:,.0f}")
        top_states["late_fmt"] = top_states["late_rate"].apply(lambda x: f"{x:.1%}")
        st.dataframe(
            top_states[["customer_state", "gmv_fmt", "orders", "late_fmt"]].rename(
                columns={
                    "customer_state": "State",
                    "gmv_fmt": "GMV",
                    "orders": "Orders",
                    "late_fmt": "Late Rate",
                }
            ),
            hide_index=True,
            use_container_width=True,
            height=280,
        )


render_sidebar()
render_home()
