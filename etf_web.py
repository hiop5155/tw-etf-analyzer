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
    calc_comparison, calc_multi_compare, calc_target_monthly, calc_lump_sum,
    simulate_gk_montecarlo, calc_return_vol,
    fetch_stock_name, run_gk_historical,
    calc_risk_metrics, calc_correlation_matrix,
    calc_target_assets_from_expense,
    avg_annual_dividend_yield, calc_tax_drag,
    effective_dividend_tax_rate, dividend_net_ratio,
    TaxFeeConfig, DEFAULT_BUY_FEE_RATE, DEFAULT_SELL_FEE_RATE,
    CASH_RETURN, CASH_VOL,
)
from etf_pdf import PDFReportBuilder

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
    # 全域:稅費 / 顯示
    "_w_tax_enabled":       False,
    "_w_tax_bracket_label": "12% (590k–1.33M)",
    "_w_buy_fee":           DEFAULT_BUY_FEE_RATE * 100,
    "_w_display_mode":      "名目",
    "_w_display_inf":       2.0,
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
                "_w_tax_enabled":       (bool,  "tax_enabled"),
                "_w_tax_bracket_label": (str,   "tax_bracket_label"),
                "_w_buy_fee":           (float, "buy_fee"),
                "_w_display_mode":      (str,   "display_mode"),
                "_w_display_inf":       (float, "display_inf"),
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

# ── 側邊欄:全域稅費與顯示設定 ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ 全域設定")

    with st.expander("💸 稅費建模", expanded=False):
        tax_enabled = st.checkbox(
            "啟用稅費計算",
            value=st.session_state.get("_w_tax_enabled", False),
            key="_w_tax_enabled",
            help="啟用後，所有頁面的報酬、終值、CAGR 皆扣除股利稅、二代健保、交易手續費",
        )
        _bracket_options = {
            "5% (年所得 ≤ 590k)":   0.05,
            "12% (590k–1.33M)":     0.12,
            "20% (1.33M–2.66M)":    0.20,
            "30% (2.66M–4.98M)":    0.30,
            "40% (4.98M+)":         0.40,
        }
        _bracket_labels = list(_bracket_options.keys())
        _bracket_default = st.session_state.get("_w_tax_bracket_label", "12% (590k–1.33M)")
        _bracket_label = st.selectbox(
            "綜所稅率級距",
            _bracket_labels,
            index=_bracket_labels.index(_bracket_default) if _bracket_default in _bracket_labels else 1,
            key="_w_tax_bracket_label",
            disabled=not tax_enabled,
            help="系統自動在「合併課稅(可抵減 8.5%，上限 8 萬)」與「分離課稅 28%」中選擇較低稅額",
        )
        tax_bracket = _bracket_options[_bracket_label]

        st.caption(
            "二代健保:**單筆股利 ≥ NT$20,000 自動扣 2.11%**(無法調整)"
        )

        buy_fee = st.number_input(
            "買進手續費 %",
            min_value=0.0, max_value=0.1425, step=0.01,
            value=float(st.session_state.get("_w_buy_fee", DEFAULT_BUY_FEE_RATE * 100)),
            key="_w_buy_fee",
            format="%.4f",
            disabled=not tax_enabled,
            help="預設 0.07125%(= 公定 0.1425% × 五折折扣)",
        )
        st.caption(f"賣出手續費 + 證交稅:**{DEFAULT_SELL_FEE_RATE*100:.4f}%**(= 0.07125% + 證交稅 0.1%,寫死)")

        _tax_cfg = TaxFeeConfig(
            enabled            = tax_enabled,
            income_tax_bracket = tax_bracket,
            buy_fee_rate       = buy_fee / 100,
            sell_fee_rate      = DEFAULT_SELL_FEE_RATE,
        )

    with st.expander("📏 報酬顯示模式", expanded=False):
        display_mode = st.radio(
            "名目 vs 實質",
            ["名目", "實質"],
            index=0 if st.session_state.get("_w_display_mode", "名目") == "名目" else 1,
            key="_w_display_mode",
            horizontal=True,
            help="實質模式會將所有金額、CAGR 以通膨率反向折算為今日購買力。通膨率使用下方設定。",
        )
        display_inflation = st.number_input(
            "顯示用通膨率 %",
            min_value=0.0, max_value=10.0,
            step=0.5,
            value=float(st.session_state.get("_w_display_inf", st.session_state.get("_w_rinf", 2.0))),
            key="_w_display_inf",
            disabled=(display_mode != "實質"),
            help="實質模式下才生效。預設值與退休模擬頁的通膨率連動。",
        )
        _is_real = (display_mode == "實質")
        _inf_rate = display_inflation / 100

    with st.expander("ℹ️ 說明", expanded=False):
        st.caption(
            "- 稅費模型採「長期年化拖累」近似:股利稅 × 殖利率,逐年扣除 CAGR\n"
            "- 手續費:買進時即時扣,賣出時用於退休提領\n"
            "- 實質報酬:所有金額 ÷ (1+通膨)^年數;CAGR 轉為 (1+名目)/(1+通膨)-1\n"
            "- 短歷史標的:稅費拖累精度有限(股利歷史樣本少)"
        )

# ── 輔助函式:實質報酬轉換 ────────────────────────────────────────────────────
def nominal_to_real_value(nominal: float, years: float, inflation: float) -> float:
    if years <= 0 or inflation <= 0:
        return nominal
    return nominal / ((1 + inflation) ** years)

def nominal_to_real_cagr(nominal_cagr: float, inflation: float) -> float:
    """輸入/輸出皆為小數(非 %)。"""
    if inflation <= 0:
        return nominal_cagr
    return (1 + nominal_cagr) / (1 + inflation) - 1

def _display_value(nominal: float, years: float) -> float:
    """依全域設定把名目值折算為實質值(若切換實質模式)。"""
    if _is_real and _inf_rate > 0:
        return nominal_to_real_value(nominal, years, _inf_rate)
    return nominal

def _display_cagr_pct(nominal_pct: float) -> float:
    """CAGR 名目 % → 實質 %(若切換實質模式)。"""
    if _is_real and _inf_rate > 0:
        return nominal_to_real_cagr(nominal_pct / 100, _inf_rate) * 100
    return nominal_pct

# 在頂部顯示當前模式提示(若非預設)
if _tax_cfg.enabled or _is_real:
    _mode_chips = []
    if _tax_cfg.enabled:
        _mode_chips.append(f"💸 稅費啟用(稅率 {_tax_cfg.income_tax_bracket*100:.0f}%)")
    if _is_real:
        _mode_chips.append(f"📏 實質報酬(通膨 {_inf_rate*100:.1f}%)")
    st.info("　｜　".join(_mode_chips))

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
# 新順序：績效 → 目標 → 退休模擬 → 壓力測試 → 提領追蹤 → 多檔 → 股利 → PDF
tab1, tab2, tab3, tab_stress, tab4, tab5, tab6, tab_pdf = st.tabs([
    "📊 績效分析", "🎯 目標試算", "🏖️ 退休提領模擬", "⚠️ 壓力測試",
    "📋 提領追蹤", "📈 多檔比較", "💰 股利歷史", "📄 PDF 匯出",
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

    # 風險指標
    _risk = calc_risk_metrics(close)

    # 稅費拖累(年化)
    _tax_drag = 0.0
    if _tax_cfg.enabled:
        try:
            _div_hist = _cached_dividend_history(stock_id, token)
            _div_yield = avg_annual_dividend_yield(_div_hist, close)
            _tax_drag = calc_tax_drag(_div_yield, f.value, _tax_cfg)
        except Exception:
            _tax_drag = 0.0

    # 摘要卡片（依顯示模式轉換）
    _cagr_label_suffix = "(實質)" if _is_real else ""
    st.subheader(f"{stock_id}　{lump.inception_date.date()} ～ {lump.last_date.date()}　（{lump.years:.1f} 年）")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("單筆總報酬",                        f"{lump.total_return_pct:+,.1f}%")
    c2.metric(f"單筆年化報酬 {_cagr_label_suffix}", f"{_display_cagr_pct(lump.cagr_pct):+.2f}%")
    c3.metric("定期定額總報酬",                    f"{f.return_pct:+.1f}%")
    c4.metric(f"定期定額年化報酬 {_cagr_label_suffix}", f"{_display_cagr_pct(result.dca_cagr_pct):+.2f}%")

    # 風險調整報酬指標
    st.markdown("#### 📉 風險調整報酬指標")
    rk1, rk2, rk3, rk4, rk5 = st.columns(5)
    rk1.metric("年化波動度",   f"{_risk.vol_pct:.2f}%")
    rk2.metric(
        "最大回撤",
        f"{_risk.mdd_pct:.2f}%",
        help=(
            f"Peak: {_risk.mdd_peak_date.date() if _risk.mdd_peak_date else '—'} → "
            f"Trough: {_risk.mdd_trough_date.date() if _risk.mdd_trough_date else '—'} → "
            f"Recovery: {_risk.mdd_recovery_date.date() if _risk.mdd_recovery_date else '尚未回復'}"
        ),
    )
    rk3.metric("Sharpe Ratio",  f"{_risk.sharpe:.2f}", help="(CAGR - Rf=0) / 年化波動度")
    rk4.metric("Sortino Ratio", f"{_risk.sortino:.2f}", help="(CAGR - Rf=0) / 下行波動度,只懲罰虧損")
    rk5.metric("Calmar Ratio",  f"{_risk.calmar:.2f}", help="CAGR / |MDD|,衡量回撤下的報酬效率")

    # 稅費扣除後摘要(啟用時才顯示)
    if _tax_cfg.enabled:
        st.markdown("#### 💸 扣除稅費後(淨值)")
        _net_cagr_pct = _display_cagr_pct((lump.cagr_pct / 100 - _tax_drag) * 100)
        _gross_final  = f.value
        _drag_factor  = (1 - _tax_drag) ** lump.years
        _buy_factor   = (1 - _tax_cfg.buy_fee_rate)
        _net_final    = _gross_final * _drag_factor * _buy_factor
        _net_final_disp = _display_value(_net_final, lump.years)
        _gross_final_disp = _display_value(_gross_final, lump.years)
        nx1, nx2, nx3 = st.columns(3)
        nx1.metric(f"淨年化(扣稅費) {_cagr_label_suffix}", f"{_net_cagr_pct:+.2f}%")
        nx2.metric(f"DCA 淨終值 {_cagr_label_suffix}",       f"{_net_final_disp:,.0f} TWD",
                   delta=f"{_net_final_disp - _gross_final_disp:+,.0f}")
        nx3.metric("年化稅費拖累",                           f"{_tax_drag*100:.2f}%",
                   help="股利稅 + 二代健保相對於總資產的年化拖累率(近似)")

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

    st.subheader("🎯 目標試算")

    _goal_mode = st.radio(
        "試算模式",
        ["📌 正推:目標金額 → 每月需投入", "🔁 反推:月支出 → 需要多少資產(4% 法則)"],
        horizontal=True,
        key="_w_goal_mode",
    )

    if _goal_mode.startswith("📌"):
        st.caption(f"以 {stock_id} 歷史年化報酬 **{lump_full.cagr_pct:.2f}%** 為基準試算")

        tc1, tc2, tc3 = st.columns(3)
        target_wan    = tc1.number_input("目標金額（萬 TWD）",         min_value=1,   step=100, key="_w_target_wan")
        target_years  = tc2.number_input("投資年限（年）",              min_value=1,   max_value=50, step=1, key="_w_target_years")
        existing_wan  = tc3.number_input("目前已持有此標的（萬 TWD）", min_value=0,   step=10,  key="_w_existing")

        target_twd   = target_wan   * 10_000
        existing_twd = existing_wan * 10_000
        base = calc_target_monthly(target_twd, target_years, lump_full.cagr_pct, existing=existing_twd)

        # 實質模式:把終值類數字折現
        _yrs2 = target_years
        _disp_target   = _display_value(target_twd, _yrs2)
        _disp_exist_fv = _display_value(base['existing_fv'], _yrs2)
        _disp_terminal = _display_value(base['terminal_value'], _yrs2)
        _disp_gain     = _display_value(base['total_gain'], _yrs2)
        _real_sfx = "(實質)" if _is_real else ""

        rc1, rc2, rc3 = st.columns(3)
        rc1.metric("每月需投入",       f"{base['monthly']:,.0f} TWD")
        rc2.metric("一次性投入等效",   f"{base['lump_sum_today']:,.0f} TWD")
        rc3.metric(f"現有持倉屆時終值 {_real_sfx}", f"{_disp_exist_fv:,.0f} TWD")
        rd1, rd2, rd3 = st.columns(3)
        rd1.metric("新增投入本金",                 f"{base['total_invested']:,.0f} TWD")
        rd2.metric(f"預估最終資產終值 {_real_sfx}", f"{_disp_terminal:,.0f} TWD")

        if base['monthly'] == 0:
            st.success(f"🎉 現有持倉預計 {target_years} 年後即可達標，不需額外定投！")
        else:
            total_new = existing_twd + base['total_invested']
            st.caption(
                f"新增投入本金：{base['total_invested']:,.0f}　＋　現有持倉：{existing_twd:,.0f}"
                f"　＝　總投入成本：{total_new:,.0f} TWD　｜　"
                f"預計獲利{_real_sfx}：{_disp_gain:,.0f} TWD"
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
                f"持倉屆時終值{_real_sfx}" : f"{_display_value(res['existing_fv'], _yrs2):,.0f}",
                "每月投入 (TWD)"  : f"{res['monthly']:,.0f}",
                "新增投入本金"    : f"{res['total_invested']:,.0f}",
                f"最終資產終值{_real_sfx}" : f"{_display_value(res['terminal_value'], _yrs2):,.0f}",
                f"預計獲利 (TWD){_real_sfx}" : f"{_display_value(res['total_gain'], _yrs2):,.0f}",
            })
        sens_df = pd.DataFrame(scenario_rows)
        st.dataframe(sens_df, width="stretch", hide_index=True)

    else:
        # 反推模式:月支出 → 需要多少退休資產
        st.caption("輸入退休後每月需要的生活費,以安全提領率(SWR)反推需要多少資產")

        rv1, rv2 = st.columns(2)
        monthly_expense = rv1.number_input(
            "退休後每月支出（TWD）",
            min_value=1_000, step=1_000,
            value=int(st.session_state.get("_w_reverse_expense", 60_000)),
            key="_w_reverse_expense",
        )
        swr_pct = rv2.number_input(
            "安全提領率 SWR %",
            min_value=2.0, max_value=10.0, step=0.5,
            value=float(st.session_state.get("_w_reverse_swr", 4.0)),
            key="_w_reverse_swr",
            help=(
                "Bengen 4% 法則 → 退休 30 年高成功率\n\n"
                "保守:3.5%；標準:4%；積極:5–6%\n\n"
                "本頁的月支出為**退休當年實質購買力**;若在實質模式,已自動換算"
            ),
        )

        required_assets = calc_target_assets_from_expense(monthly_expense, swr_pct / 100)
        st.metric("所需退休起始資產", f"{required_assets:,.0f} TWD (≈ {required_assets/10_000:,.0f} 萬)")

        st.divider()
        st.subheader("不同提領率對照")
        swr_rows = []
        for swr in [3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0]:
            need = calc_target_assets_from_expense(monthly_expense, swr / 100)
            swr_rows.append({
                "提領率 %":        f"{swr:.1f}",
                "所需資產 (TWD)":  f"{need:,.0f}",
                "所需資產 (萬)":   f"{need/10_000:,.0f}",
                "評估":            (
                    "🟢 保守" if swr <= 3.5 else
                    "🟡 標準" if swr <= 4.5 else
                    "🔴 積極"
                ),
            })
        st.dataframe(pd.DataFrame(swr_rows), hide_index=True, width="stretch")

        st.divider()
        st.caption(
            f"💡 若在「退休提領模擬」頁驗證此資產:起始資產填 **{required_assets/10_000:,.0f} 萬**,"
            f"初始提領率填 **{swr_pct:.1f}%**,即可看 Monte Carlo 成功率。"
        )


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

            # 每檔計算風險指標(從共同起始日起算)
            _risk_map = {}
            for sid, c in closes.items():
                sliced = c[c.index >= records[0].common_start].dropna()
                if len(sliced) >= 2:
                    _risk_map[sid] = calc_risk_metrics(sliced)

            # 稅費拖累:每檔獨立抓股利歷史並計算
            _tax_drag_map: dict[str, float] = {}
            if _tax_cfg.enabled:
                for sid in closes:
                    try:
                        dh = _cached_dividend_history(sid, token)
                        y = avg_annual_dividend_yield(dh, closes[sid])
                        # 用 DCA 終值作為 portfolio_value 估 NHI
                        dca_final = next((r.dca_final for r in records if r.stock_id == sid), 0.0)
                        _tax_drag_map[sid] = calc_tax_drag(y, dca_final, _tax_cfg)
                    except Exception:
                        _tax_drag_map[sid] = 0.0
            _years_cmp = records[0].years  # 共同年數

            _row_fn = lambda r: {
                "代號"        : r.stock_id,
                "原始上市日"  : str(r.inception_date.date()),
                "共同起始日"  : str(r.common_start.date()),
                "比較年數"    : f"{r.years:.2f}",
                "總報酬%"     : f"{r.total_return_pct:.1f}",
                "年化報酬%"   : round(_display_cagr_pct(r.cagr_pct), 2),
                "MDD%"        : round(_risk_map[r.stock_id].mdd_pct, 1) if r.stock_id in _risk_map else 0.0,
                "Sharpe"      : round(_risk_map[r.stock_id].sharpe, 2) if r.stock_id in _risk_map else 0.0,
                "Sortino"     : round(_risk_map[r.stock_id].sortino, 2) if r.stock_id in _risk_map else 0.0,
                "Calmar"      : round(_risk_map[r.stock_id].calmar, 2) if r.stock_id in _risk_map else 0.0,
                "淨CAGR%"     : round(_display_cagr_pct((r.cagr_pct / 100 - _tax_drag_map.get(r.stock_id, 0.0)) * 100), 2),
                f"DCA終值(月投{monthly_dca:,.0f})": f"{_display_value(r.dca_final * ((1 - _tax_drag_map.get(r.stock_id, 0.0)) ** _years_cmp if _tax_cfg.enabled else 1.0), _years_cmp):,.0f}",
                "DCA年化%"    : f"{_display_cagr_pct(r.dca_cagr_pct - _tax_drag_map.get(r.stock_id, 0.0) * 100):.2f}",
            }

            cmp_df = pd.DataFrame([_row_fn(r) for r in records])
            # 若未啟用稅費,把「淨CAGR%」欄位隱藏(與「年化報酬%」相同)
            if not _tax_cfg.enabled:
                cmp_df = cmp_df.drop(columns=["淨CAGR%"])

            _max_cagr = max(x for x in cmp_df["年化報酬%"] if isinstance(x, (float, int)))
            st.dataframe(
                cmp_df.style.map(
                    lambda v: "color: green; font-weight: bold"
                    if isinstance(v, (float, int)) and v == _max_cagr else "",
                    subset=["年化報酬%"]
                ).format({
                    "年化報酬%": "{:.2f}",
                    "MDD%":      "{:.1f}",
                    "Sharpe":    "{:.2f}",
                    "Sortino":   "{:.2f}",
                    "Calmar":    "{:.2f}",
                }),
                width="stretch", hide_index=True
            )

            # ── 相關性矩陣 ───────────────────────────────────────────────────────
            st.markdown("#### 🔗 月報酬相關性矩陣")
            st.caption("低相關的資產組合有利於分散風險;1 = 完全正相關、0 = 無關、−1 = 反向")
            _corr = calc_correlation_matrix({sid: c for sid, c in closes.items()})
            if not _corr.empty:
                fig_corr = go.Figure(data=go.Heatmap(
                    z         = _corr.values,
                    x         = _corr.columns.tolist(),
                    y         = _corr.index.tolist(),
                    colorscale = "RdBu",
                    zmin       = -1, zmax = 1, zmid = 0,
                    text       = _corr.round(2).values,
                    texttemplate = "%{text}",
                    textfont   = dict(size=13),
                    hovertemplate = "%{y} ↔ %{x}<br>相關係數: %{z:.3f}<extra></extra>",
                    colorbar   = dict(title="相關係數"),
                ))
                fig_corr.update_layout(
                    xaxis=dict(side="bottom"),
                    yaxis=dict(autorange="reversed"),
                    height=max(280, 60 * len(_corr)),
                )
                st.plotly_chart(fig_corr, width="stretch")

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

    # 稅費拖累:加權股利殖利率 × 實繳稅率
    _w_tax_drag = 0.0
    if _tax_cfg.enabled:
        _retire_port_est = retire_asset_wan * 10_000
        for _, row in portfolio_df.iterrows():
            code = str(row["代號"]).strip().upper()
            weight = row["配置比例 %"] / 100
            if code == "現金":
                continue
            try:
                dh = _cached_dividend_history(code, token)
                close_r, _ = _cached_adjusted_close(code, token)
                y = avg_annual_dividend_yield(dh, close_r)
                # 用加權後的投組金額估算 NHI
                _w_tax_drag += weight * calc_tax_drag(y, _retire_port_est * weight, _tax_cfg)
            except Exception:
                pass

    short_note = "　⚠️ 含短歷史標的，報酬偏高屬正常，請保守解讀" if short_hist_etfs else ""
    _w_ret_gross = w_ret
    w_ret = w_ret - _w_tax_drag  # 淨化加權報酬

    if _tax_cfg.enabled:
        st.success(
            f"✅ 加權毛年化報酬:**{_w_ret_gross*100:.2f}%**　｜　稅費拖累:−**{_w_tax_drag*100:.2f}%**"
            f"　｜　**淨年化 {w_ret*100:.2f}%**　｜　加權波動度:**{w_vol*100:.2f}%**{short_note}"
        )
    else:
        st.success(
            f"✅ 加權歷史年化報酬：**{w_ret*100:.2f}%**　｜　加權年化波動度：**{w_vol*100:.2f}%**"
            f"　（波動度為各資產加權平均，未考慮資產間相關係數）{short_note}"
        )

    st.divider()

    # ── Monte Carlo 模擬 ──────────────────────────────────────────────────────
    retire_asset = retire_asset_wan * 10_000

    # 分配選擇器
    _dist_label = st.radio(
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
    _dist_kind = (
        "tdist"     if _dist_label.startswith("🐘") else
        "bootstrap" if _dist_label.startswith("📚") else
        "normal"
    )

    # 若用 bootstrap,計算投組歷史月報酬
    _hist_monthly = None
    if _dist_kind == "bootstrap":
        # 對每檔資產抓月報酬,按配置比例加權
        _asset_monthly: dict[str, "pd.Series"] = {}
        for _, row in portfolio_df.iterrows():
            code = str(row["代號"]).strip().upper()
            weight = row["配置比例 %"] / 100
            if code == "現金":
                continue
            try:
                _c, _ = _cached_adjusted_close(code, token)
                _clean = _c.replace(0, float("nan")).dropna()
                _m = _clean.resample("ME").last().dropna().pct_change().dropna()
                _asset_monthly[code] = _m
            except Exception:
                pass
        if _asset_monthly:
            # 對齊共同期間,加權
            _aligned = pd.DataFrame(_asset_monthly).dropna()
            # 現金比例的月報酬 = 0
            _portfolio_monthly = pd.Series(0.0, index=_aligned.index)
            for code, series in _asset_monthly.items():
                _w = 0.0
                for _, r in portfolio_df.iterrows():
                    if str(r["代號"]).strip().upper() == code:
                        _w = r["配置比例 %"] / 100
                        break
                if code in _aligned.columns:
                    _portfolio_monthly += _aligned[code] * _w
            _hist_monthly = _portfolio_monthly.values
            st.caption(
                f"📊 Bootstrap 樣本:**{len(_hist_monthly)} 筆月報酬**"
                f"(共同可觀察期間,已用配置比例加權;現金部位月報酬 = 0)"
            )
        else:
            st.warning("找不到足夠的歷史月報酬,退回常態分配")
            _dist_kind = "normal"

    _dist_label_short = {
        "normal":    "常態",
        "tdist":     "Student-t(df=5)",
        "bootstrap": "Bootstrap",
    }[_dist_kind]

    try:
        with st.spinner(f"執行 2,000 次 Monte Carlo({_dist_label_short})..."):
            mc = simulate_gk_montecarlo(
                initial_portfolio = retire_asset,
                initial_rate      = init_rate_pct / 100,
                guardrail_pct     = guardrail_pct / 100,
                annual_return     = w_ret,
                annual_volatility = w_vol,
                inflation_rate    = inflation_pct / 100,
                years             = int(retire_years),
                n_sims            = 2000,
                dist_kind         = _dist_kind,
                hist_monthly_returns = _hist_monthly,
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
    _p50_disp = _display_value(p50_final, retire_years)
    _real_sfx = "(實質)" if _is_real else ""
    sm4.metric(f"P50 期末資產 {_real_sfx}", f"{_p50_disp/10_000:,.0f} 萬 TWD")

    # ── 圖1：資產餘額百分位扇形圖 ─────────────────────────────────────────────
    _real_chart_sfx = "(實質)" if _is_real else ""
    st.markdown(f"#### 📊 資產餘額分布（百分位數） {_real_chart_sfx}")
    yrs = mc["years"]

    def _deflate_year_arr(arr):
        if _is_real and _inf_rate > 0:
            import numpy as _np
            return _np.array([
                nominal_to_real_value(float(v), float(y), _inf_rate)
                for v, y in zip(arr, yrs)
            ])
        return arr

    _port10 = _deflate_year_arr(mc["port_pct"][10])
    _port25 = _deflate_year_arr(mc["port_pct"][25])
    _port50 = _deflate_year_arr(mc["port_pct"][50])
    _port75 = _deflate_year_arr(mc["port_pct"][75])
    _port90 = _deflate_year_arr(mc["port_pct"][90])

    fig_port = go.Figure()
    fig_port.add_trace(go.Scatter(
        x=list(yrs) + list(yrs[::-1]),
        y=list(_port90 / 10_000) + list(_port10[::-1] / 10_000),
        fill="toself", fillcolor="rgba(70,130,180,0.15)",
        line=dict(color="rgba(0,0,0,0)"), name="P10–P90", showlegend=True,
    ))
    fig_port.add_trace(go.Scatter(
        x=list(yrs) + list(yrs[::-1]),
        y=list(_port75 / 10_000) + list(_port25[::-1] / 10_000),
        fill="toself", fillcolor="rgba(70,130,180,0.30)",
        line=dict(color="rgba(0,0,0,0)"), name="P25–P75", showlegend=True,
    ))
    for p, color, dash in [(50, "steelblue", "solid"), (10, "tomato", "dash"), (90, "seagreen", "dash")]:
        _arr = {10: _port10, 50: _port50, 90: _port90}[p]
        fig_port.add_trace(go.Scatter(
            x=yrs, y=_arr / 10_000,
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
    st.markdown(f"#### 💵 每月提領額分布（百分位數） {_real_chart_sfx}")
    _wd10 = _deflate_year_arr(mc["wd_pct"][10])
    _wd25 = _deflate_year_arr(mc["wd_pct"][25])
    _wd50 = _deflate_year_arr(mc["wd_pct"][50])
    _wd75 = _deflate_year_arr(mc["wd_pct"][75])
    _wd90 = _deflate_year_arr(mc["wd_pct"][90])
    fig_wd = go.Figure()
    fig_wd.add_trace(go.Scatter(
        x=list(yrs) + list(yrs[::-1]),
        y=list(_wd90) + list(_wd10[::-1]),
        fill="toself", fillcolor="rgba(46,139,87,0.15)",
        line=dict(color="rgba(0,0,0,0)"), name="P10–P90",
    ))
    fig_wd.add_trace(go.Scatter(
        x=list(yrs) + list(yrs[::-1]),
        y=list(_wd75) + list(_wd25[::-1]),
        fill="toself", fillcolor="rgba(46,139,87,0.30)",
        line=dict(color="rgba(0,0,0,0)"), name="P25–P75",
    ))
    for p, color, dash in [(50, "seagreen", "solid"), (10, "tomato", "dash"), (90, "royalblue", "dash")]:
        _arr = {10: _wd10, 50: _wd50, 90: _wd90}[p]
        fig_wd.add_trace(go.Scatter(
            x=yrs, y=_arr,
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

    # ── Sequence-of-Returns Risk 視覺化 ──────────────────────────────────────
    st.markdown("#### 🎲 順序風險(Sequence-of-Returns Risk)")
    st.caption(
        "**相同的平均報酬,退休早期遇到壞年份 vs 好年份,結局天差地別。**"
        "以下三條路徑使用**同一組**隨機報酬,僅「順序」不同 — 但結果顯示順序本身就是重大風險。"
    )
    # 產生一組固定 seed 的隨機報酬(與 MC 相同參數)
    _sor_rng = np.random.default_rng(12345)
    _sor_returns = _sor_rng.normal(w_ret, w_vol, int(retire_years))
    _orders = [
        ("🌪️ 逆風起跑(壞年份先)", np.sort(_sor_returns)),
        ("🎲 隨機順序",           _sor_returns.copy()),
        ("🌤️ 順風起跑(好年份先)", np.sort(_sor_returns)[::-1]),
    ]
    # 手動跑 GK 路徑(不套護欄,只看資產成長)
    def _run_simple_gk(returns: "np.ndarray", initial_portfolio: float,
                        initial_rate: float, inflation_rate: float) -> list[float]:
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

    fig_sor = go.Figure()
    _colors = ["tomato", "steelblue", "seagreen"]
    _sor_yrs_axis = list(range(int(retire_years) + 1))
    for (_lab, _seq), _color in zip(_orders, _colors):
        _trace = _run_simple_gk(_seq, retire_asset, init_rate_pct / 100, inflation_pct / 100)
        _disp_trace = [_display_value(v, i) for i, v in enumerate(_trace)]
        fig_sor.add_trace(go.Scatter(
            x=_sor_yrs_axis, y=[v / 10_000 for v in _disp_trace],
            name=_lab, mode="lines",
            line=dict(color=_color, width=2),
        ))
    fig_sor.add_hline(y=0, line_dash="dot", line_color="gray")
    fig_sor.update_layout(
        xaxis_title="退休後第幾年",
        yaxis_title=f"資產餘額（萬 TWD）{'(實質)' if _is_real else ''}",
        hovermode="x unified",
        legend=dict(orientation="h", y=1.08),
        height=400,
    )
    st.plotly_chart(fig_sor, width="stretch")
    st.caption(
        "💡 三條路徑的幾何平均報酬完全相同(因使用同一組數字),但路徑末端資產可能差數倍。"
        "這就是為什麼退休前 5-10 年遇到熊市特別危險 — GK 護欄正是為此設計。"
    )

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

    # 模式切換:單次 vs Rolling
    _tk6_mode = st.radio(
        "模式",
        ["🎯 單次追蹤(選定起始日)", "🔁 Rolling 歷史回測(多起始年)"],
        horizontal=True,
        key="_w_tk6_mode",
        help=(
            "**單次追蹤**:從指定日期起至今,逐月追蹤 GK 策略\n\n"
            "**Rolling 回測**:對每個可能的起始年都跑 N 年 GK,比較「歷史上最糟/中位/最佳退休者」"
        ),
    )
    _is_rolling = _tk6_mode.startswith("🔁")

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
    if _is_rolling:
        tk6_rolling_years = _te.number_input(
            "Rolling 年數",
            min_value=5, max_value=40, step=5,
            value=int(st.session_state.get("_w_tk6_rolling_years", 20)),
            key="_w_tk6_rolling_years",
            help="每個起始年都模擬 N 年退休期間。若選 20 年,則起始年必須在 (今年 − 20) 以前",
        )
        tk6_start = _date(2003, 1, 1)  # placeholder,不使用
    else:
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

    # 若啟用稅費:對每檔 close 套用年化拖累(模擬扣稅後淨值成長)
    _tk6_drag_map: dict[str, float] = {}
    if _tax_cfg.enabled:
        _port_est = tk6_port * 10_000
        for _asset, _c in list(_tk6_close_map.items()):
            try:
                _dh = _cached_dividend_history(_asset, token)
                _y = avg_annual_dividend_yield(_dh, _c)
                _asset_weight = tk6_allocations.get(_asset, 0)
                _drag = calc_tax_drag(_y, _port_est * _asset_weight, _tax_cfg)
                _tk6_drag_map[_asset] = _drag
                if _drag > 0:
                    # 以日頻率套用拖累:net_close[i] = gross[i] × (1 - drag)^(day_elapsed/365.25)
                    _start = _c.index[0]
                    _yrs = (_c.index - _start).days / 365.25
                    _factor = (1 - _drag) ** _yrs
                    _tk6_close_map[_asset] = _c * _factor
            except Exception:
                _tk6_drag_map[_asset] = 0.0

    # ── Rolling 歷史回測分支 ──────────────────────────────────────────────────
    if _is_rolling:
        # 找最早可能起始年(所有非現金資產中最晚的首日年份)
        _earliest = max(
            _c.index[0].year for _c in _tk6_close_map.values()
        ) if _tk6_close_map else 2003
        _this_year = pd.Timestamp.today().year
        _latest_start = _this_year - int(tk6_rolling_years)
        if _latest_start < _earliest:
            st.warning(
                f"Rolling 年數 {tk6_rolling_years} 年超過可回測期間"
                f"(最早 {_earliest} ~ 最晚 {_this_year})"
            )
            st.stop()

        _start_years = list(range(_earliest, _latest_start + 1))
        _rolling_runs = []
        with st.spinner(f"跑 {len(_start_years)} 組起始年 × {tk6_rolling_years} 年 GK..."):
            for _sy in _start_years:
                try:
                    _r = run_gk_historical(
                        initial_portfolio = tk6_port * 10_000,
                        allocations       = tk6_allocations,
                        start_ym          = f"{_sy}-01",
                        initial_rate      = tk6_rate / 100,
                        guardrail_pct     = tk6_guard / 100,
                        inflation_rate    = tk6_infl / 100,
                        close_series      = _tk6_close_map,
                    )
                    # 截至 tk6_rolling_years
                    _cap = int(tk6_rolling_years) * 12
                    _m_trunc = _r["monthly"][:_cap]
                    _final_port = (
                        float(_m_trunc[-1]["資產餘額 (萬)"]) * 10_000
                        if _m_trunc else _r["final_portfolio"]
                    )
                    _rolling_runs.append({
                        "start_year":  _sy,
                        "final":       _final_port,
                        "depleted":    _final_port <= 0,
                        "monthly":     _m_trunc,
                    })
                except Exception:
                    pass

        if not _rolling_runs:
            st.error("Rolling 回測無結果,請調整配置或縮短年數")
            st.stop()

        # 摘要:最差 / 中位 / 最佳
        _sorted = sorted(_rolling_runs, key=lambda x: x["final"])
        _worst  = _sorted[0]
        _median = _sorted[len(_sorted) // 2]
        _best   = _sorted[-1]
        _depleted_count = sum(1 for r in _rolling_runs if r["depleted"])
        _success_rate = (len(_rolling_runs) - _depleted_count) / len(_rolling_runs) * 100

        _real_sfx_r = "(實質)" if _is_real else ""
        _worst_disp  = _display_value(_worst["final"],  int(tk6_rolling_years))
        _median_disp = _display_value(_median["final"], int(tk6_rolling_years))
        _best_disp   = _display_value(_best["final"],   int(tk6_rolling_years))

        st.markdown(f"#### 📊 Rolling 回測結果摘要({len(_rolling_runs)} 組起始年 × {tk6_rolling_years} 年)")
        _rc1, _rc2, _rc3, _rc4 = st.columns(4)
        _rc1.metric("存活率",                f"{_success_rate:.1f}%", help="未耗盡資產的起始年比例")
        _rc2.metric(f"最差終值 {_real_sfx_r}", f"{_worst_disp/10_000:,.0f} 萬",
                    help=f"起始年:{_worst['start_year']}")
        _rc3.metric(f"中位終值 {_real_sfx_r}", f"{_median_disp/10_000:,.0f} 萬",
                    help=f"起始年:{_median['start_year']}")
        _rc4.metric(f"最佳終值 {_real_sfx_r}", f"{_best_disp/10_000:,.0f} 萬",
                    help=f"起始年:{_best['start_year']}")

        # 條形圖:各起始年終值
        st.markdown("#### 📈 各起始年終值分布")
        _df_roll = pd.DataFrame([{
            "起始年":   r["start_year"],
            "終值(萬)": _display_value(r["final"], int(tk6_rolling_years)) / 10_000,
            "耗盡":     "是" if r["depleted"] else "否",
        } for r in _rolling_runs])
        fig_roll = go.Figure()
        fig_roll.add_trace(go.Bar(
            x=_df_roll["起始年"], y=_df_roll["終值(萬)"],
            marker_color=["tomato" if x else "steelblue" for x in _df_roll["耗盡"].eq("是")],
            hovertemplate="起始 %{x}<br>終值 %{y:,.0f} 萬<extra></extra>",
            name="終值",
        ))
        fig_roll.add_hline(y=tk6_port, line_dash="dot", line_color="gray",
                           annotation_text=f"起始 {tk6_port:,} 萬")
        fig_roll.update_layout(
            xaxis_title="退休起始年", yaxis_title=f"{tk6_rolling_years} 年後終值(萬 TWD){_real_sfx_r}",
            hovermode="x unified", height=400,
        )
        st.plotly_chart(fig_roll, width="stretch")

        # 最差 / 中位 / 最佳路徑對照
        st.markdown("#### 🔍 三條代表性路徑對照")
        fig_path = go.Figure()
        for _lab, _run, _color in [
            (f"🌪️ 最差({_worst['start_year']} 起)",  _worst,  "tomato"),
            (f"📊 中位({_median['start_year']} 起)", _median, "steelblue"),
            (f"🌤️ 最佳({_best['start_year']} 起)",   _best,   "seagreen"),
        ]:
            _m = _run["monthly"]
            if not _m:
                continue
            _x = list(range(len(_m)))
            _y = [float(row["資產餘額 (萬)"]) * 10_000 for row in _m]
            if _is_real and _inf_rate > 0:
                _y = [nominal_to_real_value(v, i / 12, _inf_rate) for i, v in enumerate(_y)]
            fig_path.add_trace(go.Scatter(
                x=_x, y=[v / 10_000 for v in _y],
                name=_lab, mode="lines",
                line=dict(color=_color, width=2),
            ))
        fig_path.update_layout(
            xaxis_title="退休後第幾個月",
            yaxis_title=f"資產餘額(萬 TWD){_real_sfx_r}",
            hovermode="x unified", height=400,
        )
        st.plotly_chart(fig_path, width="stretch")

        with st.expander("📋 各起始年明細", expanded=False):
            st.dataframe(_df_roll, hide_index=True, width="stretch")

        # 停止執行單次分支
        st.stop()

    # ── 執行歷史追蹤(單次分支) ──────────────────────────────────────────────
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

    # 賣出手續費+證交稅(若啟用):每月實際到手 = 理論月提領 × (1 − sell_fee)
    _tk6_net_factor = (1 - _tax_cfg.sell_fee_rate) if _tax_cfg.enabled else 1.0
    _tk6_final_monthly_net = _tk6_result["final_monthly_income"] * _tk6_net_factor
    _initial_monthly       = tk6_port * 10_000 * tk6_rate / 100 / 12 * _tk6_net_factor

    # 實質換算
    _tk6_years_elapsed = len(_tk6_monthly) / 12
    _tk6_final_port_disp = _display_value(_tk6_result['final_portfolio'], _tk6_years_elapsed)
    _tk6_final_mi_disp   = _display_value(_tk6_final_monthly_net, _tk6_years_elapsed)
    _real_sfx = "(實質)" if _is_real else ""

    # ── 摘要指標 ──────────────────────────────────────────────────────────────
    _tk6_m1, _tk6_m2, _tk6_m3, _tk6_m4 = st.columns(4)
    _tk6_m1.metric(f"目前資產 {_real_sfx}",     f"{_tk6_final_port_disp/10_000:,.0f} 萬 TWD")
    _tk6_m2.metric(f"目前月提領額 {_real_sfx}", f"{_tk6_final_mi_disp:,.0f} TWD")
    _tk6_m3.metric("初始月提領額(淨)",          f"{_initial_monthly:,.0f} TWD",
                   delta=f"{_tk6_final_monthly_net - _initial_monthly:+,.0f}")
    _tk6_m4.metric("追蹤期間",                  f"{len(_tk6_monthly)} 個月 / {len(_tk6_rebalances)} 次再平衡")

    if _tax_cfg.enabled:
        _drag_summary = "、".join(f"{a}: −{d*100:.2f}%" for a, d in _tk6_drag_map.items() if d > 0)
        st.caption(f"💸 已套用稅費:{_drag_summary or '無股利資料'}　｜　賣出費 {_tax_cfg.sell_fee_rate*100:.4f}%")

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


# ════════════════════════════════════════════════════════════════════════════
# 壓力測試（起點式 × 3 歷史情境）
# ════════════════════════════════════════════════════════════════════════════
with tab_stress:
    st.subheader("⚠️ 壓力測試 — 在歷史最差時刻退休會怎樣?")
    st.caption(
        "以退休模擬頁的投組與參數,模擬「在歷史熊市起點退休」後續追蹤至今。"
        "若投組內 ETF 成立日晚於情境起點,會用 **0050 代理** 補齊,並在下方明確標示。"
    )

    # 取用退休頁設定
    _stress_alloc_df = st.session_state.get("_custom_df_value")
    _stress_preset_choice = st.session_state.get("preset_choice", "保守配息型（預設）")
    if _stress_preset_choice != "自訂" or _stress_alloc_df is None:
        _pr = {
            "保守配息型（預設）": [
                {"代號": "0056",   "配置比例 %": 30},
                {"代號": "00878",  "配置比例 %": 20},
                {"代號": "00720B", "配置比例 %": 30},
                {"代號": "00679B", "配置比例 %": 10},
                {"代號": "現金",   "配置比例 %": 10},
            ],
            "債券優先型": [
                {"代號": "00720B", "配置比例 %": 40},
                {"代號": "00679B", "配置比例 %": 25},
                {"代號": "0056",   "配置比例 %": 25},
                {"代號": "現金",   "配置比例 %": 10},
            ],
            "全高股息型": [
                {"代號": "0056",   "配置比例 %": 35},
                {"代號": "00878",  "配置比例 %": 30},
                {"代號": "00713",  "配置比例 %": 15},
                {"代號": "現金",   "配置比例 %": 20},
            ],
            "均衡穩健型": [
                {"代號": "0050",   "配置比例 %": 15},
                {"代號": "00878",  "配置比例 %": 20},
                {"代號": "00720B", "配置比例 %": 30},
                {"代號": "00679B", "配置比例 %": 15},
                {"代號": "現金",   "配置比例 %": 20},
            ],
            "槓桿平衡型": [
                {"代號": "00631L", "配置比例 %": 50},
                {"代號": "現金",   "配置比例 %": 50},
            ],
        }
        _stress_rows = _pr.get(_stress_preset_choice, _pr["保守配息型（預設）"])
    else:
        _stress_rows = _stress_alloc_df[["代號", "配置比例 %"]].to_dict("records")

    _stress_alloc: dict[str, float] = {
        str(r["代號"]).strip().upper(): r["配置比例 %"] / 100
        for r in _stress_rows
        if str(r["代號"]).strip() and r["配置比例 %"] > 0
    }
    _stress_alloc = {("現金" if k in ("現金", "CASH") else k): v for k, v in _stress_alloc.items()}

    # 參數摘要
    _stress_asset   = st.session_state.get("_w_rasset", 2000) * 10_000
    _stress_rate    = st.session_state.get("_w_rrate", 5.0) / 100
    _stress_guard   = st.session_state.get("_w_rguard", 20.0) / 100
    _stress_infl    = st.session_state.get("_w_rinf", 2.0) / 100

    with st.expander("🗂️ 當前測試參數（來自退休提領模擬頁）", expanded=False):
        st.write(f"- 投組來源:**{_stress_preset_choice}**")
        st.dataframe(pd.DataFrame(_stress_rows), hide_index=True, width="stretch")
        st.write(
            f"- 起始資產:**{_stress_asset/10_000:,.0f} 萬 TWD**　"
            f"- 初始提領率:**{_stress_rate*100:.1f}%**　"
            f"- 護欄寬度:**±{_stress_guard*100:.0f}%**　"
            f"- 通膨率:**{_stress_infl*100:.1f}%**"
        )

    # 3 情境定義(起點式:在該月退休,跑到現在)
    _scenarios = [
        {"name": "💥 2008 金融海嘯", "start_ym": "2008-01",
         "desc": "Lehman 破產前夕退休,資產腰斬(-55%),護欄應啟動保命"},
        {"name": "🦠 2020 COVID 崩盤", "start_ym": "2020-02",
         "desc": "疫情爆發前一個月退休,快速崩盤 -30% 再 V 型反彈"},
        {"name": "📈 2022 升息循環",   "start_ym": "2022-01",
         "desc": "通膨高點退休,同期股債雙跌(最糟年份)"},
    ]

    # 預先下載 0050 作為代理
    try:
        _proxy_close, _ = _cached_adjusted_close("0050", token)
    except Exception as _e:
        st.error(f"代理資料 0050 載入失敗:{_e}")
        st.stop()

    # 下載各資產 close
    _stress_close_map: dict[str, pd.Series] = {}
    _stress_errors = []
    for _a in _stress_alloc:
        if _a == "現金":
            continue
        try:
            _c, _ = _cached_adjusted_close(_a, token)
            _stress_close_map[_a] = _c
        except Exception as _e:
            _stress_errors.append(f"{_a}:{_e}")

    if _stress_errors:
        for _err in _stress_errors:
            st.warning(f"資料載入失敗,將以代理或忽略:{_err}")

    # 代理補齊函式
    def _splice_proxy(asset_close: "pd.Series", proxy_close: "pd.Series",
                       start_ts: "pd.Timestamp") -> tuple["pd.Series", bool]:
        """若 asset_close 起始晚於 start_ts,用 proxy_close 報酬補齊前段。"""
        if asset_close.index[0] <= start_ts:
            return asset_close, False
        # 取 proxy 在 asset 上市日之前的資料(含代理期間)
        proxy_segment = proxy_close[
            (proxy_close.index >= start_ts) & (proxy_close.index <= asset_close.index[0])
        ]
        if proxy_segment.empty:
            return asset_close, False
        # 以 asset 首日價格為錨點,將 proxy_segment 等比縮放
        scale = float(asset_close.iloc[0]) / float(proxy_segment.iloc[-1])
        scaled = proxy_segment * scale
        combined = pd.concat([scaled[:-1], asset_close]).sort_index()
        combined = combined[~combined.index.duplicated(keep="last")]
        return combined, True

    # 套用稅費拖累到代理後的序列(若啟用)
    def _apply_drag(series, asset_code, port_weight):
        if not _tax_cfg.enabled:
            return series
        try:
            _dh = _cached_dividend_history(asset_code, token)
            _y = avg_annual_dividend_yield(_dh, series)
            _drag = calc_tax_drag(_y, _stress_asset * port_weight, _tax_cfg)
            if _drag > 0:
                _start = series.index[0]
                _yrs = (series.index - _start).days / 365.25
                return series * ((1 - _drag) ** _yrs)
        except Exception:
            pass
        return series

    # 執行 3 情境
    _stress_results: list[dict] = []
    for _sc in _scenarios:
        _start_ts = pd.Timestamp(_sc["start_ym"] + "-01")

        # 為此情境準備 close_map(補代理)
        _scenario_close_map: dict[str, pd.Series] = {}
        _proxied: list[str] = []
        for _a, _c in _stress_close_map.items():
            _combined, _was_proxied = _splice_proxy(_c, _proxy_close, _start_ts)
            _scenario_close_map[_a] = _apply_drag(_combined, _a, _stress_alloc[_a])
            if _was_proxied:
                _proxied.append(_a)

        try:
            _r = run_gk_historical(
                initial_portfolio = _stress_asset,
                allocations       = _stress_alloc,
                start_ym          = _sc["start_ym"],
                initial_rate      = _stress_rate,
                guardrail_pct     = _stress_guard,
                inflation_rate    = _stress_infl,
                close_series      = _scenario_close_map,
            )
            _stress_results.append({"sc": _sc, "r": _r, "proxied": _proxied})
        except Exception as _e:
            st.warning(f"{_sc['name']} 執行失敗:{_e}")

    if not _stress_results:
        st.error("所有情境皆無法執行,請確認投組設定")
        st.stop()

    # 摘要卡片
    st.markdown("#### 📊 情境結果摘要")
    _cols = st.columns(len(_stress_results))
    for _i, _res in enumerate(_stress_results):
        _sc, _r = _res["sc"], _res["r"]
        _months = len(_r["monthly"])
        _yrs_elapsed = _months / 12
        _final_disp = _display_value(_r["final_portfolio"], _yrs_elapsed)
        _mi_sell_fee = (1 - _tax_cfg.sell_fee_rate) if _tax_cfg.enabled else 1.0
        _mi_disp = _display_value(_r["final_monthly_income"] * _mi_sell_fee, _yrs_elapsed)
        _real_sfx = "(實質)" if _is_real else ""
        with _cols[_i]:
            st.markdown(f"**{_sc['name']}**")
            st.caption(_sc["desc"])
            st.metric(f"目前資產 {_real_sfx}", f"{_final_disp/10_000:,.0f} 萬")
            st.metric(f"目前月提領 {_real_sfx}", f"{_mi_disp:,.0f} TWD")
            st.caption(f"起點:{_sc['start_ym']} ｜ 歷時 {_yrs_elapsed:.1f} 年")
            if _res["proxied"]:
                st.warning(f"⚠️ 以 0050 代理:{', '.join(_res['proxied'])}")

    # 資產演化圖
    st.markdown("#### 📈 資產演化軌跡")
    fig_st = go.Figure()
    for _res in _stress_results:
        _sc, _r = _res["sc"], _res["r"]
        _months = _r["monthly"]
        if not _months:
            continue
        _x = [m["月份"] for m in _months]
        _y = [float(m["資產餘額 (萬)"]) * 10_000 for m in _months]
        if _is_real and _inf_rate > 0:
            _y = [
                nominal_to_real_value(float(v), (pd.Timestamp(d + "-01") - pd.Timestamp(_sc["start_ym"] + "-01")).days / 365.25, _inf_rate)
                for v, d in zip(_y, _x)
            ]
        fig_st.add_trace(go.Scatter(
            x=_x, y=[v/10_000 for v in _y],
            name=_sc["name"], mode="lines",
        ))
    fig_st.add_hline(y=_stress_asset/10_000, line_dash="dot", line_color="gray",
                      annotation_text=f"起始 {_stress_asset/10_000:,.0f} 萬")
    fig_st.update_layout(
        xaxis_title="月份", yaxis_title=f"資產餘額（萬 TWD）{'(實質)' if _is_real else ''}",
        hovermode="x unified",
        legend=dict(orientation="h", y=1.08),
        height=450,
    )
    st.plotly_chart(fig_st, width="stretch")

    # GK 事件表
    with st.expander("🛡️ GK 護欄觸發事件彙總", expanded=False):
        _gk_rows = []
        for _res in _stress_results:
            _sc, _r = _res["sc"], _res["r"]
            for _m in _r["monthly"]:
                if _m["事件"] not in ("—", "通膨調整 + 再平衡"):
                    _gk_rows.append({
                        "情境":    _sc["name"],
                        "月份":    _m["月份"],
                        "資產(萬)": _m["資產餘額 (萬)"],
                        "月提領":  _m["月提領額"],
                        "提領率%": _m["提領率 %"],
                        "事件":    _m["事件"],
                    })
        if _gk_rows:
            st.dataframe(pd.DataFrame(_gk_rows), hide_index=True, width="stretch")
        else:
            st.info("此期間無護欄觸發(僅通膨調整)")


# ════════════════════════════════════════════════════════════════════════════
# PDF 匯出
# ════════════════════════════════════════════════════════════════════════════
with tab_pdf:
    st.subheader("📄 PDF 報告匯出")
    st.caption("勾選要包含的分析區塊,產生繁中 PDF 報告(Noto Sans CJK TC 內嵌)。")

    _pdf_opts = {
        "perf":    st.checkbox("📊 績效分析 + 風險指標",            value=True,  key="_pdf_perf"),
        "target":  st.checkbox("🎯 目標試算",                        value=False, key="_pdf_target"),
        "retire":  st.checkbox("🏖️ 退休提領模擬(MC 結果)",           value=True,  key="_pdf_retire"),
        "stress":  st.checkbox("⚠️ 壓力測試(3 情境)",                value=False, key="_pdf_stress"),
        "track":   st.checkbox("📋 提領追蹤(單次歷史回測)",          value=False, key="_pdf_track"),
        "compare": st.checkbox("📈 多檔比較 + 相關性(需先輸入代號)", value=False, key="_pdf_compare"),
        "div":     st.checkbox("💰 股利歷史",                        value=False, key="_pdf_div"),
    }

    _pdf_btn_disabled = not any(_pdf_opts.values())
    if st.button("📄 產生 PDF", type="primary", disabled=_pdf_btn_disabled):
        with st.spinner("產生 PDF 中(圖表轉 PNG 可能需要 10-30 秒)..."):
            # ── 建立封面 ─────────────────────────────────────────────────────
            _builder = PDFReportBuilder(
                title    = "台股績效分析報告",
                subtitle = f"{stock_id} · 至 {pd.Timestamp.today().date()}",
                meta     = {
                    "股票代號":   stock_id,
                    "每月定投":   f"{monthly_dca:,.0f} TWD",
                    "稅費計算":   "啟用" if _tax_cfg.enabled else "未啟用",
                    "報酬模式":   "實質" if _is_real else "名目",
                    "產生日期":   pd.Timestamp.today().strftime("%Y-%m-%d %H:%M"),
                },
            )

            # ── 績效分析 ─────────────────────────────────────────────────────
            if _pdf_opts["perf"]:
                _cmp_r = calc_comparison(close_full, monthly_dca)
                _lump_r, _dca_r = _cmp_r.lump, _cmp_r.dca
                _rm = calc_risk_metrics(close_full)
                _builder.add_metrics(f"績效分析 — {stock_id} ({_lump_r.years:.1f} 年)", [
                    ("單筆總報酬",   f"{_lump_r.total_return_pct:+,.1f}%"),
                    ("單筆年化",     f"{_display_cagr_pct(_lump_r.cagr_pct):+.2f}%"),
                    ("DCA 年化",     f"{_display_cagr_pct(_cmp_r.dca_cagr_pct):+.2f}%"),
                    ("最大回撤",     f"{_rm.mdd_pct:.2f}%"),
                    ("Sharpe",       f"{_rm.sharpe:.2f}"),
                    ("Sortino",      f"{_rm.sortino:.2f}"),
                    ("Calmar",       f"{_rm.calmar:.2f}"),
                    ("年化波動度",   f"{_rm.vol_pct:.2f}%"),
                ])
                _dca_df = pd.DataFrame([{
                    "年度":        r.year,
                    "累計投入":    f"{r.cost_cum:,.0f}",
                    "期末市值":    f"{r.value:,.0f}",
                    "未實現損益":  f"{r.gain:,.0f}",
                    "累計報酬率%": f"{r.return_pct:.1f}",
                } for r in _dca_r.years])
                _builder.add_table("定期定額逐年績效", _dca_df)

                _fig_p = go.Figure()
                _fig_p.add_trace(go.Scatter(x=[r.year for r in _dca_r.years],
                                             y=[r.value for r in _dca_r.years],
                                             name="期末市值", mode="lines+markers"))
                _fig_p.add_trace(go.Scatter(x=[r.year for r in _dca_r.years],
                                             y=[r.cost_cum for r in _dca_r.years],
                                             name="累計投入", mode="lines+markers",
                                             line=dict(dash="dash")))
                _fig_p.update_layout(title=f"{stock_id} 期末市值 vs 累計投入",
                                      xaxis_title="年度", yaxis_title="TWD")
                _builder.add_chart("績效走勢", _fig_p)

            # ── 目標試算 ─────────────────────────────────────────────────────
            if _pdf_opts["target"]:
                _lump_full = calc_lump_sum(close_full)
                _t_wan = st.session_state.get("_w_target_wan", 500)
                _t_yrs = st.session_state.get("_w_target_years", 10)
                _t_exist = st.session_state.get("_w_existing", 0)
                _tr = calc_target_monthly(_t_wan * 10_000, _t_yrs, _lump_full.cagr_pct,
                                           existing=_t_exist * 10_000)
                _builder.add_metrics(f"目標試算 — {_t_wan} 萬 / {_t_yrs} 年 / CAGR {_lump_full.cagr_pct:.2f}%", [
                    ("每月需投入",       f"{_tr['monthly']:,.0f} TWD"),
                    ("一次性投入等效",   f"{_tr['lump_sum_today']:,.0f} TWD"),
                    ("新增投入本金",     f"{_tr['total_invested']:,.0f} TWD"),
                    ("預估最終終值",     f"{_tr['terminal_value']:,.0f} TWD"),
                ])

            # ── 退休 MC ──────────────────────────────────────────────────────
            if _pdf_opts["retire"]:
                _ra = st.session_state.get("_w_rasset", 2000) * 10_000
                _ry = st.session_state.get("_w_ryears", 30)
                _rr = st.session_state.get("_w_rrate", 5.0) / 100
                _rg = st.session_state.get("_w_rguard", 20.0) / 100
                _rf = st.session_state.get("_w_rinf", 2.0) / 100

                # 拿退休頁的加權報酬 / 波動
                _pf_df = st.session_state.get("_custom_df_value")
                _preset = st.session_state.get("preset_choice", "保守配息型（預設）")
                _pr_map = {
                    "保守配息型（預設）": [
                        {"代號": "0056",   "配置比例 %": 30},
                        {"代號": "00878",  "配置比例 %": 20},
                        {"代號": "00720B", "配置比例 %": 30},
                        {"代號": "00679B", "配置比例 %": 10},
                        {"代號": "現金",   "配置比例 %": 10},
                    ],
                    "債券優先型": [
                        {"代號": "00720B", "配置比例 %": 40},
                        {"代號": "00679B", "配置比例 %": 25},
                        {"代號": "0056",   "配置比例 %": 25},
                        {"代號": "現金",   "配置比例 %": 10},
                    ],
                    "全高股息型": [
                        {"代號": "0056",   "配置比例 %": 35},
                        {"代號": "00878",  "配置比例 %": 30},
                        {"代號": "00713",  "配置比例 %": 15},
                        {"代號": "現金",   "配置比例 %": 20},
                    ],
                    "均衡穩健型": [
                        {"代號": "0050",   "配置比例 %": 15},
                        {"代號": "00878",  "配置比例 %": 20},
                        {"代號": "00720B", "配置比例 %": 30},
                        {"代號": "00679B", "配置比例 %": 15},
                        {"代號": "現金",   "配置比例 %": 20},
                    ],
                    "槓桿平衡型": [
                        {"代號": "00631L", "配置比例 %": 50},
                        {"代號": "現金",   "配置比例 %": 50},
                    ],
                }
                if _preset == "自訂" and _pf_df is not None:
                    _pf_rows = _pf_df[["代號", "配置比例 %"]].to_dict("records")
                else:
                    _pf_rows = _pr_map.get(_preset, _pr_map["保守配息型（預設）"])
                _w_ret_calc, _w_vol_calc = 0.0, 0.0
                for _row in _pf_rows:
                    _code = str(_row["代號"]).strip().upper()
                    _weight = _row["配置比例 %"] / 100
                    if _code == "現金":
                        continue
                    try:
                        _c, _ = _cached_adjusted_close(_code, token)
                        _cagr_i, _vol_i = calc_return_vol(_c)
                        _w_ret_calc += _weight * _cagr_i
                        _w_vol_calc += _weight * _vol_i
                    except Exception:
                        pass

                _mc_pdf = simulate_gk_montecarlo(
                    initial_portfolio = _ra,
                    initial_rate      = _rr,
                    guardrail_pct     = _rg,
                    annual_return     = _w_ret_calc,
                    annual_volatility = _w_vol_calc,
                    inflation_rate    = _rf,
                    years             = int(_ry),
                    n_sims            = 1000,
                )
                _builder.add_metrics(
                    f"退休提領 MC — {_ra/10_000:,.0f} 萬 / {_ry} 年 / 提領率 {_rr*100:.1f}%",
                    [
                        ("加權年化報酬", f"{_w_ret_calc*100:.2f}%"),
                        ("加權波動度",   f"{_w_vol_calc*100:.2f}%"),
                        ("初始月提領",   f"{_mc_pdf['initial_monthly']:,.0f} TWD"),
                        (f"第{_ry}年存活率", f"{_mc_pdf['survival_final']:.1f}%"),
                        ("P50 期末資產", f"{_mc_pdf['port_pct'][50][-1]/10_000:,.0f} 萬"),
                        ("P10 期末資產", f"{_mc_pdf['port_pct'][10][-1]/10_000:,.0f} 萬"),
                    ],
                )
                _yrs_pdf = _mc_pdf["years"]
                _fig_mc = go.Figure()
                for _p, _col, _da in [(50, "steelblue", "solid"), (10, "tomato", "dash"), (90, "seagreen", "dash")]:
                    _fig_mc.add_trace(go.Scatter(
                        x=_yrs_pdf, y=_mc_pdf["port_pct"][_p] / 10_000,
                        name=f"P{_p}", mode="lines",
                        line=dict(color=_col, dash=_da),
                    ))
                _fig_mc.update_layout(title="資產百分位",
                                       xaxis_title="退休後第幾年",
                                       yaxis_title="資產餘額(萬 TWD)")
                _builder.add_chart("資產百分位圖(P10/P50/P90)", _fig_mc)

                _builder.add_table("投組配置", pd.DataFrame(_pf_rows))

            # ── 壓力測試 ─────────────────────────────────────────────────────
            if _pdf_opts["stress"]:
                try:
                    _proxy_cl, _ = _cached_adjusted_close("0050", token)
                    _pf_df = st.session_state.get("_custom_df_value")
                    _preset = st.session_state.get("preset_choice", "保守配息型（預設）")
                    # 用同樣的 preset map
                    _pr_map2 = {
                        "保守配息型（預設）": [
                            {"代號": "0056",   "配置比例 %": 30}, {"代號": "00878", "配置比例 %": 20},
                            {"代號": "00720B", "配置比例 %": 30}, {"代號": "00679B", "配置比例 %": 10},
                            {"代號": "現金",   "配置比例 %": 10},
                        ],
                    }
                    _s_rows = _pr_map2.get(_preset, _pr_map2["保守配息型（預設）"])
                    _s_alloc = {
                        str(r["代號"]).strip().upper(): r["配置比例 %"] / 100
                        for r in _s_rows
                    }
                    _s_alloc = {("現金" if k in ("現金", "CASH") else k): v for k, v in _s_alloc.items()}
                    _s_asset = st.session_state.get("_w_rasset", 2000) * 10_000

                    _scenarios_pdf = [("2008-01", "2008 金融海嘯"), ("2020-02", "2020 COVID"), ("2022-01", "2022 升息")]
                    _s_rows_summary = []
                    for _sym, _sname in _scenarios_pdf:
                        _start_ts = pd.Timestamp(_sym + "-01")
                        _close_map = {}
                        for _a in _s_alloc:
                            if _a == "現金":
                                continue
                            try:
                                _c, _ = _cached_adjusted_close(_a, token)
                                # 代理
                                if _c.index[0] > _start_ts:
                                    _seg = _proxy_cl[(_proxy_cl.index >= _start_ts) & (_proxy_cl.index <= _c.index[0])]
                                    if not _seg.empty:
                                        _scale = float(_c.iloc[0]) / float(_seg.iloc[-1])
                                        _c = pd.concat([(_seg[:-1] * _scale), _c]).sort_index()
                                        _c = _c[~_c.index.duplicated(keep="last")]
                                _close_map[_a] = _c
                            except Exception:
                                pass
                        try:
                            _rs = run_gk_historical(
                                initial_portfolio=_s_asset, allocations=_s_alloc,
                                start_ym=_sym, initial_rate=st.session_state.get("_w_rrate", 5.0) / 100,
                                guardrail_pct=st.session_state.get("_w_rguard", 20.0) / 100,
                                inflation_rate=st.session_state.get("_w_rinf", 2.0) / 100,
                                close_series=_close_map,
                            )
                            _s_rows_summary.append({
                                "情境":         _sname,
                                "起點":         _sym,
                                "歷時(年)":     f"{len(_rs['monthly'])/12:.1f}",
                                "目前資產(萬)": f"{_rs['final_portfolio']/10_000:,.0f}",
                                "月提領(TWD)":  f"{_rs['final_monthly_income']:,.0f}",
                            })
                        except Exception:
                            pass
                    if _s_rows_summary:
                        _builder.add_table("壓力測試 — 3 歷史情境", pd.DataFrame(_s_rows_summary))
                except Exception as _e:
                    _builder.add_text("壓力測試", f"資料載入失敗:{_e}")

            # ── 提領追蹤 ─────────────────────────────────────────────────────
            if _pdf_opts["track"]:
                try:
                    _tk_port_pdf = st.session_state.get("_w_tk6_port", 2000) * 10_000
                    _tk_rate_pdf = st.session_state.get("_w_tk6_rate", 4.0) / 100
                    _tk_guard_pdf = st.session_state.get("_w_tk6_guard", 20) / 100
                    _tk_inf_pdf  = st.session_state.get("_w_tk6_infl", 2.0) / 100
                    _tk_start_pdf = st.session_state.get("_w_tk6_start", _date(2024, 1, 1))
                    _tk_alloc_df = st.session_state.get("tk6_alloc_df")
                    if _tk_alloc_df is not None:
                        _tk_alloc_pdf = {
                            str(r["代號"]).strip().upper(): r["配置比例 %"] / 100
                            for _, r in _tk_alloc_df.iterrows()
                            if str(r["代號"]).strip() and r["配置比例 %"] > 0
                        }
                        _tk_alloc_pdf = {("現金" if k in ("現金", "CASH") else k): v for k, v in _tk_alloc_pdf.items()}
                        _tk_close_pdf: dict[str, pd.Series] = {}
                        for _a in _tk_alloc_pdf:
                            if _a == "現金":
                                continue
                            try:
                                _c, _ = _cached_adjusted_close(_a, token)
                                _tk_close_pdf[_a] = _c
                            except Exception:
                                pass
                        _tk_r = run_gk_historical(
                            initial_portfolio=_tk_port_pdf,
                            allocations=_tk_alloc_pdf,
                            start_ym=_tk_start_pdf.strftime("%Y-%m"),
                            initial_rate=_tk_rate_pdf,
                            guardrail_pct=_tk_guard_pdf,
                            inflation_rate=_tk_inf_pdf,
                            close_series=_tk_close_pdf,
                        )
                        _builder.add_metrics(
                            f"提領追蹤 — {_tk_port_pdf/10_000:,.0f} 萬 / 從 {_tk_start_pdf.strftime('%Y-%m')} 起",
                            [
                                ("目前資產",     f"{_tk_r['final_portfolio']/10_000:,.0f} 萬"),
                                ("目前月提領",   f"{_tk_r['final_monthly_income']:,.0f} TWD"),
                                ("追蹤月數",     f"{len(_tk_r['monthly'])}"),
                                ("再平衡次數",   f"{len(_tk_r['rebalances'])}"),
                            ],
                        )
                        _builder.add_table("逐月明細(節錄前 24 個月)",
                                            pd.DataFrame(_tk_r["monthly"][:24]))
                except Exception as _e:
                    _builder.add_text("提領追蹤", f"載入失敗:{_e}")

            # ── 多檔比較 ─────────────────────────────────────────────────────
            if _pdf_opts["compare"]:
                _cmp_ids = [st.session_state.get(f"_w_cmp_{i}", "").strip().upper().removesuffix(".TW")
                             for i in range(5)]
                _cmp_ids = [c for c in _cmp_ids if c]
                if len(_cmp_ids) >= 2:
                    _cmp_closes = {}
                    for _c_id in _cmp_ids:
                        try:
                            _c_series, _ = _cached_adjusted_close(_c_id, token)
                            _cmp_closes[_c_id] = _c_series
                        except Exception:
                            pass
                    if len(_cmp_closes) >= 2:
                        _cmp_records = calc_multi_compare(_cmp_closes, monthly_dca)
                        _cmp_t_df = pd.DataFrame([{
                            "代號":      r.stock_id,
                            "共同起始":  str(r.common_start.date()),
                            "年數":      f"{r.years:.2f}",
                            "總報酬%":   f"{r.total_return_pct:.1f}",
                            "年化%":     f"{r.cagr_pct:.2f}",
                            "DCA 終值":  f"{r.dca_final:,.0f}",
                        } for r in _cmp_records])
                        _builder.add_table(f"多檔比較({', '.join(_cmp_ids)})", _cmp_t_df)

                        _corr = calc_correlation_matrix(_cmp_closes)
                        if not _corr.empty:
                            _builder.add_table("相關性矩陣(月報酬)", _corr.round(3).reset_index())
                else:
                    _builder.add_text("多檔比較", "❗ 未輸入至少 2 個代號,跳過此區塊")

            # ── 股利歷史 ─────────────────────────────────────────────────────
            if _pdf_opts["div"]:
                try:
                    _div_df = _cached_dividend_history(stock_id, token)
                    if not _div_df.empty:
                        _avg_y = _div_df["yield_pct"].mean()
                        _builder.add_metrics(f"股利歷史 — {stock_id}", [
                            ("發放次數",   f"{len(_div_df)} 次"),
                            ("平均殖利率", f"{_avg_y:.2f}%"),
                            ("累計配息",   f"{_div_df['cash_dividend'].sum():.2f} TWD/股"),
                        ])
                        _div_show = _div_df[["date", "cash_dividend", "yield_pct"]].copy()
                        _div_show["date"] = pd.to_datetime(_div_show["date"]).dt.strftime("%Y-%m-%d")
                        _div_show.columns = ["除息日", "配息(TWD/股)", "殖利率%"]
                        _builder.add_table("股利明細", _div_show)
                    else:
                        _builder.add_text("股利歷史", "無股利發放紀錄")
                except Exception as _e:
                    _builder.add_text("股利歷史", f"載入失敗:{_e}")

            # ── 建置並下載 ────────────────────────────────────────────────────
            try:
                _pdf_bytes = _builder.build()
                _fname = f"tw-etf-report_{stock_id}_{pd.Timestamp.today().strftime('%Y%m%d')}.pdf"
                st.success(f"✅ 已產生 PDF:{len(_pdf_bytes):,} bytes({len(_pdf_bytes)/1024:.0f} KB)")
                st.download_button(
                    label     = "⬇️ 下載 PDF 報告",
                    data      = _pdf_bytes,
                    file_name = _fname,
                    mime      = "application/pdf",
                    type      = "primary",
                )
            except Exception as _e:
                st.error(f"PDF 產生失敗:{_e}")
                import traceback
                st.code(traceback.format_exc())

    elif _pdf_btn_disabled:
        st.warning("請至少勾選一個分頁")


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
    "tax_enabled":       bool(st.session_state.get("_w_tax_enabled", False)),
    "tax_bracket_label": str(st.session_state.get("_w_tax_bracket_label", "12% (590k–1.33M)")),
    "buy_fee":           float(st.session_state.get("_w_buy_fee", DEFAULT_BUY_FEE_RATE * 100)),
    "display_mode":      str(st.session_state.get("_w_display_mode", "名目")),
    "display_inf":       float(st.session_state.get("_w_display_inf", 2.0)),
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
