/**
 * 績效計算: 單筆投資 vs 定期定額 (DCA)、多檔比較、目標試算 (正推與反推)
 * 1:1 精確對齊 tw_etf_analyzer/core/performance.py
 */

import {
  ComparisonResult,
  DCAResult,
  DCAYearRecord,
  ETFCompareRecord,
  LumpSumResult,
  PricePoint,
} from "./types";

/**
 * 年化報酬 % 安全版；零或負值回傳 0.0
 */
export function safeCagr(
  endVal: number,
  startVal: number,
  years: number
): number {
  if (startVal <= 0 || years <= 0 || endVal < 0) {
    return 0.0;
  }
  return (Math.pow(endVal / startVal, 1.0 / years) - 1.0) * 100;
}

/**
 * 反推: 要在 N 年後達到目標金額，每月需定期定額投入多少？
 * existing: 目前已持有的本金市值，會以相同報酬率複利成長，從目標中扣除
 */
export function calcTargetMonthly(
  target: number,
  years: number,
  annualCagrPct: number,
  existing: number = 0.0
): {
  monthly: number;
  lump_sum_today: number;
  total_invested: number;
  existing_fv: number;
  remaining: number;
  total_gain: number;
  terminal_value: number;
} {
  const rA = annualCagrPct / 100;
  const rM = Math.pow(1 + rA, 1 / 12) - 1;
  const n = years * 12;

  const existingFv = rA > -1 ? existing * Math.pow(1 + rA, years) : existing;
  const remaining = Math.max(target - existingFv, 0.0);

  let monthly = 0.0;
  if (remaining === 0) {
    monthly = 0.0;
  } else if (rM > 0) {
    monthly = (remaining * rM) / (Math.pow(1 + rM, n) - 1);
  } else {
    monthly = n > 0 ? remaining / n : 0.0;
  }

  const totalInvested = monthly * n;
  const lumpSum = Math.max(target / Math.pow(1 + rA, years) - existing, 0.0);
  const terminalValue = existingFv + remaining;

  return {
    monthly: Math.round(monthly),
    lump_sum_today: Math.round(lumpSum),
    total_invested: Math.round(totalInvested),
    existing_fv: Math.round(existingFv),
    remaining: Math.round(remaining),
    total_gain: Math.round(target - existing - totalInvested),
    terminal_value: Math.round(terminalValue),
  };
}

/**
 * 給定預期每月支出與安全提領率 (SWR)，回傳退休起始所需目標資產
 * formula: assets = (monthly_expense * 12) / SWR
 */
export function calcTargetAssetsFromExpense(
  monthlyExpense: number,
  safeWithdrawalRate: number
): number {
  if (safeWithdrawalRate <= 0) return 0.0;
  return (monthlyExpense * 12) / safeWithdrawalRate;
}

/**
 * 計算單筆買進持有 (Lump-Sum) 績效
 */
export function calcLumpSum(series: PricePoint[]): LumpSumResult {
  const clean = series.filter((p) => p.close > 0);
  if (clean.length < 2) {
    return {
      total_return_pct: 0,
      cagr_pct: 0,
      years: 0,
      inception_date: "",
      last_date: "",
      p0: 0,
      p_last: 0,
    };
  }

  const p0 = clean[0].close;
  const pLast = clean[clean.length - 1].close;
  const t0 = new Date(clean[0].date).getTime();
  const tEnd = new Date(clean[clean.length - 1].date).getTime();
  const years = (tEnd - t0) / (1000 * 60 * 60 * 24 * 365.25);

  return {
    total_return_pct: p0 > 0 ? ((pLast - p0) / p0) * 100 : 0.0,
    cagr_pct: safeCagr(pLast, p0, years),
    years,
    inception_date: clean[0].date,
    last_date: clean[clean.length - 1].date,
    p0,
    p_last: pLast,
  };
}

/**
 * 計算定期定額 (DCA) 逐年成果
 * 每月第一個交易日買入 monthlyDca 金額
 */
export function calcDCA(
  series: PricePoint[],
  monthlyDca: number
): DCAResult {
  const clean = series.filter((p) => p.close > 0);
  if (clean.length < 2) {
    const emptyRecord: DCAYearRecord = {
      year: 0,
      cost_cum: 0,
      value: 0,
      gain: 0,
      return_pct: 0,
    };
    return { monthly_dca: monthlyDca, years: [], final: emptyRecord };
  }

  // 1. 找出每個月的第一個交易日 (每月月初買進)
  const monthlyFirstList: { date: string; year: number; price: number }[] = [];
  const seenYm = new Set<string>();

  for (const p of clean) {
    const ym = p.date.substring(0, 7);
    if (!seenYm.has(ym)) {
      seenYm.add(ym);
      monthlyFirstList.push({
        date: p.date,
        year: parseInt(p.date.substring(0, 4), 10),
        price: p.close,
      });
    }
  }

  // 2. 依照年份抓出當年最後一個交易日收盤價
  const yearEndPriceMap: Record<number, number> = {};
  for (const p of clean) {
    const yr = parseInt(p.date.substring(0, 4), 10);
    yearEndPriceMap[yr] = p.close;
  }

  let unitsTotal = 0.0;
  let costTotal = 0.0;
  const yearRecords: DCAYearRecord[] = [];

  for (let i = 0; i < monthlyFirstList.length; i++) {
    const item = monthlyFirstList[i];
    if (item.price > 0) {
      unitsTotal += monthlyDca / item.price;
      costTotal += monthlyDca;
    }

    const isLast = i === monthlyFirstList.length - 1;
    const nextYr = isLast ? null : monthlyFirstList[i + 1].year;
    const yearEnds = isLast || nextYr !== item.year;

    if (yearEnds) {
      const endPrice = yearEndPriceMap[item.year] || item.price;
      const endValue = unitsTotal * endPrice;
      yearRecords.push({
        year: item.year,
        cost_cum: Math.round(costTotal),
        value: Math.round(endValue),
        gain: Math.round(endValue - costTotal),
        return_pct:
          costTotal > 0
            ? Math.round(((endValue - costTotal) / costTotal) * 10000) / 100
            : 0,
      });
    }
  }

  const finalRecord =
    yearRecords.length > 0
      ? yearRecords[yearRecords.length - 1]
      : { year: 0, cost_cum: 0, value: 0, gain: 0, return_pct: 0 };

  return {
    monthly_dca: monthlyDca,
    years: yearRecords,
    final: finalRecord,
  };
}

/**
 * 比較單筆 vs 定期定額 (相同累計本金對比)
 */
export function calcComparison(
  series: PricePoint[],
  monthlyDca: number
): ComparisonResult {
  const lump = calcLumpSum(series);
  const dca = calcDCA(series, monthlyDca);
  const f = dca.final;

  const lumpSameCostFinal =
    lump.p0 > 0 ? (f.cost_cum / lump.p0) * lump.p_last : 0.0;
  const lumpSameCostRet =
    f.cost_cum > 0 ? ((lumpSameCostFinal - f.cost_cum) / f.cost_cum) * 100 : 0.0;
  const lumpSameCostCagr = safeCagr(lumpSameCostFinal, f.cost_cum, lump.years);
  const dcaCagr = safeCagr(f.value, f.cost_cum, lump.years);

  return {
    lump,
    dca,
    lump_same_cost_final: Math.round(lumpSameCostFinal),
    lump_same_cost_ret: Math.round(lumpSameCostRet * 100) / 100,
    lump_same_cost_cagr: Math.round(lumpSameCostCagr * 100) / 100,
    dca_cagr_pct: Math.round(dcaCagr * 100) / 100,
  };
}

/**
 * 多檔標的比較 (自動對齊共同上市期間)
 */
export function calcMultiCompare(
  closes: Record<string, PricePoint[]>,
  names: Record<string, string>,
  monthlyDca: number
): ETFCompareRecord[] {
  const ids = Object.keys(closes);
  if (ids.length === 0) return [];

  // 1. 找出各標的最晚起始日 (共同起點)
  let commonStart = "";
  for (const id of ids) {
    const list = closes[id];
    if (list.length > 0) {
      const s0 = list[0].date;
      if (!commonStart || s0 > commonStart) {
        commonStart = s0;
      }
    }
  }

  const records: ETFCompareRecord[] = [];

  for (const id of ids) {
    const raw = closes[id];
    const sliced = raw.filter((p) => p.date >= commonStart && p.close > 0);
    if (sliced.length < 2) continue;

    const p0 = sliced[0].close;
    const pLast = sliced[sliced.length - 1].close;
    const t0 = new Date(sliced[0].date).getTime();
    const tEnd = new Date(sliced[sliced.length - 1].date).getTime();
    const years = (tEnd - t0) / (1000 * 60 * 60 * 24 * 365.25);

    const totalRet = p0 > 0 ? ((pLast - p0) / p0) * 100 : 0;
    const cagr = safeCagr(pLast, p0, years);

    const dca = calcDCA(sliced, monthlyDca);
    const f = dca.final;
    const dcaCagr = safeCagr(f.value, f.cost_cum, years);

    // 基期標準化 (以 commonStart = 100)
    const normalized: PricePoint[] = sliced.map((p) => ({
      date: p.date,
      close: Math.round((p.close / p0) * 10000) / 100,
    }));

    records.push({
      stock_id: id,
      name: names[id] || id,
      inception_date: raw[0]?.date || "",
      common_start: commonStart,
      years: Math.round(years * 10) / 10,
      total_return_pct: Math.round(totalRet * 100) / 100,
      cagr_pct: Math.round(cagr * 100) / 100,
      dca_final: Math.round(f.value),
      dca_cagr_pct: Math.round(dcaCagr * 100) / 100,
      normalized,
    });
  }

  // 依 CAGR 降冪排序
  return records.sort((a, b) => b.cagr_pct - a.cagr_pct);
}
