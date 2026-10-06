# -*- coding: utf-8 -*-
"""風險調整報酬指標:CAGR、波動度、最大回撤、Sharpe、Sortino、Calmar、相關性矩陣。

所有函式吃 pandas Series(日收盤價)或 dict[str, Series](多檔比較)。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


def calc_return_vol(close: pd.Series) -> tuple[float, float]:
    """從日收盤價計算年化報酬(CAGR)與年化波動度(日 log return std × √252)。
    回傳 (cagr, annual_vol),均為小數(非百分比)。
    """
    close = close.replace(0, float("nan")).dropna()
    if len(close) < 2:
        return 0.0, 0.0
    years      = (close.index[-1] - close.index[0]).days / 365.25
    cagr       = float((close.iloc[-1] / close.iloc[0]) ** (1 / years) - 1)
    ratio      = (close / close.shift(1)).replace(0, float("nan")).dropna()
    log_ret    = np.log(ratio).dropna()
    annual_vol = float(log_ret.std() * np.sqrt(252))
    return cagr, annual_vol


@dataclass
class RiskMetrics:
    cagr_pct:          float       # 年化報酬 %
    vol_pct:           float       # 年化波動度 %
    mdd_pct:           float       # 最大回撤 %(負值)
    mdd_peak_date:     pd.Timestamp | None
    mdd_trough_date:   pd.Timestamp | None
    mdd_recovery_date: pd.Timestamp | None  # 若尚未回復則為 None
    sharpe:            float       # 年化 Sharpe Ratio
    sortino:           float       # 年化 Sortino Ratio
    calmar:            float       # CAGR / |MDD|


def calc_max_drawdown(close: pd.Series) -> dict:
    """計算最大回撤。回傳 {mdd, peak, trough, recovery}。

    mdd 為負值(小數);若尚未回復到新高,recovery 為 None。
    """
    close = close.replace(0, float("nan")).dropna()
    if len(close) < 2:
        return {"mdd": 0.0, "peak": None, "trough": None, "recovery": None}

    running_max = close.cummax()
    drawdown    = close / running_max - 1.0
    mdd_val     = float(drawdown.min())
    trough_idx  = drawdown.idxmin()
    prior = close.loc[:trough_idx]
    peak_idx = prior.idxmax()
    peak_val = float(close.loc[peak_idx])
    after = close.loc[trough_idx:]
    recovered = after[after >= peak_val]
    recovery_idx = recovered.index[0] if len(recovered) > 0 else None

    return {
        "mdd":      mdd_val,
        "peak":     peak_idx,
        "trough":   trough_idx,
        "recovery": recovery_idx,
    }


def calc_sharpe_ratio(close: pd.Series, risk_free_rate: float = 0.0) -> float:
    """年化 Sharpe = (CAGR - Rf) / 年化波動度。"""
    cagr, vol = calc_return_vol(close)
    if vol <= 0:
        return 0.0
    return (cagr - risk_free_rate) / vol


def calc_sortino_ratio(close: pd.Series, risk_free_rate: float = 0.0, target: float = 0.0) -> float:
    """年化 Sortino = (CAGR - Rf) / 年化下行波動度。

    下行波動度:只計算報酬 < target 的日報酬標準差。
    """
    close = close.replace(0, float("nan")).dropna()
    if len(close) < 2:
        return 0.0
    cagr, _ = calc_return_vol(close)
    daily_ret = close.pct_change().dropna()
    daily_target = (1 + target) ** (1 / 252) - 1 if target > -1 else 0.0
    downside = daily_ret[daily_ret < daily_target] - daily_target
    if len(downside) < 2:
        return 0.0
    downside_vol = float(downside.std() * np.sqrt(252))
    if downside_vol <= 0:
        return 0.0
    return (cagr - risk_free_rate) / downside_vol


def calc_risk_metrics(close: pd.Series, risk_free_rate: float = 0.0) -> RiskMetrics:
    """一次計算所有風險調整報酬指標。"""
    close = close.replace(0, float("nan")).dropna()
    if len(close) < 2:
        return RiskMetrics(0, 0, 0, None, None, None, 0, 0, 0)
    cagr, vol = calc_return_vol(close)
    dd = calc_max_drawdown(close)
    sharpe = calc_sharpe_ratio(close, risk_free_rate)
    sortino = calc_sortino_ratio(close, risk_free_rate)
    mdd = dd["mdd"]
    calmar = cagr / abs(mdd) if mdd < 0 else 0.0
    return RiskMetrics(
        cagr_pct          = cagr * 100,
        vol_pct           = vol * 100,
        mdd_pct           = mdd * 100,
        mdd_peak_date     = dd["peak"],
        mdd_trough_date   = dd["trough"],
        mdd_recovery_date = dd["recovery"],
        sharpe            = sharpe,
        sortino           = sortino,
        calmar            = calmar,
    )


def calc_correlation_matrix(closes: dict[str, pd.Series]) -> pd.DataFrame:
    """計算多檔標的月報酬相關係數矩陣。

    - 以月底收盤對齊,取 pct_change
    - 以共同可觀察期間計算(inner join)
    回傳 DataFrame(index=代號, columns=代號)。
    """
    if len(closes) < 2:
        return pd.DataFrame()
    monthly_rets = {}
    for sid, close in closes.items():
        clean = close.replace(0, float("nan")).dropna()
        m = clean.resample("ME").last().dropna()
        monthly_rets[sid] = m.pct_change().dropna()
    df = pd.DataFrame(monthly_rets).dropna()
    if df.empty:
        return pd.DataFrame()
    return df.corr()
