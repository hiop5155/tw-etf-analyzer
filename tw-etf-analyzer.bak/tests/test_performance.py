# -*- coding: utf-8 -*-
"""績效計算測試:lump / DCA / target_monthly / target_from_expense。"""

from __future__ import annotations

import pytest

from tw_etf_analyzer.core.performance import (
    calc_comparison,
    calc_dca,
    calc_lump_sum,
    calc_multi_compare,
    calc_target_assets_from_expense,
    calc_target_monthly,
)


class TestLumpSum:
    def test_synthetic_has_positive_cagr(self, synthetic_close):
        r = calc_lump_sum(synthetic_close)
        assert r.cagr_pct > 0
        assert r.years > 9  # 10 年合成資料
        assert r.p0 == pytest.approx(synthetic_close.iloc[0])


class TestDCA:
    def test_yearly_records_count(self, synthetic_close):
        r = calc_dca(synthetic_close, 10_000)
        # 10 年 → 應有 10 個年度紀錄(可能 ±1 視資料邊界)
        assert 9 <= len(r.years) <= 11
        assert r.years[-1].value > 0


class TestComparison:
    def test_lump_same_cost_consistency(self, synthetic_close):
        r = calc_comparison(synthetic_close, 10_000)
        # 相同本金下,單筆和 DCA 的起點本金相同
        assert r.dca.final.cost_cum > 0
        assert r.lump_same_cost_final > 0


class TestMultiCompare:
    def test_common_start_is_latest(self, synthetic_close, crash_close):
        records = calc_multi_compare(
            {"A": synthetic_close, "B": crash_close},
            monthly_dca=10_000,
        )
        common = records[0].common_start
        # 共同起始日 = max(起始日)
        expected = max(synthetic_close.index[0], crash_close.index[0])
        assert common == expected


class TestTargetMonthly:
    def test_zero_existing(self):
        r = calc_target_monthly(5_000_000, 10, 7.0, existing=0)
        assert r["monthly"] > 0
        assert r["terminal_value"] == pytest.approx(5_000_000, abs=1)

    def test_existing_meets_goal(self):
        # 1000 萬 @ 10 年 @ 7% → 終值 ~ 1967 萬,遠超 500 萬目標
        r = calc_target_monthly(5_000_000, 10, 7.0, existing=10_000_000)
        assert r["monthly"] == 0
        assert r["existing_fv"] > 5_000_000

    def test_zero_return_linear(self):
        # 0% 報酬 → 每月簡單線性 = 目標 / n_months
        r = calc_target_monthly(1_200_000, 10, 0.0)
        assert r["monthly"] == pytest.approx(1_200_000 / 120, abs=1)


class TestTargetAssetsFromExpense:
    def test_basic_4pct_rule(self):
        # 5 萬/月 × 12 / 4% = 1500 萬
        assets = calc_target_assets_from_expense(50_000, 0.04)
        assert assets == pytest.approx(15_000_000)

    def test_zero_swr_guards(self):
        assert calc_target_assets_from_expense(50_000, 0) == 0.0
