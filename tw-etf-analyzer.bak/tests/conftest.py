# -*- coding: utf-8 -*-
"""共用 fixtures — 不打 FinMind API 的合成資料。"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def synthetic_close() -> pd.Series:
    """10 年每日收盤:deterministic 8% CAGR + 固定 sine 波動模擬 volatility。

    不使用隨機,完全可重現。終值/首值 = 1.08^10 ≈ 2.159(+115%)。
    """
    dates = pd.date_range("2015-01-01", periods=10 * 252, freq="B")
    n = len(dates)
    t = np.arange(n) / 252
    drift = 100.0 * (1 + 0.08) ** t
    # 小幅 sine noise(±3%)仍保持正趨勢
    noise = 0.03 * np.sin(np.arange(n) * 0.1)
    price = drift * (1 + noise)
    return pd.Series(price, index=dates, name="close")


@pytest.fixture
def synthetic_dividends() -> pd.DataFrame:
    """每年一次除息,殖利率約 2%,配合 synthetic_close。"""
    rows = []
    for year in range(2015, 2025):
        rows.append({
            "date":          pd.Timestamp(f"{year}-07-15"),
            "stock_id":      "TEST",
            "before_price":  100.0,
            "after_price":   98.0,
            "cash_dividend": 2.0,
            "yield_pct":     2.0,
            "year":          year,
        })
    return pd.DataFrame(rows)


@pytest.fixture
def flat_close() -> pd.Series:
    """固定價格(用於 drawdown=0、vol=0 測試)。"""
    dates = pd.date_range("2020-01-01", periods=252 * 3, freq="B")
    return pd.Series(100.0, index=dates)


@pytest.fixture
def crash_close() -> pd.Series:
    """明確的 -50% 崩盤,用於驗證 MDD 正確性。"""
    dates = pd.date_range("2020-01-01", periods=300, freq="B")
    prices = [100.0] * 100 + [100.0 - i * 0.5 for i in range(100)] + [50.0 + i * 0.25 for i in range(100)]
    return pd.Series(prices[:300], index=dates)
