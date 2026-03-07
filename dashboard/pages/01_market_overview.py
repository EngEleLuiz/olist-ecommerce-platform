"""Market Overview — GMV, order volume, geographic distribution, categories."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
from app import get_loader, render_sidebar
from dashboard.charts import (
    monthly_volume_bar,
    state_bar,
    category_treemap,
    review_score_bar,
)

render_sidebar()

st.markdown("# 📊 Market Overview")
st.markdown(
    "<p style='color:#4e6278;margin-top:-8px;'>Revenue, volume and geographic breakdown</p>",
    unsafe_allow_html=True,
)
st.markdown("<br>", unsafe_allow_html=True)

loader = get_loader()
df = loader.order_features()
kpi = loader.summary()

# ── KPIs ──────────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total GMV", f"R$ {df['payment_value'].sum():,.0f}")
c2.metric("Total Orders", f"{len(df):,}")
c3.metric("Avg Order Value", f"R$ {df['payment_value'].mean():.2f}")
c4.metric("Unique Customers", f"{df['customer_unique_id'].nunique():,}")
c5.metric("Active States", f"{df['customer_state'].nunique()}")

st.markdown("<br>", unsafe_allow_html=True)

# ── Volume trend ──────────────────────────────────────────────────────────────
st.plotly_chart(monthly_volume_bar(df), use_container_width=True)

# ── Geography + Categories ────────────────────────────────────────────────────
col_l, col_r = st.columns(2)
with col_l:
    metric = st.selectbox(
        "State metric",
        ["gmv", "order_count", "payment_value"],
        format_func=lambda x: {
            "gmv": "GMV",
            "order_count": "Orders",
            "payment_value": "Payment Value",
        }[x],
    )
    # Recompute for selected metric
    state_agg = (
        df.groupby("customer_state")
        .agg(
            gmv=("payment_value", "sum"),
            order_count=("order_id", "count"),
            payment_value=("payment_value", "mean"),
        )
        .reset_index()
    )
    st.plotly_chart(
        state_bar(
            df if metric == "gmv" else df,
            metric=metric,
            title=f"{metric.upper().replace('_', ' ')} by State",
        ),
        use_container_width=True,
    )
with col_r:
    st.plotly_chart(category_treemap(df), use_container_width=True)

# ── Region breakdown ──────────────────────────────────────────────────────────
st.markdown("---")
st.markdown('<div class="section-header">Revenue by Region</div>', unsafe_allow_html=True)

region_df = (
    df.groupby("customer_region")
    .agg(
        gmv=("payment_value", "sum"),
        orders=("order_id", "count"),
        late_rate=("is_late", "mean"),
        avg_review=("review_score", "mean"),
    )
    .reset_index()
    .sort_values("gmv", ascending=False)
)
region_df["gmv_share"] = (region_df["gmv"] / region_df["gmv"].sum() * 100).round(1)
region_df["gmv"] = region_df["gmv"].apply(lambda x: f"R$ {x:,.0f}")
region_df["late_rate"] = region_df["late_rate"].apply(lambda x: f"{x:.1%}")
region_df["avg_review"] = region_df["avg_review"].apply(lambda x: f"{x:.2f} ⭐")
region_df["gmv_share"] = region_df["gmv_share"].apply(lambda x: f"{x}%")

st.dataframe(
    region_df.rename(
        columns={
            "customer_region": "Region",
            "gmv": "GMV",
            "orders": "Orders",
            "late_rate": "Late Rate",
            "avg_review": "Avg Review",
            "gmv_share": "GMV Share",
        }
    ),
    hide_index=True,
    use_container_width=True,
)

# ── Reviews ───────────────────────────────────────────────────────────────────
st.markdown("---")
col_a, col_b = st.columns([1, 2])
with col_a:
    st.plotly_chart(review_score_bar(df), use_container_width=True)
with col_b:
    st.markdown(
        '<div class="section-header">Top 15 Categories by GMV</div>', unsafe_allow_html=True
    )
    cat_df = (
        df.groupby("main_category")
        .agg(
            gmv=("payment_value", "sum"),
            orders=("order_id", "count"),
            late_rate=("is_late", "mean"),
            avg_review=("review_score", "mean"),
        )
        .sort_values("gmv", ascending=False)
        .head(15)
        .reset_index()
    )
    cat_df["gmv"] = cat_df["gmv"].apply(lambda x: f"R$ {x:,.0f}")
    cat_df["late_rate"] = cat_df["late_rate"].apply(lambda x: f"{x:.1%}")
    cat_df["avg_review"] = cat_df["avg_review"].apply(lambda x: f"{x:.2f}")
    st.dataframe(
        cat_df.rename(
            columns={
                "main_category": "Category",
                "gmv": "GMV",
                "orders": "Orders",
                "late_rate": "Late Rate",
                "avg_review": "Review",
            }
        ),
        hide_index=True,
        use_container_width=True,
        height=350,
    )
