# -*- coding: utf-8 -*-
"""📄 PDF 報告匯出分頁(Tab 8)。勾選分頁 → 組裝 PDFReportBuilder → 下載。"""

from __future__ import annotations

import traceback
from datetime import date as _date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from tw_etf_analyzer.core.metrics import calc_correlation_matrix, calc_return_vol, calc_risk_metrics
from tw_etf_analyzer.core.performance import (
    calc_comparison, calc_lump_sum, calc_multi_compare, calc_target_monthly,
)
from tw_etf_analyzer.core.simulation import run_gk_historical, simulate_gk_montecarlo
from tw_etf_analyzer.pdf.builder import PDFReportBuilder

from tw_etf_analyzer.web.cache import cached_adjusted_close, cached_dividend_history
from tw_etf_analyzer.web.context import AppContext
from tw_etf_analyzer.web.presets import PRESETS, get_preset


_PDF_DEFAULTS = {
    "_pdf_perf":    True,
    "_pdf_target":  False,
    "_pdf_retire":  True,
    "_pdf_stress":  False,
    "_pdf_track":   False,
    "_pdf_compare": False,
    "_pdf_div":     False,
}


def render(ctx: AppContext) -> None:
    st.subheader("📄 PDF 報告匯出")
    st.caption("勾選要包含的分析區塊,產生繁中 PDF 報告(Noto Sans CJK TC 內嵌)。")

    # 第一次進入時才 seed 預設值,之後由 session_state 驅動(避免 Streamlit 警告)
    for k, v in _PDF_DEFAULTS.items():
        st.session_state.setdefault(k, v)

    opts = {
        "perf":    st.checkbox("📊 績效分析 + 風險指標",            key="_pdf_perf"),
        "target":  st.checkbox("🎯 目標試算",                        key="_pdf_target"),
        "retire":  st.checkbox("🏖️ 退休提領模擬(MC 結果)",           key="_pdf_retire"),
        "stress":  st.checkbox("⚠️ 壓力測試(3 情境)",                key="_pdf_stress"),
        "track":   st.checkbox("📋 提領追蹤(單次歷史回測)",          key="_pdf_track"),
        "compare": st.checkbox("📈 多檔比較 + 相關性(需先輸入代號)", key="_pdf_compare"),
        "div":     st.checkbox("💰 股利歷史",                        key="_pdf_div"),
    }

    btn_disabled = not any(opts.values())
    if btn_disabled:
        st.warning("請至少勾選一個分頁")
        return

    if not st.button("📄 產生 PDF", type="primary", disabled=btn_disabled):
        return

    with st.spinner("產生 PDF 中(圖表轉 PNG 可能需要 10-30 秒)..."):
        builder = PDFReportBuilder(
            title    = "台股績效分析報告",
            subtitle = f"{ctx.stock_id} · 至 {pd.Timestamp.today().date()}",
            meta     = {
                "股票代號": ctx.stock_id,
                "每月定投": f"{ctx.monthly_dca:,.0f} TWD",
                "稅費計算": "啟用" if ctx.tax_cfg.enabled else "未啟用",
                "報酬模式": "實質" if ctx.is_real else "名目",
                "產生日期": pd.Timestamp.today().strftime("%Y-%m-%d %H:%M"),
            },
        )

        if opts["perf"]:
            _add_performance_section(builder, ctx)
        if opts["target"]:
            _add_target_section(builder, ctx)
        if opts["retire"]:
            _add_retire_section(builder, ctx)
        if opts["stress"]:
            _add_stress_section(builder, ctx)
        if opts["track"]:
            _add_tracking_section(builder, ctx)
        if opts["compare"]:
            _add_compare_section(builder, ctx)
        if opts["div"]:
            _add_dividend_section(builder, ctx)

        try:
            pdf_bytes = builder.build()
            fname = f"tw-etf-report_{ctx.stock_id}_{pd.Timestamp.today().strftime('%Y%m%d')}.pdf"
            st.success(f"✅ 已產生 PDF:{len(pdf_bytes):,} bytes({len(pdf_bytes)/1024:.0f} KB)")
            st.download_button(
                label     = "⬇️ 下載 PDF 報告",
                data      = pdf_bytes,
                file_name = fname,
                mime      = "application/pdf",
                type      = "primary",
            )
        except Exception as e:
            st.error(f"PDF 產生失敗:{e}")
            st.code(traceback.format_exc())


def _add_performance_section(builder: PDFReportBuilder, ctx: AppContext) -> None:
    cmp_r = calc_comparison(ctx.close_full, ctx.monthly_dca)
    lump_r, dca_r = cmp_r.lump, cmp_r.dca
    rm = calc_risk_metrics(ctx.close_full)
    builder.add_metrics(f"績效分析 — {ctx.stock_id} ({lump_r.years:.1f} 年)", [
        ("單筆總報酬",   f"{lump_r.total_return_pct:+,.1f}%"),
        ("單筆年化",     f"{ctx.display_cagr_pct(lump_r.cagr_pct):+.2f}%"),
        ("DCA 年化",     f"{ctx.display_cagr_pct(cmp_r.dca_cagr_pct):+.2f}%"),
        ("最大回撤",     f"{rm.mdd_pct:.2f}%"),
        ("Sharpe",       f"{rm.sharpe:.2f}"),
        ("Sortino",      f"{rm.sortino:.2f}"),
        ("Calmar",       f"{rm.calmar:.2f}"),
        ("年化波動度",   f"{rm.vol_pct:.2f}%"),
    ])
    dca_df = pd.DataFrame([{
        "年度":        r.year,
        "累計投入":    f"{r.cost_cum:,.0f}",
        "期末市值":    f"{r.value:,.0f}",
        "未實現損益":  f"{r.gain:,.0f}",
        "累計報酬率%": f"{r.return_pct:.1f}",
    } for r in dca_r.years])
    builder.add_table("定期定額逐年績效", dca_df)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[r.year for r in dca_r.years], y=[r.value for r in dca_r.years],
                              name="期末市值", mode="lines+markers"))
    fig.add_trace(go.Scatter(x=[r.year for r in dca_r.years], y=[r.cost_cum for r in dca_r.years],
                              name="累計投入", mode="lines+markers", line=dict(dash="dash")))
    fig.update_layout(title=f"{ctx.stock_id} 期末市值 vs 累計投入",
                       xaxis_title="年度", yaxis_title="TWD")
    builder.add_chart("績效走勢", fig)


def _add_target_section(builder: PDFReportBuilder, ctx: AppContext) -> None:
    lump_full = calc_lump_sum(ctx.close_full)
    t_wan = st.session_state.get("_w_target_wan", 500)
    t_yrs = st.session_state.get("_w_target_years", 10)
    t_exist = st.session_state.get("_w_existing", 0)
    tr = calc_target_monthly(t_wan * 10_000, t_yrs, lump_full.cagr_pct, existing=t_exist * 10_000)
    builder.add_metrics(f"目標試算 — {t_wan} 萬 / {t_yrs} 年 / CAGR {lump_full.cagr_pct:.2f}%", [
        ("每月需投入",       f"{tr['monthly']:,.0f} TWD"),
        ("一次性投入等效",   f"{tr['lump_sum_today']:,.0f} TWD"),
        ("新增投入本金",     f"{tr['total_invested']:,.0f} TWD"),
        ("預估最終終值",     f"{tr['terminal_value']:,.0f} TWD"),
    ])


def _resolve_retire_portfolio() -> list[dict]:
    """依退休頁 session_state 決定投組(自訂 or preset)。"""
    pf_df = st.session_state.get("_custom_df_value")
    preset = st.session_state.get("preset_choice", "保守配息型（預設）")
    if preset == "自訂" and pf_df is not None:
        return pf_df[["代號", "配置比例 %"]].to_dict("records")
    return get_preset(preset)


def _add_retire_section(builder: PDFReportBuilder, ctx: AppContext) -> None:
    ra = st.session_state.get("_w_rasset", 2000) * 10_000
    ry = st.session_state.get("_w_ryears", 30)
    rr = st.session_state.get("_w_rrate", 5.0) / 100
    rg = st.session_state.get("_w_rguard", 20.0) / 100
    rf = st.session_state.get("_w_rinf", 2.0) / 100

    pf_rows = _resolve_retire_portfolio()
    w_ret, w_vol = 0.0, 0.0
    for row in pf_rows:
        code = str(row["代號"]).strip().upper()
        weight = row["配置比例 %"] / 100
        if code == "現金":
            continue
        try:
            c, _ = cached_adjusted_close(code, ctx.token)
            cagr_i, vol_i = calc_return_vol(c)
            w_ret += weight * cagr_i
            w_vol += weight * vol_i
        except Exception:
            pass

    mc = simulate_gk_montecarlo(
        initial_portfolio = ra,
        initial_rate      = rr,
        guardrail_pct     = rg,
        annual_return     = w_ret,
        annual_volatility = w_vol,
        inflation_rate    = rf,
        years             = int(ry),
        n_sims            = 1000,
    )
    builder.add_metrics(
        f"退休提領 MC — {ra/10_000:,.0f} 萬 / {ry} 年 / 提領率 {rr*100:.1f}%",
        [
            ("加權年化報酬",     f"{w_ret*100:.2f}%"),
            ("加權波動度",       f"{w_vol*100:.2f}%"),
            ("初始月提領",       f"{mc['initial_monthly']:,.0f} TWD"),
            (f"第{ry}年存活率",  f"{mc['survival_final']:.1f}%"),
            ("P50 期末資產",     f"{mc['port_pct'][50][-1]/10_000:,.0f} 萬"),
            ("P10 期末資產",     f"{mc['port_pct'][10][-1]/10_000:,.0f} 萬"),
        ],
    )
    yrs_pdf = mc["years"]
    fig_mc = go.Figure()
    for p, col, da in [(50, "steelblue", "solid"), (10, "tomato", "dash"), (90, "seagreen", "dash")]:
        fig_mc.add_trace(go.Scatter(
            x=yrs_pdf, y=mc["port_pct"][p] / 10_000,
            name=f"P{p}", mode="lines", line=dict(color=col, dash=da),
        ))
    fig_mc.update_layout(title="資產百分位",
                          xaxis_title="退休後第幾年",
                          yaxis_title="資產餘額(萬 TWD)")
    builder.add_chart("資產百分位圖(P10/P50/P90)", fig_mc)
    builder.add_table("投組配置", pd.DataFrame(pf_rows))


def _add_stress_section(builder: PDFReportBuilder, ctx: AppContext) -> None:
    try:
        proxy_cl, _ = cached_adjusted_close("0050", ctx.token)
        preset = st.session_state.get("preset_choice", "保守配息型（預設）")
        s_rows = get_preset(preset)
        s_alloc = {
            str(r["代號"]).strip().upper(): r["配置比例 %"] / 100
            for r in s_rows
        }
        s_alloc = {("現金" if k in ("現金", "CASH") else k): v for k, v in s_alloc.items()}
        s_asset = st.session_state.get("_w_rasset", 2000) * 10_000

        scenarios_pdf = [("2008-01", "2008 金融海嘯"), ("2020-02", "2020 COVID"), ("2022-01", "2022 升息")]
        summary = []
        for sym, sname in scenarios_pdf:
            start_ts = pd.Timestamp(sym + "-01")
            close_map = {}
            for a in s_alloc:
                if a == "現金":
                    continue
                try:
                    c, _ = cached_adjusted_close(a, ctx.token)
                    if c.index[0] > start_ts:
                        seg = proxy_cl[(proxy_cl.index >= start_ts) & (proxy_cl.index <= c.index[0])]
                        if not seg.empty:
                            scale = float(c.iloc[0]) / float(seg.iloc[-1])
                            c = pd.concat([(seg[:-1] * scale), c]).sort_index()
                            c = c[~c.index.duplicated(keep="last")]
                    close_map[a] = c
                except Exception:
                    pass
            try:
                rs = run_gk_historical(
                    initial_portfolio=s_asset, allocations=s_alloc,
                    start_ym=sym, initial_rate=st.session_state.get("_w_rrate", 5.0) / 100,
                    guardrail_pct=st.session_state.get("_w_rguard", 20.0) / 100,
                    inflation_rate=st.session_state.get("_w_rinf", 2.0) / 100,
                    close_series=close_map,
                )
                summary.append({
                    "情境":         sname,
                    "起點":         sym,
                    "歷時(年)":     f"{len(rs['monthly'])/12:.1f}",
                    "目前資產(萬)": f"{rs['final_portfolio']/10_000:,.0f}",
                    "月提領(TWD)":  f"{rs['final_monthly_income']:,.0f}",
                })
            except Exception:
                pass
        if summary:
            builder.add_table("壓力測試 — 3 歷史情境", pd.DataFrame(summary))
    except Exception as e:
        builder.add_text("壓力測試", f"資料載入失敗:{e}")


def _add_tracking_section(builder: PDFReportBuilder, ctx: AppContext) -> None:
    try:
        tk_port  = st.session_state.get("_w_tk6_port", 2000) * 10_000
        tk_rate  = st.session_state.get("_w_tk6_rate", 4.0) / 100
        tk_guard = st.session_state.get("_w_tk6_guard", 20) / 100
        tk_inf   = st.session_state.get("_w_tk6_infl", 2.0) / 100
        tk_start = st.session_state.get("_w_tk6_start", _date(2024, 1, 1))
        tk_alloc_df = st.session_state.get("tk6_alloc_df")
        if tk_alloc_df is None:
            return
        tk_alloc = {
            str(r["代號"]).strip().upper(): r["配置比例 %"] / 100
            for _, r in tk_alloc_df.iterrows()
            if str(r["代號"]).strip() and r["配置比例 %"] > 0
        }
        tk_alloc = {("現金" if k in ("現金", "CASH") else k): v for k, v in tk_alloc.items()}
        tk_close: dict[str, pd.Series] = {}
        for a in tk_alloc:
            if a == "現金":
                continue
            try:
                c, _ = cached_adjusted_close(a, ctx.token)
                tk_close[a] = c
            except Exception:
                pass
        tk_r = run_gk_historical(
            initial_portfolio=tk_port,
            allocations=tk_alloc,
            start_ym=tk_start.strftime("%Y-%m"),
            initial_rate=tk_rate,
            guardrail_pct=tk_guard,
            inflation_rate=tk_inf,
            close_series=tk_close,
        )
        builder.add_metrics(
            f"提領追蹤 — {tk_port/10_000:,.0f} 萬 / 從 {tk_start.strftime('%Y-%m')} 起",
            [
                ("目前資產",     f"{tk_r['final_portfolio']/10_000:,.0f} 萬"),
                ("目前月提領",   f"{tk_r['final_monthly_income']:,.0f} TWD"),
                ("追蹤月數",     f"{len(tk_r['monthly'])}"),
                ("再平衡次數",   f"{len(tk_r['rebalances'])}"),
            ],
        )
        builder.add_table("逐月明細(節錄前 24 個月)", pd.DataFrame(tk_r["monthly"][:24]))
    except Exception as e:
        builder.add_text("提領追蹤", f"載入失敗:{e}")


def _add_compare_section(builder: PDFReportBuilder, ctx: AppContext) -> None:
    cmp_ids = [st.session_state.get(f"_w_cmp_{i}", "").strip().upper().removesuffix(".TW")
                for i in range(5)]
    cmp_ids = [c for c in cmp_ids if c]
    if len(cmp_ids) < 2:
        builder.add_text("多檔比較", "❗ 未輸入至少 2 個代號,跳過此區塊")
        return
    cmp_closes = {}
    for c_id in cmp_ids:
        try:
            c_series, _ = cached_adjusted_close(c_id, ctx.token)
            cmp_closes[c_id] = c_series
        except Exception:
            pass
    if len(cmp_closes) < 2:
        return
    cmp_records = calc_multi_compare(cmp_closes, ctx.monthly_dca)
    cmp_df = pd.DataFrame([{
        "代號":      r.stock_id,
        "共同起始":  str(r.common_start.date()),
        "年數":      f"{r.years:.2f}",
        "總報酬%":   f"{r.total_return_pct:.1f}",
        "年化%":     f"{r.cagr_pct:.2f}",
        "DCA 終值":  f"{r.dca_final:,.0f}",
    } for r in cmp_records])
    builder.add_table(f"多檔比較({', '.join(cmp_ids)})", cmp_df)

    corr = calc_correlation_matrix(cmp_closes)
    if not corr.empty:
        builder.add_table("相關性矩陣(月報酬)", corr.round(3).reset_index())


def _add_dividend_section(builder: PDFReportBuilder, ctx: AppContext) -> None:
    try:
        div_df = cached_dividend_history(ctx.stock_id, ctx.token)
        if div_df.empty:
            builder.add_text("股利歷史", "無股利發放紀錄")
            return
        avg_y = div_df["yield_pct"].mean()
        builder.add_metrics(f"股利歷史 — {ctx.stock_id}", [
            ("發放次數",   f"{len(div_df)} 次"),
            ("平均殖利率", f"{avg_y:.2f}%"),
            ("累計配息",   f"{div_df['cash_dividend'].sum():.2f} TWD/股"),
        ])
        div_show = div_df[["date", "cash_dividend", "yield_pct"]].copy()
        div_show["date"] = pd.to_datetime(div_show["date"]).dt.strftime("%Y-%m-%d")
        div_show.columns = ["除息日", "配息(TWD/股)", "殖利率%"]
        builder.add_table("股利明細", div_show)
    except Exception as e:
        builder.add_text("股利歷史", f"載入失敗:{e}")
