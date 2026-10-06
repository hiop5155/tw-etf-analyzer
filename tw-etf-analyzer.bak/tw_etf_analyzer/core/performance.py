# -*- coding: utf-8 -*-
"""績效計算:單筆 vs DCA、多檔比較、目標試算(正推與反推)。

邊界:
- 只處理「一組收盤價 → 績效數字」的計算
- 不涉及模擬(交給 simulation.py)與風險指標(交給 metrics.py)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


# ── 輔助 ──────────────────────────────────────────────────────────────────────
def _safe_cagr(end_val: float, start_val: float, years: float) -> float:
    """年化報酬 % 安全版;零/負值直接回 0.0。"""
    if start_val <= 0 or years <= 0 or end_val < 0:
        return 0.0
    return ((end_val / start_val) ** (1.0 / years) - 1) * 100


# ── 目標試算 ──────────────────────────────────────────────────────────────────
def calc_target_monthly(
    target: float,
    years: int,
    annual_cagr_pct: float,
    existing: float = 0.0,
) -> dict:
    """反推:要在 N 年後達到目標金額,每月需投入多少?

    existing:目前已持有的市值,會以相同報酬率複利成長,從目標中扣除。
    """
    r_a = annual_cagr_pct / 100
    r_m = (1 + r_a) ** (1 / 12) - 1
    n   = years * 12

    existing_fv = existing * ((1 + r_a) ** years) if r_a > -1 else existing
    remaining = max(target - existing_fv, 0.0)

    if remaining == 0:
        monthly = 0.0
    elif r_m > 0:
        monthly = remaining * r_m / ((1 + r_m) ** n - 1)
    else:
        monthly = remaining / n if n > 0 else 0.0

    total_invested = monthly * n
    lump_sum = max(target / (1 + r_a) ** years - existing, 0.0)
    terminal_value = existing_fv + remaining

    return {
        "monthly"        : monthly,
        "lump_sum_today" : lump_sum,
        "total_invested" : total_invested,
        "existing_fv"    : existing_fv,
        "remaining"      : remaining,
        "total_gain"     : target - existing - total_invested,
        "terminal_value" : terminal_value,
    }


def calc_target_assets_from_expense(
    monthly_expense: float,
    safe_withdrawal_rate: float,
) -> float:
    """給定月支出與安全提領率,回傳退休起始所需資產。

    formula: assets = annual_expense / SWR
    """
    if safe_withdrawal_rate <= 0:
        return 0.0
    return monthly_expense * 12 / safe_withdrawal_rate


# ── Dataclasses ───────────────────────────────────────────────────────────────
@dataclass
class LumpSumResult:
    total_return_pct: float
    cagr_pct:         float
    years:            float
    inception_date:   pd.Timestamp
    last_date:        pd.Timestamp
    p0:               float
    p_last:           float


@dataclass
class DCAYearRecord:
    year:       int
    cost_cum:   float
    value:      float
    gain:       float
    return_pct: float


@dataclass
class DCAResult:
    monthly_dca: float
    years: list[DCAYearRecord] = field(default_factory=list)

    @property
    def final(self) -> DCAYearRecord:
        return self.years[-1]


@dataclass
class ComparisonResult:
    lump:                 LumpSumResult
    dca:                  DCAResult
    lump_same_cost_final: float
    lump_same_cost_ret:   float
    lump_same_cost_cagr:  float
    dca_cagr_pct:         float


@dataclass
class ETFCompareRecord:
    stock_id:         str
    inception_date:   pd.Timestamp
    common_start:     pd.Timestamp
    years:            float
    total_return_pct: float
    cagr_pct:         float
    dca_final:        float
    dca_cagr_pct:     float
    normalized:       pd.Series


# ── 計算函式 ──────────────────────────────────────────────────────────────────
def calc_lump_sum(close: pd.Series) -> LumpSumResult:
    close  = close.replace(0, float("nan")).dropna()
    p0     = float(close.iloc[0])
    p_last = float(close.iloc[-1])
    years  = (close.index[-1] - close.index[0]).days / 365.25
    return LumpSumResult(
        total_return_pct = (p_last / p0 - 1) * 100 if p0 > 0 else 0.0,
        cagr_pct         = _safe_cagr(p_last, p0, years),
        years            = years,
        inception_date   = close.index[0],
        last_date        = close.index[-1],
        p0               = p0,
        p_last           = p_last,
    )


def calc_dca(close: pd.Series, monthly_dca: float) -> DCAResult:
    monthly_first = close.resample("MS").first().dropna()
    units_total = 0.0
    cost_total  = 0.0
    result      = DCAResult(monthly_dca=monthly_dca)

    for i, (ts, price) in enumerate(monthly_first.items()):
        yr = ts.year
        if price <= 0:
            continue
        units_total += monthly_dca / price
        cost_total  += monthly_dca

        is_last   = (i == len(monthly_first) - 1)
        next_ts   = monthly_first.index[i + 1] if not is_last else None
        year_ends = is_last or (next_ts is not None and next_ts.year != yr)

        if year_ends:
            yr_prices = close[close.index.year == yr]
            end_price = float(yr_prices.iloc[-1]) if not yr_prices.empty else price
            end_value = units_total * end_price
            result.years.append(DCAYearRecord(
                year       = yr,
                cost_cum   = cost_total,
                value      = end_value,
                gain       = end_value - cost_total,
                return_pct = (end_value / cost_total - 1) * 100,
            ))
    return result


def calc_comparison(close: pd.Series, monthly_dca: float) -> ComparisonResult:
    lump = calc_lump_sum(close)
    dca  = calc_dca(close, monthly_dca)
    f    = dca.final

    lump_final = (f.cost_cum / lump.p0 * lump.p_last) if lump.p0 > 0 else 0.0
    dca_cagr   = _safe_cagr(f.value, f.cost_cum, lump.years)

    return ComparisonResult(
        lump                 = lump,
        dca                  = dca,
        lump_same_cost_final = lump_final,
        lump_same_cost_ret   = (lump_final / f.cost_cum - 1) * 100 if f.cost_cum > 0 else 0.0,
        lump_same_cost_cagr  = _safe_cagr(lump_final, f.cost_cum, lump.years),
        dca_cagr_pct         = dca_cagr,
    )


def calc_multi_compare(
    closes: dict[str, pd.Series],
    monthly_dca: float,
) -> list[ETFCompareRecord]:
    """多檔績效比較。以各標的中上市最晚的日期為共同起始點。"""
    common_start = max(s.index[0] for s in closes.values())

    records = []
    for sid, close in closes.items():
        sliced = close[close.index >= common_start].dropna()
        if len(sliced) < 2:
            continue

        p0     = float(sliced.iloc[0])
        p_last = float(sliced.iloc[-1])
        years  = (sliced.index[-1] - sliced.index[0]).days / 365.25

        total_ret = (p_last / p0 - 1) * 100 if p0 > 0 else 0.0
        cagr      = _safe_cagr(p_last, p0, years)

        dca = calc_dca(sliced, monthly_dca)
        f   = dca.final
        dca_cagr = _safe_cagr(f.value, f.cost_cum, years)

        records.append(ETFCompareRecord(
            stock_id        = sid,
            inception_date  = close.index[0],
            common_start    = common_start,
            years           = years,
            total_return_pct= total_ret,
            cagr_pct        = cagr,
            dca_final       = f.value,
            dca_cagr_pct    = dca_cagr,
            normalized      = (sliced / p0 * 100),
        ))

    return sorted(records, key=lambda r: r.cagr_pct, reverse=True)
