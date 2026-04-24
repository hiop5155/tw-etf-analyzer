# -*- coding: utf-8 -*-
"""📋 提領追蹤分頁(Tab 4)。單次追蹤 + Rolling 歷史回測。"""

from __future__ import annotations

from datetime import date as _date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from tw_etf_analyzer.core.simulation import run_gk_historical
from tw_etf_analyzer.core.tax import avg_annual_dividend_yield, calc_tax_drag

from tw_etf_analyzer.web.cache import cached_adjusted_close, cached_dividend_history
from tw_etf_analyzer.web.context import AppContext
from tw_etf_analyzer.web.display import nominal_to_real_value


def render(ctx: AppContext) -> None:
    st.subheader("📋 提領策略追蹤")
    st.caption(
        "輸入開始提領的時間與初始條件，系統以**歷史實際報酬**逐月追蹤 GK 提領策略結果。"
        "每年一月自動進行 GK 護欄檢查與資產再平衡建議。"
    )

    mode = st.radio(
        "模式",
        ["🎯 單次追蹤(選定起始日)", "🔁 Rolling 歷史回測(多起始年)"],
        horizontal=True,
        key="_w_tk6_mode",
        help=(
            "**單次追蹤**:從指定日期起至今,逐月追蹤 GK 策略\n\n"
            "**Rolling 回測**:對每個可能的起始年都跑 N 年 GK,比較「歷史上最糟/中位/最佳退休者」"
        ),
    )
    is_rolling = mode.startswith("🔁")

    # 基本參數
    st.markdown("#### ⚙️ 基本參數")
    ta, tb, tc, td = st.columns(4)
    tk6_port  = ta.number_input("初始資產（萬 TWD）", min_value=1, step=100, key="_w_tk6_port")
    tk6_rate  = tb.number_input("初始提領率 %",       min_value=0.5, max_value=15.0, step=0.5, key="_w_tk6_rate")
    guard_prev = st.session_state.get("_w_tk6_guard", 20)
    gu = tk6_rate * (1 + guard_prev / 100)
    gl = tk6_rate * (1 - guard_prev / 100)
    tk6_guard = tc.number_input(
        "護欄寬度 %",
        min_value=1, max_value=50, step=5, key="_w_tk6_guard",
        help=(
            f"初始提領率 {tk6_rate:.1f}%，護欄寬度 ±{guard_prev:.0f}%\n\n"
            f"當前提領率 > {gu:.2f}% → 提領額 ×0.9（減 10%）\n\n"
            f"當前提領率 < {gl:.2f}% → 提領額 ×1.1（加 10%）\n\n"
            f"繁榮規則（↑）僅在資產未低於去年一月時觸發。"
        ),
    )
    tk6_infl = td.number_input("通膨率 %", min_value=0.0, max_value=10.0, step=0.5, key="_w_tk6_infl")

    st.caption(
        f"護欄觸發：提領率 > **{tk6_rate*(1+tk6_guard/100):.2f}%** 減10%；"
        f"< **{tk6_rate*(1-tk6_guard/100):.2f}%** 加10%"
    )

    te, tf = st.columns([1, 3])
    if is_rolling:
        st.session_state.setdefault("_w_tk6_rolling_years", 20)
        tk6_rolling_years = te.number_input(
            "Rolling 年數",
            min_value=5, max_value=40, step=5,
            key="_w_tk6_rolling_years",
            help="每個起始年都模擬 N 年退休期間。若選 20 年,則起始年必須在 (今年 − 20) 以前",
        )
        tk6_start = _date(2003, 1, 1)
    else:
        tk6_start = te.date_input(
            "開始提領月份",
            min_value=_date(2003, 1, 1),
            key="_w_tk6_start",
            help="選擇月份即可，日期忽略",
        )

    # 持倉配置
    st.markdown("#### 📦 持倉配置（目標比例）")
    default_rows = [
        {"代號": "0050",   "配置比例 %": 90},
        {"代號": "00859B", "配置比例 %": 5},
        {"代號": "現金",   "配置比例 %": 5},
    ]
    if "tk6_alloc_base" not in st.session_state:
        st.session_state["tk6_alloc_base"] = default_rows

    editor = st.data_editor(
        pd.DataFrame(st.session_state["tk6_alloc_base"]),
        num_rows="dynamic",
        column_config={
            "代號":       st.column_config.TextColumn("代號", width="small"),
            "配置比例 %": st.column_config.NumberColumn("配置比例 %", min_value=0, max_value=100, step=1),
        },
        hide_index=True,
        key="_tk6_editor",
        width=320,
    )
    st.session_state["tk6_alloc_df"] = editor

    total = int(editor["配置比例 %"].sum())
    if total != 100:
        st.warning(f"配置比例總和為 {total}%，需等於 100% 才能執行。")
        return

    allocations: dict[str, float] = {
        str(row["代號"]).strip().upper(): row["配置比例 %"] / 100
        for _, row in editor.iterrows()
        if str(row["代號"]).strip() and pd.notna(row["配置比例 %"]) and row["配置比例 %"] > 0
    }
    if "現金" not in allocations and "現金".upper() in allocations:
        allocations["現金"] = allocations.pop("現金".upper())
    fixed = {}
    for k, v in allocations.items():
        fixed["現金" if k in ("現金", "CASH", "現金".upper()) else k] = v
    allocations = fixed

    st.divider()

    # 歷史資料
    close_map: dict[str, pd.Series] = {}
    fetch_errors = []
    for asset in allocations:
        if asset == "現金":
            continue
        try:
            c, _ = cached_adjusted_close(asset, ctx.token)
            close_map[asset] = c
        except Exception as e:
            fetch_errors.append(f"{asset}:{e}")

    if fetch_errors:
        for err in fetch_errors:
            st.error(f"資料取得失敗 — {err}")
        return

    # 稅費拖累
    drag_map: dict[str, float] = {}
    if ctx.tax_cfg.enabled:
        port_est = tk6_port * 10_000
        for asset, c in list(close_map.items()):
            try:
                dh = cached_dividend_history(asset, ctx.token)
                y = avg_annual_dividend_yield(dh, c)
                weight = allocations.get(asset, 0)
                drag = calc_tax_drag(y, port_est * weight, ctx.tax_cfg)
                drag_map[asset] = drag
                if drag > 0:
                    start = c.index[0]
                    yrs = (c.index - start).days / 365.25
                    close_map[asset] = c * ((1 - drag) ** yrs)
            except Exception:
                drag_map[asset] = 0.0

    # ── Rolling 回測分支 ──────────────────────────────────────────────────
    if is_rolling:
        _render_rolling(ctx, close_map, allocations, tk6_port, tk6_rate, tk6_guard, tk6_infl, tk6_rolling_years)
        return

    # ── 單次追蹤分支 ───────────────────────────────────────────────────────
    _render_single(ctx, close_map, allocations, tk6_port, tk6_rate, tk6_guard, tk6_infl, tk6_start, drag_map)


def _render_rolling(ctx, close_map, allocations, port, rate, guard, infl, rolling_years) -> None:
    earliest = max(c.index[0].year for c in close_map.values()) if close_map else 2003
    this_year = pd.Timestamp.today().year
    latest_start = this_year - int(rolling_years)
    if latest_start < earliest:
        st.warning(
            f"Rolling 年數 {rolling_years} 年超過可回測期間"
            f"(最早 {earliest} ~ 最晚 {this_year})"
        )
        return

    start_years = list(range(earliest, latest_start + 1))
    runs = []
    with st.spinner(f"跑 {len(start_years)} 組起始年 × {rolling_years} 年 GK..."):
        for sy in start_years:
            try:
                r = run_gk_historical(
                    initial_portfolio = port * 10_000,
                    allocations       = allocations,
                    start_ym          = f"{sy}-01",
                    initial_rate      = rate / 100,
                    guardrail_pct     = guard / 100,
                    inflation_rate    = infl / 100,
                    close_series      = close_map,
                )
                cap = int(rolling_years) * 12
                m_trunc = r["monthly"][:cap]
                final_port = float(m_trunc[-1]["資產餘額 (萬)"]) * 10_000 if m_trunc else r["final_portfolio"]
                runs.append({
                    "start_year":  sy,
                    "final":       final_port,
                    "depleted":    final_port <= 0,
                    "monthly":     m_trunc,
                })
            except Exception:
                pass

    if not runs:
        st.error("Rolling 回測無結果,請調整配置或縮短年數")
        return

    sorted_runs = sorted(runs, key=lambda x: x["final"])
    worst  = sorted_runs[0]
    median = sorted_runs[len(sorted_runs) // 2]
    best   = sorted_runs[-1]
    depleted_count = sum(1 for r in runs if r["depleted"])
    success_rate = (len(runs) - depleted_count) / len(runs) * 100

    sfx = ctx.real_sfx
    worst_disp  = ctx.display_value(worst["final"],  int(rolling_years))
    median_disp = ctx.display_value(median["final"], int(rolling_years))
    best_disp   = ctx.display_value(best["final"],   int(rolling_years))

    st.markdown(f"#### 📊 Rolling 回測結果摘要({len(runs)} 組起始年 × {rolling_years} 年)")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("存活率",            f"{success_rate:.1f}%", help="未耗盡資產的起始年比例")
    c2.metric(f"最差終值 {sfx}",   f"{worst_disp/10_000:,.0f} 萬",   help=f"起始年:{worst['start_year']}")
    c3.metric(f"中位終值 {sfx}",   f"{median_disp/10_000:,.0f} 萬",  help=f"起始年:{median['start_year']}")
    c4.metric(f"最佳終值 {sfx}",   f"{best_disp/10_000:,.0f} 萬",    help=f"起始年:{best['start_year']}")

    # 條形圖
    st.markdown("#### 📈 各起始年終值分布")
    df_roll = pd.DataFrame([{
        "起始年":   r["start_year"],
        "終值(萬)": ctx.display_value(r["final"], int(rolling_years)) / 10_000,
        "耗盡":     "是" if r["depleted"] else "否",
    } for r in runs])
    fig_roll = go.Figure()
    fig_roll.add_trace(go.Bar(
        x=df_roll["起始年"], y=df_roll["終值(萬)"],
        marker_color=["tomato" if x else "steelblue" for x in df_roll["耗盡"].eq("是")],
        hovertemplate="起始 %{x}<br>終值 %{y:,.0f} 萬<extra></extra>",
        name="終值",
    ))
    fig_roll.add_hline(y=port, line_dash="dot", line_color="gray",
                        annotation_text=f"起始 {port:,} 萬")
    fig_roll.update_layout(
        xaxis_title="退休起始年",
        yaxis_title=f"{rolling_years} 年後終值(萬 TWD){sfx}",
        hovermode="x unified", height=400,
    )
    st.plotly_chart(fig_roll, width="stretch")

    # 三條路徑對照
    st.markdown("#### 🔍 三條代表性路徑對照")
    fig_path = go.Figure()
    for lab, run, color in [
        (f"🌪️ 最差({worst['start_year']} 起)",  worst,  "tomato"),
        (f"📊 中位({median['start_year']} 起)", median, "steelblue"),
        (f"🌤️ 最佳({best['start_year']} 起)",   best,   "seagreen"),
    ]:
        m = run["monthly"]
        if not m:
            continue
        x = list(range(len(m)))
        y = [float(row["資產餘額 (萬)"]) * 10_000 for row in m]
        if ctx.is_real and ctx.inflation > 0:
            y = [nominal_to_real_value(v, i / 12, ctx.inflation) for i, v in enumerate(y)]
        fig_path.add_trace(go.Scatter(
            x=x, y=[v / 10_000 for v in y],
            name=lab, mode="lines",
            line=dict(color=color, width=2),
        ))
    fig_path.update_layout(
        xaxis_title="退休後第幾個月",
        yaxis_title=f"資產餘額(萬 TWD){sfx}",
        hovermode="x unified", height=400,
    )
    st.plotly_chart(fig_path, width="stretch")

    with st.expander("📋 各起始年明細", expanded=False):
        st.dataframe(df_roll, hide_index=True, width="stretch")


def _render_single(ctx, close_map, allocations, port, rate, guard, infl, start_date, drag_map) -> None:
    start_ym = start_date.strftime("%Y-%m")
    try:
        with st.spinner("以歷史資料逐月計算 GK 提領策略..."):
            result = run_gk_historical(
                initial_portfolio = port * 10_000,
                allocations       = allocations,
                start_ym          = start_ym,
                initial_rate      = rate / 100,
                guardrail_pct     = guard / 100,
                inflation_rate    = infl / 100,
                close_series      = close_map,
            )
    except Exception as e:
        st.error(f"計算失敗:{e}")
        return

    monthly    = result["monthly"]
    rebalances = result["rebalances"]

    for dw in result.get("data_warnings", []):
        st.warning(dw)

    if not monthly:
        st.warning("所選月份無歷史資料，請調整起始月份。")
        return

    net_factor = (1 - ctx.tax_cfg.sell_fee_rate) if ctx.tax_cfg.enabled else 1.0
    final_monthly_net = result["final_monthly_income"] * net_factor
    initial_monthly   = port * 10_000 * rate / 100 / 12 * net_factor

    years_elapsed = len(monthly) / 12
    final_port_disp = ctx.display_value(result["final_portfolio"], years_elapsed)
    final_mi_disp   = ctx.display_value(final_monthly_net, years_elapsed)
    sfx = ctx.real_sfx

    m1, m2, m3, m4 = st.columns(4)
    m1.metric(f"目前資產 {sfx}",     f"{final_port_disp/10_000:,.0f} 萬 TWD")
    m2.metric(f"目前月提領額 {sfx}", f"{final_mi_disp:,.0f} TWD")
    m3.metric("初始月提領額(淨)",     f"{initial_monthly:,.0f} TWD",
               delta=f"{final_monthly_net - initial_monthly:+,.0f}")
    m4.metric("追蹤期間",             f"{len(monthly)} 個月 / {len(rebalances)} 次再平衡")

    if ctx.tax_cfg.enabled:
        drag_summary = "、".join(f"{a}: −{d*100:.2f}%" for a, d in drag_map.items() if d > 0)
        st.caption(f"💸 已套用稅費:{drag_summary or '無股利資料'}　｜　賣出費 {ctx.tax_cfg.sell_fee_rate*100:.4f}%")

    with st.expander("📅 逐月明細", expanded=False):
        st.dataframe(pd.DataFrame(monthly), hide_index=True, width="stretch")

    if rebalances:
        st.markdown("#### 🔄 年度再平衡事件（每年一月）")
        st.caption("GK 護欄檢查與資產再平衡建議。每筆均可輸入實際持倉取得精確交易指示。")

        label_map = {
            "capital_preservation": "↓ 減提領 10%（提領率過高）",
            "prosperity":           "↑ 增提領 10%（提領率過低）",
            "":                     "通膨調整（無護欄觸發）",
        }

        for rb in rebalances:
            is_latest = (rb is rebalances[-1])
            title = (
                f"**{rb['year']} 年一月再平衡**　｜　"
                f"資產 {rb['portfolio']/10_000:,.0f} 萬　｜　"
                f"新月提領 {rb['monthly_income']:,.0f} TWD"
            )
            with st.expander(title, expanded=is_latest):
                st.info(f"GK 調整:{label_map.get(rb['gk_trigger'], '—')}")

                alloc_rows = []
                for a in rb["target_alloc"]:
                    target = rb["target_alloc"][a] * 100
                    drift  = rb["drift_alloc"].get(a, 0.0) * 100
                    trade  = rb["trades"].get(a, 0.0)
                    alloc_rows.append({
                        "標的":             a,
                        "目標 %":           f"{target:.1f}",
                        "漂移後實際 %":     f"{drift:.1f}",
                        "偏差":             f"{drift - target:+.1f}",
                        "再平衡建議（萬）": (
                            f"{'買入' if trade > 0 else '賣出'} {abs(trade)/10_000:,.1f}"
                            if abs(trade) > 500 else "—"
                        ),
                    })
                st.dataframe(pd.DataFrame(alloc_rows), hide_index=True, width=600)

                st.markdown("---")
                st.markdown("**💡 輸入您的實際持倉，取得精確再平衡建議**")
                st.caption("預設值為理論漂移後金額，請依實際帳戶餘額修改。")

                actual_cols = st.columns(len(rb["target_alloc"]))
                actual_vals: dict[str, float] = {}
                for j, (a, tw) in enumerate(rb["target_alloc"].items()):
                    default = round(rb["portfolio"] * rb["drift_alloc"].get(a, tw) / 10_000, 1)
                    actual_vals[a] = actual_cols[j].number_input(
                        f"{a}（萬）",
                        min_value=0.0,
                        value=float(default),
                        step=1.0,
                        key=f"_tk6_act_{a}_{rb['year']}",
                    )

                total_actual = sum(actual_vals.values()) * 10_000
                if total_actual > 0:
                    st.markdown(f"**總資產：{total_actual/10_000:,.1f} 萬 → 再平衡至目標配置：**")
                    trade_cols = st.columns(len(rb["target_alloc"]))
                    for j, (a, tw) in enumerate(rb["target_alloc"].items()):
                        cur  = actual_vals[a] * 10_000
                        tgt  = total_actual * tw
                        delta = tgt - cur
                        op = "買入" if delta > 0 else "賣出"
                        trade_cols[j].metric(
                            a,
                            f"{op} {abs(delta)/10_000:,.1f} 萬",
                            delta=f"{delta/10_000:+.1f} 萬",
                            delta_color="normal" if delta > 0 else "inverse",
                        )
    else:
        st.info("尚無再平衡事件（提領開始後的第一個一月才會觸發）。")
