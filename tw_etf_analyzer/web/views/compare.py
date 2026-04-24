# -*- coding: utf-8 -*-
"""📈 多檔比較 + 相關性矩陣(Tab 5)。"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from tw_etf_analyzer.core.metrics import calc_correlation_matrix, calc_risk_metrics
from tw_etf_analyzer.core.performance import calc_multi_compare
from tw_etf_analyzer.core.tax import avg_annual_dividend_yield, calc_tax_drag

from tw_etf_analyzer.web.cache import cached_adjusted_close, cached_dividend_history
from tw_etf_analyzer.web.context import AppContext


def render(ctx: AppContext) -> None:
    st.subheader("📊 多檔績效比較")
    st.caption("選 2～5 檔股票／ETF，以上市最晚的日期為共同起點比較報酬")

    cols = st.columns(5)
    inputs = [
        cols[i].text_input(f"代號 {i+1}", key=f"_w_cmp_{i}", placeholder="例如 0050")
        for i in range(5)
    ]
    ids = [v.strip().upper().removesuffix(".TW") for v in inputs if v.strip()]

    if len(ids) < 2:
        st.info("請至少輸入 2 個股票代號")
        return

    with st.spinner("載入比較資料..."):
        closes: dict = {}
        errors: list = []
        for sid in ids:
            try:
                c, _ = cached_adjusted_close(sid, ctx.token)
                closes[sid] = c
            except Exception as e:
                errors.append(f"{sid}：{e}")
        for err in errors:
            st.warning(err)

    if len(closes) < 2:
        return

    try:
        records = calc_multi_compare(closes, ctx.monthly_dca)
    except Exception as e:
        st.error(f"比較計算失敗:{e}")
        return

    common_start = records[0].common_start.date()
    last_date    = max(r.normalized.index[-1] for r in records)

    st.caption(f"共同起始日：{common_start}　最新資料：{last_date.date()}")

    fig2 = go.Figure()
    for r in records:
        fig2.add_trace(go.Scatter(
            x=r.normalized.index, y=r.normalized.values,
            name=r.stock_id, mode="lines",
        ))
    fig2.add_hline(y=100, line_dash="dot", line_color="gray")
    fig2.update_layout(
        xaxis_title="日期", yaxis_title="指數（起始=100）",
        hovermode="x unified", legend_title="代號",
    )
    st.plotly_chart(fig2, width="stretch")

    # 每檔風險指標(從共同起始日起算)
    risk_map: dict = {}
    for sid, c in closes.items():
        sliced = c[c.index >= records[0].common_start].dropna()
        if len(sliced) >= 2:
            risk_map[sid] = calc_risk_metrics(sliced)

    # 稅費拖累:每檔獨立抓股利歷史
    tax_drag_map: dict[str, float] = {}
    if ctx.tax_cfg.enabled:
        for sid in closes:
            try:
                dh = cached_dividend_history(sid, ctx.token)
                y = avg_annual_dividend_yield(dh, closes[sid])
                dca_final = next((r.dca_final for r in records if r.stock_id == sid), 0.0)
                tax_drag_map[sid] = calc_tax_drag(y, dca_final, ctx.tax_cfg)
            except Exception:
                tax_drag_map[sid] = 0.0
    years_cmp = records[0].years

    def _row_fn(r):
        return {
            "代號":         r.stock_id,
            "原始上市日":   str(r.inception_date.date()),
            "共同起始日":   str(r.common_start.date()),
            "比較年數":     f"{r.years:.2f}",
            "總報酬%":      f"{r.total_return_pct:.1f}",
            "年化報酬%":    round(ctx.display_cagr_pct(r.cagr_pct), 2),
            "MDD%":         round(risk_map[r.stock_id].mdd_pct, 1)   if r.stock_id in risk_map else 0.0,
            "Sharpe":       round(risk_map[r.stock_id].sharpe,  2)   if r.stock_id in risk_map else 0.0,
            "Sortino":      round(risk_map[r.stock_id].sortino, 2)   if r.stock_id in risk_map else 0.0,
            "Calmar":       round(risk_map[r.stock_id].calmar,  2)   if r.stock_id in risk_map else 0.0,
            "淨CAGR%":      round(ctx.display_cagr_pct((r.cagr_pct / 100 - tax_drag_map.get(r.stock_id, 0.0)) * 100), 2),
            f"DCA終值(月投{ctx.monthly_dca:,.0f})":
                f"{ctx.display_value(r.dca_final * ((1 - tax_drag_map.get(r.stock_id, 0.0)) ** years_cmp if ctx.tax_cfg.enabled else 1.0), years_cmp):,.0f}",
            "DCA年化%":     f"{ctx.display_cagr_pct(r.dca_cagr_pct - tax_drag_map.get(r.stock_id, 0.0) * 100):.2f}",
        }

    cmp_df = pd.DataFrame([_row_fn(r) for r in records])
    if not ctx.tax_cfg.enabled:
        cmp_df = cmp_df.drop(columns=["淨CAGR%"])

    max_cagr = max(x for x in cmp_df["年化報酬%"] if isinstance(x, (float, int)))
    st.dataframe(
        cmp_df.style.map(
            lambda v: "color: green; font-weight: bold"
            if isinstance(v, (float, int)) and v == max_cagr else "",
            subset=["年化報酬%"],
        ).format({
            "年化報酬%": "{:.2f}",
            "MDD%":      "{:.1f}",
            "Sharpe":    "{:.2f}",
            "Sortino":   "{:.2f}",
            "Calmar":    "{:.2f}",
        }),
        width="stretch", hide_index=True,
    )

    # ── 相關性矩陣 ────────────────────────────────────────────────────────────
    st.markdown("#### 🔗 月報酬相關性矩陣")
    st.caption("低相關的資產組合有利於分散風險;1 = 完全正相關、0 = 無關、−1 = 反向")
    corr = calc_correlation_matrix({sid: c for sid, c in closes.items()})
    if not corr.empty:
        fig_corr = go.Figure(data=go.Heatmap(
            z            = corr.values,
            x            = corr.columns.tolist(),
            y            = corr.index.tolist(),
            colorscale   = "RdBu",
            zmin         = -1, zmax = 1, zmid = 0,
            text         = corr.round(2).values,
            texttemplate = "%{text}",
            textfont     = dict(size=13),
            hovertemplate= "%{y} ↔ %{x}<br>相關係數: %{z:.3f}<extra></extra>",
            colorbar     = dict(title="相關係數"),
        ))
        # 強制 categorical axis,避免 "0050" 被當數字 50 解讀
        fig_corr.update_xaxes(type="category", side="bottom")
        fig_corr.update_yaxes(type="category", autorange="reversed")
        fig_corr.update_layout(height=max(320, 80 * len(corr)))
        st.plotly_chart(fig_corr, width="stretch")

    cmp_csv = cmp_df.drop(columns=["原始上市日"]).to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label     = "⬇️ 下載比較結果 CSV",
        data      = cmp_csv,
        file_name = f"多檔比較_{'_'.join(r.stock_id for r in records)}_{last_date.strftime('%Y%m%d')}.csv",
        mime      = "text/csv",
    )
