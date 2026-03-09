"""Olist E-Commerce Intelligence Dashboard."""

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
    initial_sidebar_state="expanded",
)

# ── Shared CSS — injected on every page via render_sidebar() ──────────────────
OLIST_CSS = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

  :root {
    --bg:      #FFFDF5;
    --surface: #FFFFFF;
    --border:  #F0E8C8;
    --text:    #1A1400;
    --muted:   #6B5B00;
    --gold:    #FFD400;
    --amber:   #FF8C00;
    --orange:  #FF5F00;
    --yellow:  #FFC300;
    --dark:    #2D2000;
    --sans:    'Inter', sans-serif;
  }

  html, body, [data-testid="stAppViewContainer"] {
    background-color: var(--bg) !important;
    color: var(--text) !important;
    font-family: var(--sans) !important;
  }

  [data-testid="stSidebar"] {
    background-color: var(--dark) !important;
    border-right: 2px solid var(--gold) !important;
  }
  [data-testid="stSidebar"] * { color: #F5E988 !important; }
  [data-testid="stSidebar"] a { color: #FFD400 !important; }
  [data-testid="stSidebar"] strong { color: #FFFFFF !important; }

  h1, h2, h3 {
    font-family: var(--sans) !important;
    color: var(--dark) !important;
    font-weight: 700 !important;
  }

  div[data-testid="stMetric"] {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    padding: 16px 20px !important;
    border-top: 3px solid var(--gold) !important;
  }
  div[data-testid="stMetric"] label {
    font-size: 0.72rem !important;
    color: var(--muted) !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600 !important;
  }
  div[data-testid="stMetric"] [data-testid="stMetricValue"] {
    font-size: 1.6rem !important;
    font-weight: 700 !important;
    color: var(--dark) !important;
  }

  .section-header {
    font-size: 0.72rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-weight: 700;
    border-bottom: 2px solid var(--gold);
    padding-bottom: 6px;
    margin-bottom: 16px;
  }

  .badge { display:inline-block; font-size:0.7rem; padding:3px 10px; border-radius:12px; font-weight:600; }
  .badge-live       { background:#FFF3B0; color:#6B5B00; border:1px solid #FFD400; }
  .badge-simulation { background:#FFE8CC; color:#7A3000; border:1px solid #FF8C00; }

  [data-testid="stDataFrame"] {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
  }

  .stTabs [data-baseweb="tab-list"] {
    background: var(--surface) !important;
    border-bottom: 2px solid var(--gold) !important;
  }
  .stTabs [data-baseweb="tab"] {
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    color: var(--muted) !important;
    background: transparent !important;
    padding: 10px 20px !important;
  }
  .stTabs [aria-selected="true"] {
    color: var(--dark) !important;
    border-bottom: 2px solid var(--orange) !important;
    font-weight: 700 !important;
  }

  .stPlotlyChart { border: 1px solid var(--border) !important; border-radius: 8px !important; }
  #MainMenu, footer, header { visibility: hidden; }
  .block-container { padding-top: 1.5rem !important; }

  /* Force page background white on all subpages */
  section[data-testid="stMain"] { background-color: var(--bg) !important; }
</style>
"""


@st.cache_resource(show_spinner="Loading Olist dataset…")
def get_loader():
    from data_loader import OlistLoader
    return OlistLoader()



def html_table(df, height: int = 400) -> None:
    """Render a DataFrame as a styled HTML table matching the gold palette."""
    thead_bg = "#2D2000"
    thead_fg = "#FFD400"
    row_even  = "#FFFFFF"
    row_odd   = "#FFFDF5"
    border    = "#F0E8C8"
    text      = "#000000"

    cols = "".join(f"<th style='padding:8px 14px;text-align:left;font-size:0.78rem;"
                   f"letter-spacing:0.06em;text-transform:uppercase;white-space:nowrap;'>{c}</th>"
                   for c in df.columns)
    rows = ""
    for i, (_, row) in enumerate(df.iterrows()):
        bg = row_even if i % 2 == 0 else row_odd
        cells = "".join(
            f"<td style='padding:7px 14px;font-size:0.82rem;border-bottom:1px solid {border};"
            f"white-space:nowrap;'>{v}</td>"
            for v in row.values
        )
        rows += f"<tr style='background:{bg};color:{text};'>{cells}</tr>"

    html = f"""
    <div style='overflow:auto;max-height:{height}px;border:1px solid {border};border-radius:8px;'>
      <table style='border-collapse:collapse;width:100%;font-family:Inter,Arial,sans-serif;'>
        <thead>
          <tr style='background:{thead_bg};color:{thead_fg};position:sticky;top:0;z-index:1;'>{cols}</tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>"""
    import streamlit as st
    st.markdown(html, unsafe_allow_html=True)

def render_sidebar():
    # Inject CSS on every page that calls this
    st.markdown(OLIST_CSS, unsafe_allow_html=True)

    use_duckdb = os.getenv("USE_DUCKDB", "true").lower() == "true"

    with st.sidebar:
        st.markdown("""
        <div style="padding:12px 0 20px;">
          <div style="font-size:1.15rem;color:#FFD400;font-weight:700;">🛒 Olist Intelligence</div>
          <div style="color:#A89000;font-size:0.78rem;margin-top:2px;">Brazilian E-Commerce Analytics</div>
        </div>
        """, unsafe_allow_html=True)

        badge_cls = "badge-simulation" if use_duckdb else "badge-live"
        badge_txt = "● Local CSV" if use_duckdb else "● Redshift Live"
        st.markdown(f'<span class="badge {badge_cls}">{badge_txt}</span>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown('<div class="section-header" style="color:#A89000;border-color:#FFD400;">Navigation</div>', unsafe_allow_html=True)
        st.page_link("app.py",                           label="🏠  Home")
        st.page_link("pages/01_market_overview.py",      label="📊  Market Overview")
        st.page_link("pages/02_delivery_performance.py", label="🚚  Delivery Performance")
        st.page_link("pages/03_customer_ltv.py",         label="💎  Customer LTV")
        st.page_link("pages/04_demand_forecast.py",      label="📈  Demand Forecast")
        st.page_link("pages/05_ml_predictions.py",       label="🤖  ML Predictions")

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="section-header" style="color:#A89000;border-color:#FFD400;">Dataset</div>', unsafe_allow_html=True)

        loader = get_loader()
        summary = loader.summary()
        st.markdown(f"""
        <div style="font-size:0.78rem;color:#A89000;line-height:2.2;">
          Orders &nbsp;&nbsp;&nbsp; <strong style="color:#FFD400;">{summary['total_orders']:,}</strong><br>
          Delivered &nbsp; <strong style="color:#FFD400;">{summary['delivered']:,}</strong><br>
          From &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; <strong style="color:#FFD400;">{summary['date_range'][0]}</strong><br>
          To &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; <strong style="color:#FFD400;">{summary['date_range'][1]}</strong><br>
          Files &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; <strong style="color:#FFD400;">{summary['files_loaded']}/9</strong>
        </div>
        """, unsafe_allow_html=True)


def render_home():
    loader = get_loader()
    df = loader.order_features()

    st.markdown("# Olist E-Commerce Intelligence")
    st.markdown("<p style='color:#6B5B00;font-size:1rem;margin-top:-6px;'>Brazilian market analytics — 100k real orders · 27 states · 3 ML models</p>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    delivered = df[df["order_status"] == "delivered"]
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Orders",    f"{len(df):,}")
    c2.metric("GMV",             f"R$ {df['payment_value'].sum():,.0f}")
    c3.metric("Avg Order Value", f"R$ {df['payment_value'].mean():,.2f}")
    c4.metric("Late Rate",       f"{delivered['is_late'].mean():.1%}")
    c5.metric("Avg Review",      f"{df['review_score'].mean():.2f} ⭐")

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
        fig.add_trace(go.Bar(
            x=monthly["purchase_ym"], y=monthly["orders"],
            marker_color="#FFD400", marker_opacity=0.9, name="Orders",
        ))
        fig.update_layout(
            title="Monthly Order Volume", height=300,
            paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFDF5",
            font=dict(family="Inter, Arial, sans-serif", color="#2D2000", size=11),
            margin=dict(t=40, b=20, l=10, r=10),
            xaxis=dict(showgrid=False, color="#6B5B00"),
            yaxis=dict(showgrid=True, gridcolor="#F0E8C8", color="#6B5B00"),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.markdown('<div class="section-header">Top States by GMV</div>', unsafe_allow_html=True)
        top_states = (
            df.groupby("customer_state")
            .agg(gmv=("payment_value", "sum"), orders=("order_id", "count"),
                 late_rate=("is_late", "mean"))
            .sort_values("gmv", ascending=False).head(8).reset_index()
        )
        top_states["gmv_fmt"]  = top_states["gmv"].apply(lambda x: f"R$ {x:,.0f}")
        top_states["late_fmt"] = top_states["late_rate"].apply(lambda x: f"{x:.1%}")
        html_table(
            top_states[["customer_state", "gmv_fmt", "orders", "late_fmt"]].rename(columns={
                "customer_state": "State", "gmv_fmt": "GMV",
                "orders": "Orders", "late_fmt": "Late Rate",
            }), height=280)


render_sidebar()
render_home()
