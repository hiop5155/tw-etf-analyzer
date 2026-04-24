# -*- coding: utf-8 -*-
"""⚠️ 壓力測試分頁(起點式 × 3 歷史情境,ETF 不存在期間以 0050 代理)。"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from tw_etf_analyzer.core.simulation import run_gk_historical
from tw_etf_analyzer.core.tax import avg_annual_dividend_yield, calc_tax_drag

from tw_etf_analyzer.web.cache import cached_adjusted_close, cached_dividend_history
from tw_etf_analyzer.web.context import AppContext
from tw_etf_analyzer.web.display import nominal_to_real_value
from tw_etf_analyzer.web.presets import get_preset


_SCENARIOS = [
    {"name": "💥 2008 金融海嘯", "start_ym": "2008-01",
     "desc": "Lehman 破產前夕退休,資產腰斬(-55%),護欄應啟動保命"},
    {"name": "🦠 2020 COVID 崩盤", "start_ym": "2020-02",
     "desc": "疫情爆發前一個月退休,快速崩盤 -30% 再 V 型反彈"},
    {"name": "📈 2022 升息循環", "start_ym": "2022-01",
     "desc": "通膨高點退休,同期股債雙跌(最糟年份)"},
]


def render(ctx: AppContext) -> None:
    st.subheader("⚠️ 壓力測試 — 在歷史最差時刻退休會怎樣?")
    st.caption(
        "以退休模擬頁的投組與參數,模擬「在歷史熊市起點退休」後續追蹤至今。"
        "若投組內 ETF 成立日晚於情境起點,會用 **0050 代理** 補齊,並在下方明確標示。"
    )

    # 取用退休頁設定
    stress_alloc_df = st.session_state.get("_custom_df_value")
    preset_choice   = st.session_state.get("preset_choice", "保守配息型（預設）")
    if preset_choice != "自訂" or stress_alloc_df is None:
        stress_rows = get_preset(preset_choice)
    else:
        stress_rows = stress_alloc_df[["代號", "配置比例 %"]].to_dict("records")

    stress_alloc: dict[str, float] = {
        str(r["代號"]).strip().upper(): r["配置比例 %"] / 100
        for r in stress_rows
        if str(r["代號"]).strip() and r["配置比例 %"] > 0
    }
    stress_alloc = {("現金" if k in ("現金", "CASH") else k): v for k, v in stress_alloc.items()}

    # 參數摘要
    stress_asset = st.session_state.get("_w_rasset", 2000) * 10_000
    stress_rate  = st.session_state.get("_w_rrate", 5.0) / 100
    stress_guard = st.session_state.get("_w_rguard", 20.0) / 100
    stress_infl  = st.session_state.get("_w_rinf", 2.0) / 100

    with st.expander("🗂️ 當前測試參數（來自退休提領模擬頁）", expanded=False):
        st.write(f"- 投組來源:**{preset_choice}**")
        st.dataframe(pd.DataFrame(stress_rows), hide_index=True, width="stretch")
        st.write(
            f"- 起始資產:**{stress_asset/10_000:,.0f} 萬 TWD**　"
            f"- 初始提領率:**{stress_rate*100:.1f}%**　"
            f"- 護欄寬度:**±{stress_guard*100:.0f}%**　"
            f"- 通膨率:**{stress_infl*100:.1f}%**"
        )

    # 下載 0050 作為代理
    try:
        proxy_close, _ = cached_adjusted_close("0050", ctx.token)
    except Exception as e:
        st.error(f"代理資料 0050 載入失敗:{e}")
        return

    # 下載各資產 close
    stress_close_map: dict[str, pd.Series] = {}
    for asset in stress_alloc:
        if asset == "現金":
            continue
        try:
            c, _ = cached_adjusted_close(asset, ctx.token)
            stress_close_map[asset] = c
        except Exception as e:
            st.warning(f"資料載入失敗,將以代理或忽略:{asset}:{e}")

    # 執行 3 情境
    stress_results: list[dict] = []
    for sc in _SCENARIOS:
        start_ts = pd.Timestamp(sc["start_ym"] + "-01")
        scenario_close_map: dict[str, pd.Series] = {}
        proxied: list[str] = []
        for asset, close in stress_close_map.items():
            combined, was_proxied = _splice_proxy(close, proxy_close, start_ts)
            scenario_close_map[asset] = _apply_drag(
                combined, asset, stress_alloc[asset], stress_asset, ctx,
            )
            if was_proxied:
                proxied.append(asset)

        try:
            r = run_gk_historical(
                initial_portfolio = stress_asset,
                allocations       = stress_alloc,
                start_ym          = sc["start_ym"],
                initial_rate      = stress_rate,
                guardrail_pct     = stress_guard,
                inflation_rate    = stress_infl,
                close_series      = scenario_close_map,
            )
            stress_results.append({"sc": sc, "r": r, "proxied": proxied})
        except Exception as e:
            st.warning(f"{sc['name']} 執行失敗:{e}")

    if not stress_results:
        st.error("所有情境皆無法執行,請確認投組設定")
        return

    # 摘要卡片
    st.markdown("#### 📊 情境結果摘要")
    cols = st.columns(len(stress_results))
    for i, res in enumerate(stress_results):
        sc, r = res["sc"], res["r"]
        months = len(r["monthly"])
        yrs_elapsed = months / 12
        final_disp = ctx.display_value(r["final_portfolio"], yrs_elapsed)
        mi_sell_fee = (1 - ctx.tax_cfg.sell_fee_rate) if ctx.tax_cfg.enabled else 1.0
        mi_disp = ctx.display_value(r["final_monthly_income"] * mi_sell_fee, yrs_elapsed)
        with cols[i]:
            st.markdown(f"**{sc['name']}**")
            st.caption(sc["desc"])
            st.metric(f"目前資產 {ctx.real_sfx}",   f"{final_disp/10_000:,.0f} 萬")
            st.metric(f"目前月提領 {ctx.real_sfx}", f"{mi_disp:,.0f} TWD")
            st.caption(f"起點:{sc['start_ym']} ｜ 歷時 {yrs_elapsed:.1f} 年")
            if res["proxied"]:
                st.warning(f"⚠️ 以 0050 代理:{', '.join(res['proxied'])}")

    # 資產演化圖
    st.markdown("#### 📈 資產演化軌跡")
    fig = go.Figure()
    for res in stress_results:
        sc, r = res["sc"], res["r"]
        monthly = r["monthly"]
        if not monthly:
            continue
        x = [m["月份"] for m in monthly]
        y = [float(m["資產餘額 (萬)"]) * 10_000 for m in monthly]
        if ctx.is_real and ctx.inflation > 0:
            y = [
                nominal_to_real_value(float(v), (pd.Timestamp(d + "-01") - pd.Timestamp(sc["start_ym"] + "-01")).days / 365.25, ctx.inflation)
                for v, d in zip(y, x)
            ]
        fig.add_trace(go.Scatter(x=x, y=[v/10_000 for v in y], name=sc["name"], mode="lines"))
    fig.add_hline(y=stress_asset/10_000, line_dash="dot", line_color="gray",
                   annotation_text=f"起始 {stress_asset/10_000:,.0f} 萬")
    fig.update_layout(
        xaxis_title="月份",
        yaxis_title=f"資產餘額（萬 TWD）{ctx.real_sfx}",
        hovermode="x unified",
        legend=dict(orientation="h", y=1.08),
        height=450,
    )
    st.plotly_chart(fig, width="stretch")

    # GK 事件彙總
    with st.expander("🛡️ GK 護欄觸發事件彙總", expanded=False):
        rows = []
        for res in stress_results:
            sc, r = res["sc"], res["r"]
            for m in r["monthly"]:
                if m["事件"] not in ("—", "通膨調整 + 再平衡"):
                    rows.append({
                        "情境":    sc["name"],
                        "月份":    m["月份"],
                        "資產(萬)": m["資產餘額 (萬)"],
                        "月提領":  m["月提領額"],
                        "提領率%": m["提領率 %"],
                        "事件":    m["事件"],
                    })
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        else:
            st.info("此期間無護欄觸發(僅通膨調整)")


def _splice_proxy(
    asset_close: pd.Series,
    proxy_close: pd.Series,
    start_ts: pd.Timestamp,
) -> tuple[pd.Series, bool]:
    """若 asset_close 起始晚於 start_ts,用 proxy_close 報酬補齊前段。"""
    if asset_close.index[0] <= start_ts:
        return asset_close, False
    proxy_segment = proxy_close[
        (proxy_close.index >= start_ts) & (proxy_close.index <= asset_close.index[0])
    ]
    if proxy_segment.empty:
        return asset_close, False
    scale = float(asset_close.iloc[0]) / float(proxy_segment.iloc[-1])
    scaled = proxy_segment * scale
    combined = pd.concat([scaled[:-1], asset_close]).sort_index()
    combined = combined[~combined.index.duplicated(keep="last")]
    return combined, True


def _apply_drag(
    series: pd.Series,
    asset_code: str,
    port_weight: float,
    total_asset: float,
    ctx: AppContext,
) -> pd.Series:
    """套用稅費拖累到代理後的序列(若啟用)。"""
    if not ctx.tax_cfg.enabled:
        return series
    try:
        dh = cached_dividend_history(asset_code, ctx.token)
        y = avg_annual_dividend_yield(dh, series)
        drag = calc_tax_drag(y, total_asset * port_weight, ctx.tax_cfg)
        if drag > 0:
            start = series.index[0]
            yrs = (series.index - start).days / 365.25
            return series * ((1 - drag) ** yrs)
    except Exception:
        pass
    return series
