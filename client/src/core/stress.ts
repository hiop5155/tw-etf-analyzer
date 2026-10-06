/**
 * ⚠️ 壓力測試: 在歷史最差時刻退休會怎樣？
 * 1:1 精確對齊 tw_etf_analyzer/web/views/stress.py
 */

import { runGKHistorical } from "./simulation";
import { PricePoint, StressScenario, StressScenarioResult } from "./types";

export const STRESS_SCENARIOS: StressScenario[] = [
  {
    name: "💥 2008 金融海嘯",
    start_ym: "2008-01",
    desc: "Lehman 破產前夕退休，資產快速腰斬 (-55%)，考驗護欄保命機制",
  },
  {
    name: "🦠 2020 COVID 崩盤",
    start_ym: "2020-02",
    desc: "疫情爆發前夕退休，單月急跌 -30% 後隨即迎來強力 V 型反彈",
  },
  {
    name: "📈 2022 升息循環",
    start_ym: "2022-01",
    desc: "通膨高點啟動退休，遭遇歷史罕見的股債雙殺大回撤",
  },
];

/**
 * 補齊代理資料: 若標的成立日晚於情境起始點，使用 0050 等比例縮放補齊前段
 */
export function spliceProxy(
  assetClose: PricePoint[],
  proxyClose: PricePoint[],
  startYm: string
): { series: PricePoint[]; wasProxied: boolean } {
  const startDate = `${startYm}-01`;
  if (!assetClose || assetClose.length === 0) {
    return { series: proxyClose, wasProxied: true };
  }

  // 若標的在該情境起點前就已上市，不需代理
  if (assetClose[0].date <= startDate) {
    return { series: assetClose, wasProxied: false };
  }

  // 截取 proxy 介於 startDate 與 assetClose[0].date 的區間
  const assetInception = assetClose[0].date;
  const proxySegment = proxyClose.filter(
    (p) => p.date >= startDate && p.date <= assetInception
  );

  if (proxySegment.length === 0) {
    return { series: assetClose, wasProxied: false };
  }

  const proxyEndPrice = proxySegment[proxySegment.length - 1].close;
  const scale = assetClose[0].close / proxyEndPrice;

  // 縮放代理區間
  const scaledProxy = proxySegment.slice(0, -1).map((p) => ({
    date: p.date,
    close: p.close * scale,
  }));

  const combined = [...scaledProxy, ...assetClose];
  return { series: combined, wasProxied: true };
}

/**
 * 執行三大極端壓力測試
 */
export function runStressTests(
  allocations: Record<string, number>,
  initialAsset: number,
  initialRate: number,
  guardrailPct: number,
  inflationRate: number,
  closeSeriesMap: Record<string, PricePoint[]>,
  proxyCloseSeries: PricePoint[]
): StressScenarioResult[] {
  const results: StressScenarioResult[] = [];

  for (const sc of STRESS_SCENARIOS) {
    const scenarioCloseMap: Record<string, PricePoint[]> = {};
    const proxied: string[] = [];

    for (const [asset, weight] of Object.entries(allocations)) {
      if (asset === "現金" || asset === "CASH" || weight <= 0) continue;
      const raw = closeSeriesMap[asset] || [];
      const { series, wasProxied } = spliceProxy(
        raw,
        proxyCloseSeries,
        sc.start_ym
      );
      scenarioCloseMap[asset] = series;
      if (wasProxied) {
        proxied.push(asset);
      }
    }

    try {
      const res = runGKHistorical(
        initialAsset,
        allocations,
        sc.start_ym,
        initialRate,
        guardrailPct,
        inflationRate,
        scenarioCloseMap
      );
      results.push({
        scenario: sc,
        result: res,
        proxied,
      });
    } catch (e) {
      console.error(`壓力測試 ${sc.name} 執行失敗:`, e);
    }
  }

  return results;
}
