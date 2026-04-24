# -*- coding: utf-8 -*-
"""localStorage 持久化:所有使用者設定打包為單一 JSON 存於 browser localStorage。

運作流程:
1. 頁面載入時,LocalStorage.getItem() 非同步讀取 — 第一次 render 回傳 None
2. JS component 載入完成後觸發 rerun,第二次 render 拿到值
3. 用 session_state["_ls_applied"] 旗標確保只套用一次(避免蓋掉使用者後續輸入)
4. 儲存時比對上次存的值,只有變動才呼叫 setItem(避免無限 rerun)
"""

from __future__ import annotations

import json
from datetime import date as _date

import streamlit as st

from tw_etf_analyzer.constants import DEFAULT_BUY_FEE_RATE


_STORAGE_KEY = "etf_all"


# ── 預設值(種子 session_state) ───────────────────────────────────────────────
_DEFAULTS: dict = {
    "_w_sid":        "0050",
    "_w_dca":        10000,
    "_w_rasset":     2000,
    "_w_ryears":     30,
    "_w_rinf":       2.0,
    "_w_rrate":      5.0,
    "_w_rguard":     20.0,
    "preset_choice": "保守配息型（預設）",
    # 目標試算
    "_w_target_wan":   500,
    "_w_target_years": 10,
    "_w_existing":     0,
    # 多檔比較
    "_w_cmp_0": "", "_w_cmp_1": "", "_w_cmp_2": "",
    "_w_cmp_3": "", "_w_cmp_4": "",
    # 提領追蹤
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


# ── session_state key ↔ localStorage key 映射 ─────────────────────────────────
_FIELD_MAP: dict[str, tuple[type, str]] = {
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


def init_session_state_and_load(ls) -> None:
    """種子預設值並從 localStorage 還原已存設定。

    流程(見本檔 docstring):第二次 render 才能讀到 localStorage。
    """
    if "_ls_render" not in st.session_state:
        st.session_state["_ls_render"] = 0
    st.session_state["_ls_render"] += 1

    # Step 1: 種子預設值
    for k, v in _DEFAULTS.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # Step 2: 從 localStorage 還原(只在未套用時做)
    if st.session_state.get("_ls_applied"):
        return

    raw_all = ls.getItem(_STORAGE_KEY)

    if raw_all is not None:
        try:
            saved = json.loads(raw_all)
            for ss_key, (cast, ls_key) in _FIELD_MAP.items():
                if ls_key in saved:
                    try:
                        st.session_state[ss_key] = cast(saved[ls_key])
                    except (ValueError, TypeError):
                        pass
            # 日期型別單獨處理
            if "tk6_start" in saved:
                try:
                    st.session_state["_w_tk6_start"] = _date.fromisoformat(saved["tk6_start"])
                except (ValueError, TypeError):
                    pass
            # 陣列/複雜型別
            if "tk6_alloc" in saved and isinstance(saved["tk6_alloc"], list):
                st.session_state["tk6_alloc_base"] = saved["tk6_alloc"]
            if "r_custom" in saved and isinstance(saved["r_custom"], list):
                # 相容舊 localStorage:欄位曾叫 "ETF代號"
                st.session_state["_custom_base"] = [
                    {("代號" if k == "ETF代號" else k): v for k, v in row.items()}
                    for row in saved["r_custom"]
                ]
                st.session_state.pop("retire_portfolio_custom", None)
                st.session_state["_custom_ls_done"] = True
        except Exception:
            pass
        st.session_state["_ls_applied"] = True
        st.session_state["_lsprev_etf_all"] = ""
    elif st.session_state["_ls_render"] >= 2:
        # JS 元件已載入但 localStorage 空白(全新瀏覽器 / 清除過) → 解鎖寫入
        st.session_state["_ls_applied"] = True
        st.session_state["_lsprev_etf_all"] = ""


def persist(ls, stock_id: str, monthly_dca: int) -> None:
    """把 session_state 的設定打包寫入 localStorage。

    只在 _ls_applied=True 後才寫,避免 render 1 的預設值蓋掉已存的值。
    """
    payload: dict = {
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

    # 複雜型別:DataFrame return value → list of dicts
    tk6_alloc_df = st.session_state.get("tk6_alloc_df")
    if tk6_alloc_df is not None and hasattr(tk6_alloc_df, "columns"):
        try:
            payload["tk6_alloc"] = json.loads(
                tk6_alloc_df[["代號", "配置比例 %"]].to_json(orient="records", force_ascii=False)
            )
        except Exception:
            pass

    custom_df = st.session_state.get("_custom_df_value")
    if custom_df is not None and hasattr(custom_df, "columns"):
        try:
            payload["r_custom"] = json.loads(
                custom_df[["代號", "配置比例 %"]].to_json(orient="records", force_ascii=False)
            )
        except Exception:
            pass

    new_val = json.dumps(payload, ensure_ascii=False)

    # 只在 applied 且值真的變了才寫(用遞增 counter 當 key,強制重新掛載 React 元件)
    if st.session_state.get("_ls_applied") and st.session_state.get("_lsprev_etf_all") != new_val:
        n = st.session_state.get("_ls_save_n", 0) + 1
        st.session_state["_ls_save_n"] = n
        ls.setItem(_STORAGE_KEY, new_val, key=f"_lssave_{n}")
        st.session_state["_lsprev_etf_all"] = new_val
