"""純計算邏輯(無 UI / IO 邊界)的公開 API。

Sub-modules:
    data        — FinMind + 快取 + 還原股價
    performance — 單筆 / DCA / 比較 / 目標試算
    metrics     — CAGR / MDD / Sharpe / Sortino / Calmar / 相關性
    simulation  — Guyton-Klinger(確定性 / Monte Carlo / 歷史月頻)
    tax         — 稅費模型
"""

from tw_etf_analyzer.core.data import (
    _finmind_get, _cache_path, _div_cache_path, _is_fresh,
    clear_cache, fetch_adjusted_close, fetch_stock_name, fetch_dividend_history,
)
from tw_etf_analyzer.core.performance import (
    LumpSumResult, DCAYearRecord, DCAResult, ComparisonResult, ETFCompareRecord,
    calc_lump_sum, calc_dca, calc_comparison, calc_multi_compare,
    calc_target_monthly, calc_target_assets_from_expense,
)
from tw_etf_analyzer.core.metrics import (
    RiskMetrics,
    calc_return_vol, calc_max_drawdown,
    calc_sharpe_ratio, calc_sortino_ratio,
    calc_risk_metrics, calc_correlation_matrix,
)
from tw_etf_analyzer.core.simulation import (
    GKYearRecord, GKResult,
    simulate_gk, simulate_gk_montecarlo, run_gk_historical,
)
from tw_etf_analyzer.core.tax import (
    TaxFeeConfig,
    effective_dividend_tax_rate, dividend_net_ratio,
    avg_annual_dividend_yield,
    calc_tax_drag, calc_fee_drag,
    apply_buy_fee, apply_sell_fee,
)

__all__ = [
    # data
    "clear_cache", "fetch_adjusted_close", "fetch_stock_name", "fetch_dividend_history",
    # performance
    "LumpSumResult", "DCAYearRecord", "DCAResult", "ComparisonResult", "ETFCompareRecord",
    "calc_lump_sum", "calc_dca", "calc_comparison", "calc_multi_compare",
    "calc_target_monthly", "calc_target_assets_from_expense",
    # metrics
    "RiskMetrics",
    "calc_return_vol", "calc_max_drawdown",
    "calc_sharpe_ratio", "calc_sortino_ratio",
    "calc_risk_metrics", "calc_correlation_matrix",
    # simulation
    "GKYearRecord", "GKResult",
    "simulate_gk", "simulate_gk_montecarlo", "run_gk_historical",
    # tax
    "TaxFeeConfig",
    "effective_dividend_tax_rate", "dividend_net_ratio",
    "avg_annual_dividend_yield",
    "calc_tax_drag", "calc_fee_drag",
    "apply_buy_fee", "apply_sell_fee",
]
