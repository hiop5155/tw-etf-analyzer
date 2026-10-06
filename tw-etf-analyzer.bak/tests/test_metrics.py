# -*- coding: utf-8 -*-
"""風險指標測試:MDD / Sharpe / Sortino / Calmar / 相關性。"""

from __future__ import annotations

import pandas as pd
import pytest

from tw_etf_analyzer.core.metrics import (
    calc_correlation_matrix,
    calc_max_drawdown,
    calc_return_vol,
    calc_risk_metrics,
    calc_sharpe_ratio,
    calc_sortino_ratio,
)


class TestReturnVol:
    def test_flat_price_zero_return(self, flat_close):
        cagr, vol = calc_return_vol(flat_close)
        assert cagr == pytest.approx(0.0, abs=1e-10)
        assert vol  == pytest.approx(0.0, abs=1e-10)

    def test_empty_returns_zero(self):
        cagr, vol = calc_return_vol(pd.Series(dtype=float))
        assert cagr == 0.0 and vol == 0.0


class TestMaxDrawdown:
    def test_flat_no_drawdown(self, flat_close):
        dd = calc_max_drawdown(flat_close)
        assert dd["mdd"] == pytest.approx(0.0, abs=1e-10)

    def test_crash_detects_50pct_mdd(self, crash_close):
        dd = calc_max_drawdown(crash_close)
        # 100 → 50.5(第 199 天),mdd ≈ -49.5%(因 crash_close 100 天跌到 50.5 而非正好 50)
        assert dd["mdd"] < -0.45
        assert dd["mdd"] > -0.55
        assert dd["peak"]   is not None
        assert dd["trough"] is not None


class TestRiskMetrics:
    def test_all_fields_populated(self, synthetic_close):
        rm = calc_risk_metrics(synthetic_close)
        assert rm.cagr_pct > 0        # 合成資料 CAGR 應為正
        assert rm.vol_pct  > 0
        assert rm.mdd_pct  < 0         # 回撤必為負
        assert isinstance(rm.sharpe,  float)
        assert isinstance(rm.sortino, float)
        assert isinstance(rm.calmar,  float)

    def test_sortino_ratio_is_finite(self, synthetic_close):
        # Sortino 與 Sharpe 的嚴格關係依賴報酬分布,不適合做一般斷言
        sortino = calc_sortino_ratio(synthetic_close)
        assert isinstance(sortino, float)
        assert sortino != float("inf")


class TestCorrelationMatrix:
    def test_identical_series_corr_1(self, synthetic_close):
        corr = calc_correlation_matrix({"A": synthetic_close, "B": synthetic_close})
        assert corr.loc["A", "A"] == pytest.approx(1.0, abs=1e-6)
        assert corr.loc["A", "B"] == pytest.approx(1.0, abs=1e-6)

    def test_single_asset_empty(self, synthetic_close):
        corr = calc_correlation_matrix({"A": synthetic_close})
        assert corr.empty

    def test_square_matrix_for_3_assets(self, synthetic_close, flat_close):
        import numpy as np
        rng = np.random.default_rng(99)
        dates = synthetic_close.index
        c3 = pd.Series(
            100 * np.cumprod(1 + rng.normal(0.05 / 252, 0.1 / 15.87, len(dates))),
            index=dates,
        )
        corr = calc_correlation_matrix({
            "A": synthetic_close,
            "B": synthetic_close * 1.001,   # 近似相同
            "C": c3,
        })
        assert corr.shape == (3, 3)
