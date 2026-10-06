/**
 * 風險調整報酬指標: CAGR、波動度、最大回撤 (MDD)、Sharpe、Sortino、Calmar 與相關係數矩陣
 * 1:1 精確對齊 tw_etf_analyzer/core/metrics.py
 */

import { PricePoint, RiskMetrics } from "./types";

/**
 * 輔助: 計算陣列標準差 (樣本標準差，N-1 自由度)
 */
function sampleStdDev(values: number[]): number {
  if (values.length < 2) return 0;
  const mean = values.reduce((sum, v) => sum + v, 0) / values.length;
  const variance =
    values.reduce((sum, v) => sum + (v - mean) ** 2, 0) / (values.length - 1);
  return Math.sqrt(variance);
}

/**
 * 從日收盤價計算年化報酬 (CAGR) 與年化波動度 (日 log return std × √252)
 * 回傳 [cagr, annualVol]，均為小數 (非百分比)
 */
export function calcReturnVol(series: PricePoint[]): [number, number] {
  const clean = series.filter((p) => p.close > 0);
  if (clean.length < 2) return [0.0, 0.0];

  const t0 = new Date(clean[0].date).getTime();
  const tEnd = new Date(clean[clean.length - 1].date).getTime();
  const years = (tEnd - t0) / (1000 * 60 * 60 * 24 * 365.25);
  if (years <= 0) return [0.0, 0.0];

  const p0 = clean[0].close;
  const pLast = clean[clean.length - 1].close;
  const cagr = Math.pow(pLast / p0, 1 / years) - 1;

  // 日對數報酬 log return
  const logReturns: number[] = [];
  for (let i = 1; i < clean.length; i++) {
    const ratio = clean[i].close / clean[i - 1].close;
    if (ratio > 0) {
      logReturns.push(Math.log(ratio));
    }
  }

  const vol = sampleStdDev(logReturns) * Math.sqrt(252);
  return [cagr, vol];
}

/**
 * 計算最大回撤 (MDD)，回傳 { mdd, peak, trough, recovery }
 * mdd 為負值 (小數)；若尚未回復到新高，recovery 為 null
 */
export function calcMaxDrawdown(series: PricePoint[]): {
  mdd: number;
  peak: string | null;
  trough: string | null;
  recovery: string | null;
} {
  const clean = series.filter((p) => p.close > 0);
  if (clean.length < 2) {
    return { mdd: 0.0, peak: null, trough: null, recovery: null };
  }

  let runningMax = -Infinity;
  let runningMaxIdx = 0;
  let mddVal = 0.0;
  let peakIdx = 0;
  let troughIdx = 0;

  for (let i = 0; i < clean.length; i++) {
    const price = clean[i].close;
    if (price > runningMax) {
      runningMax = price;
      runningMaxIdx = i;
    }
    const dd = price / runningMax - 1.0;
    if (dd < mddVal) {
      mddVal = dd;
      troughIdx = i;
      peakIdx = runningMaxIdx;
    }
  }

  if (mddVal === 0.0) {
    return { mdd: 0.0, peak: null, trough: null, recovery: null };
  }

  const peakVal = clean[peakIdx].close;
  let recoveryDate: string | null = null;
  for (let i = troughIdx; i < clean.length; i++) {
    if (clean[i].close >= peakVal) {
      recoveryDate = clean[i].date;
      break;
    }
  }

  return {
    mdd: mddVal,
    peak: clean[peakIdx].date,
    trough: clean[troughIdx].date,
    recovery: recoveryDate,
  };
}

/**
 * 年化 Sharpe = (CAGR - Rf) / 年化波動度
 */
export function calcSharpeRatio(
  series: PricePoint[],
  riskFreeRate: number = 0.0
): number {
  const [cagr, vol] = calcReturnVol(series);
  if (vol <= 0) return 0.0;
  return (cagr - riskFreeRate) / vol;
}

/**
 * 年化 Sortino = (CAGR - Rf) / 年化下行波動度
 * 下行波動度: 只計算日報酬 < target 的標準差 × √252
 */
export function calcSortinoRatio(
  series: PricePoint[],
  riskFreeRate: number = 0.0,
  target: number = 0.0
): number {
  const clean = series.filter((p) => p.close > 0);
  if (clean.length < 2) return 0.0;

  const [cagr] = calcReturnVol(clean);
  const dailyTarget = target > -1 ? Math.pow(1 + target, 1 / 252) - 1 : 0.0;

  const downsideDiffs: number[] = [];
  for (let i = 1; i < clean.length; i++) {
    const dailyRet = (clean[i].close - clean[i - 1].close) / clean[i - 1].close;
    if (dailyRet < dailyTarget) {
      downsideDiffs.push(dailyRet - dailyTarget);
    }
  }

  if (downsideDiffs.length < 2) return 0.0;
  const downsideVol = sampleStdDev(downsideDiffs) * Math.sqrt(252);
  if (downsideVol <= 0) return 0.0;

  return (cagr - riskFreeRate) / downsideVol;
}

/**
 * 一次計算所有風險調整報酬指標
 */
export function calcRiskMetrics(
  series: PricePoint[],
  riskFreeRate: number = 0.0
): RiskMetrics {
  const clean = series.filter((p) => p.close > 0);
  if (clean.length < 2) {
    return {
      cagr_pct: 0,
      vol_pct: 0,
      mdd_pct: 0,
      mdd_peak_date: null,
      mdd_trough_date: null,
      mdd_recovery_date: null,
      sharpe: 0,
      sortino: 0,
      calmar: 0,
    };
  }

  const [cagr, vol] = calcReturnVol(clean);
  const dd = calcMaxDrawdown(clean);
  const sharpe = calcSharpeRatio(clean, riskFreeRate);
  const sortino = calcSortinoRatio(clean, riskFreeRate);
  const mdd = dd.mdd;
  const calmar = mdd < 0 ? cagr / Math.abs(mdd) : 0.0;

  return {
    cagr_pct: Math.round(cagr * 10000) / 100,
    vol_pct: Math.round(vol * 10000) / 100,
    mdd_pct: Math.round(mdd * 10000) / 100,
    mdd_peak_date: dd.peak,
    mdd_trough_date: dd.trough,
    mdd_recovery_date: dd.recovery,
    sharpe: Math.round(sharpe * 100) / 100,
    sortino: Math.round(sortino * 100) / 100,
    calmar: Math.round(calmar * 100) / 100,
  };
}

/**
 * 計算多檔標的月報酬相關係數矩陣
 * 以月底最後一個收盤價對齊，取 pct_change 後計算 Pearson 相關係數
 */
export function calcCorrelationMatrix(
  closes: Record<string, PricePoint[]>
): { ids: string[]; matrix: number[][] } {
  const ids = Object.keys(closes);
  if (ids.length < 2) return { ids: [], matrix: [] };

  // 1. 取得每檔標的的月收盤價對應 (YYYY-MM -> last close)
  const monthlyLastMap: Record<string, Map<string, number>> = {};
  for (const id of ids) {
    const map = new Map<string, number>();
    const pts = closes[id].filter((p) => p.close > 0);
    for (const p of pts) {
      const ym = p.date.substring(0, 7);
      map.set(ym, p.close); // 遍歷到該月最後一筆即為月收盤
    }
    monthlyLastMap[id] = map;
  }

  // 2. 找出所有共同月份 (交集)
  const commonYMs: string[] = [];
  const firstIdMap = monthlyLastMap[ids[0]];
  for (const ym of firstIdMap.keys()) {
    if (ids.every((id) => monthlyLastMap[id].has(ym))) {
      commonYMs.push(ym);
    }
  }
  commonYMs.sort();

  if (commonYMs.length < 3) return { ids, matrix: [] };

  // 3. 計算各標的在共同月份的月報酬
  const monthlyReturns: Record<string, number[]> = {};
  for (const id of ids) {
    const rets: number[] = [];
    for (let i = 1; i < commonYMs.length; i++) {
      const prev = monthlyLastMap[id].get(commonYMs[i - 1])!;
      const curr = monthlyLastMap[id].get(commonYMs[i])!;
      rets.push(prev > 0 ? (curr - prev) / prev : 0);
    }
    monthlyReturns[id] = rets;
  }

  // 4. 計算 Pearson 相關係數
  const n = ids.length;
  const matrix: number[][] = Array.from({ length: n }, () => Array(n).fill(1));

  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      const x = monthlyReturns[ids[i]];
      const y = monthlyReturns[ids[j]];
      const meanX = x.reduce((s, v) => s + v, 0) / x.length;
      const meanY = y.reduce((s, v) => s + v, 0) / y.length;

      let num = 0;
      let denX = 0;
      let denY = 0;
      for (let k = 0; k < x.length; k++) {
        const dx = x[k] - meanX;
        const dy = y[k] - meanY;
        num += dx * dy;
        denX += dx * dx;
        denY += dy * dy;
      }
      const corr =
        denX > 0 && denY > 0 ? num / Math.sqrt(denX * denY) : 0;
      const rounded = Math.round(corr * 100) / 100;
      matrix[i][j] = rounded;
      matrix[j][i] = rounded;
    }
  }

  return { ids, matrix };
}
