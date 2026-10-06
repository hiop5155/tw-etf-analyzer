# -*- coding: utf-8 -*-
"""稅費模型測試:合併 vs 分離、NHI 閾值、到手比率。"""

from __future__ import annotations

import pytest

from tw_etf_analyzer.core.tax import (
    TaxFeeConfig,
    apply_buy_fee, apply_sell_fee,
    avg_annual_dividend_yield,
    calc_tax_drag,
    dividend_net_ratio,
    effective_dividend_tax_rate,
)


class TestEffectiveDividendTaxRate:
    def test_zero_dividend(self):
        rate, method = effective_dividend_tax_rate(0, 0.20)
        assert rate == 0.0

    def test_combined_beats_separate_for_low_bracket(self):
        # 12% 綜所 - 8.5% 抵減 = 3.5%,遠低於分離 28%
        rate, method = effective_dividend_tax_rate(100_000, 0.12)
        assert method == "combined"
        assert rate == pytest.approx(0.035, abs=1e-6)

    def test_separate_beats_combined_for_high_bracket(self):
        # 40% 綜所 - 8.5% = 31.5% > 分離 28%
        rate, method = effective_dividend_tax_rate(500_000, 0.40)
        assert method == "separate"
        assert rate == 0.28

    def test_deduction_cap_at_80k(self):
        # 100 萬股利 × 8.5% = 85,000 > 上限 80,000
        # 合併課稅 = 100萬 × 20% - 80,000 = 120,000 → 有效稅率 12%
        rate, method = effective_dividend_tax_rate(1_000_000, 0.20)
        assert method == "combined"
        assert rate == pytest.approx(0.12, abs=1e-6)


class TestDividendNetRatio:
    def test_below_nhi_threshold(self):
        # 10k 股利 < 20k,不課 NHI;20% 綜所 - 8.5% = 11.5% 稅率
        net = dividend_net_ratio(10_000, 0.20)
        assert net == pytest.approx(1 - 0.115, abs=1e-6)

    def test_above_nhi_threshold(self):
        # 50k 股利 ≥ 20k,扣 NHI 2.11%;12% 綜所 - 8.5% = 3.5% 稅率
        net = dividend_net_ratio(50_000, 0.12)
        assert net == pytest.approx(1 - 0.035 - 0.0211, abs=1e-6)

    def test_zero_dividend_gives_full(self):
        assert dividend_net_ratio(0, 0.30) == 1.0


class TestFees:
    def test_buy_fee_disabled(self):
        cfg = TaxFeeConfig(enabled=False, buy_fee_rate=0.001)
        net, fee = apply_buy_fee(10_000, cfg)
        assert net == 10_000
        assert fee == 0.0

    def test_buy_fee_enabled(self):
        cfg = TaxFeeConfig(enabled=True, buy_fee_rate=0.001)
        net, fee = apply_buy_fee(10_000, cfg)
        assert fee == pytest.approx(10.0)
        assert net == pytest.approx(9_990.0)

    def test_sell_fee(self):
        cfg = TaxFeeConfig(enabled=True, sell_fee_rate=0.002)
        net, fee = apply_sell_fee(50_000, cfg)
        assert fee == pytest.approx(100.0)
        assert net == pytest.approx(49_900.0)


class TestTaxDrag:
    def test_disabled_returns_zero(self):
        cfg = TaxFeeConfig(enabled=False)
        assert calc_tax_drag(0.03, 1_000_000, cfg) == 0.0

    def test_zero_yield_returns_zero(self):
        cfg = TaxFeeConfig(enabled=True, income_tax_bracket=0.20)
        assert calc_tax_drag(0.0, 1_000_000, cfg) == 0.0

    def test_positive_drag_on_enabled(self):
        cfg = TaxFeeConfig(enabled=True, income_tax_bracket=0.12)
        # 3% 殖利率 × 1M portfolio = 30k 年股利(超過 NHI 閾值)
        # 到手 = 1 - 0.035 - 0.0211 = 0.9439
        # 拖累 = 3% × (1 - 0.9439) = 0.168%
        drag = calc_tax_drag(0.03, 1_000_000, cfg)
        assert drag == pytest.approx(0.03 * (1 - 0.9439), abs=1e-4)


class TestAvgAnnualDividendYield:
    def test_normal(self, synthetic_close, synthetic_dividends):
        y = avg_annual_dividend_yield(synthetic_dividends, synthetic_close)
        # synthetic: 每年固定 2 元配息,平均股價約 140(漲 40%)→ 殖利率 ~ 1.4%
        assert 0.0 < y < 0.05

    def test_empty_df(self, synthetic_close):
        import pandas as pd
        assert avg_annual_dividend_yield(pd.DataFrame(), synthetic_close) == 0.0
