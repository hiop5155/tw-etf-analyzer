# -*- coding: utf-8 -*-
"""🎯 目標試算分頁(Tab 2)。正推 + 反推模式。"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from tw_etf_analyzer.core.performance import (
    calc_lump_sum, calc_target_monthly, calc_target_assets_from_expense,
)
from tw_etf_analyzer.web.cache import cached_adjusted_close

from tw_etf_analyzer.web.context import AppContext


def _normalize_holding(stock_id: object, shares: object) -> dict[str, int | str] | None:
    sid = str(stock_id).strip().upper()
    if not sid:
        return None

    try:
        share_count = int(float(shares))
    except (TypeError, ValueError):
        return None

    if share_count <= 0:
        return None

    return {"stock_id": sid, "shares": share_count}


def _quote_holding(stock_id: str, token: str, fallback_cagr_pct: float) -> dict[str, float | str | None]:
    if stock_id == "現金":
        return {
            "stock_id": stock_id,
            "latest_price": 1.0,
            "cagr_pct": 0.0,
            "error": None,
        }

    try:
        close_h, _ = cached_adjusted_close(stock_id, token)
        latest_price = float(close_h.iloc[-1])
        cagr_pct = calc_lump_sum(close_h).cagr_pct
        return {
            "stock_id": stock_id,
            "latest_price": latest_price,
            "cagr_pct": cagr_pct,
            "error": None,
        }
    except Exception:
        return {
            "stock_id": stock_id,
            "latest_price": None,
            "cagr_pct": fallback_cagr_pct,
            "error": "查價失敗",
        }


def _merge_holdings(rows: list[dict[str, int | str]]) -> list[dict[str, int | str]]:
    merged: dict[str, int] = {}
    for row in rows:
        sid = str(row["stock_id"])
        merged[sid] = merged.get(sid, 0) + int(row["shares"])
    return [{"stock_id": sid, "shares": shares} for sid, shares in merged.items() if shares > 0]


def _calc_required_monthly(target_twd: float, years: int, annual_cagr_pct: float, existing_fv: float) -> dict:
    base = calc_target_monthly(max(target_twd - existing_fv, 0.0), years, annual_cagr_pct, existing=0.0)
    terminal_value = existing_fv + max(target_twd - existing_fv, 0.0)
    base["existing_fv"] = existing_fv
    base["remaining"] = max(target_twd - existing_fv, 0.0)
    base["terminal_value"] = terminal_value
    return base


def render(ctx: AppContext) -> None:
    st.subheader("🎯 目標試算")

    target_stock_id = st.text_input(
        "試算標的（不需要 .TW）",
        key="_w_target_sid",
    ).strip().upper().removesuffix(".TW")

    mode = st.radio(
        "試算模式",
        ["📌 正推:目標金額 → 每月需投入", "🔁 反推:月支出 → 需要多少資產(4% 法則)"],
        horizontal=True,
        key="_w_goal_mode",
    )

    if not target_stock_id:
        st.info("請輸入目標試算標的")
        return

    try:
        target_close, _ = cached_adjusted_close(target_stock_id, ctx.token)
    except Exception as exc:
        st.error(str(exc))
        return

    lump_full = calc_lump_sum(target_close)

    if mode.startswith("📌"):
        _forward_mode(ctx, target_stock_id, lump_full)
    else:
        _reverse_mode(ctx)


def _forward_mode(ctx: AppContext, target_stock_id: str, lump_full) -> None:
    st.caption(f"以 {target_stock_id} 歷史年化報酬 **{lump_full.cagr_pct:.2f}%** 為基準試算")

    st.subheader("目前持股明細")
    if "_w_holdings" not in st.session_state:
        st.session_state["_w_holdings"] = []

    holdings = st.session_state["_w_holdings"]
    latest_prices: dict[str, float | None] = {}
    holding_cagrs: dict[str, float] = {}
    fv_details: list[str] = []
    holdings_df = pd.DataFrame(holdings, columns=["stock_id", "shares"])

    if not holdings_df.empty:
        failed_quotes: list[str] = []
        for sid in holdings_df["stock_id"].unique():
            quote = _quote_holding(sid, ctx.token, lump_full.cagr_pct)
            latest_prices[sid] = quote["latest_price"]
            holding_cagrs[sid] = float(quote["cagr_pct"])
            if quote["latest_price"] is None:
                failed_quotes.append(sid)

        holdings_df["最新價格"] = holdings_df["stock_id"].map(latest_prices)
        holdings_df["年化報酬%"] = holdings_df["stock_id"].map(lambda sid: holding_cagrs.get(sid, lump_full.cagr_pct))
        holdings_df["市值 (TWD)"] = holdings_df.apply(
            lambda row: float(row["shares"]) * float(row["最新價格"])
            if pd.notna(row["最新價格"]) else 0.0,
            axis=1,
        )

        edited = st.data_editor(
            holdings_df,
            column_config={
                "stock_id": st.column_config.TextColumn("股票代號"),
                "shares": st.column_config.NumberColumn("股數", min_value=0, step=1, format="%d"),
                "最新價格": st.column_config.NumberColumn("最新價格 (TWD)", format="%.2f", disabled=True),
                "年化報酬%": st.column_config.NumberColumn("歷史年化報酬 %", format="%.2f", disabled=True),
                "市值 (TWD)": st.column_config.NumberColumn("市值 (TWD)", format="%,.0f", disabled=True),
            },
            hide_index=True,
            num_rows="dynamic",
            key="_w_holdings_editor",
        )

        normalized_holdings = []
        for _, row in edited.iterrows():
            normalized = _normalize_holding(row["stock_id"], row["shares"])
            if normalized is not None:
                normalized_holdings.append(normalized)
        normalized_holdings = _merge_holdings(normalized_holdings)

        if normalized_holdings != holdings:
            st.session_state["_w_holdings"] = normalized_holdings
            st.rerun()

        existing_twd = float(holdings_df["市值 (TWD)"].sum())
        if failed_quotes:
            st.warning(f"以下代號目前查不到價格，市值先以 0 計：{', '.join(failed_quotes)}")
    else:
        existing_twd = 0.0

    tc1, tc2 = st.columns(2)
    with tc1:
        target_wan = st.number_input("目標金額（萬 TWD）", min_value=1, step=100, key="_w_target_wan")
    with tc2:
        target_years = st.number_input("投資年限（年）", min_value=1, max_value=50, step=1, key="_w_target_years")

    target_twd = target_wan * 10_000
    total_existing_fv = 0.0
    if holdings:
        for holding in holdings:
            sid = str(holding["stock_id"])
            current_value = float(holding["shares"]) * float(latest_prices.get(sid) or 0.0)
            cagr_pct = holding_cagrs.get(sid, lump_full.cagr_pct)
            future_value = current_value * ((1 + cagr_pct / 100) ** target_years)
            total_existing_fv += future_value
            fv_details.append(f"{sid}: {future_value:,.0f} TWD")

    base = _calc_required_monthly(target_twd, target_years, lump_full.cagr_pct, total_existing_fv)
    base["total_gain"] = base["terminal_value"] - existing_twd - base["total_invested"]

    _yrs2 = target_years
    disp_exist_fv = ctx.display_value(base["existing_fv"], _yrs2)
    disp_terminal = ctx.display_value(base["terminal_value"], _yrs2)
    disp_gain     = ctx.display_value(base["total_gain"], _yrs2)
    sfx = ctx.real_sfx

    rc1, rc2, rc3 = st.columns(3)
    rc1.metric("每月需投入",       f"{base['monthly']:,.0f} TWD")
    rc2.metric("一次性投入等效",   f"{base['lump_sum_today']:,.0f} TWD")
    rc3.metric(f"現有持倉屆時終值 {sfx}", f"{disp_exist_fv:,.0f} TWD")
    rd1, rd2, rd3 = st.columns(3)
    rd1.metric("新增投入本金",                 f"{base['total_invested']:,.0f} TWD")
    rd2.metric(f"預估最終資產終值 {sfx}", f"{disp_terminal:,.0f} TWD")

    if base["monthly"] == 0:
        st.success(f"🎉 現有持倉預計 {target_years} 年後即可達標，不需額外定投！")
    else:
        total_new = existing_twd + base["total_invested"]
        st.caption(
            f"新增投入本金：{base['total_invested']:,.0f}　＋　現有持倉：{existing_twd:,.0f}"
            f"　＝　總投入成本：{total_new:,.0f} TWD　｜　"
            f"預計獲利{sfx}：{disp_gain:,.0f} TWD"
        )

    if fv_details:
        with st.expander("📊 各持倉屆時終值明細"):
            for d in fv_details:
                st.caption(d)

    st.divider()
    st.subheader("敏感度分析（不同報酬情境）")
    scenarios = [0.5, 0.75, 1.0, 1.25, 1.5]
    scenario_rows = []
    for mult in scenarios:
        rate = lump_full.cagr_pct * mult
        scenario_existing_fv = 0.0
        for holding in holdings:
            sid = str(holding["stock_id"])
            current_value = float(holding["shares"]) * float(latest_prices.get(sid) or 0.0)
            scaled_cagr_pct = holding_cagrs.get(sid, lump_full.cagr_pct) * mult
            scenario_existing_fv += current_value * ((1 + scaled_cagr_pct / 100) ** target_years)

        res = _calc_required_monthly(target_twd, target_years, rate, scenario_existing_fv)
        res["total_gain"] = res["terminal_value"] - existing_twd - res["total_invested"]
        scenario_rows.append({
            "情境":            f"{mult*100:.0f}% 歷史報酬",
            "假設年化報酬%":   f"{rate:.2f}",
            f"持倉屆時終值{sfx}":       f"{ctx.display_value(res['existing_fv'], _yrs2):,.0f}",
            "每月投入 (TWD)":  f"{res['monthly']:,.0f}",
            "新增投入本金":    f"{res['total_invested']:,.0f}",
            f"最終資產終值{sfx}":       f"{ctx.display_value(res['terminal_value'], _yrs2):,.0f}",
            f"預計獲利 (TWD){sfx}":     f"{ctx.display_value(res['total_gain'], _yrs2):,.0f}",
        })
    st.dataframe(pd.DataFrame(scenario_rows), width="stretch", hide_index=True)


def _reverse_mode(ctx: AppContext) -> None:
    st.caption("輸入退休後每月需要的生活費,以安全提領率(SWR)反推需要多少資產")

    # 第一次進入時 seed 預設值;之後由 session_state 驅動(避免 Streamlit 警告)
    st.session_state.setdefault("_w_reverse_expense", 60_000)
    st.session_state.setdefault("_w_reverse_swr",     4.0)

    rv1, rv2 = st.columns(2)
    monthly_expense = rv1.number_input(
        "退休後每月支出（TWD）",
        min_value=1_000, step=1_000,
        key="_w_reverse_expense",
    )
    swr_pct = rv2.number_input(
        "安全提領率 SWR %",
        min_value=2.0, max_value=10.0, step=0.5,
        key="_w_reverse_swr",
        help=(
            "Bengen 4% 法則 → 退休 30 年高成功率\n\n"
            "保守:3.5%；標準:4%；積極:5–6%\n\n"
            "本頁的月支出為**退休當年實質購買力**;若在實質模式,已自動換算"
        ),
    )

    required = calc_target_assets_from_expense(monthly_expense, swr_pct / 100)
    st.metric("所需退休起始資產", f"{required:,.0f} TWD (≈ {required/10_000:,.0f} 萬)")

    st.divider()
    st.subheader("不同提領率對照")
    swr_rows = []
    for swr in [3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0]:
        need = calc_target_assets_from_expense(monthly_expense, swr / 100)
        swr_rows.append({
            "提領率 %":        f"{swr:.1f}",
            "所需資產 (TWD)":  f"{need:,.0f}",
            "所需資產 (萬)":   f"{need/10_000:,.0f}",
            "評估": (
                "🟢 保守" if swr <= 3.5 else
                "🟡 標準" if swr <= 4.5 else
                "🔴 積極"
            ),
        })
    st.dataframe(pd.DataFrame(swr_rows), hide_index=True, width="stretch")

    st.divider()
    st.caption(
        f"💡 若在「退休提領模擬」頁驗證此資產:起始資產填 **{required/10_000:,.0f} 萬**,"
        f"初始提領率填 **{swr_pct:.1f}%**,即可看 Monte Carlo 成功率。"
    )
