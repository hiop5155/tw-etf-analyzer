# -*- coding: utf-8 -*-
"""稅費模型:股利所得稅 + 二代健保 + 交易手續費。

邊界:
- 給定稅率、股利金額 → 計算有效稅率 / 到手比率
- 給定組合殖利率 + 投組金額 → 年化稅費拖累
- 給定交易金額 → 買/賣手續費

使用者面的 TaxFeeConfig 由 UI 層(sidebar.py)建立。
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from tw_etf_analyzer.constants import (
    COMBINED_DEDUCTION_CAP,
    COMBINED_DEDUCTION_RATE,
    DEFAULT_BUY_FEE_RATE,
    DEFAULT_SELL_FEE_RATE,
    NHI_RATE,
    NHI_THRESHOLD,
    SEPARATE_TAX_RATE,
)


@dataclass
class TaxFeeConfig:
    """全域稅費設定,由 Streamlit 側邊欄控制。"""
    enabled:            bool  = False
    income_tax_bracket: float = 0.12       # 綜所稅率（小數；5/12/20/30/40%）
    buy_fee_rate:       float = DEFAULT_BUY_FEE_RATE
    sell_fee_rate:      float = DEFAULT_SELL_FEE_RATE


def effective_dividend_tax_rate(dividend_amount: float, income_tax_bracket: float) -> tuple[float, str]:
    """對單筆股利金額,自動選擇「合併 vs 分離課稅」較小者。

    回傳 (有效稅率, 'combined'/'separate')。不含二代健保。
    """
    if dividend_amount <= 0:
        return 0.0, "combined"
    combined_tax = max(
        0.0,
        dividend_amount * income_tax_bracket
        - min(dividend_amount * COMBINED_DEDUCTION_RATE, COMBINED_DEDUCTION_CAP),
    )
    separate_tax = dividend_amount * SEPARATE_TAX_RATE
    if combined_tax <= separate_tax:
        return combined_tax / dividend_amount, "combined"
    return SEPARATE_TAX_RATE, "separate"


def dividend_net_ratio(annual_dividend: float, income_tax_bracket: float) -> float:
    """對一年份股利總額,回傳「到手比率」(扣所得稅 + 二代健保後 / 毛股利)。"""
    if annual_dividend <= 0:
        return 1.0
    tax_rate, _ = effective_dividend_tax_rate(annual_dividend, income_tax_bracket)
    nhi = NHI_RATE if annual_dividend >= NHI_THRESHOLD else 0.0
    return max(0.0, 1.0 - tax_rate - nhi)


def avg_annual_dividend_yield(dividends_df: pd.DataFrame, close: pd.Series) -> float:
    """從股利明細估算歷史平均年殖利率(小數)。會排除首尾不完整的年份。"""
    if dividends_df is None or dividends_df.empty or close.empty:
        return 0.0
    df = dividends_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.year
    if "cash_dividend" not in df.columns:
        return 0.0
    annual = df.groupby("year")["cash_dividend"].sum()
    if annual.empty:
        return 0.0
    first_yr, last_yr = close.index[0].year, close.index[-1].year
    complete = [y for y in annual.index if y not in (first_yr, last_yr)]
    avg_div_per_share = float(annual.loc[complete].mean()) if complete else float(annual.mean())
    avg_price = float(close.mean())
    if avg_price <= 0:
        return 0.0
    return avg_div_per_share / avg_price


def calc_tax_drag(
    dividend_yield: float,
    portfolio_value: float,
    tax: TaxFeeConfig,
) -> float:
    """計算股利稅 + 二代健保造成的年化 CAGR 拖累(小數)。

    portfolio_value 用於估算年股利總額,決定 NHI 是否觸發。
    """
    if not tax.enabled or dividend_yield <= 0 or portfolio_value <= 0:
        return 0.0
    annual_div_est = dividend_yield * portfolio_value
    net_ratio = dividend_net_ratio(annual_div_est, tax.income_tax_bracket)
    return dividend_yield * (1.0 - net_ratio)


def calc_fee_drag(tax: TaxFeeConfig, turnover_per_year: float = 0.0) -> float:
    """交易成本年化拖累:買入成本 + 年度再平衡周轉造成的賣出成本。

    * DCA 情境:每年投入金額相對總資產小,買入成本拖累近似買費率 × 當期再投入 / 總資產。
      保守用 buy_fee × 1(視為一次性 drag),賣出成本在退休階段才計。
    * turnover_per_year:投組每年換手率(0 ~ 1),預設 0 = 純買進持有。
    """
    if not tax.enabled:
        return 0.0
    return tax.sell_fee_rate * turnover_per_year


def apply_buy_fee(amount: float, tax: TaxFeeConfig) -> tuple[float, float]:
    """套用買進手續費:回傳 (實際買到的金額, 手續費金額)。"""
    if not tax.enabled:
        return amount, 0.0
    fee = amount * tax.buy_fee_rate
    return amount - fee, fee


def apply_sell_fee(amount: float, tax: TaxFeeConfig) -> tuple[float, float]:
    """套用賣出手續費+證交稅:回傳 (實拿, 總費)。"""
    if not tax.enabled:
        return amount, 0.0
    fee = amount * tax.sell_fee_rate
    return amount - fee, fee
