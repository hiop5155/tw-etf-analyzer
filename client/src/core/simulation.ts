/**
 * 退休提領模擬: Guyton-Klinger 動態提領 + 蒙地卡羅 (Normal / Student-t / Bootstrap) + 歷史月頻追蹤
 * 1:1 精確對齊 tw_etf_analyzer/core/simulation.py
 */

import { CASH_RETURN } from "./constants";
import {
  GKResult,
  GKYearRecord,
  HistoricalTrackingResult,
  MonteCarloPercentiles,
  MonteCarloResult,
  PricePoint,
  RebalanceRecord,
} from "./types";

/**
 * 簡單偽隨機數產生器 (LCG/Mulberry32)，支援固定 seed 重現性
 */
function createRng(seed: number = 42) {
  let s = seed >>> 0;
  return function next() {
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * Box-Muller 變換產生標準常態隨機變數 N(0, 1)
 */
function boxMuller(rng: () => number): number {
  let u = 0;
  let v = 0;
  while (u === 0) u = rng();
  while (v === 0) v = rng();
  return Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
}

/**
 * 單次確定性 Guyton-Klinger 動態提領模擬
 */
export function simulateGK(
  initialPortfolio: number,
  initialRate: number = 0.05,
  guardrailPct: number = 0.2,
  annualReturn: number = 0.06,
  inflationRate: number = 0.02,
  years: number = 30
): GKResult {
  let portfolio = initialPortfolio;
  let withdrawal = initialPortfolio * initialRate;
  const upperGuard = initialRate * (1 + guardrailPct);
  const lowerGuard = initialRate * (1 - guardrailPct);

  const records: GKYearRecord[] = [];
  let depletedYear: number | null = null;
  let prevEnd = initialPortfolio;

  for (let yr = 1; yr <= years; yr++) {
    if (portfolio <= 0) break;

    const growth = portfolio * annualReturn;
    const portfolioGrown = portfolio + growth;

    // 通膨調整提領額，但若上年資產下滑則跳過 (Capital Preservation Bypass)
    if (portfolioGrown >= prevEnd) {
      withdrawal *= 1 + inflationRate;
    }

    let currentRate =
      portfolioGrown > 0 ? withdrawal / portfolioGrown : Infinity;
    let trigger: "" | "capital_preservation" | "prosperity" = "";

    // 資本保護規則: 提領率衝破上限，提領額調降 10%
    if (currentRate > upperGuard) {
      withdrawal *= 0.9;
      trigger = "capital_preservation";
      currentRate = withdrawal / portfolioGrown;
    }
    // 繁榮規則: 提領率跌破下限，提領額調升 10%
    else if (currentRate < lowerGuard) {
      withdrawal *= 1.1;
      trigger = "prosperity";
      currentRate = withdrawal / portfolioGrown;
    }

    const portfolioEnd = portfolioGrown - withdrawal;

    records.push({
      year: yr,
      portfolio_start: Math.round(portfolio),
      growth: Math.round(growth),
      withdrawal: Math.round(withdrawal),
      portfolio_end: Math.max(0, Math.round(portfolioEnd)),
      withdrawal_rate: Math.round(currentRate * 10000) / 100,
      monthly_income: Math.round(withdrawal / 12),
      trigger,
    });

    prevEnd = portfolioGrown;
    portfolio = Math.max(0, portfolioEnd);

    if (portfolioEnd <= 0) {
      depletedYear = yr;
      break;
    }
  }

  return {
    records,
    depleted_year: depletedYear,
    final_portfolio: Math.round(portfolio),
    initial_monthly: Math.round((initialPortfolio * initialRate) / 12),
  };
}

/**
 * 輔助: 計算陣列的特定百分位數 (0 ~ 100)
 */
function getPercentile(sortedArr: number[], p: number): number {
  if (sortedArr.length === 0) return 0;
  const index = (p / 100) * (sortedArr.length - 1);
  const lower = Math.floor(index);
  const upper = Math.ceil(index);
  const weight = index - lower;
  return sortedArr[lower] * (1 - weight) + sortedArr[upper] * weight;
}

/**
 * 蒙地卡羅 Guyton-Klinger 動態提領模擬 (純前端毫秒級 1,000 次運算)
 */
export function simulateGKMonteCarlo(
  initialPortfolio: number,
  initialRate: number,
  guardrailPct: number,
  annualReturn: number, // 小數
  annualVolatility: number, // 小數
  inflationRate: number,
  years: number,
  nSims: number = 1000,
  seed: number = 42,
  distKind: "normal" | "bootstrap" = "normal",
  histMonthlyReturns: number[] | null = null
): MonteCarloResult {
  const rng = createRng(seed);

  // 1. 生成回報矩陣 (nSims x years)
  const retMat: number[][] = Array.from({ length: nSims }, () =>
    new Array(years).fill(0)
  );

  if (
    distKind === "bootstrap" &&
    histMonthlyReturns &&
    histMonthlyReturns.length >= 12
  ) {
    const pool = histMonthlyReturns.filter((r) => !isNaN(r) && isFinite(r));
    for (let s = 0; s < nSims; s++) {
      for (let y = 0; y < years; y++) {
        let compound = 1.0;
        for (let m = 0; m < 12; m++) {
          const randIdx = Math.floor(rng() * pool.length);
          compound *= 1.0 + pool[randIdx];
        }
        retMat[s][y] = Math.max(-0.99, compound - 1.0);
      }
    }
  } else {
    for (let s = 0; s < nSims; s++) {
      for (let y = 0; y < years; y++) {
        const z = boxMuller(rng);
        const r = annualReturn + z * annualVolatility;
        retMat[s][y] = Math.max(-0.99, r);
      }
    }
  }

  // 2. 模擬每條路徑的提領與資產變動
  const portMat: number[][] = Array.from({ length: nSims }, () =>
    new Array(years).fill(0)
  );
  const wdMat: number[][] = Array.from({ length: nSims }, () =>
    new Array(years).fill(0)
  );

  const upper = initialRate * (1 + guardrailPct);
  const lower = initialRate * (1 - guardrailPct);

  for (let s = 0; s < nSims; s++) {
    let portfolio = initialPortfolio;
    let withdrawal = initialPortfolio * initialRate;
    let prevEnd = initialPortfolio;

    for (let y = 0; y < years; y++) {
      if (portfolio <= 0) {
        portMat[s][y] = 0;
        wdMat[s][y] = 0;
        continue;
      }

      const r = retMat[s][y];
      const portfolioGrown = portfolio * (1 + r);

      if (portfolioGrown >= prevEnd) {
        withdrawal *= 1 + inflationRate;
      }

      let curRate =
        portfolioGrown > 0 ? withdrawal / portfolioGrown : Infinity;

      if (curRate > upper) {
        withdrawal *= 0.9;
      } else if (curRate < lower) {
        withdrawal *= 1.1;
      }

      const portfolioEnd = portfolioGrown - withdrawal;
      prevEnd = portfolioGrown;
      portfolio = Math.max(0, portfolioEnd);

      portMat[s][y] = portfolio;
      wdMat[s][y] = withdrawal / 12;
    }
  }

  // 3. 計算各年度存活率與分位數
  const yearsArr = Array.from({ length: years }, (_, i) => i + 1);
  const survivalRate: number[] = [];

  const portPct: MonteCarloPercentiles = {
    p10: [],
    p25: [],
    p50: [],
    p75: [],
    p90: [],
  };
  const wdPct: MonteCarloPercentiles = {
    p10: [],
    p25: [],
    p50: [],
    p75: [],
    p90: [],
  };

  for (let y = 0; y < years; y++) {
    const colPort: number[] = [];
    const colWd: number[] = [];
    let survivedCount = 0;

    for (let s = 0; s < nSims; s++) {
      colPort.push(portMat[s][y]);
      colWd.push(wdMat[s][y]);
      if (portMat[s][y] > 0) survivedCount++;
    }

    survivalRate.push(
      Math.round((survivedCount / nSims) * 1000) / 10
    );

    colPort.sort((a, b) => a - b);
    colWd.sort((a, b) => a - b);

    portPct.p10.push(Math.round(getPercentile(colPort, 10)));
    portPct.p25.push(Math.round(getPercentile(colPort, 25)));
    portPct.p50.push(Math.round(getPercentile(colPort, 50)));
    portPct.p75.push(Math.round(getPercentile(colPort, 75)));
    portPct.p90.push(Math.round(getPercentile(colPort, 90)));

    wdPct.p10.push(Math.round(getPercentile(colWd, 10)));
    wdPct.p25.push(Math.round(getPercentile(colWd, 25)));
    wdPct.p50.push(Math.round(getPercentile(colWd, 50)));
    wdPct.p75.push(Math.round(getPercentile(colWd, 75)));
    wdPct.p90.push(Math.round(getPercentile(colWd, 90)));
  }

  // 4. 代表性歷程 (1%, 10%, 50%, 90%)
  const simFinalVals = portMat.map((p, idx) => ({ idx, val: p[years - 1] }));
  simFinalVals.sort((a, b) => a.val - b.val);

  function gkTrace(returnSeq: number[]) {
    const records = [];
    let p = initialPortfolio;
    let w = initialPortfolio * initialRate;
    let pe = initialPortfolio;

    for (let y = 0; y < returnSeq.length; y++) {
      if (p <= 0) {
        records.push({
          年度: y + 1,
          "年化報酬 %": `${(returnSeq[y] * 100).toFixed(1)}%`,
          "年末資產 (萬)": "0",
          月提領額: "0",
          "提領率 %": "—",
          護欄觸發: "💀 資產耗盡",
        });
        continue;
      }

      const r = returnSeq[y];
      const grown = p * (1 + r);
      if (grown >= pe) {
        w *= 1 + inflationRate;
      }
      let cr = grown > 0 ? w / grown : Infinity;
      let tr = "—";
      if (cr > upper) {
        w *= 0.9;
        tr = "↓ 減10%";
        cr = w / grown;
      } else if (cr < lower) {
        w *= 1.1;
        tr = "↑ 加10%";
        cr = w / grown;
      }

      const pend = grown - w;
      pe = grown;
      p = Math.max(0, pend);

      records.push({
        年度: y + 1,
        "年化報酬 %": `${(r * 100).toFixed(1)}%`,
        "年末資產 (萬)": (p / 10000).toLocaleString(undefined, {
          maximumFractionDigits: 0,
        }),
        月提領額: Math.round(w / 12).toLocaleString(),
        "提領率 %": `${(cr * 100).toFixed(2)}%`,
        護欄觸發: tr,
      });
    }
    return records;
  }

  const repPaths: Record<number, any[]> = {};
  for (const pct of [1, 10, 50, 90]) {
    const targetIdx = Math.floor((nSims * pct) / 100);
    const simIdx = simFinalVals[Math.min(targetIdx, nSims - 1)].idx;
    repPaths[pct] = gkTrace(retMat[simIdx]);
  }

  const finalSurv = survivalRate[years - 1] || 0;

  return {
    years: yearsArr,
    port_pct: portPct,
    wd_pct: wdPct,
    survival_rate: survivalRate,
    survival_final: finalSurv,
    depleted_pct: Math.round((100 - finalSurv) * 10) / 10,
    n_sims: nSims,
    initial_monthly: Math.round((initialPortfolio * initialRate) / 12),
    rep_paths: repPaths,
  };
}

/**
 * 以真實歷史月報酬逐月執行 GK 提領策略 (含每年一月再平衡)
 */
export function runGKHistorical(
  initialPortfolio: number,
  allocations: Record<string, number>, // { "0050": 0.6, "0056": 0.4 }
  startYm: string, // "YYYY-MM"
  initialRate: number,
  guardrailPct: number,
  inflationRate: number,
  closeSeries: Record<string, PricePoint[]>
): HistoricalTrackingResult {
  const assets = Object.keys(allocations);
  const dataWarnings: string[] = [];

  // 1. 建立各資產月報酬對照 (YYYY-MM -> return)
  const monthlyRetMap: Record<string, Record<string, number>> = {};
  for (const asset of assets) {
    if (asset === "現金" || asset === "CASH") continue;
    const series = closeSeries[asset] || [];
    const map: Record<string, number> = {};
    if (series.length < 2) {
      dataWarnings.push(`${asset}: 歷史資料不足，無法計算月報酬，將以 0% 計算。`);
      monthlyRetMap[asset] = map;
      continue;
    }

    // 取得每月收盤價
    const ymCloseMap = new Map<string, number>();
    for (const p of series) {
      if (p.close > 0) {
        ymCloseMap.set(p.date.substring(0, 7), p.close);
      }
    }

    const yms = Array.from(ymCloseMap.keys()).sort();
    for (let i = 1; i < yms.length; i++) {
      const prev = ymCloseMap.get(yms[i - 1])!;
      const curr = ymCloseMap.get(yms[i])!;
      map[yms[i]] = prev > 0 ? (curr - prev) / prev : 0;
    }
    monthlyRetMap[asset] = map;
  }

  // 2. 生成月份時間軸 (startYm 至最新月份)
  // 找出所有資產的最新月份
  let latestYm = "2026-03";
  for (const asset of assets) {
    const series = closeSeries[asset];
    if (series && series.length > 0) {
      const lastDate = series[series.length - 1].date.substring(0, 7);
      if (lastDate > latestYm) latestYm = lastDate;
    }
  }

  const months: string[] = [];
  let cur = new Date(`${startYm}-01T00:00:00`);
  const end = new Date(`${latestYm}-01T00:00:00`);

  while (cur <= end) {
    const ym = cur.toISOString().substring(0, 7);
    months.push(ym);
    cur.setMonth(cur.getMonth() + 1);
  }

  const cashMonthly = Math.pow(1 + CASH_RETURN, 1 / 12) - 1;
  const upperRate = initialRate * (1 + guardrailPct);
  const lowerRate = initialRate * (1 - guardrailPct);

  const assetValues: Record<string, number> = {};
  for (const a of assets) {
    assetValues[a] = initialPortfolio * allocations[a];
  }

  let annualWithdrawal = initialPortfolio * initialRate;
  let monthlyIncome = annualWithdrawal / 12;
  let prevJanPort = initialPortfolio;

  const monthlyRecords: any[] = [];
  const rebalanceRecords: RebalanceRecord[] = [];

  for (let i = 0; i < months.length; i++) {
    const ym = months[i];
    const isJan = ym.endsWith("-01") && i > 0;
    let gkTrigger = "";

    const portfolioNow = Object.values(assetValues).reduce((s, v) => s + v, 0);

    // 一月: 通膨調整 (在護欄檢查之前)
    if (isJan && portfolioNow > 0) {
      if (portfolioNow >= prevJanPort) {
        annualWithdrawal *= 1 + inflationRate;
      }
      monthlyIncome = annualWithdrawal / 12;
      prevJanPort = portfolioNow;
    }

    // 每月: 護欄檢查
    if (portfolioNow > 0) {
      const curRate = annualWithdrawal / portfolioNow;
      if (curRate > upperRate) {
        annualWithdrawal *= 0.9;
        gkTrigger = "capital_preservation";
        monthlyIncome = annualWithdrawal / 12;
      } else if (curRate < lowerRate && portfolioNow >= prevJanPort) {
        annualWithdrawal *= 1.1;
        gkTrigger = "prosperity";
        monthlyIncome = annualWithdrawal / 12;
      }
    }

    // 一月: 再平衡 (護欄調整後)
    if (isJan && portfolioNow > 0) {
      const driftAlloc: Record<string, number> = {};
      const trades: Record<string, number> = {};
      for (const a of assets) {
        const drift = assetValues[a] / portfolioNow;
        driftAlloc[a] = Math.round(drift * 1000) / 1000;
        trades[a] = Math.round(
          (allocations[a] - drift) * portfolioNow
        );
        assetValues[a] = portfolioNow * allocations[a];
      }

      rebalanceRecords.push({
        year: parseInt(ym.substring(0, 4), 10),
        month: ym,
        portfolio: Math.round(portfolioNow),
        drift_alloc: driftAlloc,
        target_alloc: { ...allocations },
        trades,
        gk_trigger: gkTrigger,
        monthly_income: Math.round(monthlyIncome),
      });
    }

    // 套用當月市場報酬
    const portBefore = Object.values(assetValues).reduce((s, v) => s + v, 0);
    for (const a of assets) {
      const r =
        a === "現金" || a === "CASH"
          ? cashMonthly
          : monthlyRetMap[a]?.[ym] || 0.0;
      assetValues[a] *= 1 + r;
    }

    const portAfterReturn = Object.values(assetValues).reduce(
      (s, v) => s + v,
      0
    );
    const monthlyRetPct =
      portBefore > 0
        ? ((portAfterReturn - portBefore) / portBefore) * 100
        : 0.0;

    // 扣除月提領
    const effWd = Math.min(monthlyIncome, portAfterReturn);
    if (portAfterReturn > 0) {
      const ratio = effWd / portAfterReturn;
      for (const a of assets) {
        assetValues[a] *= 1 - ratio;
      }
    }

    const portEnd = Math.max(0, portAfterReturn - effWd);
    const wr = portEnd > 0 ? (annualWithdrawal / portEnd) * 100 : Infinity;

    let triggerLabel = "—";
    if (isJan) {
      if (gkTrigger === "capital_preservation") {
        triggerLabel = "↓ 減提領 + 再平衡";
      } else if (gkTrigger === "prosperity") {
        triggerLabel = "↑ 增提領 + 再平衡";
      } else {
        triggerLabel = "通膨調整 + 再平衡";
      }
    } else if (gkTrigger === "capital_preservation") {
      triggerLabel = "↓ 減提領";
    } else if (gkTrigger === "prosperity") {
      triggerLabel = "↑ 增提領";
    }

    monthlyRecords.push({
      月份: ym,
      "月報酬 %": Math.round(monthlyRetPct * 100) / 100,
      "資產餘額 (萬)": Math.round((portEnd / 10000) * 10) / 10,
      月提領額: Math.round(monthlyIncome),
      "提領率 %": Math.round(wr * 100) / 100,
      事件: triggerLabel,
    });
  }

  const finalPortfolio = Object.values(assetValues).reduce((s, v) => s + v, 0);

  return {
    monthly: monthlyRecords,
    rebalances: rebalanceRecords,
    final_portfolio: Math.round(finalPortfolio),
    final_monthly_income: Math.round(monthlyIncome),
    asset_values: assetValues,
    data_warnings: dataWarnings,
  };
}
