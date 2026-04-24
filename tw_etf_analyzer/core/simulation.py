# -*- coding: utf-8 -*-
"""退休提領模擬:Guyton-Klinger 動態提領 + Monte Carlo(Normal / Student-t / Bootstrap)+ 歷史月頻追蹤。

三個公開函式:
- simulate_gk — 單次確定性模擬(給定固定年化報酬)
- simulate_gk_montecarlo — Monte Carlo,可選分配模型
- run_gk_historical — 以真實歷史月報酬逐月追蹤,含每年一月再平衡
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from tw_etf_analyzer.constants import CASH_RETURN


# ── Dataclasses ───────────────────────────────────────────────────────────────
@dataclass
class GKYearRecord:
    year:            int
    portfolio_start: float
    growth:          float
    withdrawal:      float
    portfolio_end:   float
    withdrawal_rate: float   # 實際提領率 %
    monthly_income:  float
    trigger:         str     # "" / "capital_preservation" / "prosperity"


@dataclass
class GKResult:
    records:         list[GKYearRecord]
    depleted_year:   int | None   # None = 撐過全期
    final_portfolio: float
    initial_monthly: float


# ── 單次確定性 GK ─────────────────────────────────────────────────────────────
def simulate_gk(
    initial_portfolio: float,
    initial_rate:      float = 0.06,
    guardrail_pct:     float = 0.20,
    annual_return:     float = 0.0475,
    inflation_rate:    float = 0.02,
    years:             int   = 30,
) -> GKResult:
    """Guyton-Klinger 動態提領模擬(年粒度,固定年化報酬)。

    規則(每年起點執行):
    1. 通膨調整提領額,但若上年資產下滑則跳過。
    2. 資本保護:若當前提領率 > init_rate × (1+guardrail),提領額 ×0.90。
    3. 繁榮規則:若當前提領率 < init_rate × (1-guardrail),提領額 ×1.10。
    """
    portfolio    = initial_portfolio
    withdrawal   = initial_portfolio * initial_rate
    upper_guard  = initial_rate * (1 + guardrail_pct)
    lower_guard  = initial_rate * (1 - guardrail_pct)

    records: list[GKYearRecord] = []
    depleted_year = None
    prev_end      = initial_portfolio

    for yr in range(1, years + 1):
        if portfolio <= 0:
            break

        growth          = portfolio * annual_return
        portfolio_grown = portfolio + growth

        if portfolio_grown >= prev_end:
            withdrawal *= (1 + inflation_rate)

        current_rate = withdrawal / portfolio_grown if portfolio_grown > 0 else float("inf")
        trigger = ""
        if current_rate > upper_guard:
            withdrawal *= 0.90
            trigger = "capital_preservation"
            current_rate = withdrawal / portfolio_grown
        elif current_rate < lower_guard:
            withdrawal *= 1.10
            trigger = "prosperity"
            current_rate = withdrawal / portfolio_grown

        portfolio_end = portfolio_grown - withdrawal

        records.append(GKYearRecord(
            year            = yr,
            portfolio_start = portfolio,
            growth          = growth,
            withdrawal      = withdrawal,
            portfolio_end   = max(0.0, portfolio_end),
            withdrawal_rate = current_rate * 100,
            monthly_income  = withdrawal / 12,
            trigger         = trigger,
        ))

        prev_end  = portfolio_grown
        portfolio = max(0.0, portfolio_end)

        if portfolio_end <= 0:
            depleted_year = yr
            break

    return GKResult(
        records         = records,
        depleted_year   = depleted_year,
        final_portfolio = portfolio,
        initial_monthly = initial_portfolio * initial_rate / 12,
    )


# ── Monte Carlo GK ────────────────────────────────────────────────────────────
def simulate_gk_montecarlo(
    initial_portfolio: float,
    initial_rate:      float,
    guardrail_pct:     float,
    annual_return:     float,      # 加權平均報酬(小數)
    annual_volatility: float,      # 加權平均波動(小數)
    inflation_rate:    float,
    years:             int,
    n_sims:            int  = 1000,
    seed:              int  = 42,
    dist_kind:         str  = "normal",      # "normal" | "tdist" | "bootstrap"
    hist_monthly_returns: "np.ndarray | None" = None,  # bootstrap 需要
    t_df:              int  = 5,
) -> dict:
    """Monte Carlo GK。回傳各年度資產、月提領百分位與存活率。

    dist_kind:
      - normal:    N(μ, σ)
      - tdist:     Student-t(df=t_df),縮放至 σ
      - bootstrap: 從 hist_monthly_returns 有放回抽樣 12 筆複利為年報酬
    """
    rng = np.random.default_rng(seed)

    if dist_kind == "tdist":
        raw = rng.standard_t(t_df, size=(n_sims, years))
        scale = annual_volatility / np.sqrt(t_df / max(t_df - 2, 1e-6))
        ret_mat = annual_return + raw * scale
    elif dist_kind == "bootstrap" and hist_monthly_returns is not None and len(hist_monthly_returns) >= 12:
        arr = np.asarray(hist_monthly_returns, dtype=float)
        arr = arr[~np.isnan(arr)]
        samples = rng.choice(arr, size=(n_sims, years, 12), replace=True)
        ret_mat = np.prod(1.0 + samples, axis=2) - 1.0
    else:
        ret_mat = rng.normal(annual_return, annual_volatility, size=(n_sims, years))

    port_mat = np.zeros((n_sims, years))
    wd_mat   = np.zeros((n_sims, years))

    for sim in range(n_sims):
        portfolio  = initial_portfolio
        withdrawal = initial_portfolio * initial_rate
        prev_end   = initial_portfolio
        upper      = initial_rate * (1 + guardrail_pct)
        lower      = initial_rate * (1 - guardrail_pct)

        for yr in range(years):
            if portfolio <= 0:
                break
            r = float(ret_mat[sim, yr])
            portfolio_grown = portfolio * (1 + r)
            if portfolio_grown >= prev_end:
                withdrawal *= (1 + inflation_rate)
            cur_rate = withdrawal / portfolio_grown if portfolio_grown > 0 else float("inf")
            if cur_rate > upper:
                withdrawal *= 0.90
            elif cur_rate < lower:
                withdrawal *= 1.10
            portfolio_end = portfolio_grown - withdrawal
            prev_end  = portfolio_grown
            portfolio = max(0.0, portfolio_end)
            port_mat[sim, yr] = portfolio
            wd_mat[sim, yr]   = withdrawal / 12

    survived  = port_mat > 0
    surv_rate = survived.mean(axis=0) * 100
    pcts = [10, 25, 50, 75, 90]
    years_arr = np.arange(1, years + 1)
    port_pct = {p: np.percentile(port_mat, p, axis=0) for p in pcts}
    wd_pct   = {p: np.percentile(wd_mat,   p, axis=0) for p in pcts}
    sorted_idx = np.argsort(port_mat[:, -1])

    def _gk_trace(return_seq: np.ndarray) -> list[dict]:
        records = []
        portfolio  = initial_portfolio
        withdrawal = initial_portfolio * initial_rate
        prev_end   = initial_portfolio
        upper      = initial_rate * (1 + guardrail_pct)
        lower      = initial_rate * (1 - guardrail_pct)
        for yr, r in enumerate(return_seq):
            if portfolio <= 0:
                records.append({
                    "年度": yr + 1, "年化報酬 %": f"{r*100:+.1f}",
                    "年末資產 (萬)": "0", "月提領額": "0",
                    "提領率 %": "—", "護欄觸發": "💀 資產耗盡",
                })
                continue
            portfolio_grown = portfolio * (1 + r)
            if portfolio_grown >= prev_end:
                withdrawal *= (1 + inflation_rate)
            trigger = ""
            cur_rate = withdrawal / portfolio_grown if portfolio_grown > 0 else float("inf")
            if cur_rate > upper:
                withdrawal *= 0.90
                trigger = "↓ 減10%"
            elif cur_rate < lower:
                withdrawal *= 1.10
                trigger = "↑ 加10%"
            portfolio_end = portfolio_grown - withdrawal
            prev_end  = portfolio_grown
            portfolio = max(0.0, portfolio_end)
            records.append({
                "年度":          yr + 1,
                "年化報酬 %":    f"{r*100:+.1f}",
                "年末資產 (萬)": f"{portfolio/10_000:,.0f}",
                "月提領額":      f"{withdrawal/12:,.0f}",
                "提領率 %":      f"{cur_rate*100:.2f}",
                "護欄觸發":      trigger if trigger else "—",
            })
        return records

    rep_paths: dict[int, list[dict]] = {}
    for pct in (1, 10, 50, 90):
        idx = sorted_idx[int(n_sims * pct / 100)]
        rep_paths[pct] = _gk_trace(ret_mat[idx])

    return {
        "years":            years_arr,
        "port_pct":         port_pct,
        "wd_pct":           wd_pct,
        "survival_rate":    surv_rate,
        "survival_final":   float(surv_rate[-1]),
        "depleted_pct":     100 - float(surv_rate[-1]),
        "n_sims":           n_sims,
        "initial_monthly":  initial_portfolio * initial_rate / 12,
        "rep_paths":        rep_paths,
    }


# ── 歷史月頻追蹤 ──────────────────────────────────────────────────────────────
def run_gk_historical(
    initial_portfolio: float,
    allocations:   dict[str, float],
    start_ym:      str,                          # 'YYYY-MM'
    initial_rate:  float,
    guardrail_pct: float,
    inflation_rate: float,
    close_series:  dict[str, pd.Series],
) -> dict:
    """以實際歷史報酬逐月執行 GK 提領策略。

    每年一月:
      1. 通膨調整(若資產未較前一月縮水)
      2. 護欄檢查(capital_preservation / prosperity)
      3. 再平衡回目標配置
    回傳 monthly 逐月明細與 rebalances 年度再平衡明細。
    """
    start_ts = pd.Timestamp(start_ym + "-01")
    today_ts = pd.Timestamp.today().normalize()
    end_ts   = (today_ts.replace(day=1) - pd.offsets.Day(1)).replace(day=1)
    if end_ts < start_ts:
        end_ts = start_ts

    monthly_ret_map: dict[str, dict[tuple, float]] = {}
    _data_warnings: list[str] = []
    for asset, close in close_series.items():
        clean   = close.replace(0, float("nan")).dropna()
        monthly = clean.resample("ME").last().dropna()
        rets    = monthly.pct_change().dropna()
        if rets.empty:
            _data_warnings.append(f"{asset}：歷史資料不足，無法計算月報酬，將以 0% 計算。")
        else:
            first_data_ym = (rets.index[0].year, rets.index[0].month)
            start_ym_tuple = (start_ts.year, start_ts.month)
            if first_data_ym > start_ym_tuple:
                _data_warnings.append(
                    f"{asset}：資料起始於 {rets.index[0].strftime('%Y-%m')}，"
                    f"早於此日期的月份以 0% 報酬計算。"
                )
        monthly_ret_map[asset] = {
            (ts.year, ts.month): float(r) for ts, r in rets.items()
        }

    cash_monthly = (1 + CASH_RETURN) ** (1 / 12) - 1
    upper_rate   = initial_rate * (1 + guardrail_pct)
    lower_rate   = initial_rate * (1 - guardrail_pct)

    asset_values      = {a: initial_portfolio * w for a, w in allocations.items()}
    annual_withdrawal = initial_portfolio * initial_rate
    monthly_income    = annual_withdrawal / 12
    prev_jan_port     = initial_portfolio

    monthly_records:   list[dict] = []
    rebalance_records: list[dict] = []

    months = pd.date_range(start=start_ts, end=end_ts, freq="MS")

    for i, mts in enumerate(months):
        ym     = (mts.year, mts.month)
        is_jan = (mts.month == 1) and (i > 0)
        gk_trigger = ""

        portfolio_now = sum(asset_values.values())

        # 一月:通膨調整(在護欄檢查之前)
        if is_jan and portfolio_now > 0:
            if portfolio_now >= prev_jan_port:
                annual_withdrawal *= (1 + inflation_rate)
            monthly_income = annual_withdrawal / 12
            prev_jan_port = portfolio_now

        # 每月:護欄檢查
        if portfolio_now > 0:
            cur_rate = annual_withdrawal / portfolio_now
            if cur_rate > upper_rate:
                annual_withdrawal *= 0.90
                gk_trigger = "capital_preservation"
                monthly_income = annual_withdrawal / 12
            elif cur_rate < lower_rate and portfolio_now >= prev_jan_port:
                annual_withdrawal *= 1.10
                gk_trigger = "prosperity"
                monthly_income = annual_withdrawal / 12

        # 一月:再平衡(護欄調整後)
        if is_jan and portfolio_now > 0:
            drift_alloc = {a: v / portfolio_now for a, v in asset_values.items()}
            trades = {
                a: (allocations[a] - drift_alloc.get(a, 0.0)) * portfolio_now
                for a in allocations
            }
            rebalance_records.append({
                "year":           mts.year,
                "month":          mts.strftime("%Y-%m"),
                "portfolio":      portfolio_now,
                "drift_alloc":    drift_alloc,
                "target_alloc":   dict(allocations),
                "trades":         trades,
                "gk_trigger":     gk_trigger,
                "monthly_income": monthly_income,
            })
            for a in asset_values:
                asset_values[a] = portfolio_now * allocations[a]

        # 套用當月市場報酬
        port_before = sum(asset_values.values())
        for a in list(asset_values.keys()):
            if a == "現金":
                ret = cash_monthly
            else:
                ret = monthly_ret_map.get(a, {}).get(ym, 0.0)
            asset_values[a] *= (1 + ret)

        port_after_return = sum(asset_values.values())
        monthly_ret_pct = (
            (port_after_return - port_before) / port_before * 100
            if port_before > 0 else 0.0
        )

        # 扣除月提領
        eff_wd = min(monthly_income, port_after_return)
        if port_after_return > 0:
            ratio = eff_wd / port_after_return
            for a in asset_values:
                asset_values[a] *= (1 - ratio)

        port_end = max(0.0, port_after_return - eff_wd)
        wr = annual_withdrawal / port_end * 100 if port_end > 0 else float("inf")

        if is_jan:
            if gk_trigger == "capital_preservation":
                _trigger_label = "↓ 減提領 + 再平衡"
            elif gk_trigger == "prosperity":
                _trigger_label = "↑ 增提領 + 再平衡"
            else:
                _trigger_label = "通膨調整 + 再平衡"
        elif gk_trigger == "capital_preservation":
            _trigger_label = "↓ 減提領"
        elif gk_trigger == "prosperity":
            _trigger_label = "↑ 增提領"
        else:
            _trigger_label = "—"

        monthly_records.append({
            "月份":           mts.strftime("%Y-%m"),
            "月報酬 %":       round(monthly_ret_pct, 2),
            "資產餘額 (萬)":  round(port_end / 10_000, 1),
            "月提領額":       round(monthly_income),
            "提領率 %":       round(wr, 2),
            "事件":           _trigger_label,
        })

    return {
        "monthly":              monthly_records,
        "rebalances":           rebalance_records,
        "final_portfolio":      sum(asset_values.values()),
        "final_monthly_income": monthly_income,
        "asset_values":         dict(asset_values),
        "data_warnings":        _data_warnings,
    }
