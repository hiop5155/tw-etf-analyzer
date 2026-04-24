# -*- coding: utf-8 -*-
"""🎯 目標試算分頁(Tab 2)。正推 + 反推模式。"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from tw_etf_analyzer.core.performance import (
    calc_lump_sum, calc_target_monthly, calc_target_assets_from_expense,
)

from tw_etf_analyzer.web.context import AppContext


def render(ctx: AppContext) -> None:
    lump_full = calc_lump_sum(ctx.close_full)

    st.subheader("🎯 目標試算")

    mode = st.radio(
        "試算模式",
        ["📌 正推:目標金額 → 每月需投入", "🔁 反推:月支出 → 需要多少資產(4% 法則)"],
        horizontal=True,
        key="_w_goal_mode",
    )

    if mode.startswith("📌"):
        _forward_mode(ctx, lump_full)
    else:
        _reverse_mode(ctx)


def _forward_mode(ctx: AppContext, lump_full) -> None:
    st.caption(f"以 {ctx.stock_id} 歷史年化報酬 **{lump_full.cagr_pct:.2f}%** 為基準試算")

    tc1, tc2, tc3 = st.columns(3)
    target_wan   = tc1.number_input("目標金額（萬 TWD）",         min_value=1, step=100, key="_w_target_wan")
    target_years = tc2.number_input("投資年限（年）",              min_value=1, max_value=50, step=1, key="_w_target_years")
    existing_wan = tc3.number_input("目前已持有此標的（萬 TWD）", min_value=0, step=10,  key="_w_existing")

    target_twd   = target_wan   * 10_000
    existing_twd = existing_wan * 10_000
    base = calc_target_monthly(target_twd, target_years, lump_full.cagr_pct, existing=existing_twd)

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

    st.divider()
    st.subheader("敏感度分析（不同報酬情境）")
    scenarios = [0.5, 0.75, 1.0, 1.25, 1.5]
    scenario_rows = []
    for mult in scenarios:
        rate = lump_full.cagr_pct * mult
        res = calc_target_monthly(target_twd, target_years, rate, existing=existing_twd)
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
