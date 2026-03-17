"""Olist Intelligence Dashboard — tab navigation, no sidebar, full width."""
import os, sys
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

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* ── KILL SIDEBAR ── */
[data-testid="stSidebar"],
[data-testid="collapsedControl"],
[data-testid="stSidebarNav"],
section[data-testid="stSidebarNav"],
div[data-testid="stSidebarNavItems"] { display:none !important; width:0 !important; }

/* ── GLOBAL ── */
html, body,
[data-testid="stAppViewContainer"],
section[data-testid="stMain"],
.main .block-container {
  background:#FFFDF5 !important;
  font-family:'Inter',sans-serif !important;
  color:#000 !important;
}
/* Full width — remove all side padding */
.block-container {
  padding-top:0.5rem !important;
  padding-left:1rem !important;
  padding-right:1rem !important;
  max-width:100% !important;
}
#MainMenu, footer, header { visibility:hidden; }

/* ── TOP BAR ── */
.topbar {
  background:#2D2000; color:#FFD400;
  padding:10px 24px; border-radius:8px;
  display:flex; align-items:center;
  border-bottom:3px solid #FFD400;
  margin-bottom:8px;
}
.topbar-title { font-size:1rem; font-weight:700; }
.topbar-sub   { font-size:0.75rem; color:#A89000; margin-left:10px; }
.topbar-badge {
  margin-left:auto; font-size:0.7rem;
  background:#FFF3B0; color:#6B5B00;
  padding:2px 10px; border-radius:12px;
  border:1px solid #FFD400; font-weight:600;
}

/* ── TABS ── */
.stTabs [data-baseweb="tab-list"] {
  background:#2D2000 !important;
  border-radius:8px 8px 0 0 !important;
  padding:0 6px !important; gap:2px !important;
  border-bottom:3px solid #FFD400 !important;
}
.stTabs [data-baseweb="tab"] {
  background:transparent !important;
  color:#A89000 !important;
  font-size:0.82rem !important; font-weight:500 !important;
  padding:10px 20px !important;
  border-radius:6px 6px 0 0 !important;
  border:none !important; white-space:nowrap !important;
}
.stTabs [data-baseweb="tab"]:hover { background:#3D2E00 !important; color:#FFD400 !important; }
.stTabs [aria-selected="true"]     { background:#FFD400 !important; color:#2D2000 !important; font-weight:700 !important; }
.stTabs [data-baseweb="tab-highlight"],
.stTabs [data-baseweb="tab-border"] { display:none !important; }
.stTabs [data-baseweb="tab-panel"]  { background:#FFFDF5 !important; padding-top:16px !important; }

/* ── METRICS ── */
div[data-testid="stMetric"] {
  background:#fff !important; border:1px solid #F0E8C8 !important;
  border-top:3px solid #FFD400 !important; border-radius:8px !important;
  padding:14px 18px !important;
}
div[data-testid="stMetric"] label {
  font-size:0.7rem !important; color:#6B5B00 !important;
  text-transform:uppercase; letter-spacing:.08em; font-weight:600 !important;
}
div[data-testid="stMetric"] [data-testid="stMetricValue"] {
  font-size:1.5rem !important; font-weight:700 !important; color:#000 !important;
}

/* ── MISC ── */
h1,h2,h3 { color:#000 !important; font-family:'Inter',sans-serif !important; font-weight:700 !important; }
.section-hdr {
  font-size:.7rem; color:#6B5B00; text-transform:uppercase;
  letter-spacing:.1em; font-weight:700;
  border-bottom:2px solid #FFD400; padding-bottom:5px; margin-bottom:14px;
}
.stPlotlyChart { border:1px solid #F0E8C8 !important; border-radius:8px !important; }
</style>
""", unsafe_allow_html=True)

# ── helpers ──────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner="Loading Olist data…")
def get_loader():
    from data_loader import OlistLoader
    return OlistLoader()

def tbl(df, height=380):
    hdr="#2D2000"; hfg="#FFD400"; even="#fff"; odd="#FFFDF5"; bdr="#F0E8C8"
    ths = "".join(f"<th style='padding:7px 13px;text-align:left;font-size:.75rem;"
                  f"letter-spacing:.06em;text-transform:uppercase;color:{hfg};'>{c}</th>"
                  for c in df.columns)
    rows = ""
    for i,(_, r) in enumerate(df.iterrows()):
        bg = even if i%2==0 else odd
        tds = "".join(f"<td style='padding:6px 13px;font-size:.82rem;"
                      f"border-bottom:1px solid {bdr};color:#000;white-space:nowrap;'>{v}</td>"
                      for v in r.values)
        rows += f"<tr style='background:{bg};'>{tds}</tr>"
    st.markdown(
        f"<div style='overflow:auto;max-height:{height}px;border:1px solid {bdr};border-radius:8px;'>"
        f"<table style='border-collapse:collapse;width:100%;font-family:Inter,sans-serif;'>"
        f"<thead><tr style='background:{hdr};position:sticky;top:0;z-index:1;'>{ths}</tr></thead>"
        f"<tbody>{rows}</tbody></table></div>", unsafe_allow_html=True)

def cb():
    return dict(paper_bgcolor="#fff", plot_bgcolor="#FFFDF5",
                font=dict(family="Inter,Arial,sans-serif", color="#000", size=11),
                margin=dict(t=44,b=24,l=12,r=12),
                xaxis=dict(showgrid=False, tickfont=dict(color="#000"), title_font=dict(color="#000")),
                yaxis=dict(showgrid=True, gridcolor="#F0E8C8", tickfont=dict(color="#000"), title_font=dict(color="#000")),
                legend=dict(font=dict(color="#000")))

def rgba(h,a):
    h=h.lstrip("#"); r,g,b=int(h[:2],16),int(h[2:4],16),int(h[4:],16)
    return f"rgba({r},{g},{b},{a})"

# ── top bar ───────────────────────────────────────────────────────────────────
st.markdown("""
<div class="topbar">
  <span class="topbar-title">🛒 Olist Intelligence</span>
  <span class="topbar-sub">Brazilian E-Commerce Analytics</span>
  <span class="topbar-badge">● Local CSV</span>
</div>""", unsafe_allow_html=True)

loader = get_loader()

t0,t1,t2,t3,t4,t5 = st.tabs([
    "🏠  Home",
    "📊  Market Overview",
    "🚚  Delivery",
    "💎  Customer Segments",
    "🏪  Seller Intelligence",
    "📦  Order Patterns",
])

# ══════════════════════════════════════════════════════════════ HOME ══════════
with t0:
    import plotly.graph_objects as go
    df = loader.order_features()
    st.markdown("## Olist E-Commerce Intelligence")
    st.markdown("<p style='color:#6B5B00;margin-top:-8px;'>100k real Brazilian e-commerce orders · 27 states · analytics platform</p>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    deliv = df[df["order_status"]=="delivered"]
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Total Orders",    f"{len(df):,}")
    c2.metric("GMV",             f"R$ {df['payment_value'].sum():,.0f}")
    c3.metric("Avg Order Value", f"R$ {df['payment_value'].mean():.2f}")
    c4.metric("Late Rate",       f"{(deliv['is_late']==1).mean():.1%}")
    c5.metric("Avg Review",      f"{df['review_score'].mean():.2f} ⭐")
    st.markdown("<br>", unsafe_allow_html=True)
    col_l,col_r = st.columns([3,2])
    with col_l:
        m = df.groupby("purchase_ym").agg(orders=("order_id","count"),gmv=("payment_value","sum")).reset_index()
        from plotly.subplots import make_subplots
        fig = make_subplots(rows=2,cols=1,shared_xaxes=True,row_heights=[.6,.4],vertical_spacing=.06)
        fig.add_trace(go.Bar(x=m["purchase_ym"],y=m["orders"],marker_color="#FFD400",marker_opacity=.9,name="Orders"),row=1,col=1)
        fig.add_trace(go.Scatter(x=m["purchase_ym"],y=m["gmv"],fill="tozeroy",
                                  fillcolor=rgba("#FF8C00",.15),line=dict(color="#FF8C00",width=2),name="GMV"),row=2,col=1)
        fig.update_layout(title="Monthly Orders & GMV",height=380,**cb())
        fig.update_yaxes(showgrid=True,gridcolor="#F0E8C8",tickfont=dict(color="#000"))
        st.plotly_chart(fig,use_container_width=True)
    with col_r:
        st.markdown('<div class="section-hdr">Top States by GMV</div>', unsafe_allow_html=True)
        top = (df.groupby("customer_state")
               .agg(gmv=("payment_value","sum"),orders=("order_id","count"),lr=("is_late","mean"))
               .sort_values("gmv",ascending=False).head(10).reset_index())
        top["GMV"]  = top["gmv"].apply(lambda x: f"R$ {x:,.0f}")
        top["Late"] = top["lr"].apply(lambda x: f"{x:.1%}")
        tbl(top[["customer_state","GMV","orders","Late"]].rename(
            columns={"customer_state":"State","orders":"Orders"}), height=340)

# ════════════════════════════════════════════════ MARKET OVERVIEW ═════════════
with t1:
    import plotly.graph_objects as go, plotly.express as px
    df = loader.order_features()
    st.markdown("## 📊 Market Overview")
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Total GMV",        f"R$ {df['payment_value'].sum():,.0f}")
    c2.metric("Total Orders",     f"{len(df):,}")
    c3.metric("Avg Order Value",  f"R$ {df['payment_value'].mean():.2f}")
    c4.metric("Unique Customers", f"{df['customer_unique_id'].nunique():,}")
    c5.metric("Active States",    f"{df['customer_state'].nunique()}")
    st.markdown("<br>", unsafe_allow_html=True)
    col_l,col_r = st.columns(2)
    with col_l:
        metric = st.selectbox("State metric",["gmv","orders"],
                              format_func=lambda x:{"gmv":"GMV","orders":"Order Count"}[x])
        col  = "payment_value" if metric=="gmv" else "order_id"
        fn   = "sum" if metric=="gmv" else "count"
        agg  = df.groupby("customer_state")[col].agg(fn).sort_values(ascending=True).tail(20)
        colors = ["#FFD400"]*(len(agg)-1)+["#FF5F00"]
        fig = go.Figure(go.Bar(x=agg.values,y=agg.index,orientation="h",marker_color=colors,marker_opacity=.9))
        fig.update_layout(title=f"{'GMV' if metric=='gmv' else 'Orders'} by State",height=520,**cb())
        st.plotly_chart(fig,use_container_width=True)
    with col_r:
        cat = df.groupby("main_category").agg(gmv=("payment_value","sum"),orders=("order_id","count")).reset_index()
        fig2 = px.treemap(cat,path=["main_category"],values="gmv",color="orders",
                          color_continuous_scale=["#FFF3B0","#FFD400","#FF5F00"])
        fig2.update_layout(title="GMV by Category",height=520,paper_bgcolor="#fff",
                           font=dict(family="Inter",color="#000",size=11),margin=dict(t=44,b=10,l=10,r=10))
        st.plotly_chart(fig2,use_container_width=True)
    st.markdown("---")
    sd = (df.groupby("customer_state")
          .agg(gmv=("payment_value","sum"),orders=("order_id","count"),
               late_rate=("is_late","mean"),avg_review=("review_score","mean"))
          .sort_values("gmv",ascending=False).reset_index())
    sd["GMV Share"] = (sd["gmv"]/sd["gmv"].sum()*100).apply(lambda x: f"{x:.1f}%")
    sd["GMV"]       = sd["gmv"].apply(lambda x: f"R$ {x:,.0f}")
    sd["Late Rate"] = sd["late_rate"].apply(lambda x: f"{x:.1%}")
    sd["Review"]    = sd["avg_review"].apply(lambda x: f"{x:.2f} ⭐")
    tbl(sd[["customer_state","GMV","orders","Late Rate","Review","GMV Share"]].rename(
        columns={"customer_state":"State","orders":"Orders"}))

# ════════════════════════════════════════════════ DELIVERY ════════════════════
with t2:
    import plotly.graph_objects as go
    df = loader.order_features()
    deliv = df[df["order_status"]=="delivered"]
    st.markdown("## 🚚 Delivery Performance")
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Delivered",    f"{len(deliv):,}")
    c2.metric("On-Time Rate", f"{(deliv['is_late']==0).mean():.1%}")
    c3.metric("Late Rate",    f"{(deliv['is_late']==1).mean():.1%}")
    c4.metric("Avg Delay",    f"{deliv['delay_days'].mean():.1f} days")
    c5.metric("Avg Delivery", f"{deliv['actual_days'].mean():.1f} days")
    st.markdown("<br>", unsafe_allow_html=True)
    col_l,col_r = st.columns(2)
    with col_l:
        late_o = deliv[deliv["delay_days"]>0]
        med = late_o["delay_days"].median()
        fig = go.Figure(go.Histogram(x=late_o["delay_days"].clip(0,40),nbinsx=40,
                                      marker_color="#FF8C00",marker_opacity=.85))
        fig.add_vline(x=med,line_color="#CC2200",line_dash="dash",
                      annotation_text=f"Median {med:.1f}d",annotation_font_color="#CC2200")
        fig.update_layout(title=f"Late Delivery Distribution ({len(late_o):,} late orders)",height=360,**cb())
        fig.update_xaxes(title_text="Days Late"); fig.update_yaxes(title_text="Orders")
        st.plotly_chart(fig,use_container_width=True)
    with col_r:
        bands={"On Time":(deliv["is_late"]==0).sum(),
               "1–3 days late":((deliv["delay_days"]>=1)&(deliv["delay_days"]<=3)).sum(),
               "4–7 days late":((deliv["delay_days"]>=4)&(deliv["delay_days"]<=7)).sum(),
               "8+ days late": (deliv["delay_days"]>7).sum()}
        fig2=go.Figure(go.Pie(labels=list(bands.keys()),values=list(bands.values()),hole=.6,
                               marker_colors=["#2D7A00","#FFC300","#FF8C00","#CC2200"],
                               textfont=dict(color="#000",size=11)))
        fig2.update_layout(title="SLA Breakdown",height=360,paper_bgcolor="#fff",
                           font=dict(family="Inter",color="#000",size=11),
                           margin=dict(t=44,b=10,l=10,r=10),legend=dict(font=dict(color="#000")))
        st.plotly_chart(fig2,use_container_width=True)
    state_lr = deliv.groupby("customer_state")["is_late"].mean().sort_values(ascending=True)
    colors = ["#CC2200" if v>.15 else "#FF8C00" if v>.08 else "#2D7A00" for v in state_lr.values]
    fig3 = go.Figure(go.Bar(x=state_lr.values*100,y=state_lr.index,orientation="h",
                             marker_color=colors,marker_opacity=.85))
    fig3.add_vline(x=state_lr.mean()*100,line_color="#FFD400",line_dash="dash",
                   annotation_text=f"Avg {state_lr.mean():.1%}",annotation_font_color="#000")
    fig3.update_layout(title="Late Rate by State (%)",height=540,**cb())
    fig3.update_xaxes(title_text="Late Rate (%)")
    st.plotly_chart(fig3,use_container_width=True)
    col_a,col_b = st.columns(2)
    with col_a:
        cat_late = (deliv.groupby("main_category")
                    .agg(orders=("order_id","count"),late_rate=("is_late","mean"))
                    .query("orders > 100").sort_values("late_rate",ascending=False).head(15).reset_index())
        cat_late["Late Rate"] = cat_late["late_rate"].apply(lambda x: f"{x:.1%}")
        cat_late["Orders"]    = cat_late["orders"].apply(lambda x: f"{x:,}")
        tbl(cat_late[["main_category","Orders","Late Rate"]].rename(columns={"main_category":"Category"}), height=400)
    with col_b:
        monthly_lr = (deliv.groupby("purchase_ym")["is_late"].mean()*100).reset_index()
        fig4 = go.Figure(go.Scatter(x=monthly_lr["purchase_ym"],y=monthly_lr["is_late"],
                                     fill="tozeroy",fillcolor=rgba("#FF8C00",.15),
                                     line=dict(color="#FF8C00",width=2)))
        fig4.update_layout(title="Monthly Late Rate (%)",height=360,**cb())
        fig4.update_yaxes(title_text="Late Rate (%)")
        st.plotly_chart(fig4,use_container_width=True)

# ════════════════════════════════════════════════ CUSTOMER SEGMENTS ═══════════
with t3:
    import plotly.graph_objects as go
    import pandas as pd
    df  = loader.order_features()
    rfm = loader.customer_rfm()
    st.markdown("## 💎 Customer Segments")
    st.markdown("<p style='color:#6B5B00;margin-top:-8px;'>RFM-based segmentation — no ML required, instant results</p>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Unique Customers",  f"{len(rfm):,}")
    c2.metric("Repeat Buyers",     f"{(rfm['frequency_repeat']>0).sum():,}")
    c3.metric("Repeat Rate",       f"{(rfm['frequency_repeat']>0).mean():.1%}")
    c4.metric("Median Spend",      f"R$ {rfm['total_spend'].median():.2f}")
    c5.metric("Avg Order Value",   f"R$ {rfm['monetary_mean'].mean():.2f}")
    st.markdown("<br>", unsafe_allow_html=True)

    # Pure percentile segmentation — no ML
    rfm2 = rfm.copy()
    rfm2["r_score"] = pd.qcut(rfm2["recency_days"], q=4, labels=[4,3,2,1]).astype(int)
    rfm2["f_score"] = pd.qcut(rfm2["frequency_repeat"].clip(lower=0)+0.0001, q=4,
                               labels=[1,2,3,4], duplicates="drop").astype(int)
    rfm2["m_score"] = pd.qcut(rfm2["total_spend"], q=4, labels=[1,2,3,4]).astype(int)
    rfm2["rfm_score"] = rfm2["r_score"] + rfm2["f_score"] + rfm2["m_score"]

    def segment(s):
        if s >= 10: return "Champions"
        elif s >= 8: return "Loyal"
        elif s >= 6: return "Potential"
        elif s >= 4: return "At Risk"
        else: return "Lost"

    rfm2["segment"] = rfm2["rfm_score"].apply(segment)
    seg_colors = {"Champions":"#FF5F00","Loyal":"#FFD400","Potential":"#FFC300",
                  "At Risk":"#FF8C00","Lost":"#C8A000"}

    col_l,col_r = st.columns(2)
    with col_l:
        seg_cnt = rfm2["segment"].value_counts().reset_index()
        seg_cnt.columns = ["segment","count"]
        fig = go.Figure(go.Pie(labels=seg_cnt["segment"],values=seg_cnt["count"],hole=.55,
                               marker_colors=[seg_colors.get(s,"#FFD400") for s in seg_cnt["segment"]],
                               textfont=dict(color="#000",size=12)))
        fig.update_layout(title="Customer Segments",height=380,paper_bgcolor="#fff",
                          font=dict(family="Inter",color="#000",size=11),
                          margin=dict(t=44,b=10,l=10,r=10),legend=dict(font=dict(color="#000")))
        st.plotly_chart(fig,use_container_width=True)
    with col_r:
        seg_rev = (rfm2.groupby("segment")
                   .agg(customers=("customer_unique_id","count"),
                        total_spend=("total_spend","sum"),
                        avg_spend=("total_spend","mean"),
                        avg_recency=("recency_days","mean"))
                   .reset_index().sort_values("total_spend",ascending=False))
        fig2 = go.Figure(go.Bar(
            x=seg_rev["segment"], y=seg_rev["total_spend"],
            marker_color=[seg_colors.get(s,"#FFD400") for s in seg_rev["segment"]],
            marker_opacity=.9, text=seg_rev["total_spend"].apply(lambda x: f"R${x:,.0f}"),
            textposition="outside", textfont=dict(color="#000")))
        fig2.update_layout(title="Total Spend by Segment",height=380,**cb())
        fig2.update_yaxes(title_text="Total Spend (R$)")
        st.plotly_chart(fig2,use_container_width=True)

    st.markdown("---")
    col_a,col_b = st.columns(2)
    with col_a:
        # Recency distribution per segment
        fig3 = go.Figure()
        for seg,color in seg_colors.items():
            data = rfm2[rfm2["segment"]==seg]["recency_days"]
            if len(data)>0:
                fig3.add_trace(go.Box(y=data,name=seg,marker_color=color,
                                       line=dict(color=color),showlegend=False))
        fig3.update_layout(title="Recency Distribution by Segment",height=380,**cb())
        fig3.update_yaxes(title_text="Days Since Last Purchase")
        st.plotly_chart(fig3,use_container_width=True)
    with col_b:
        sample = rfm2.sample(min(5000,len(rfm2)),random_state=42)
        fig4 = go.Figure()
        for seg,color in seg_colors.items():
            d = sample[sample["segment"]==seg]
            if len(d)>0:
                fig4.add_trace(go.Scattergl(x=d["recency_days"],y=d["total_spend"],
                                             mode="markers",name=seg,
                                             marker=dict(size=4,color=color,opacity=.5)))
        fig4.update_layout(title="Recency vs Total Spend",height=380,**cb())
        fig4.update_xaxes(title_text="Recency (days)",autorange="reversed")
        fig4.update_yaxes(title_text="Total Spend (R$)")
        st.plotly_chart(fig4,use_container_width=True)

    st.markdown("---")
    st.markdown('<div class="section-hdr">Segment Summary</div>', unsafe_allow_html=True)
    seg_tbl = seg_rev.copy()
    seg_tbl["total_spend"] = seg_tbl["total_spend"].apply(lambda x: f"R$ {x:,.0f}")
    seg_tbl["avg_spend"]   = seg_tbl["avg_spend"].apply(lambda x: f"R$ {x:.2f}")
    seg_tbl["avg_recency"] = seg_tbl["avg_recency"].apply(lambda x: f"{x:.0f} days")
    tbl(seg_tbl.rename(columns={"segment":"Segment","customers":"Customers",
        "total_spend":"Total Spend","avg_spend":"Avg Spend","avg_recency":"Avg Recency"}))

# ════════════════════════════════════════════════ SELLER INTELLIGENCE ═════════
with t4:
    import plotly.graph_objects as go
    df = loader.order_features()
    st.markdown("## 🏪 Seller Intelligence")
    st.markdown("<p style='color:#6B5B00;margin-top:-8px;'>Seller performance, rankings and category breakdown</p>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    sellers = (df.groupby("seller_id")
               .agg(orders=("order_id","count"),
                    gmv=("payment_value","sum"),
                    avg_ticket=("payment_value","mean"),
                    late_rate=("is_late","mean"),
                    avg_review=("review_score","mean"),
                    categories=("main_category","nunique"))
               .reset_index())

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Total Sellers",     f"{len(sellers):,}")
    c2.metric("Avg Orders/Seller", f"{sellers['orders'].mean():.1f}")
    c3.metric("Avg GMV/Seller",    f"R$ {sellers['gmv'].mean():,.0f}")
    c4.metric("Avg Review",        f"{sellers['avg_review'].mean():.2f} ⭐")
    st.markdown("<br>", unsafe_allow_html=True)

    col_l,col_r = st.columns(2)
    with col_l:
        top_s = sellers.nlargest(20,"gmv")
        fig = go.Figure(go.Bar(x=top_s["gmv"],y=top_s["seller_id"].str[:8]+"…",
                                orientation="h",marker_color="#FFD400",marker_opacity=.9))
        fig.update_layout(title="Top 20 Sellers by GMV",height=500,**cb())
        fig.update_xaxes(title_text="GMV (R$)")
        st.plotly_chart(fig,use_container_width=True)
    with col_r:
        fig2 = go.Figure(go.Scattergl(
            x=sellers["orders"], y=sellers["avg_review"],
            mode="markers",
            marker=dict(size=5,color=sellers["late_rate"],
                        colorscale=[[0,"#2D7A00"],[.5,"#FFD400"],[1,"#CC2200"]],
                        opacity=.6,showscale=True,
                        colorbar=dict(title="Late Rate",tickfont=dict(color="#000"),
                                     title_font=dict(color="#000"))),
            text=sellers["seller_id"].str[:8],
        ))
        fig2.update_layout(title="Sellers — Orders vs Review Score (color = late rate)",height=500,**cb())
        fig2.update_xaxes(title_text="Number of Orders")
        fig2.update_yaxes(title_text="Avg Review Score")
        st.plotly_chart(fig2,use_container_width=True)

    st.markdown("---")
    col_a,col_b = st.columns(2)
    with col_a:
        cat_perf = (df.groupby("main_category")
                    .agg(sellers=("seller_id","nunique"),orders=("order_id","count"),
                         gmv=("payment_value","sum"),late_rate=("is_late","mean"),
                         avg_review=("review_score","mean"))
                    .sort_values("gmv",ascending=False).head(15).reset_index())
        fig3 = go.Figure(go.Bar(x=cat_perf["gmv"],y=cat_perf["main_category"],
                                 orientation="h",
                                 marker_color=["#FF5F00" if lr>.1 else "#FFD400" for lr in cat_perf["late_rate"]],
                                 marker_opacity=.9))
        fig3.update_layout(title="Top 15 Categories by GMV (red = high late rate)",height=460,**cb())
        fig3.update_xaxes(title_text="GMV (R$)")
        st.plotly_chart(fig3,use_container_width=True)
    with col_b:
        # Late rate distribution among sellers
        fig4 = go.Figure(go.Histogram(x=sellers["late_rate"]*100,nbinsx=40,
                                       marker_color="#FF8C00",marker_opacity=.85))
        med_lr = sellers["late_rate"].median()*100
        fig4.add_vline(x=med_lr,line_color="#CC2200",line_dash="dash",
                       annotation_text=f"Median {med_lr:.1f}%",annotation_font_color="#CC2200")
        fig4.update_layout(title="Seller Late Rate Distribution",height=300,**cb())
        fig4.update_xaxes(title_text="Late Rate (%)")
        st.plotly_chart(fig4,use_container_width=True)

        fig5 = go.Figure(go.Histogram(x=sellers["avg_review"].dropna(),nbinsx=20,
                                       marker_color="#FFD400",marker_opacity=.85))
        fig5.update_layout(title="Seller Review Score Distribution",height=280,**cb())
        fig5.update_xaxes(title_text="Avg Review Score")
        st.plotly_chart(fig5,use_container_width=True)

    st.markdown("---")
    st.markdown('<div class="section-hdr">Top 30 Sellers</div>', unsafe_allow_html=True)
    top30 = sellers.nlargest(30,"gmv").copy()
    top30["seller_id"] = top30["seller_id"].str[:12]+"…"
    top30["gmv"]       = top30["gmv"].apply(lambda x: f"R$ {x:,.0f}")
    top30["avg_ticket"]= top30["avg_ticket"].apply(lambda x: f"R$ {x:.2f}")
    top30["late_rate"] = top30["late_rate"].apply(lambda x: f"{x:.1%}")
    top30["avg_review"]= top30["avg_review"].apply(lambda x: f"{x:.2f} ⭐")
    tbl(top30[["seller_id","orders","gmv","avg_ticket","late_rate","avg_review","categories"]].rename(
        columns={"seller_id":"Seller","orders":"Orders","gmv":"GMV","avg_ticket":"Avg Ticket",
                 "late_rate":"Late Rate","avg_review":"Review","categories":"Categories"}))

# ════════════════════════════════════════════════ ORDER PATTERNS ══════════════
with t5:
    import plotly.graph_objects as go
    import pandas as pd
    df = loader.order_features()
    st.markdown("## 📦 Order Patterns")
    st.markdown("<p style='color:#6B5B00;margin-top:-8px;'>Payment methods, order timing, pricing and review analysis</p>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Total Orders",      f"{len(df):,}")
    c2.metric("Avg Items/Order",   f"{df['order_item_id'].mean():.1f}" if "order_item_id" in df.columns else "N/A")
    c3.metric("Median Order Value",f"R$ {df['payment_value'].median():.2f}")
    c4.metric("Max Order Value",   f"R$ {df['payment_value'].max():,.0f}")
    c5.metric("Avg Review Score",  f"{df['review_score'].mean():.2f} ⭐")
    st.markdown("<br>", unsafe_allow_html=True)

    col_l,col_r = st.columns(2)
    with col_l:
        # Payment type distribution
        if "payment_type" in df.columns:
            pt = df["payment_type"].value_counts().reset_index()
            pt.columns = ["type","count"]
            fig = go.Figure(go.Pie(labels=pt["type"],values=pt["count"],hole=.5,
                                    marker_colors=["#FFD400","#FF8C00","#FF5F00","#FFC300","#C8A000"],
                                    textfont=dict(color="#000",size=12)))
            fig.update_layout(title="Payment Methods",height=360,paper_bgcolor="#fff",
                              font=dict(family="Inter",color="#000",size=11),
                              margin=dict(t=44,b=10,l=10,r=10),legend=dict(font=dict(color="#000")))
            st.plotly_chart(fig,use_container_width=True)
    with col_r:
        # Review score distribution
        rev = df["review_score"].value_counts().sort_index()
        fig2 = go.Figure(go.Bar(x=rev.index,y=rev.values,
                                 marker_color=["#CC2200","#FF8C00","#FFC300","#FFD400","#2D7A00"],
                                 marker_opacity=.9,
                                 text=rev.values,textposition="outside",
                                 textfont=dict(color="#000")))
        fig2.update_layout(title="Review Score Distribution",height=360,**cb())
        fig2.update_xaxes(title_text="Score",tickvals=[1,2,3,4,5])
        fig2.update_yaxes(title_text="Orders")
        st.plotly_chart(fig2,use_container_width=True)

    col_a,col_b = st.columns(2)
    with col_a:
        # Orders by day of week
        if "purchase_dayofweek" in df.columns:
            days = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
            dow  = df.groupby("purchase_dayofweek")["order_id"].count().reindex(range(7),fill_value=0)
            fig3 = go.Figure(go.Bar(x=days,y=dow.values,
                                     marker_color=["#FFD400" if i<5 else "#FF8C00" for i in range(7)],
                                     marker_opacity=.9))
            fig3.update_layout(title="Orders by Day of Week",height=340,**cb())
            fig3.update_yaxes(title_text="Orders")
            st.plotly_chart(fig3,use_container_width=True)
    with col_b:
        # Order value distribution (clipped)
        fig4 = go.Figure(go.Histogram(x=df["payment_value"].clip(0,1000),nbinsx=50,
                                       marker_color="#FFD400",marker_opacity=.85))
        med_val = df["payment_value"].median()
        avg_val = df["payment_value"].mean()
        fig4.add_vline(x=med_val,line_color="#FF8C00",line_dash="dash",
                       annotation_text=f"Median R${med_val:.0f}",annotation_font_color="#FF8C00")
        fig4.add_vline(x=avg_val,line_color="#CC2200",line_dash="dot",
                       annotation_text=f"Avg R${avg_val:.0f}",annotation_font_color="#CC2200")
        fig4.update_layout(title="Order Value Distribution (clipped R$1k)",height=340,**cb())
        fig4.update_xaxes(title_text="Order Value (R$)")
        st.plotly_chart(fig4,use_container_width=True)

    st.markdown("---")
    col_c,col_d = st.columns(2)
    with col_c:
        # Monthly review trend
        rev_trend = df.groupby("purchase_ym")["review_score"].mean().reset_index()
        fig5 = go.Figure(go.Scatter(x=rev_trend["purchase_ym"],y=rev_trend["review_score"],
                                     fill="tozeroy",fillcolor=rgba("#FFD400",.15),
                                     line=dict(color="#FFD400",width=2)))
        fig5.update_layout(title="Monthly Avg Review Score",height=300,**cb())
        fig5.update_yaxes(title_text="Avg Review",range=[3,5])
        st.plotly_chart(fig5,use_container_width=True)
    with col_d:
        # Category avg ticket
        cat_ticket = (df.groupby("main_category")["payment_value"]
                      .mean().sort_values(ascending=False).head(15))
        fig6 = go.Figure(go.Bar(x=cat_ticket.values,y=cat_ticket.index,
                                 orientation="h",marker_color="#FF8C00",marker_opacity=.9))
        fig6.update_layout(title="Top 15 Categories by Avg Ticket",height=440,**cb())
        fig6.update_xaxes(title_text="Avg Order Value (R$)")
        st.plotly_chart(fig6,use_container_width=True)
