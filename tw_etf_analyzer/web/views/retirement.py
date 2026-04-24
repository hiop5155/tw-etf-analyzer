# -*- coding: utf-8 -*-
"""🏖️ 退休提領模擬分頁(Tab 3)。GK × MC × Sequence-of-Returns × Bootstrap。"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from tw_etf_analyzer.constants import CASH_RETURN, CASH_VOL
from tw_etf_analyzer.core.data import fetch_stock_name
from tw_etf_analyzer.core.metrics import calc_return_vol
from tw_etf_analyzer.core.simulation import simulate_gk_montecarlo
from tw_etf_analyzer.core.tax import avg_annual_dividend_yield, calc_tax_drag

from tw_etf_analyzer.web.cache import cached_adjusted_close, cached_dividend_history
from tw_etf_analyzer.web.context import AppContext
from tw_etf_analyzer.web.display import nominal_to_real_value
from tw_etf_analyzer.web.presets import PRESETS


def render(ctx: AppContext) -> None:
    st.subheader("🏖️ 退休提領模擬 — Guyton-Klinger × Monte Carlo")
    st.caption(
        "目標達成後轉換為保守組合，以 GK 動態提領策略提領。"
        "報酬率與波動度**自動從 FinMind 歷史資料計算**，執行 1,000 次 Monte Carlo 模擬。"
    )

    # 基本參數
    st.markdown("#### ⚙️ 基本參數")
    pc1, pc2, pc3 = st.columns(3)
    retire_asset_wan = pc1.number_input(
        "退休起始資產（萬 TWD）", min_value=100, step=100,
        key="_w_rasset", help="可直接填入「目標試算」頁的目標金額",
    )
    retire_years  = pc2.number_input("模擬年數", min_value=5, max_value=60, step=5, key="_w_ryears")
    inflation_pct = pc3.number_input("通膨率 %", min_value=0.0, max_value=10.0, step=0.5, key="_w_rinf")

    pg1, pg2, pg3 = st.columns(3)
    init_rate_pct = pg1.number_input("初始提領率 %", min_value=1.0, max_value=15.0,
                                     step=0.5, key="_w_rrate")
    init_monthly = retire_asset_wan * 10_000 * init_rate_pct / 100 / 12
    pg2.number_input("初始月提領額（TWD）", value=init_monthly, disabled=True, format="%.0f")
    guard_prev = st.session_state.get("_w_rguard", 20.0)
    gu = init_rate_pct * (1 + guard_prev / 100)
    gl = init_rate_pct * (1 - guard_prev / 100)
    guardrail_pct = pg3.number_input(
        "護欄寬度 %",
        min_value=5.0, max_value=50.0, step=5.0, key="_w_rguard",
        help=(
            f"初始提領率 {init_rate_pct:.1f}%，護欄寬度 ±{guard_prev:.0f}%\n\n"
            f"當前提領率 > {gu:.2f}% → 提領額 ×0.9（減 10%）\n\n"
            f"當前提領率 < {gl:.2f}% → 提領額 ×1.1（加 10%）\n\n"
            f"繁榮規則（↑）僅在資產未低於去年一月時觸發。"
        ),
    )

    st.caption(
        f"護欄觸發：提領率 > **{init_rate_pct*(1+guardrail_pct/100):.2f}%** 減10%；"
        f"< **{init_rate_pct*(1-guardrail_pct/100):.2f}%** 加10%"
    )

    # 投組
    st.markdown("#### 🗂️ 退休後投資組合")
    preset_names = list(PRESETS.keys()) + ["自訂"]
    preset_choice = st.radio("選擇預設組合", preset_names, horizontal=True, key="preset_choice")

    with st.expander("📋 各預設組合說明", expanded=False):
        st.markdown("""
| 組合 | 特色 | 適合對象 |
|------|------|---------|
| **保守配息型** | 高股息50% + 投資級債40% + 現金10% | 希望穩定配息、接受適度波動 |
| **債券優先型** | 債券65% + 高股息25% + 現金10% | 追求資本保全、降低股市風險 |
| **全高股息型** | 高股息80% + 現金20% | 信任台灣配息ETF、接受較高波動 |
| **均衡穩健型** | 股35% + 債45% + 現金20% | 需要均衡成長與防禦的退休者 |
| **槓桿平衡型** | 00631L 50% + 現金50%（淨曝險≈1x 台灣50）| 信任再平衡紀律、想用高現金 buffer 抗 sequence risk |
        """)

    if preset_choice == "自訂":
        if "_custom_base" not in st.session_state:
            st.session_state["_custom_base"] = [
                {"代號": row["代號"], "配置比例 %": row["配置比例 %"]}
                for row in PRESETS["保守配息型（預設）"]
            ]
        base_rows = [
            {("代號" if k == "ETF代號" else k): v for k, v in row.items()}
            for row in st.session_state["_custom_base"]
        ]
        custom_editor = st.data_editor(
            pd.DataFrame(base_rows),
            num_rows="dynamic",
            width="stretch",
            key="retire_portfolio_custom",
            column_config={
                "代號":    st.column_config.TextColumn(help="台股代號（ETF 或個股），現金請填「現金」", required=True),
                "配置比例 %": st.column_config.NumberColumn(min_value=0, max_value=100, step=5, format="%.0f"),
            },
        )
        st.session_state["_custom_df_value"] = custom_editor

        with st.spinner("查詢股票名稱..."):
            custom_editor["資產名稱"] = custom_editor["代號"].apply(
                lambda c: fetch_stock_name(str(c).strip().upper(), ctx.token) if str(c).strip() else ""
            )
        portfolio_df = custom_editor[["資產名稱", "代號", "配置比例 %"]]
    else:
        portfolio_df = st.data_editor(
            pd.DataFrame(PRESETS[preset_choice]),
            num_rows="fixed",
            width="stretch",
            key=f"retire_portfolio_{preset_choice}",
            column_config={
                "資產名稱": st.column_config.TextColumn(disabled=True),
                "代號":     st.column_config.TextColumn(disabled=True),
                "配置比例 %": st.column_config.NumberColumn(min_value=0, max_value=100, step=5, format="%.0f"),
            },
        )

    total_alloc = portfolio_df["配置比例 %"].sum()
    if abs(total_alloc - 100) > 0.5:
        st.warning(f"⚠️ 配置比例加總為 {total_alloc:.1f}%，請調整至 100%")
        return

    # 歷史報酬
    st.markdown("#### 📡 歷史報酬自動計算（從 FinMind）")
    etf_stats: dict[str, tuple[float, float, str, float]] = {}
    stat_rows = []
    fetch_errors = []
    codes = [
        str(r["代號"]).strip().upper()
        for _, r in portfolio_df.iterrows()
        if str(r["代號"]).strip().upper() != "現金"
    ]
    spinner_msg = f"載入 {', '.join(codes)} 歷史資料..." if codes else "計算中..."

    with st.spinner(spinner_msg):
        for _, row in portfolio_df.iterrows():
            code = str(row["代號"]).strip().upper()
            if code == "現金":
                etf_stats[code] = (CASH_RETURN, CASH_VOL, "固定假設", 999)
                stat_rows.append({
                    "資產名稱":     row["資產名稱"],
                    "代號":         "現金",
                    "資料期間":     "固定假設",
                    "歷史CAGR %":   f"{CASH_RETURN*100:.2f}",
                    "年化波動度 %": f"{CASH_VOL*100:.2f}",
                })
            else:
                try:
                    close_r, _ = cached_adjusted_close(code, ctx.token)
                    cagr, vol  = calc_return_vol(close_r)
                    period     = f"{close_r.index[0].date()} ～ {close_r.index[-1].date()}"
                    yrs        = (close_r.index[-1] - close_r.index[0]).days / 365.25
                    warn       = " ⚠️ 歷史<10年" if yrs < 10 else ""
                    etf_stats[code] = (cagr, vol, period, yrs)
                    stat_rows.append({
                        "資產名稱":     row["資產名稱"],
                        "代號":         code,
                        "資料期間":     period + warn,
                        "歷史CAGR %":   f"{cagr*100:.2f}",
                        "年化波動度 %": f"{vol*100:.2f}",
                    })
                except Exception as e:
                    fetch_errors.append(f"{code}：{e}")

    for err in fetch_errors:
        st.error(err)
    if fetch_errors:
        return

    st.dataframe(pd.DataFrame(stat_rows), width="stretch", hide_index=True)

    short_hist = [
        (str(row["代號"]).strip().upper(), row["資產名稱"])
        for _, row in portfolio_df.iterrows()
        if str(row["代號"]).strip().upper() != "現金"
        and etf_stats.get(str(row["代號"]).strip().upper(), (0, 0, "", 999))[3] < 10
    ]
    if short_hist:
        names = "、".join(f"{code}（{name}）" for code, name in short_hist)
        st.warning(
            f"⚠️ **回測期間不足警告**\n\n"
            f"以下標的歷史資料不足 10 年：**{names}**。\n\n"
            "其 CAGR 可能因取樣期間恰好涵蓋多頭行情而**嚴重高估長期報酬**，"
            "以此數字進行退休模擬時請保守解讀結果，建議實際規劃時適度下調預期報酬假設。"
        )

    # 加權
    w_ret, w_vol = 0.0, 0.0
    for _, row in portfolio_df.iterrows():
        code = str(row["代號"]).strip().upper()
        weight = row["配置比例 %"] / 100
        cagr, vol, _, _yrs = etf_stats.get(code, (CASH_RETURN, CASH_VOL, "", 999))
        w_ret += weight * cagr
        w_vol += weight * vol

    # 稅費拖累
    w_tax_drag = 0.0
    if ctx.tax_cfg.enabled:
        retire_port_est = retire_asset_wan * 10_000
        for _, row in portfolio_df.iterrows():
            code = str(row["代號"]).strip().upper()
            weight = row["配置比例 %"] / 100
            if code == "現金":
                continue
            try:
                dh = cached_dividend_history(code, ctx.token)
                close_r, _ = cached_adjusted_close(code, ctx.token)
                y = avg_annual_dividend_yield(dh, close_r)
                w_tax_drag += weight * calc_tax_drag(y, retire_port_est * weight, ctx.tax_cfg)
            except Exception:
                pass

    short_note = "　⚠️ 含短歷史標的，報酬偏高屬正常，請保守解讀" if short_hist else ""
    w_ret_gross = w_ret
    w_ret = w_ret - w_tax_drag

    if ctx.tax_cfg.enabled:
        st.success(
            f"✅ 加權毛年化報酬:**{w_ret_gross*100:.2f}%**　｜　稅費拖累:−**{w_tax_drag*100:.2f}%**"
            f"　｜　**淨年化 {w_ret*100:.2f}%**　｜　加權波動度:**{w_vol*100:.2f}%**{short_note}"
        )
    else:
        st.success(
            f"✅ 加權歷史年化報酬：**{w_ret*100:.2f}%**　｜　加權年化波動度：**{w_vol*100:.2f}%**"
            f"　（波動度為各資產加權平均，未考慮資產間相關係數）{short_note}"
        )

    st.divider()

    # MC
    retire_asset = retire_asset_wan * 10_000

    dist_label = st.radio(
        "報酬分配模型",
        ["🔔 常態(現狀)", "🐘 Student-t 肥尾(df=5)", "📚 Bootstrap(歷史月報酬)"],
        horizontal=True,
        key="_w_mc_dist",
        help=(
            "**常態**:報酬服從 N(μ, σ),低估極端事件機率\n\n"
            "**Student-t 肥尾**:df=5 時肥尾,更符合實際股市極端事件\n\n"
            "**Bootstrap**:從各檔歷史月報酬有放回抽樣,12 筆複利為年報酬 — 最不依賴分配假設"
        ),
    )
    dist_kind = (
        "tdist"     if dist_label.startswith("🐘") else
        "bootstrap" if dist_label.startswith("📚") else
        "normal"
    )

    hist_monthly = None
    if dist_kind == "bootstrap":
        asset_monthly: dict[str, pd.Series] = {}
        for _, row in portfolio_df.iterrows():
            code = str(row["代號"]).strip().upper()
            if code == "現金":
                continue
            try:
                c, _ = cached_adjusted_close(code, ctx.token)
                clean = c.replace(0, float("nan")).dropna()
                m = clean.resample("ME").last().dropna().pct_change().dropna()
                asset_monthly[code] = m
            except Exception:
                pass
        if asset_monthly:
            aligned = pd.DataFrame(asset_monthly).dropna()
            portfolio_monthly = pd.Series(0.0, index=aligned.index)
            for code, series in asset_monthly.items():
                w = 0.0
                for _, r in portfolio_df.iterrows():
                    if str(r["代號"]).strip().upper() == code:
                        w = r["配置比例 %"] / 100
                        break
                if code in aligned.columns:
                    portfolio_monthly += aligned[code] * w
            hist_monthly = portfolio_monthly.values
            st.caption(
                f"📊 Bootstrap 樣本:**{len(hist_monthly)} 筆月報酬**"
                f"(共同可觀察期間,已用配置比例加權;現金部位月報酬 = 0)"
            )
        else:
            st.warning("找不到足夠的歷史月報酬,退回常態分配")
            dist_kind = "normal"

    dist_label_short = {
        "normal":    "常態",
        "tdist":     "Student-t(df=5)",
        "bootstrap": "Bootstrap",
    }[dist_kind]

    try:
        with st.spinner(f"執行 2,000 次 Monte Carlo({dist_label_short})..."):
            mc = simulate_gk_montecarlo(
                initial_portfolio = retire_asset,
                initial_rate      = init_rate_pct / 100,
                guardrail_pct     = guardrail_pct / 100,
                annual_return     = w_ret,
                annual_volatility = w_vol,
                inflation_rate    = inflation_pct / 100,
                years             = int(retire_years),
                n_sims            = 2000,
                dist_kind         = dist_kind,
                hist_monthly_returns = hist_monthly,
            )
    except Exception as e:
        st.error(f"Monte Carlo 模擬失敗：{e}")
        return

    # 摘要
    st.markdown("#### 📋 模擬結果摘要（2,000 次模擬）")
    sm1, sm2, sm3, sm4 = st.columns(4)
    sm1.metric("初始月提領額",             f"{mc['initial_monthly']:,.0f} TWD")
    sm2.metric(f"第{retire_years}年存活率", f"{mc['survival_final']:.1f}%")
    sm3.metric("資產耗盡機率",             f"{mc['depleted_pct']:.1f}%")
    p50_final = mc["port_pct"][50][-1]
    p50_disp = ctx.display_value(p50_final, retire_years)
    sfx = ctx.real_sfx
    sm4.metric(f"P50 期末資產 {sfx}", f"{p50_disp/10_000:,.0f} 萬 TWD")

    # 資產百分位圖
    st.markdown(f"#### 📊 資產餘額分布（百分位數） {sfx}")
    yrs = mc["years"]

    def _deflate(arr):
        if ctx.is_real and ctx.inflation > 0:
            return np.array([
                nominal_to_real_value(float(v), float(y), ctx.inflation)
                for v, y in zip(arr, yrs)
            ])
        return arr

    port10 = _deflate(mc["port_pct"][10])
    port25 = _deflate(mc["port_pct"][25])
    port50 = _deflate(mc["port_pct"][50])
    port75 = _deflate(mc["port_pct"][75])
    port90 = _deflate(mc["port_pct"][90])

    fig_port = go.Figure()
    fig_port.add_trace(go.Scatter(
        x=list(yrs) + list(yrs[::-1]),
        y=list(port90 / 10_000) + list(port10[::-1] / 10_000),
        fill="toself", fillcolor="rgba(70,130,180,0.15)",
        line=dict(color="rgba(0,0,0,0)"), name="P10–P90", showlegend=True,
    ))
    fig_port.add_trace(go.Scatter(
        x=list(yrs) + list(yrs[::-1]),
        y=list(port75 / 10_000) + list(port25[::-1] / 10_000),
        fill="toself", fillcolor="rgba(70,130,180,0.30)",
        line=dict(color="rgba(0,0,0,0)"), name="P25–P75", showlegend=True,
    ))
    for p, color, dash in [(50, "steelblue", "solid"), (10, "tomato", "dash"), (90, "seagreen", "dash")]:
        arr = {10: port10, 50: port50, 90: port90}[p]
        fig_port.add_trace(go.Scatter(
            x=yrs, y=arr / 10_000,
            name=f"P{p}", mode="lines",
            line=dict(color=color, dash=dash, width=2 if p == 50 else 1.5),
        ))
    fig_port.add_hline(y=0, line_dash="dot", line_color="gray")
    fig_port.update_layout(
        xaxis_title="退休後第幾年", yaxis_title="資產餘額（萬 TWD）",
        hovermode="x unified", legend=dict(orientation="h", y=1.08),
    )
    st.plotly_chart(fig_port, width="stretch")

    # 月提領額
    st.markdown(f"#### 💵 每月提領額分布（百分位數） {sfx}")
    wd10 = _deflate(mc["wd_pct"][10])
    wd25 = _deflate(mc["wd_pct"][25])
    wd50 = _deflate(mc["wd_pct"][50])
    wd75 = _deflate(mc["wd_pct"][75])
    wd90 = _deflate(mc["wd_pct"][90])
    fig_wd = go.Figure()
    fig_wd.add_trace(go.Scatter(
        x=list(yrs) + list(yrs[::-1]),
        y=list(wd90) + list(wd10[::-1]),
        fill="toself", fillcolor="rgba(46,139,87,0.15)",
        line=dict(color="rgba(0,0,0,0)"), name="P10–P90",
    ))
    fig_wd.add_trace(go.Scatter(
        x=list(yrs) + list(yrs[::-1]),
        y=list(wd75) + list(wd25[::-1]),
        fill="toself", fillcolor="rgba(46,139,87,0.30)",
        line=dict(color="rgba(0,0,0,0)"), name="P25–P75",
    ))
    for p, color, dash in [(50, "seagreen", "solid"), (10, "tomato", "dash"), (90, "royalblue", "dash")]:
        arr = {10: wd10, 50: wd50, 90: wd90}[p]
        fig_wd.add_trace(go.Scatter(
            x=yrs, y=arr, name=f"P{p}", mode="lines",
            line=dict(color=color, dash=dash, width=2 if p == 50 else 1.5),
        ))
    fig_wd.update_layout(
        xaxis_title="退休後第幾年", yaxis_title="每月提領額（TWD）",
        hovermode="x unified", legend=dict(orientation="h", y=1.08),
    )
    st.plotly_chart(fig_wd, width="stretch")

    # 存活率
    st.markdown("#### 📉 逐年存活率")
    fig_surv = go.Figure()
    fig_surv.add_trace(go.Scatter(
        x=yrs, y=mc["survival_rate"],
        mode="lines+markers", line=dict(color="steelblue", width=2),
        fill="toself", fillcolor="rgba(70,130,180,0.15)",
        name="存活率 %",
    ))
    fig_surv.add_hline(y=80, line_dash="dash", line_color="orange", annotation_text="80% 安全門檻")
    fig_surv.add_hline(y=50, line_dash="dash", line_color="tomato", annotation_text="50%")
    fig_surv.update_layout(
        xaxis_title="退休後第幾年", yaxis_title="資產存活率 %",
        yaxis=dict(range=[0, 105]), hovermode="x unified",
    )
    st.plotly_chart(fig_surv, width="stretch")

    # Sequence-of-Returns
    st.markdown("#### 🎲 順序風險(Sequence-of-Returns Risk)")
    st.caption(
        "**相同的平均報酬,退休早期遇到壞年份 vs 好年份,結局天差地別。**"
        "以下三條路徑使用**同一組**隨機報酬,僅「順序」不同 — 但結果顯示順序本身就是重大風險。"
    )
    sor_rng = np.random.default_rng(12345)
    sor_returns = sor_rng.normal(w_ret, w_vol, int(retire_years))
    orders = [
        ("🌪️ 逆風起跑(壞年份先)", np.sort(sor_returns)),
        ("🎲 隨機順序",           sor_returns.copy()),
        ("🌤️ 順風起跑(好年份先)", np.sort(sor_returns)[::-1]),
    ]
    fig_sor = go.Figure()
    colors = ["tomato", "steelblue", "seagreen"]
    sor_yrs_axis = list(range(int(retire_years) + 1))
    for (lab, seq), color in zip(orders, colors):
        trace = _run_simple_gk(seq, retire_asset, init_rate_pct / 100, inflation_pct / 100)
        disp_trace = [ctx.display_value(v, i) for i, v in enumerate(trace)]
        fig_sor.add_trace(go.Scatter(
            x=sor_yrs_axis, y=[v / 10_000 for v in disp_trace],
            name=lab, mode="lines",
            line=dict(color=color, width=2),
        ))
    fig_sor.add_hline(y=0, line_dash="dot", line_color="gray")
    fig_sor.update_layout(
        xaxis_title="退休後第幾年",
        yaxis_title=f"資產餘額（萬 TWD）{sfx}",
        hovermode="x unified",
        legend=dict(orientation="h", y=1.08),
        height=400,
    )
    st.plotly_chart(fig_sor, width="stretch")
    st.caption(
        "💡 三條路徑的幾何平均報酬完全相同(因使用同一組數字),但路徑末端資產可能差數倍。"
        "這就是為什麼退休前 5-10 年遇到熊市特別危險 — GK 護欄正是為此設計。"
    )

    # 逐年明細
    with st.expander("📄 逐年 GK 提領明細（代表性路徑）", expanded=False):
        st.caption(
            "從 2,000 次模擬中，按最終資產排名取出 **P1（極端悲觀）、P10（悲觀）、P50（中位）、P90（樂觀）** "
            "四條代表性路徑，對各自的報酬序列重跑 GK 策略，呈現每年確定的提領與護欄觸發結果。"
        )
        for pct, label in [
            ( 1, "😰 極端悲觀路徑 P1　（最終資產排第 1%，最不利情境）"),
            (10, "😟 悲觀路徑 P10　（最終資產排第 10%，資產消耗較快）"),
            (50, "😐 中位路徑 P50　（最終資產排第 50%，典型情境）"),
            (90, "😊 樂觀路徑 P90　（最終資產排第 90%，投資環境較好）"),
        ]:
            with st.expander(label, expanded=(pct == 1)):
                if pct not in mc["rep_paths"]:
                    st.info("請重新整理頁面以載入此路徑（模擬快取過期）。")
                else:
                    st.dataframe(pd.DataFrame(mc["rep_paths"][pct]), width="stretch", hide_index=True)

    with st.expander("ℹ️ Guyton-Klinger 策略與 Monte Carlo 說明", expanded=False):
        st.markdown(f"""
**Guyton-Klinger 動態提領規則**

| 規則 | 觸發條件 | 動作 |
|------|---------|------|
| 通膨調整 | 每年自動 | 提領額 ×(1+通膨率)；若上年資產下滑則跳過 |
| 資本保護 (↓) | 當年提領率 > {init_rate_pct*(1+guardrail_pct/100):.2f}% | 提領額減少 10% |
| 繁榮規則 (↑) | 當年提領率 < {init_rate_pct*(1-guardrail_pct/100):.2f}% | 提領額增加 10% |

**Monte Carlo 方法**
- 每年報酬從 **正態分布 N(加權年化報酬, 加權波動度)** 中隨機抽樣
- 執行 **2,000 次**獨立模擬，統計各年度資產與提領額的百分位數分布
- 波動度為各資產加權平均（簡化；不含資產間相關係數）
- P50 = 中位數情境；P10 = 悲觀情境；P90 = 樂觀情境
        """)

    # 下載
    mc_summary = pd.DataFrame({
        "年度":        yrs,
        "P10資產(萬)": (mc["port_pct"][10] / 10_000).round(1),
        "P25資產(萬)": (mc["port_pct"][25] / 10_000).round(1),
        "P50資產(萬)": (mc["port_pct"][50] / 10_000).round(1),
        "P75資產(萬)": (mc["port_pct"][75] / 10_000).round(1),
        "P90資產(萬)": (mc["port_pct"][90] / 10_000).round(1),
        "P50月提領":   mc["wd_pct"][50].round(0).astype(int),
        "存活率%":     mc["survival_rate"].round(1),
    })
    retire_csv = mc_summary.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label     = "⬇️ 下載 Monte Carlo 摘要 CSV",
        data      = retire_csv,
        file_name = f"退休提領MC_{retire_asset_wan}萬_{retire_years}年.csv",
        mime      = "text/csv",
    )


def _run_simple_gk(returns, initial_portfolio: float, initial_rate: float, inflation_rate: float) -> list[float]:
    """每年套用固定順序的報酬序列,簡單 GK(不含護欄,僅通膨調整)。"""
    port = initial_portfolio
    wd = initial_portfolio * initial_rate
    trace = [port]
    prev_end = initial_portfolio
    for r in returns:
        if port <= 0:
            trace.append(0)
            continue
        port_grown = port * (1 + r)
        if port_grown >= prev_end:
            wd *= (1 + inflation_rate)
        port_end = max(0, port_grown - wd)
        prev_end = port_grown
        port = port_end
        trace.append(port)
    return trace
