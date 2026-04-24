# -*- coding: utf-8 -*-
"""全域側邊欄:稅費建模 + 報酬顯示模式 + 說明。

render_sidebar() 回傳 (TaxFeeConfig, is_real: bool, inflation_rate: float)。
app.py 用此 3 件包成 AppContext 傳遞給各 view。
"""

from __future__ import annotations

import streamlit as st

from tw_etf_analyzer.constants import DEFAULT_BUY_FEE_RATE, DEFAULT_SELL_FEE_RATE
from tw_etf_analyzer.core.tax import TaxFeeConfig


_BRACKET_OPTIONS: dict[str, float] = {
    "5% (年所得 ≤ 590k)":  0.05,
    "12% (590k–1.33M)":    0.12,
    "20% (1.33M–2.66M)":   0.20,
    "30% (2.66M–4.98M)":   0.30,
    "40% (4.98M+)":        0.40,
}


def render_sidebar() -> tuple[TaxFeeConfig, bool, float]:
    """渲染側邊欄並回傳當前設定。

    注意:所有 widget 的初始值都由 storage.init_session_state_and_load() 預先 seed 到
    st.session_state,此處不再重複傳 value=/index=(避免 Streamlit 發警告)。
    """
    with st.sidebar:
        st.markdown("### ⚙️ 全域設定")

        # ── 稅費建模 ──────────────────────────────────────────────────────
        with st.expander("💸 稅費建模", expanded=False):
            tax_enabled = st.checkbox(
                "啟用稅費計算",
                key="_w_tax_enabled",
                help="啟用後，所有頁面的報酬、終值、CAGR 皆扣除股利稅、二代健保、交易手續費",
            )
            labels = list(_BRACKET_OPTIONS.keys())
            bracket_label = st.selectbox(
                "綜所稅率級距",
                labels,
                key="_w_tax_bracket_label",
                disabled=not tax_enabled,
                help="系統自動在「合併課稅(可抵減 8.5%，上限 8 萬)」與「分離課稅 28%」中選擇較低稅額",
            )
            tax_bracket = _BRACKET_OPTIONS[bracket_label]

            st.caption("二代健保:**單筆股利 ≥ NT$20,000 自動扣 2.11%**(無法調整)")

            buy_fee = st.number_input(
                "買進手續費 %",
                min_value=0.0, max_value=0.1425, step=0.01,
                key="_w_buy_fee",
                format="%.4f",
                disabled=not tax_enabled,
                help="預設 0.07125%(= 公定 0.1425% × 五折折扣)",
            )
            st.caption(
                f"賣出手續費 + 證交稅:**{DEFAULT_SELL_FEE_RATE*100:.4f}%**"
                "(= 0.07125% + 證交稅 0.1%,寫死)"
            )

            tax_cfg = TaxFeeConfig(
                enabled            = tax_enabled,
                income_tax_bracket = tax_bracket,
                buy_fee_rate       = buy_fee / 100,
                sell_fee_rate      = DEFAULT_SELL_FEE_RATE,
            )

        # ── 報酬顯示模式 ──────────────────────────────────────────────────
        with st.expander("📏 報酬顯示模式", expanded=False):
            display_mode = st.radio(
                "名目 vs 實質",
                ["名目", "實質"],
                key="_w_display_mode",
                horizontal=True,
                help="實質模式會將所有金額、CAGR 以通膨率反向折算為今日購買力。通膨率使用下方設定。",
            )
            display_inflation = st.number_input(
                "顯示用通膨率 %",
                min_value=0.0, max_value=10.0,
                step=0.5,
                key="_w_display_inf",
                disabled=(display_mode != "實質"),
                help="實質模式下才生效。預設值與退休模擬頁的通膨率連動。",
            )
            is_real  = (display_mode == "實質")
            inf_rate = display_inflation / 100

        # ── 說明 ──────────────────────────────────────────────────────────
        with st.expander("ℹ️ 說明", expanded=False):
            st.caption(
                "- 稅費模型採「長期年化拖累」近似:股利稅 × 殖利率,逐年扣除 CAGR\n"
                "- 手續費:買進時即時扣,賣出時用於退休提領\n"
                "- 實質報酬:所有金額 ÷ (1+通膨)^年數;CAGR 轉為 (1+名目)/(1+通膨)-1\n"
                "- 短歷史標的:稅費拖累精度有限(股利歷史樣本少)"
            )

    return tax_cfg, is_real, inf_rate


def render_mode_chips(tax_cfg: TaxFeeConfig, is_real: bool, inf_rate: float) -> None:
    """頂部模式提示條(只在啟用稅費或實質時顯示)。"""
    if not tax_cfg.enabled and not is_real:
        return
    chips = []
    if tax_cfg.enabled:
        chips.append(f"💸 稅費啟用(稅率 {tax_cfg.income_tax_bracket*100:.0f}%)")
    if is_real:
        chips.append(f"📏 實質報酬(通膨 {inf_rate*100:.1f}%)")
    st.info("　｜　".join(chips))
