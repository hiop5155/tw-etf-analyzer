# -*- coding: utf-8 -*-
"""GK 模擬測試:護欄觸發、MC 分配、歷史月頻。"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tw_etf_analyzer.core.simulation import (
    simulate_gk,
    simulate_gk_montecarlo,
    run_gk_historical,
)


class TestSimulateGk:
    def test_basic_depletion(self):
        # 高提領率 + 低報酬 → 應該耗盡
        r = simulate_gk(
            initial_portfolio = 1_000_000,
            initial_rate      = 0.15,
            annual_return     = 0.02,
            inflation_rate    = 0.02,
            years             = 20,
        )
        assert r.depleted_year is not None

    def test_capital_preservation_trigger(self):
        # 提領率超過護欄時應觸發減提
        r = simulate_gk(
            initial_portfolio = 1_000_000,
            initial_rate      = 0.10,
            guardrail_pct     = 0.10,
            annual_return     = -0.20,  # 大跌觸發護欄
            inflation_rate    = 0.0,
            years             = 5,
        )
        triggers = [rec.trigger for rec in r.records]
        assert "capital_preservation" in triggers


class TestMonteCarloDist:
    def test_normal_default(self):
        mc = simulate_gk_montecarlo(
            initial_portfolio = 1_000_000,
            initial_rate      = 0.04,
            guardrail_pct     = 0.20,
            annual_return     = 0.07,
            annual_volatility = 0.15,
            inflation_rate    = 0.02,
            years             = 30,
            n_sims            = 200,
        )
        assert mc["survival_final"] > 0
        assert len(mc["years"]) == 30
        assert 10 in mc["port_pct"] and 50 in mc["port_pct"]

    def test_tdist_has_fatter_tails(self):
        # Student-t 肥尾模式應該能跑
        mc = simulate_gk_montecarlo(
            initial_portfolio = 1_000_000,
            initial_rate      = 0.04,
            guardrail_pct     = 0.20,
            annual_return     = 0.07,
            annual_volatility = 0.15,
            inflation_rate    = 0.02,
            years             = 20,
            n_sims            = 200,
            dist_kind         = "tdist",
        )
        assert len(mc["port_pct"][50]) == 20

    def test_bootstrap_needs_history(self):
        # Bootstrap 需要 hist_monthly_returns
        hist = np.random.default_rng(1).normal(0.005, 0.04, 120)
        mc = simulate_gk_montecarlo(
            initial_portfolio = 1_000_000,
            initial_rate      = 0.04,
            guardrail_pct     = 0.20,
            annual_return     = 0.07,
            annual_volatility = 0.15,
            inflation_rate    = 0.02,
            years             = 10,
            n_sims            = 100,
            dist_kind         = "bootstrap",
            hist_monthly_returns = hist,
        )
        assert mc["survival_final"] >= 0

    def test_bootstrap_falls_back_when_no_history(self):
        # 沒傳 hist_monthly_returns 時應 fallback 到 normal
        mc = simulate_gk_montecarlo(
            initial_portfolio = 1_000_000,
            initial_rate      = 0.04,
            guardrail_pct     = 0.20,
            annual_return     = 0.07,
            annual_volatility = 0.15,
            inflation_rate    = 0.02,
            years             = 10,
            n_sims            = 100,
            dist_kind         = "bootstrap",
            hist_monthly_returns = None,
        )
        assert mc is not None


class TestRunGkHistorical:
    def test_monthly_records_structure(self, synthetic_close):
        result = run_gk_historical(
            initial_portfolio = 1_000_000,
            allocations       = {"TEST": 1.0},
            start_ym          = "2020-01",
            initial_rate      = 0.04,
            guardrail_pct     = 0.20,
            inflation_rate    = 0.02,
            close_series      = {"TEST": synthetic_close},
        )
        assert "monthly" in result
        assert "rebalances" in result
        assert "final_portfolio" in result
        if result["monthly"]:
            first = result["monthly"][0]
            assert "月份" in first
            assert "資產餘額 (萬)" in first

    def test_cash_only_no_growth(self):
        result = run_gk_historical(
            initial_portfolio = 1_000_000,
            allocations       = {"現金": 1.0},
            start_ym          = "2023-01",
            initial_rate      = 0.04,
            guardrail_pct     = 0.20,
            inflation_rate    = 0.02,
            close_series      = {},  # 純現金無需 close
        )
        # 純現金:每月只扣提領,不會增值
        assert result["final_portfolio"] < 1_000_000
