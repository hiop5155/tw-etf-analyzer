# -*- coding: utf-8 -*-
"""Streamlit 記憶體快取包裝 — 讓多個 view 共用同一份資料,避免重複讀 CSV / 打 API。"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from tw_etf_analyzer.core.data import fetch_adjusted_close, fetch_dividend_history


@st.cache_data(ttl=86400, show_spinner=False)
def cached_adjusted_close(stock_id: str, token: str) -> tuple[pd.Series, list[str]]:
    """優先從 st.cache_data → 磁碟 CSV → FinMind API。"""
    return fetch_adjusted_close(stock_id, token, force=False)


@st.cache_data(ttl=86400, show_spinner=False)
def cached_dividend_history(stock_id: str, token: str) -> pd.DataFrame:
    return fetch_dividend_history(stock_id, token)


def clear_all_caches() -> None:
    """強制重新下載時呼叫。"""
    cached_adjusted_close.clear()
    cached_dividend_history.clear()
