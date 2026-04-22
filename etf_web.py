# -*- coding: utf-8 -*-
"""台股績效分析 — Web UI (Streamlit)"""

import subprocess, sys, io
for pkg in ["streamlit", "pandas", "plotly", "openpyxl"]:
    try:
        __import__(pkg)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])
try:
    from streamlit_local_storage import LocalStorage
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "streamlit-local-storage", "-q"])
    from streamlit_local_storage import LocalStorage

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date as _date
from etf_core import (
    load_token, fetch_adjusted_close, fetch_dividend_history,
    calc_comparison, calc_multi_compare, calc_target_monthly,
    simulate_gk_montecarlo, calc_return_vol,
    fetch_stock_name, run_gk_historical,
    CASH_RETURN, CASH_VOL,
)

# ── Streamlit 記憶體快取包裝（避免每次 rerun 重新讀 CSV / 打 API）─────────────
@st.cache_data(ttl=86400, show_spinner=False)
def _cached_adjusted_close(stock_id: str, token: str):
    """一般讀取，優先從 st.cache_data → 再從磁碟 CSV → 最後才打 API。"""
    return fetch_adjusted_close(stock_id, token, force=False)

@st.cache_data(ttl=86400, show_spinner=False)
def _cached_dividend_history(stock_id: str, token: str):
    return fetch_dividend_history(stock_id, token)

st.set_page_config(page_title="台股績效分析", page_icon="📈", layout="wide")
st.title("📈 台股績效分析")

# ── Token ─────────────────────────────────────────────────────────────────────
token = load_token()
if not token:
    st.error("找不到 FINMIND_TOKEN，請在 .env 檔設定：`FINMIND_TOKEN=你的token`")
    st.stop()

# ── localStorage 持久化設定 ────────────────────────────────────────────────────
import json as _json
_ls = LocalStorage()

# 計算 render 次數（session 重置時歸零）。
# LocalStorage JS 元件在 render 1 時載入，觸發 rerun → render 2 起 getItem 才有值。
# render >= 2 時即使 localStorage 完全空白，也要解鎖寫入（否則永遠存不了）。
if "_ls_render" not in st.session_state:
    st.session_state["_ls_render"] = 0
st.session_state["_ls_render"] += 1

# Step 1: seed session state with hardcoded defaults (only on very first run)
_DEFAULTS: dict = {
    "_w_sid":        "0050",
    "_w_dca":        10000,
    "_w_rasset":     2000,
    "_w_ryears":     30,
    "_w_rinf":       2.0,
    "_w_rrate":      5.0,
    "_w_rguard":     20.0,
    "preset_choice": "保守配息型（預設）",
    # Tab 2 目標試算
    "_w_target_wan":   500,
    "_w_target_years": 10,
    "_w_existing":     0,
    # Tab 4 多檔比較
    "_w_cmp_0": "", "_w_cmp_1": "", "_w_cmp_2": "",
    "_w_cmp_3": "", "_w_cmp_4": "",
    # Tab 6 提領追蹤
    "_w_tk6_port":  2000,
    "_w_tk6_rate":  4.0,
    "_w_tk6_guard": 20,
    "_w_tk6_infl":  2.0,
    "_w_tk6_start": _date(2024, 1, 1),
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# Step 2: on first successful localStorage read, overwrite with saved values.
# All settings packed in one JSON key ("etf_all") to use only one setItem call.
if not st.session_state.get("_ls_applied"):
    _raw_all = _ls.getItem("etf_all")

    if _raw_all is not None:
        # localStorage 有資料 → 還原
        try:
            _saved = _json.loads(_raw_all)
            _field_map = {
                "_w_sid":          (str,   "sid"),
                "_w_dca":          (int,   "dca"),
                "_w_rasset":       (int,   "r_asset"),
                "_w_ryears":       (int,   "r_years"),
                "_w_rinf":         (float, "r_inf"),
                "_w_rrate":        (float, "r_rate"),
                "_w_rguard":       (float, "r_guard"),
                "preset_choice":   (str,   "r_preset"),
                "_w_target_wan":   (int,   "target_wan"),
                "_w_target_years": (int,   "target_years"),
                "_w_existing":     (int,   "existing"),
                "_w_cmp_0":        (str,   "cmp_0"),
                "_w_cmp_1":        (str,   "cmp_1"),
                "_w_cmp_2":        (str,   "cmp_2"),
                "_w_cmp_3":        (str,   "cmp_3"),
                "_w_cmp_4":        (str,   "cmp_4"),
                "_w_tk6_port":     (int,   "tk6_port"),
                "_w_tk6_rate":     (float, "tk6_rate"),
                "_w_tk6_guard":    (int,   "tk6_guard"),
                "_w_tk6_infl":     (float, "tk6_infl"),
            }
            for ss_key, (cast, ls_key) in _field_map.items():
                if ls_key in _saved:
                    try:
                        st.session_state[ss_key] = cast(_saved[ls_key])
                    except (ValueError, TypeError):
                        pass
            if "tk6_start" in _saved:
                try:
                    st.session_state["_w_tk6_start"] = _date.fromisoformat(_saved["tk6_start"])
                except (ValueError, TypeError):
                    pass
            if "tk6_alloc" in _saved and isinstance(_saved["tk6_alloc"], list):
                st.session_state["tk6_alloc_base"] = _saved["tk6_alloc"]
            if "r_custom" in _saved and isinstance(_saved["r_custom"], list):
                # 相容舊 localStorage：欄位曾叫 "ETF代號"，已改名為 "代號"
                st.session_state["_custom_base"] = [
                    {("代號" if k == "ETF代號" else k): v for k, v in row.items()}
                    for row in _saved["r_custom"]
                ]
                st.session_state.pop("retire_portfolio_custom", None)
                st.session_state["_custom_ls_done"] = True
        except Exception:
            pass
        st.session_state["_ls_applied"] = True
        # prev 設為 "" → 底部一定觸發一次 setItem，確保 etf_all 與 session 同步
        st.session_state["_lsprev_etf_all"] = ""

    elif st.session_state["_ls_render"] >= 2:
        # JS 元件已載入但 localStorage 是空白（全新瀏覽器 / 清除過）→ 解鎖寫入
        st.session_state["_ls_applied"] = True
        st.session_state["_lsprev_etf_all"] = ""

# ── 全域輸入（所有 tab 共用） ─────────────────────────────────────────────────
c1, c2, c3 = st.columns([2, 2, 1])
stock_id    = c1.text_input("股票代號（不需要 .TW）",
                             key="_w_sid").upper().removesuffix(".TW")
monthly_dca = c2.number_input("每月定期定額（TWD）", min_value=1000,
                               step=1000, key="_w_dca")
c3.write(""); c3.write("")
refresh = c3.button("🔄 重新下載", width="stretch")


st.divider()

if not stock_id:
    st.info("請輸入股票代號")
    st.stop()

# ── 載入完整資料（所有 tab 共用） ────────────────────────────────────────────
with st.spinner(f"載入 {stock_id} 資料..."):
    try:
        if refresh:
            # 強制重抓：清除 st.cache_data，直接打 API 更新磁碟快取
            _cached_adjusted_close.clear()
            _cached_dividend_history.clear()
            close_full, _ = fetch_adjusted_close(stock_id, token, force=True)
        else:
            close_full, _ = _cached_adjusted_close(stock_id, token)
    except Exception as e:
        st.error(str(e)); st.stop()

# ── 分頁 ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 績效分析", "🎯 目標試算", "🏖️ 退休提領模擬", "📋 提領追蹤", "📈 多檔比較", "💰 股利歷史",
])


# ════════════════════════════════════════════════════════════════════════════
# Tab 1：績效分析
# ════════════════════════════════════════════════════════════════════════════
with tab1:
    min_date = close_full.index[0].date()
    max_date = close_full.index[-1].date()

    with st.expander("⚙️ 自訂分析起始日（預設：上市日）", expanded=False):
        custom_start = st.date_input(
            "分析起始日",
            value=min_date,
            min_value=min_date,
            max_value=max_date,
            key=f"custom_start_date_{stock_id}",
        )
        if custom_start > min_date:
            st.caption(f"上市日為 {min_date}，目前從 {custom_start} 開始分析")

    close = close_full[close_full.index >= pd.Timestamp(custom_start)]
    if len(close) < 2:
        st.error("所選起始日後資料不足，請選擇更早的日期")
        st.stop()

    result = calc_comparison(close, monthly_dca)
    lump   = result.lump
    dca    = result.dca
    f      = dca.final

    # 摘要卡片
    st.subheader(f"{stock_id}　{lump.inception_date.date()} ～ {lump.last_date.date()}　（{lump.years:.1f} 年）")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("單筆總報酬",       f"{lump.total_return_pct:+,.1f}%")
    c2.metric("單筆年化報酬",     f"{lump.cagr_pct:+.2f}%")
    c3.metric("定期定額總報酬",   f"{f.return_pct:+.1f}%")
    c4.metric("定期定額年化報酬", f"{result.dca_cagr_pct:+.2f}%")

    # 逐年績效表
    st.subheader(f"定期定額每月 {monthly_dca:,.0f} TWD — 逐年績效")
    df = pd.DataFrame([{
        "年度"       : r.year,
        "累計投入"   : f"{r.cost_cum:,.0f}",
        "期末市值"   : f"{r.value:,.0f}",
        "未實現損益" : r.gain,
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
            subset=["未實現損益", "累計報酬率%"]
        ).format({"未實現損益": "{:,.0f}"}),
        width="stretch", hide_index=True
    )

    # 折線圖
    st.subheader("期末市值 vs 累計投入")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["年度"], y=df["期末市值"], name="期末市值", mode="lines+markers"))
    fig.add_trace(go.Scatter(x=df["年度"], y=df["累計投入"], name="累計投入", mode="lines+markers", line=dict(dash="dash")))
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

    def build_excel(stock_id, monthly_dca, lump, result, df, cmp) -> bytes:
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

    excel_bytes = build_excel(stock_id, monthly_dca, lump, result, df, cmp)
    filename    = f"{stock_id}_績效分析_{lump.last_date.strftime('%Y%m%d')}.xlsx"

    dl1, dl2 = st.columns(2)
    dl1.download_button(
        label    = "⬇️ 下載 Excel（含三個工作表）",
        data     = excel_bytes,
        file_name= filename,
        mime     = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width    = "stretch",
    )
    csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
    dl2.download_button(
        label    = "⬇️ 下載 CSV（逐年績效）",
        data     = csv_bytes,
        file_name= f"{stock_id}_逐年績效_{lump.last_date.strftime('%Y%m%d')}.csv",
        mime     = "text/csv",
        width    = "stretch",
    )


# ════════════════════════════════════════════════════════════════════════════
# Tab 2：目標試算
# ════════════════════════════════════════════════════════════════════════════
with tab2:
    # 需要 lump.cagr_pct，先用全期計算
    from etf_core import calc_lump_sum
    lump_full = calc_lump_sum(close_full)

    st.subheader("🎯 目標終值試算")
    st.caption(f"以 {stock_id} 歷史年化報酬 **{lump_full.cagr_pct:.2f}%** 為基準試算")

    tc1, tc2, tc3 = st.columns(3)
    target_wan    = tc1.number_input("目標金額（萬 TWD）",         min_value=1,   step=100, key="_w_target_wan")
    target_years  = tc2.number_input("投資年限（年）",              min_value=1,   max_value=50, step=1, key="_w_target_years")
    existing_wan  = tc3.number_input("目前已持有此標的（萬 TWD）", min_value=0,   step=10,  key="_w_existing")

    target_twd   = target_wan   * 10_000
    existing_twd = existing_wan * 10_000
    base = calc_target_monthly(target_twd, target_years, lump_full.cagr_pct, existing=existing_twd)

    rc1, rc2, rc3 = st.columns(3)
    rc1.metric("每月需投入",       f"{base['monthly']:,.0f} TWD")
    rc2.metric("一次性投入等效",   f"{base['lump_sum_today']:,.0f} TWD")
    rc3.metric("現有持倉屆時終值", f"{base['existing_fv']:,.0f} TWD")
    rd1, rd2, rd3 = st.columns(3)
    rd1.metric("新增投入本金",     f"{base['total_invested']:,.0f} TWD")
    rd2.metric("預估最終資產終值", f"{base['terminal_value']:,.0f} TWD")

    if base['monthly'] == 0:
        st.success(f"🎉 現有持倉預計 {target_years} 年後即可達標，不需額外定投！")
    else:
        total_new = existing_twd + base['total_invested']
        st.caption(
            f"新增投入本金：{base['total_invested']:,.0f}　＋　現有持倉：{existing_twd:,.0f}"
            f"　＝　總投入成本：{total_new:,.0f} TWD　｜　"
            f"預計獲利：{base['total_gain']:,.0f} TWD"
        )

    st.divider()
    st.subheader("敏感度分析（不同報酬情境）")
    scenarios = [0.5, 0.75, 1.0, 1.25, 1.5]
    scenario_rows = []
    for mult in scenarios:
        rate = lump_full.cagr_pct * mult
        res  = calc_target_monthly(target_twd, target_years, rate, existing=existing_twd)
        scenario_rows.append({
            "情境"            : f"{mult*100:.0f}% 歷史報酬",
            "假設年化報酬%"   : f"{rate:.2f}",
            "持倉屆時終值"    : f"{res['existing_fv']:,.0f}",
            "每月投入 (TWD)"  : f"{res['monthly']:,.0f}",
            "新增投入本金"    : f"{res['total_invested']:,.0f}",
            "最終資產終值"    : f"{res['terminal_value']:,.0f}",
            "預計獲利 (TWD)"  : f"{res['total_gain']:,.0f}",
        })
    sens_df = pd.DataFrame(scenario_rows)
    st.dataframe(sens_df, width="stretch", hide_index=True)


# ════════════════════════════════════════════════════════════════════════════
# Tab 6：股利歷史
# ════════════════════════════════════════════════════════════════════════════
with tab6:
    st.subheader("💰 股利發放歷史")

    with st.spinner("載入股利資料..."):
        try:
            div_df = _cached_dividend_history(stock_id, token)
        except Exception as e:
            st.error(f"載入股利資料失敗：{e}")
            st.stop()

    if div_df.empty:
        st.info(f"{stock_id} 無股利發放記錄（可能為非配息型股票/ETF）")
    else:
        avg_yield = div_df["yield_pct"].mean()
        total_div = div_df["cash_dividend"].sum()
        dc1, dc2, dc3 = st.columns(3)
        dc1.metric("發放次數",     f"{len(div_df)} 次")
        dc2.metric("歷史平均殖利率", f"{avg_yield:.2f}%")
        dc3.metric("累計配息",     f"{total_div:.2f} TWD/股")

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
                    "配息(TWD/股)" : "{:.4f}",
                    "除息前股價"   : "{:.2f}",
                    "除息後股價"   : "{:.2f}",
                    "殖利率%"      : "{:.2f}",
                }),
                width="stretch", hide_index=True
            )


# ════════════════════════════════════════════════════════════════════════════
# Tab 5：多檔比較
# ════════════════════════════════════════════════════════════════════════════
with tab5:
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
    else:
        with st.spinner("載入比較資料..."):
            closes = {}
            errors = []
            for sid in ids:
                try:
                    c, _ = _cached_adjusted_close(sid, token)
                    closes[sid] = c
                except Exception as e:
                    errors.append(f"{sid}：{e}")
            for err in errors:
                st.warning(err)

        if len(closes) >= 2:
            try:
                records = calc_multi_compare(closes, monthly_dca)
            except Exception as e:
                st.error(f"比較計算失敗：{e}")
                st.stop()
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

            cmp_df = pd.DataFrame([{
                "代號"         : r.stock_id,
                "原始上市日"   : str(r.inception_date.date()),
                "共同起始日"   : str(r.common_start.date()),
                "比較年數"     : f"{r.years:.2f}",
                "總報酬%"      : f"{r.total_return_pct:.1f}",
                "年化報酬%"    : round(r.cagr_pct, 2),
                f"DCA終值(月投{monthly_dca:,.0f})": f"{r.dca_final:,.0f}",
                "DCA年化%"     : f"{r.dca_cagr_pct:.2f}",
            } for r in records])

            st.dataframe(
                cmp_df.style.map(
                    lambda v: "color: green; font-weight: bold"
                    if isinstance(v, float) and v == max(
                        x for x in cmp_df["年化報酬%"] if isinstance(x, float)
                    ) else "",
                    subset=["年化報酬%"]
                ).format({"年化報酬%": "{:.2f}"}),
                width="stretch", hide_index=True
            )

            cmp_csv = cmp_df.drop(columns=["原始上市日"]).to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label    = "⬇️ 下載比較結果 CSV",
                data     = cmp_csv,
                file_name= f"多檔比較_{'_'.join(r.stock_id for r in records)}_{last_date.strftime('%Y%m%d')}.csv",
                mime     = "text/csv",
            )


# ════════════════════════════════════════════════════════════════════════════
# Tab 3：退休提領模擬（Guyton-Klinger + Monte Carlo）
# ════════════════════════════════════════════════════════════════════════════
with tab3:
    import numpy as np

    # 現金固定假設（無上市 ETF）
    _CASH_RETURN = CASH_RETURN
    _CASH_VOL    = CASH_VOL

    # 預設組合定義
    _PRESETS = {
        "保守配息型（預設）": [
            {"資產名稱": "元大台灣高股息",    "代號": "0056",   "配置比例 %": 30},
            {"資產名稱": "國泰永續高股息",    "代號": "00878",  "配置比例 %": 20},
            {"資產名稱": "元大投資級公司債",  "代號": "00720B", "配置比例 %": 30},
            {"資產名稱": "元大美債20年",      "代號": "00679B", "配置比例 %": 10},
            {"資產名稱": "現金 / 貨幣市場",   "代號": "現金",   "配置比例 %": 10},
        ],
        "債券優先型": [
            {"資產名稱": "元大投資級公司債",  "代號": "00720B", "配置比例 %": 40},
            {"資產名稱": "元大美債20年",      "代號": "00679B", "配置比例 %": 25},
            {"資產名稱": "元大台灣高股息",    "代號": "0056",   "配置比例 %": 25},
            {"資產名稱": "現金 / 貨幣市場",   "代號": "現金",   "配置比例 %": 10},
        ],
        "全高股息型": [
            {"資產名稱": "元大台灣高股息",    "代號": "0056",   "配置比例 %": 35},
            {"資產名稱": "國泰永續高股息",    "代號": "00878",  "配置比例 %": 30},
            {"資產名稱": "元大台灣高息低波",  "代號": "00713",  "配置比例 %": 15},
            {"資產名稱": "現金 / 貨幣市場",   "代號": "現金",   "配置比例 %": 20},
        ],
        "均衡穩健型": [
            {"資產名稱": "元大台灣50",        "代號": "0050",   "配置比例 %": 15},
            {"資產名稱": "國泰永續高股息",    "代號": "00878",  "配置比例 %": 20},
            {"資產名稱": "元大投資級公司債",  "代號": "00720B", "配置比例 %": 30},
            {"資產名稱": "元大美債20年",      "代號": "00679B", "配置比例 %": 15},
            {"資產名稱": "現金 / 貨幣市場",   "代號": "現金",   "配置比例 %": 20},
        ],
        "槓桿平衡型": [
            {"資產名稱": "元大台灣50正2",     "代號": "00631L", "配置比例 %": 50},
            {"資產名稱": "現金 / 貨幣市場",   "代號": "現金",   "配置比例 %": 50},
        ],
    }

    st.subheader("🏖️ 退休提領模擬 — Guyton-Klinger × Monte Carlo")
    st.caption(
        "目標達成後轉換為保守組合，以 GK 動態提領策略提領。"
        "報酬率與波動度**自動從 FinMind 歷史資料計算**，執行 1,000 次 Monte Carlo 模擬。"
    )

    # ── 基本參數 ──────────────────────────────────────────────────────────────
    st.markdown("#### ⚙️ 基本參數")
    pc1, pc2, pc3 = st.columns(3)
    retire_asset_wan = pc1.number_input(
        "退休起始資產（萬 TWD）", min_value=100, step=100,
        key="_w_rasset", help="可直接填入「目標試算」頁的目標金額",
    )
    retire_years  = pc2.number_input("模擬年數", min_value=5, max_value=60,
                                     step=5, key="_w_ryears")
    inflation_pct = pc3.number_input("通膨率 %", min_value=0.0, max_value=10.0,
                                     step=0.5, key="_w_rinf")

    pg1, pg2, pg3 = st.columns(3)
    init_rate_pct = pg1.number_input("初始提領率 %", min_value=1.0, max_value=15.0,
                                     step=0.5, key="_w_rrate")
    _init_monthly = retire_asset_wan * 10_000 * init_rate_pct / 100 / 12
    pg2.number_input("初始月提領額（TWD）", value=_init_monthly, disabled=True, format="%.0f")
    _guard_prev = st.session_state.get("_w_rguard", 20.0)
    _gu = init_rate_pct * (1 + _guard_prev / 100)
    _gl = init_rate_pct * (1 - _guard_prev / 100)
    guardrail_pct = pg3.number_input(
        "護欄寬度 %",
        min_value=5.0, max_value=50.0, step=5.0, key="_w_rguard",
        help=(
            f"初始提領率 {init_rate_pct:.1f}%，護欄寬度 ±{_guard_prev:.0f}%\n\n"
            f"當前提領率 > {_gu:.2f}% → 提領額 ×0.9（減 10%）\n\n"
            f"當前提領率 < {_gl:.2f}% → 提領額 ×1.1（加 10%）\n\n"
            f"繁榮規則（↑）僅在資產未低於去年一月時觸發。"
        ),
    )

    st.caption(
        f"護欄觸發：提領率 > **{init_rate_pct*(1+guardrail_pct/100):.2f}%** 減10%；"
        f"< **{init_rate_pct*(1-guardrail_pct/100):.2f}%** 加10%"
    )

    # ── 退休後投資組合 ────────────────────────────────────────────────────────
    st.markdown("#### 🗂️ 退休後投資組合")

    preset_names = list(_PRESETS.keys()) + ["自訂"]
    preset_choice = st.radio(
        "選擇預設組合",
        preset_names,
        horizontal=True,
        key="preset_choice",
    )

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
        # 若 session 內沒有 base（第一次或清掉了），用預設組合
        if "_custom_base" not in st.session_state:
            st.session_state["_custom_base"] = [
                {"代號": row["代號"], "配置比例 %": row["配置比例 %"]}
                for row in _PRESETS["保守配息型（預設）"]
            ]

        # normalize 欄名（相容舊 localStorage 中 "ETF代號" → "代號"）
        _base_rows = [
            {("代號" if k == "ETF代號" else k): v for k, v in row.items()}
            for row in st.session_state["_custom_base"]
        ]
        custom_editor = st.data_editor(
            pd.DataFrame(_base_rows),
            num_rows="dynamic",
            width="stretch",
            key="retire_portfolio_custom",
            column_config={
                "代號":    st.column_config.TextColumn(
                    help="台股代號（ETF 或個股），現金請填「現金」",
                    required=True,
                ),
                "配置比例 %": st.column_config.NumberColumn(
                    min_value=0, max_value=100, step=5, format="%.0f",
                ),
            },
        )
        # 把 data_editor 的 DataFrame return value 存進 session state，
        # 讓底部的存檔邏輯能讀到（session_state["retire_portfolio_custom"] 存的是 delta dict，不是 DataFrame）
        st.session_state["_custom_df_value"] = custom_editor

        # 自動帶入資產名稱（從 FinMind TaiwanStockInfo 查詢）
        with st.spinner("查詢股票名稱..."):
            custom_editor["資產名稱"] = custom_editor["代號"].apply(
                lambda c: fetch_stock_name(str(c).strip().upper(), token) if str(c).strip() else ""
            )
        portfolio_df = custom_editor[["資產名稱", "代號", "配置比例 %"]]
    else:
        _init_data = _PRESETS[preset_choice]
        portfolio_df = st.data_editor(
            pd.DataFrame(_init_data),
            num_rows="fixed",
            width="stretch",
            key=f"retire_portfolio_{preset_choice}",
            column_config={
                "資產名稱":   st.column_config.TextColumn(disabled=True),
                "代號":    st.column_config.TextColumn(disabled=True),
                "配置比例 %": st.column_config.NumberColumn(
                    min_value=0, max_value=100, step=5, format="%.0f",
                ),
            },
        )

    total_alloc = portfolio_df["配置比例 %"].sum()
    if abs(total_alloc - 100) > 0.5:
        st.warning(f"⚠️ 配置比例加總為 {total_alloc:.1f}%，請調整至 100%")
        st.stop()

    # ── 自動計算歷史報酬與波動度 ─────────────────────────────────────────────
    st.markdown("#### 📡 歷史報酬自動計算（從 FinMind）")

    etf_stats: dict[str, tuple[float, float, str, float]] = {}
    stat_rows = []
    fetch_errors = []
    _codes = [
        str(r["代號"]).strip().upper()
        for _, r in portfolio_df.iterrows()
        if str(r["代號"]).strip().upper() != "現金"
    ]
    _spinner_msg = f"載入 {', '.join(_codes)} 歷史資料..." if _codes else "計算中..."

    with st.spinner(_spinner_msg):
        for _, row in portfolio_df.iterrows():
            code = str(row["代號"]).strip().upper()
            if code == "現金":
                etf_stats[code] = (_CASH_RETURN, _CASH_VOL, "固定假設", 999)
                stat_rows.append({
                    "資產名稱":     row["資產名稱"],
                    "代號":      "現金",
                    "資料期間":     "固定假設",
                    "歷史CAGR %":   f"{_CASH_RETURN*100:.2f}",
                    "年化波動度 %": f"{_CASH_VOL*100:.2f}",
                })
            else:
                try:
                    close_r, _ = _cached_adjusted_close(code, token)
                    cagr, vol  = calc_return_vol(close_r)
                    period     = f"{close_r.index[0].date()} ～ {close_r.index[-1].date()}"
                    yrs        = (close_r.index[-1] - close_r.index[0]).days / 365.25
                    warn       = " ⚠️ 歷史<10年" if yrs < 10 else ""
                    etf_stats[code] = (cagr, vol, period, yrs)
                    stat_rows.append({
                        "資產名稱":     row["資產名稱"],
                        "代號":      code,
                        "資料期間":     period + warn,
                        "歷史CAGR %":   f"{cagr*100:.2f}",
                        "年化波動度 %": f"{vol*100:.2f}",
                    })
                except Exception as e:
                    fetch_errors.append(f"{code}：{e}")

    for err in fetch_errors:
        st.error(err)

    if fetch_errors:
        st.stop()

    st.dataframe(pd.DataFrame(stat_rows), width="stretch", hide_index=True)

    # 短歷史警告
    short_hist_etfs = [
        (str(row["代號"]).strip().upper(), row["資產名稱"])
        for _, row in portfolio_df.iterrows()
        if str(row["代號"]).strip().upper() != "現金"
        and etf_stats.get(str(row["代號"]).strip().upper(), (0, 0, "", 999))[3] < 10
    ]
    if short_hist_etfs:
        names = "、".join(f"{code}（{name}）" for code, name in short_hist_etfs)
        st.warning(
            f"⚠️ **回測期間不足警告**\n\n"
            f"以下標的歷史資料不足 10 年：**{names}**。\n\n"
            "其 CAGR 可能因取樣期間恰好涵蓋多頭行情而**嚴重高估長期報酬**，"
            "以此數字進行退休模擬時請保守解讀結果，建議實際規劃時適度下調預期報酬假設。"
        )

    # 加權計算
    w_ret = 0.0
    w_vol = 0.0
    for _, row in portfolio_df.iterrows():
        code   = str(row["代號"]).strip().upper()
        weight = row["配置比例 %"] / 100
        cagr, vol, _, _yrs = etf_stats.get(code, (_CASH_RETURN, _CASH_VOL, "", 999))
        w_ret += weight * cagr
        w_vol += weight * vol

    short_note = "　⚠️ 含短歷史標的，報酬偏高屬正常，請保守解讀" if short_hist_etfs else ""
    st.success(
        f"✅ 加權歷史年化報酬：**{w_ret*100:.2f}%**　｜　加權年化波動度：**{w_vol*100:.2f}%**"
        f"　（波動度為各資產加權平均，未考慮資產間相關係數）{short_note}"
    )

    st.divider()

    # ── Monte Carlo 模擬 ──────────────────────────────────────────────────────
    retire_asset = retire_asset_wan * 10_000

    try:
        with st.spinner("執行 2,000 次 Monte Carlo 模擬中..."):
            mc = simulate_gk_montecarlo(
                initial_portfolio = retire_asset,
                initial_rate      = init_rate_pct / 100,
                guardrail_pct     = guardrail_pct / 100,
                annual_return     = w_ret,
                annual_volatility = w_vol,
                inflation_rate    = inflation_pct / 100,
                years             = int(retire_years),
                n_sims            = 2000,
            )
    except Exception as e:
        st.error(f"Monte Carlo 模擬失敗：{e}")
        st.stop()

    # ── 摘要指標 ──────────────────────────────────────────────────────────────
    st.markdown("#### 📋 模擬結果摘要（2,000 次模擬）")
    sm1, sm2, sm3, sm4 = st.columns(4)
    sm1.metric("初始月提領額",   f"{mc['initial_monthly']:,.0f} TWD")
    sm2.metric(f"第{retire_years}年存活率", f"{mc['survival_final']:.1f}%")
    sm3.metric("資產耗盡機率",   f"{mc['depleted_pct']:.1f}%")
    p50_final = mc["port_pct"][50][-1]
    sm4.metric("P50 期末資產",   f"{p50_final/10_000:,.0f} 萬 TWD")

    # ── 圖1：資產餘額百分位扇形圖 ─────────────────────────────────────────────
    st.markdown("#### 📊 資產餘額分布（百分位數）")
    yrs = mc["years"]

    fig_port = go.Figure()
    # 填色區間：P10–P90
    fig_port.add_trace(go.Scatter(
        x=list(yrs) + list(yrs[::-1]),
        y=list(mc["port_pct"][90] / 10_000) + list(mc["port_pct"][10][::-1] / 10_000),
        fill="toself", fillcolor="rgba(70,130,180,0.15)",
        line=dict(color="rgba(0,0,0,0)"), name="P10–P90", showlegend=True,
    ))
    fig_port.add_trace(go.Scatter(
        x=list(yrs) + list(yrs[::-1]),
        y=list(mc["port_pct"][75] / 10_000) + list(mc["port_pct"][25][::-1] / 10_000),
        fill="toself", fillcolor="rgba(70,130,180,0.30)",
        line=dict(color="rgba(0,0,0,0)"), name="P25–P75", showlegend=True,
    ))
    for p, color, dash in [(50, "steelblue", "solid"), (10, "tomato", "dash"), (90, "seagreen", "dash")]:
        fig_port.add_trace(go.Scatter(
            x=yrs, y=mc["port_pct"][p] / 10_000,
            name=f"P{p}", mode="lines",
            line=dict(color=color, dash=dash, width=2 if p == 50 else 1.5),
        ))
    fig_port.add_hline(y=0, line_dash="dot", line_color="gray")
    fig_port.update_layout(
        xaxis_title="退休後第幾年",
        yaxis_title="資產餘額（萬 TWD）",
        hovermode="x unified",
        legend=dict(orientation="h", y=1.08),
    )
    st.plotly_chart(fig_port, width="stretch")

    # ── 圖2：月提領額百分位 ───────────────────────────────────────────────────
    st.markdown("#### 💵 每月提領額分布（百分位數）")
    fig_wd = go.Figure()
    fig_wd.add_trace(go.Scatter(
        x=list(yrs) + list(yrs[::-1]),
        y=list(mc["wd_pct"][90]) + list(mc["wd_pct"][10][::-1]),
        fill="toself", fillcolor="rgba(46,139,87,0.15)",
        line=dict(color="rgba(0,0,0,0)"), name="P10–P90",
    ))
    fig_wd.add_trace(go.Scatter(
        x=list(yrs) + list(yrs[::-1]),
        y=list(mc["wd_pct"][75]) + list(mc["wd_pct"][25][::-1]),
        fill="toself", fillcolor="rgba(46,139,87,0.30)",
        line=dict(color="rgba(0,0,0,0)"), name="P25–P75",
    ))
    for p, color, dash in [(50, "seagreen", "solid"), (10, "tomato", "dash"), (90, "royalblue", "dash")]:
        fig_wd.add_trace(go.Scatter(
            x=yrs, y=mc["wd_pct"][p],
            name=f"P{p}", mode="lines",
            line=dict(color=color, dash=dash, width=2 if p == 50 else 1.5),
        ))
    fig_wd.update_layout(
        xaxis_title="退休後第幾年",
        yaxis_title="每月提領額（TWD）",
        hovermode="x unified",
        legend=dict(orientation="h", y=1.08),
    )
    st.plotly_chart(fig_wd, width="stretch")

    # ── 圖3：逐年存活率 ───────────────────────────────────────────────────────
    st.markdown("#### 📉 逐年存活率")
    fig_surv = go.Figure()
    fig_surv.add_trace(go.Scatter(
        x=yrs, y=mc["survival_rate"],
        mode="lines+markers", line=dict(color="steelblue", width=2),
        fill="toself", fillcolor="rgba(70,130,180,0.15)",
        name="存活率 %",
    ))
    fig_surv.add_hline(y=80, line_dash="dash", line_color="orange",
                       annotation_text="80% 安全門檻")
    fig_surv.add_hline(y=50, line_dash="dash", line_color="tomato",
                       annotation_text="50%")
    fig_surv.update_layout(
        xaxis_title="退休後第幾年",
        yaxis_title="資產存活率 %",
        yaxis=dict(range=[0, 105]),
        hovermode="x unified",
    )
    st.plotly_chart(fig_surv, width="stretch")

    # ── 逐年 Monte Carlo 百分位明細 ────────────────────────────────────────────
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
                    st.dataframe(
                        pd.DataFrame(mc["rep_paths"][pct]),
                        width="stretch", hide_index=True,
                    )

    # ── GK 策略說明 ────────────────────────────────────────────────────────────
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

    # ── 下載 ──────────────────────────────────────────────────────────────────
    mc_summary = pd.DataFrame({
        "年度":          yrs,
        "P10資產(萬)":   (mc["port_pct"][10] / 10_000).round(1),
        "P25資產(萬)":   (mc["port_pct"][25] / 10_000).round(1),
        "P50資產(萬)":   (mc["port_pct"][50] / 10_000).round(1),
        "P75資產(萬)":   (mc["port_pct"][75] / 10_000).round(1),
        "P90資產(萬)":   (mc["port_pct"][90] / 10_000).round(1),
        "P50月提領":     mc["wd_pct"][50].round(0).astype(int),
        "存活率%":       mc["survival_rate"].round(1),
    })
    retire_csv = mc_summary.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label    = "⬇️ 下載 Monte Carlo 摘要 CSV",
        data     = retire_csv,
        file_name= f"退休提領MC_{retire_asset_wan}萬_{retire_years}年.csv",
        mime     = "text/csv",
    )

# ════════════════════════════════════════════════════════════════════════════
# Tab 4：提領追蹤（GK 歷史實際報酬逐月追蹤 + 再平衡）
# ════════════════════════════════════════════════════════════════════════════
with tab4:
    import numpy as _np6

    st.subheader("📋 提領策略追蹤")
    st.caption(
        "輸入開始提領的時間與初始條件，系統以**歷史實際報酬**逐月追蹤 GK 提領策略結果。"
        "每年一月自動進行 GK 護欄檢查與資產再平衡建議。"
    )

    # ── 參數輸入 ──────────────────────────────────────────────────────────────
    st.markdown("#### ⚙️ 基本參數")
    _ta, _tb, _tc, _td = st.columns(4)
    tk6_port  = _ta.number_input("初始資產（萬 TWD）", min_value=1, step=100, key="_w_tk6_port")
    tk6_rate  = _tb.number_input("初始提領率 %",       min_value=0.5, max_value=15.0, step=0.5, key="_w_tk6_rate")
    _guard6_prev = st.session_state.get("_w_tk6_guard", 20)
    _gu6 = tk6_rate * (1 + _guard6_prev / 100)
    _gl6 = tk6_rate * (1 - _guard6_prev / 100)
    tk6_guard = _tc.number_input(
        "護欄寬度 %",
        min_value=1, max_value=50, step=5, key="_w_tk6_guard",
        help=(
            f"初始提領率 {tk6_rate:.1f}%，護欄寬度 ±{_guard6_prev:.0f}%\n\n"
            f"當前提領率 > {_gu6:.2f}% → 提領額 ×0.9（減 10%）\n\n"
            f"當前提領率 < {_gl6:.2f}% → 提領額 ×1.1（加 10%）\n\n"
            f"繁榮規則（↑）僅在資產未低於去年一月時觸發。"
        ),
    )
    tk6_infl  = _td.number_input("通膨率 %",           min_value=0.0, max_value=10.0, step=0.5, key="_w_tk6_infl")

    st.caption(
        f"護欄觸發：提領率 > **{tk6_rate*(1+tk6_guard/100):.2f}%** 減10%；"
        f"< **{tk6_rate*(1-tk6_guard/100):.2f}%** 加10%"
    )

    _te, _tf = st.columns([1, 3])
    tk6_start = _te.date_input(
        "開始提領月份",
        min_value=_date(2003, 1, 1),
        key="_w_tk6_start",
        help="選擇月份即可，日期忽略",
    )

    st.markdown("#### 📦 持倉配置（目標比例）")
    _tk6_default_rows = [
        {"代號": "0050",   "配置比例 %": 90},
        {"代號": "00859B", "配置比例 %": 5},
        {"代號": "現金",   "配置比例 %": 5},
    ]
    if "tk6_alloc_base" not in st.session_state:
        st.session_state["tk6_alloc_base"] = _tk6_default_rows

    tk6_editor = st.data_editor(
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
    st.session_state["tk6_alloc_df"] = tk6_editor

    # 驗證總和
    _tk6_total = int(tk6_editor["配置比例 %"].sum())
    if _tk6_total != 100:
        st.warning(f"配置比例總和為 {_tk6_total}%，需等於 100% 才能執行。")
        st.stop()

    # 建立 allocations dict
    tk6_allocations: dict[str, float] = {
        str(row["代號"]).strip().upper(): row["配置比例 %"] / 100
        for _, row in tk6_editor.iterrows()
        if str(row["代號"]).strip() and row["配置比例 %"] > 0
    }
    # 現金特殊處理（不大寫）
    if "現金" not in tk6_allocations and "現金".upper() in tk6_allocations:
        tk6_allocations["現金"] = tk6_allocations.pop("現金".upper())
    # 修正大寫問題
    _fixed = {}
    for k, v in tk6_allocations.items():
        _fixed["現金" if k in ("現金", "CASH", "現金".upper()) else k] = v
    tk6_allocations = _fixed

    st.divider()

    # ── 取得歷史資料 ──────────────────────────────────────────────────────────
    _tk6_close_map: dict[str, pd.Series] = {}
    _tk6_fetch_errors = []
    for _asset in tk6_allocations:
        if _asset == "現金":
            continue
        try:
            _close, _ = _cached_adjusted_close(_asset, token)
            _tk6_close_map[_asset] = _close
        except Exception as _e:
            _tk6_fetch_errors.append(f"{_asset}：{_e}")

    if _tk6_fetch_errors:
        for _err in _tk6_fetch_errors:
            st.error(f"資料取得失敗 — {_err}")
        st.stop()

    # ── 執行歷史追蹤 ──────────────────────────────────────────────────────────
    _tk6_start_ym = tk6_start.strftime("%Y-%m")
    try:
        with st.spinner("以歷史資料逐月計算 GK 提領策略..."):
            _tk6_result = run_gk_historical(
                initial_portfolio = tk6_port * 10_000,
                allocations       = tk6_allocations,
                start_ym          = _tk6_start_ym,
                initial_rate      = tk6_rate / 100,
                guardrail_pct     = tk6_guard / 100,
                inflation_rate    = tk6_infl / 100,
                close_series      = _tk6_close_map,
            )
    except Exception as _e:
        st.error(f"計算失敗：{_e}")
        st.stop()

    _tk6_monthly    = _tk6_result["monthly"]
    _tk6_rebalances = _tk6_result["rebalances"]

    for _dw in _tk6_result.get("data_warnings", []):
        st.warning(_dw)

    if not _tk6_monthly:
        st.warning("所選月份無歷史資料，請調整起始月份。")
        st.stop()

    # ── 摘要指標 ──────────────────────────────────────────────────────────────
    _tk6_m1, _tk6_m2, _tk6_m3, _tk6_m4 = st.columns(4)
    _tk6_m1.metric("目前資產",       f"{_tk6_result['final_portfolio']/10_000:,.0f} 萬 TWD")
    _tk6_m2.metric("目前月提領額",   f"{_tk6_result['final_monthly_income']:,.0f} TWD")
    _initial_monthly = tk6_port * 10_000 * tk6_rate / 100 / 12
    _tk6_m3.metric("初始月提領額",   f"{_initial_monthly:,.0f} TWD",
                   delta=f"{_tk6_result['final_monthly_income'] - _initial_monthly:+,.0f}")
    _tk6_m4.metric("追蹤期間",       f"{len(_tk6_monthly)} 個月 / {len(_tk6_rebalances)} 次再平衡")

    # ── 逐月明細表 ────────────────────────────────────────────────────────────
    with st.expander("📅 逐月明細", expanded=False):
        st.dataframe(pd.DataFrame(_tk6_monthly), hide_index=True, width="stretch")

    # ── 年度再平衡事件 ────────────────────────────────────────────────────────
    if _tk6_rebalances:
        st.markdown("#### 🔄 年度再平衡事件（每年一月）")
        st.caption("GK 護欄檢查與資產再平衡建議。每筆均可輸入實際持倉取得精確交易指示。")

        _gk_label_map = {
            "capital_preservation": "↓ 減提領 10%（提領率過高）",
            "prosperity":           "↑ 增提領 10%（提領率過低）",
            "":                     "通膨調整（無護欄觸發）",
        }

        for _rb in _tk6_rebalances:
            _is_latest = (_rb is _tk6_rebalances[-1])
            _rb_title = (
                f"**{_rb['year']} 年一月再平衡**　｜　"
                f"資產 {_rb['portfolio']/10_000:,.0f} 萬　｜　"
                f"新月提領 {_rb['monthly_income']:,.0f} TWD"
            )
            with st.expander(_rb_title, expanded=_is_latest):
                # GK 調整
                st.info(f"GK 調整：{_gk_label_map.get(_rb['gk_trigger'], '—')}")

                # 配置漂移表
                _alloc_rows = []
                for _a in _rb["target_alloc"]:
                    _target = _rb["target_alloc"][_a] * 100
                    _drift  = _rb["drift_alloc"].get(_a, 0.0) * 100
                    _trade  = _rb["trades"].get(_a, 0.0)
                    _alloc_rows.append({
                        "標的":             _a,
                        "目標 %":           f"{_target:.1f}",
                        "漂移後實際 %":     f"{_drift:.1f}",
                        "偏差":             f"{_drift - _target:+.1f}",
                        "再平衡建議（萬）": (
                            f"{'買入' if _trade > 0 else '賣出'} {abs(_trade)/10_000:,.1f}"
                            if abs(_trade) > 500 else "—"
                        ),
                    })
                st.dataframe(pd.DataFrame(_alloc_rows), hide_index=True, width=600)

                # ── 互動式實際持倉輸入 ────────────────────────────────────────
                st.markdown("---")
                st.markdown("**💡 輸入您的實際持倉，取得精確再平衡建議**")
                st.caption("預設值為理論漂移後金額，請依實際帳戶餘額修改。")

                _actual_cols = st.columns(len(_rb["target_alloc"]))
                _actual_vals: dict[str, float] = {}
                for _j, (_a, _tw) in enumerate(_rb["target_alloc"].items()):
                    _default = round(_rb["portfolio"] * _rb["drift_alloc"].get(_a, _tw) / 10_000, 1)
                    _actual_vals[_a] = _actual_cols[_j].number_input(
                        f"{_a}（萬）",
                        min_value=0.0,
                        value=float(_default),
                        step=1.0,
                        key=f"_tk6_act_{_a}_{_rb['year']}",
                    )

                _total_actual = sum(_actual_vals.values()) * 10_000
                if _total_actual > 0:
                    st.markdown(f"**總資產：{_total_actual/10_000:,.1f} 萬 → 再平衡至目標配置：**")
                    _trade_cols = st.columns(len(_rb["target_alloc"]))
                    for _j, (_a, _tw) in enumerate(_rb["target_alloc"].items()):
                        _cur  = _actual_vals[_a] * 10_000
                        _tgt  = _total_actual * _tw
                        _delta = _tgt - _cur
                        _op    = "買入" if _delta > 0 else "賣出"
                        _trade_cols[_j].metric(
                            _a,
                            f"{_op} {abs(_delta)/10_000:,.1f} 萬",
                            delta=f"{_delta/10_000:+.1f} 萬",
                            delta_color="normal" if _delta > 0 else "inverse",
                        )
    else:
        st.info("尚無再平衡事件（提領開始後的第一個一月才會觸發）。")

# ── 寫入 localStorage（單一 key 打包，只觸發最多一次 rerun）────────────────────
_ls_all: dict = {
    "sid":          stock_id,
    "dca":          int(monthly_dca),
    "r_asset":      int(st.session_state.get("_w_rasset", 1000)),
    "r_years":      int(st.session_state.get("_w_ryears", 30)),
    "r_inf":        float(st.session_state.get("_w_rinf", 2.0)),
    "r_rate":       float(st.session_state.get("_w_rrate", 6.0)),
    "r_guard":      float(st.session_state.get("_w_rguard", 20.0)),
    "r_preset":     str(st.session_state.get("preset_choice", "保守配息型（預設）")),
    "target_wan":   int(st.session_state.get("_w_target_wan", 500)),
    "target_years": int(st.session_state.get("_w_target_years", 10)),
    "existing":     int(st.session_state.get("_w_existing", 0)),
    "cmp_0":        str(st.session_state.get("_w_cmp_0", "")),
    "cmp_1":        str(st.session_state.get("_w_cmp_1", "")),
    "cmp_2":        str(st.session_state.get("_w_cmp_2", "")),
    "cmp_3":        str(st.session_state.get("_w_cmp_3", "")),
    "cmp_4":        str(st.session_state.get("_w_cmp_4", "")),
    "tk6_port":     int(st.session_state.get("_w_tk6_port", 2000)),
    "tk6_rate":     float(st.session_state.get("_w_tk6_rate", 4.0)),
    "tk6_guard":    int(st.session_state.get("_w_tk6_guard", 20)),
    "tk6_infl":     float(st.session_state.get("_w_tk6_infl", 2.0)),
    "tk6_start":    st.session_state.get("_w_tk6_start", _date(2024, 1, 1)).strftime("%Y-%m-%d"),
}
_tk6_alloc_df = st.session_state.get("tk6_alloc_df")
if _tk6_alloc_df is not None and hasattr(_tk6_alloc_df, "columns"):
    try:
        _ls_all["tk6_alloc"] = _json.loads(
            _tk6_alloc_df[["代號", "配置比例 %"]].to_json(orient="records", force_ascii=False)
        )
    except Exception:
        pass
_custom_df = st.session_state.get("_custom_df_value")  # data_editor return value（DataFrame）
if _custom_df is not None and hasattr(_custom_df, "columns"):
    try:
        _ls_all["r_custom"] = _json.loads(
            _custom_df[["代號", "配置比例 %"]].to_json(orient="records", force_ascii=False)
        )
    except Exception:
        pass

_ls_new_val = _json.dumps(_ls_all, ensure_ascii=False)
# 只有 _ls_applied=True（localStorage 已讀完）後才允許寫入，避免 render 1 的 defaults
# 蓋掉 localStorage 裡已存的值。
# 用遞增 counter 當 key，讓每次 setItem 都強制重新掛載 React 元件（同 key 會被快取跳過）。
if st.session_state.get("_ls_applied") and st.session_state.get("_lsprev_etf_all") != _ls_new_val:
    _n = st.session_state.get("_ls_save_n", 0) + 1
    st.session_state["_ls_save_n"] = _n
    _ls.setItem("etf_all", _ls_new_val, key=f"_lssave_{_n}")
    st.session_state["_lsprev_etf_all"] = _ls_new_val
