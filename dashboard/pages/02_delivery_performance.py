"""Delivery Performance — SLA, delays, state-level breakdown."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from app import get_loader, render_sidebar
from dashboard.charts import (delay_histogram, estimated_vs_actual,
                               late_rate_by_state, sla_donut)

render_sidebar()

st.markdown("# 🚚 Delivery Performance")
st.markdown("<p style='color:#6B5B00;margin-top:-8px;'>SLA compliance, delay distribution and state-level breakdown</p>",
            unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

loader = get_loader()
df     = loader.order_features()
deliv  = df[df["order_status"] == "delivered"]

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Delivered Orders", f"{len(deliv):,}")
on_time_rate = (deliv["is_late"] == 0).mean()
late_rate    = (deliv["is_late"] == 1).mean()
c2.metric("On-Time Rate", f"{on_time_rate:.1%}")
c3.metric("Late Rate",    f"{late_rate:.1%}")
c4.metric("Avg Delay",        f"{deliv['delay_days'].mean():.1f} days")
c5.metric("Avg Actual Days",  f"{deliv['actual_days'].mean():.1f} days")

st.markdown("<br>", unsafe_allow_html=True)

col_l, col_r = st.columns([1, 1])
with col_l:
    st.plotly_chart(delay_histogram(df), use_container_width=True)
with col_r:
    st.plotly_chart(sla_donut(df), use_container_width=True)

st.plotly_chart(late_rate_by_state(df), use_container_width=True)
st.plotly_chart(estimated_vs_actual(df), use_container_width=True)
