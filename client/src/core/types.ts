/**
 * 全域型別定義
 */

export interface PricePoint {
  date: string;
  close: number;
}

export interface DividendRecord {
  date: string;
  year: number;
  stock_id: string;
  cash_dividend: number;
  before_price: number;
  after_price: number;
  yield_pct: number;
}

export interface StockInfo {
  stock_id: string;
  stock_name: string;
  industry_category?: string;
}

export interface RiskMetrics {
  cagr_pct: number;
  vol_pct: number;
  mdd_pct: number;
  mdd_peak_date: string | null;
  mdd_trough_date: string | null;
  mdd_recovery_date: string | null;
  sharpe: number;
  sortino: number;
  calmar: number;
}

export interface TaxFeeConfig {
  enabled: boolean;
  income_tax_bracket: number; // 綜合所得稅率: 0.05, 0.12, 0.20, 0.30, 0.40
  buy_fee_rate: number;
  sell_fee_rate: number;
}

export interface LumpSumResult {
  total_return_pct: number;
  cagr_pct: number;
  years: number;
  inception_date: string;
  last_date: string;
  p0: number;
  p_last: number;
}

export interface DCAYearRecord {
  year: number;
  cost_cum: number;
  value: number;
  gain: number;
  return_pct: number;
}

export interface DCAResult {
  monthly_dca: number;
  years: DCAYearRecord[];
  final: DCAYearRecord;
}

export interface ComparisonResult {
  lump: LumpSumResult;
  dca: DCAResult;
  lump_same_cost_final: number;
  lump_same_cost_ret: number;
  lump_same_cost_cagr: number;
  dca_cagr_pct: number;
}

export interface ETFCompareRecord {
  stock_id: string;
  name: string;
  inception_date: string;
  common_start: string;
  years: number;
  total_return_pct: number;
  cagr_pct: number;
  dca_final: number;
  dca_cagr_pct: number;
  normalized: PricePoint[];
}

// 退休提領模擬型別
export interface GKYearRecord {
  year: number;
  portfolio_start: number;
  growth: number;
  withdrawal: number;
  portfolio_end: number;
  withdrawal_rate: number; // %
  monthly_income: number;
  trigger: "" | "capital_preservation" | "prosperity";
}

export interface GKResult {
  records: GKYearRecord[];
  depleted_year: number | null; // null = 撐過全期
  final_portfolio: number;
  initial_monthly: number;
}

export interface MonteCarloPercentiles {
  p10: number[];
  p25: number[];
  p50: number[];
  p75: number[];
  p90: number[];
}

export interface MonteCarloResult {
  years: number[];
  port_pct: MonteCarloPercentiles;
  wd_pct: MonteCarloPercentiles;
  survival_rate: number[];
  survival_final: number;
  depleted_pct: number;
  n_sims: number;
  initial_monthly: number;
  rep_paths: {
    [percentile: number]: {
      年度: number;
      "年化報酬 %": string;
      "年末資產 (萬)": string;
      月提領額: string;
      "提領率 %": string;
      護欄觸發: string;
    }[];
  };
}

export interface RebalanceRecord {
  year: number;
  month: string;
  portfolio: number;
  drift_alloc: Record<string, number>;
  target_alloc: Record<string, number>;
  trades: Record<string, number>;
  gk_trigger: string;
  monthly_income: number;
}

export interface MonthlyTrackingRecord {
  月份: string;
  "月報酬 %": number;
  "資產餘額 (萬)": number;
  月提領額: number;
  "提領率 %": number;
  事件: string;
}

export interface HistoricalTrackingResult {
  monthly: MonthlyTrackingRecord[];
  rebalances: RebalanceRecord[];
  final_portfolio: number;
  final_monthly_income: number;
  asset_values: Record<string, number>;
  data_warnings: string[];
}

export interface StressScenario {
  name: string;
  start_ym: string;
  desc: string;
}

export interface StressScenarioResult {
  scenario: StressScenario;
  result: HistoricalTrackingResult;
  proxied: string[];
}
