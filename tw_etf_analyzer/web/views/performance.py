# -*- coding: utf-8 -*-
"""📊 績效分析分頁(Tab 1)。單筆 vs 定期定額 + 風險指標 + 稅費淨值。"""

from __future__ import annotations

import io

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from tw_etf_analyzer.core.metrics import calc_risk_metrics
from tw_etf_analyzer.core.performance import calc_comparison
from tw_etf_analyzer.core.tax import avg_annual_dividend_yield, calc_tax_drag

from tw_etf_analyzer.web.cache import cached_dividend_history
from tw_etf_analyzer.web.context import AppContext


def render(ctx: AppContext) -> None:
    close_full = ctx.close_full
    min_date = close_full.index[0].date()
    max_date = close_full.index[-1].date()

    with st.expander("⚙️ 自訂分析起始日（預設：上市日）", expanded=False):
        custom_start = st.date_input(
            "分析起始日",
            value=min_date,
            min_value=min_date,
            max_value=max_date,
            key=f"custom_start_date_{ctx.stock_id}",
        )
        if custom_start > min_date:
            st.caption(f"上市日為 {min_date}，目前從 {custom_start} 開始分析")

    close = close_full[close_full.index >= pd.Timestamp(custom_start)]
    if len(close) < 2:
        st.error("所選起始日後資料不足，請選擇更早的日期")
        return

    result = calc_comparison(close, ctx.monthly_dca)
    lump   = result.lump
    dca    = result.dca
    f      = dca.final

    risk = calc_risk_metrics(close)

    # 稅費拖累
    tax_drag = 0.0
    if ctx.tax_cfg.enabled:
        try:
            div_hist = cached_dividend_history(ctx.stock_id, ctx.token)
            div_yield = avg_annual_dividend_yield(div_hist, close)
            tax_drag = calc_tax_drag(div_yield, f.value, ctx.tax_cfg)
        except Exception:
            tax_drag = 0.0

    sfx = ctx.real_sfx
    st.subheader(
        f"{ctx.stock_id}　{lump.inception_date.date()} ～ {lump.last_date.date()}　({lump.years:.1f} 年)"
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("單筆總報酬",                   f"{lump.total_return_pct:+,.1f}%")
    c2.metric(f"單筆年化報酬 {sfx}",          f"{ctx.display_cagr_pct(lump.cagr_pct):+.2f}%")
    c3.metric("定期定額總報酬",               f"{f.return_pct:+.1f}%")
    c4.metric(f"定期定額年化報酬 {sfx}",       f"{ctx.display_cagr_pct(result.dca_cagr_pct):+.2f}%")

    # 風險調整報酬指標
    st.markdown("#### 📉 風險調整報酬指標")
    rk1, rk2, rk3, rk4, rk5 = st.columns(5)
    rk1.metric("年化波動度",   f"{risk.vol_pct:.2f}%")
    rk2.metric(
        "最大回撤",
        f"{risk.mdd_pct:.2f}%",
        help=(
            f"Peak: {risk.mdd_peak_date.date() if risk.mdd_peak_date else '—'} → "
            f"Trough: {risk.mdd_trough_date.date() if risk.mdd_trough_date else '—'} → "
            f"Recovery: {risk.mdd_recovery_date.date() if risk.mdd_recovery_date else '尚未回復'}"
        ),
    )
    rk3.metric("Sharpe Ratio",  f"{risk.sharpe:.2f}",  help="(CAGR - Rf=0) / 年化波動度")
    rk4.metric("Sortino Ratio", f"{risk.sortino:.2f}", help="(CAGR - Rf=0) / 下行波動度,只懲罰虧損")
    rk5.metric("Calmar Ratio",  f"{risk.calmar:.2f}",  help="CAGR / |MDD|,衡量回撤下的報酬效率")

    # 稅費扣除後摘要
    if ctx.tax_cfg.enabled:
        st.markdown("#### 💸 扣除稅費後(淨值)")
        net_cagr_pct = ctx.display_cagr_pct((lump.cagr_pct / 100 - tax_drag) * 100)
        gross_final  = f.value
        drag_factor  = (1 - tax_drag) ** lump.years
        buy_factor   = (1 - ctx.tax_cfg.buy_fee_rate)
        net_final    = gross_final * drag_factor * buy_factor
        net_final_disp   = ctx.display_value(net_final,   lump.years)
        gross_final_disp = ctx.display_value(gross_final, lump.years)
        nx1, nx2, nx3 = st.columns(3)
        nx1.metric(f"淨年化(扣稅費) {sfx}", f"{net_cagr_pct:+.2f}%")
        nx2.metric(f"DCA 淨終值 {sfx}",       f"{net_final_disp:,.0f} TWD",
                   delta=f"{net_final_disp - gross_final_disp:+,.0f}")
        nx3.metric("年化稅費拖累",             f"{tax_drag*100:.2f}%",
                   help="股利稅 + 二代健保相對於總資產的年化拖累率(近似)")

    # 逐年績效表
    st.subheader(f"定期定額每月 {ctx.monthly_dca:,.0f} TWD — 逐年績效")
    df = pd.DataFrame([{
        "年度":        r.year,
        "累計投入":    f"{r.cost_cum:,.0f}",
        "期末市值":    f"{r.value:,.0f}",
        "未實現損益":  r.gain,
        "累計報酬率%": f"{r.return_pct:.1f}",
    } for r in dca.years])

    def _red_if_neg(v):
        if isinstance(v, (int, float)):
            return "color: red" if v < 0 else ""
        if isinstance(v, str):
            return "color: red" if v.lstrip().startswith("-") else ""
        return ""

    st.dataframe(
        df.style.map(
            _red_if_neg,
            subset=["未實現損益", "累計報酬率%"],
        ).format({"未實現損益": "{:,.0f}"}),
        width="stretch", hide_index=True,
    )

    # 折線圖
    st.subheader("期末市值 vs 累計投入")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["年度"], y=df["期末市值"], name="期末市值", mode="lines+markers"))
    fig.add_trace(go.Scatter(x=df["年度"], y=df["累計投入"], name="累計投入",
                              mode="lines+markers", line=dict(dash="dash")))
    fig.update_layout(xaxis_title="年度", yaxis_title="TWD", hovermode="x unified")
    st.plotly_chart(fig, width="stretch")

    # 單筆 vs 定期定額
    st.subheader("單筆 vs 定期定額 對照（同等本金）")
    inception = lump.inception_date.strftime("%Y-%m-%d")
    cmp = pd.DataFrame([
        {"項目": "開始投入日期",  "單筆投入": inception,                             "定期定額": inception},
        {"項目": "總本金 (TWD)", "單筆投入": f"{f.cost_cum:,.0f}",                  "定期定額": f"{f.cost_cum:,.0f}"},
        {"項目": "終值 (TWD)",   "單筆投入": f"{result.lump_same_cost_final:,.0f}",  "定期定額": f"{f.value:,.0f}"},
        {"項目": "總報酬",       "單筆投入": f"{result.lump_same_cost_ret:.1f}%",    "定期定額": f"{f.return_pct:.2f}%"},
        {"項目": "年化報酬",     "單筆投入": f"{result.lump_same_cost_cagr:.2f}%",   "定期定額": f"{result.dca_cagr_pct:.2f}%"},
    ])
    st.dataframe(cmp, width="stretch", hide_index=True)

    # 下載
    st.divider()
    st.subheader("下載結果")

    excel_bytes = _build_excel(ctx.stock_id, ctx.monthly_dca, lump, result, df, cmp)
    filename    = f"{ctx.stock_id}_績效分析_{lump.last_date.strftime('%Y%m%d')}.xlsx"

    dl1, dl2 = st.columns(2)
    dl1.download_button(
        label     = "⬇️ 下載 Excel（含三個工作表）",
        data      = excel_bytes,
        file_name = filename,
        mime      = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width     = "stretch",
    )
    csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
    dl2.download_button(
        label     = "⬇️ 下載 CSV（逐年績效）",
        data      = csv_bytes,
        file_name = f"{ctx.stock_id}_逐年績效_{lump.last_date.strftime('%Y%m%d')}.csv",
        mime      = "text/csv",
        width     = "stretch",
    )


def _build_excel(stock_id, monthly_dca, lump, result, df, cmp) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        summary = pd.DataFrame([
            {"項目": "股票代號",        "數值": stock_id},
            {"項目": "資料起始日",      "數值": str(lump.inception_date.date())},
            {"項目": "最新資料日",      "數值": str(lump.last_date.date())},
            {"項目": "持有年數",        "數值": round(lump.years, 2)},
            {"項目": "每月定期定額",    "數值": monthly_dca},
            {"項目": "單筆總報酬%",     "數值": round(lump.total_return_pct, 2)},
            {"項目": "單筆年化報酬%",   "數值": round(lump.cagr_pct, 2)},
            {"項目": "定期定額總報酬%", "數值": round(result.dca.final.return_pct, 2)},
            {"項目": "定期定額年化%",   "數值": round(result.dca_cagr_pct, 2)},
        ])
        summary.to_excel(writer, sheet_name="摘要", index=False)
        df.to_excel(writer, sheet_name="逐年績效", index=False)
        cmp.to_excel(writer, sheet_name="單筆vs定期定額", index=False)
    return buf.getvalue()
