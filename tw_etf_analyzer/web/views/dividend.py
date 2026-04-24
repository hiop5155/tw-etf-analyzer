# -*- coding: utf-8 -*-
"""💰 股利歷史分頁(Tab 6)。"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from tw_etf_analyzer.web.cache import cached_dividend_history
from tw_etf_analyzer.web.context import AppContext


def render(ctx: AppContext) -> None:
    st.subheader("💰 股利發放歷史")

    with st.spinner("載入股利資料..."):
        try:
            div_df = cached_dividend_history(ctx.stock_id, ctx.token)
        except Exception as e:
            st.error(f"載入股利資料失敗:{e}")
            st.stop()

    if div_df.empty:
        st.info(f"{ctx.stock_id} 無股利發放記錄(可能為非配息型股票/ETF)")
        return

    avg_yield = div_df["yield_pct"].mean()
    total_div = div_df["cash_dividend"].sum()
    dc1, dc2, dc3 = st.columns(3)
    dc1.metric("發放次數",       f"{len(div_df)} 次")
    dc2.metric("歷史平均殖利率", f"{avg_yield:.2f}%")
    dc3.metric("累計配息",       f"{total_div:.2f} TWD/股")

    # 年度彙總雙軸圖
    annual = (
        div_df.groupby("year")
        .agg(total_cash=("cash_dividend", "sum"), avg_yield=("yield_pct", "mean"))
        .reset_index()
    )
    fig_div = go.Figure()
    fig_div.add_trace(go.Bar(
        x=annual["year"], y=annual["total_cash"],
        name="年度配息 (TWD/股)", marker_color="steelblue", yaxis="y",
    ))
    fig_div.add_trace(go.Scatter(
        x=annual["year"], y=annual["avg_yield"],
        name="平均殖利率 %", mode="lines+markers",
        line=dict(color="orange"), yaxis="y2",
    ))
    fig_div.update_layout(
        xaxis_title="年度",
        yaxis=dict(title="配息金額 (TWD/股)"),
        yaxis2=dict(title="殖利率 %", overlaying="y", side="right"),
        hovermode="x unified",
        legend=dict(orientation="h", y=1.1),
    )
    st.plotly_chart(fig_div, width="stretch")

    with st.expander("查看完整股利明細", expanded=False):
        show_df = div_df[["date", "cash_dividend", "before_price", "after_price", "yield_pct"]].copy()
        show_df["date"] = pd.to_datetime(show_df["date"]).dt.strftime("%Y-%m-%d")
        show_df.columns = ["除息日", "配息(TWD/股)", "除息前股價", "除息後股價", "殖利率%"]
        st.dataframe(
            show_df.style.format({
                "配息(TWD/股)": "{:.4f}",
                "除息前股價":   "{:.2f}",
                "除息後股價":   "{:.2f}",
                "殖利率%":      "{:.2f}",
            }),
            width="stretch", hide_index=True,
        )
