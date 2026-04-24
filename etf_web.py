# -*- coding: utf-8 -*-
"""台股績效分析 — Streamlit 進入點(路由層)。

薄 dispatcher:側邊欄 + 8 分頁 → tw_etf_analyzer/web/views/*.render(ctx)。
所有業務邏輯都在 tw_etf_analyzer package 內。
"""

# ── 依賴補裝(Streamlit Cloud 首次啟動保險) ─────────────────────────────────
from tw_etf_analyzer.web.bootstrap import ensure_deps
ensure_deps()

import streamlit as st
from streamlit_local_storage import LocalStorage

from tw_etf_analyzer.config import load_token
from tw_etf_analyzer.core.data import fetch_adjusted_close

from tw_etf_analyzer.web.cache import cached_adjusted_close, clear_all_caches
from tw_etf_analyzer.web.context import AppContext
from tw_etf_analyzer.web.sidebar import render_mode_chips, render_sidebar
from tw_etf_analyzer.web.storage import init_session_state_and_load, persist
from tw_etf_analyzer.web.views import (
    compare     as view_compare,
    dividend    as view_dividend,
    pdf_export  as view_pdf_export,
    performance as view_performance,
    retirement  as view_retirement,
    stress      as view_stress,
    target      as view_target,
    tracking    as view_tracking,
)

st.set_page_config(page_title="台股績效分析", page_icon="📈", layout="wide")
st.title("📈 台股績效分析")

# ── Token ─────────────────────────────────────────────────────────────────────
token = load_token()
if not token:
    st.error("找不到 FINMIND_TOKEN，請在 .env 檔設定：`FINMIND_TOKEN=你的token`")
    st.stop()

# ── localStorage 初始化與 session state 還原 ──────────────────────────────────
_ls = LocalStorage()
init_session_state_and_load(_ls)

# ── 側邊欄(稅費 + 顯示模式) ─────────────────────────────────────────────────
_tax_cfg, _is_real, _inf_rate = render_sidebar()
render_mode_chips(_tax_cfg, _is_real, _inf_rate)

# ── 全域輸入(所有 tab 共用) ─────────────────────────────────────────────────
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

# ── 載入完整資料(所有 view 共用) ────────────────────────────────────────────
with st.spinner(f"載入 {stock_id} 資料..."):
    try:
        if refresh:
            clear_all_caches()
            close_full, _ = fetch_adjusted_close(stock_id, token, force=True)
        else:
            close_full, _ = cached_adjusted_close(stock_id, token)
    except Exception as e:
        st.error(str(e)); st.stop()

# ── 共用 Context(傳給各 view) ──────────────────────────────────────────────
ctx = AppContext(
    token       = token,
    stock_id    = stock_id,
    monthly_dca = int(monthly_dca),
    close_full  = close_full,
    tax_cfg     = _tax_cfg,
    is_real     = _is_real,
    inflation   = _inf_rate,
)

# ── 8 分頁 dispatcher ─────────────────────────────────────────────────────────
# 順序:績效 → 目標 → 退休模擬 → 壓力測試 → 提領追蹤 → 多檔 → 股利 → PDF
tab1, tab2, tab3, tab_stress, tab4, tab5, tab6, tab_pdf = st.tabs([
    "📊 績效分析", "🎯 目標試算", "🏖️ 退休提領模擬", "⚠️ 壓力測試",
    "📋 提領追蹤", "📈 多檔比較", "💰 股利歷史", "📄 PDF 匯出",
])

with tab1:        view_performance.render(ctx)
with tab2:        view_target.render(ctx)
with tab3:        view_retirement.render(ctx)
with tab_stress:  view_stress.render(ctx)
with tab4:        view_tracking.render(ctx)
with tab5:        view_compare.render(ctx)
with tab6:        view_dividend.render(ctx)
with tab_pdf:     view_pdf_export.render(ctx)

# ── 寫入 localStorage ─────────────────────────────────────────────────────────
persist(_ls, stock_id, monthly_dca)
