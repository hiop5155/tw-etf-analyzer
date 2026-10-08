import React, { useState, useEffect } from "react";
import {
  AlertTriangle,
  Flame,
  ShieldAlert,
  Calendar,
  Activity,
  CheckCircle,
  Loader2,
  AlertCircle,
} from "lucide-react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
  ReferenceLine,
} from "recharts";
import { useApp } from "../context/AppContext";
import { fetchAdjustedPrices } from "../services/api";
import { PricePoint, StressScenarioResult } from "../core/types";
import { runStressTests } from "../core/stress";
import { MetricCard } from "../components/MetricCard";
import { PortfolioEditor } from "../components/PortfolioEditor";

export const StressTestView: React.FC = () => {
  const {
    portfolioAllocations,
    initialAsset,
    initialWithdrawalRate,
    guardrailPct,
    inflationRate,
  } = useApp();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stressResults, setStressResults] = useState<StressScenarioResult[]>([]);

  useEffect(() => {
    let isMounted = true;
    async function executeStress() {
      setLoading(true);
      setError(null);
      try {
        // 載入 0050 作為歷史代理
        const proxyPrices = await fetchAdjustedPrices("0050");

        // 載入當前投組各標的價格
        const closeMap: Record<string, PricePoint[]> = {};
        for (const asset of Object.keys(portfolioAllocations)) {
          if (asset !== "現金" && asset !== "CASH") {
            const p = await fetchAdjustedPrices(asset);
            closeMap[asset] = p;
          }
        }

        if (!isMounted) return;

        const results = runStressTests(
          portfolioAllocations,
          initialAsset,
          initialWithdrawalRate,
          guardrailPct,
          inflationRate,
          closeMap,
          proxyPrices
        );

        setStressResults(results);
      } catch (err: any) {
        if (isMounted) setError(err.message || "壓力測試執行失敗");
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    executeStress();
    return () => {
      isMounted = false;
    };
  }, [
    portfolioAllocations,
    initialAsset,
    initialWithdrawalRate,
    guardrailPct,
    inflationRate,
  ]);

  return (
    <div className="space-y-6">
      {/* 標題與簡介 */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 px-1">
        <div>
          <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
            ⚠️ 壓力測試 — 在歷史最差時刻退休會怎樣？
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            以您設定的投組與護欄參數，模擬在極端黑天鵝事件當月退休並追蹤至今。成立較晚之標的將自動以 0050 報酬率補齊。
          </p>
        </div>
      </div>

      {/* 壓力測試投組配置 */}
      <PortfolioEditor
        title="🗂️ 壓力測試投資組合"
        subtitle="調整要在歷史熊市黑天鵝情境下進行壓力測試的 ETF 配置比例 %"
      />

      {loading && (
        <div className="glass-panel rounded-2xl p-16 flex flex-col items-center justify-center gap-3">
          <Loader2 className="w-8 h-8 text-rose-400 animate-spin" />
          <p className="text-sm text-slate-300 font-medium">
            正在計算三大歷史黑天鵝極端回撤壓力路徑...
          </p>
        </div>
      )}

      {error && !loading && (
        <div className="glass-panel rounded-2xl p-6 border-rose-500/30 bg-rose-950/20 flex items-center gap-3 text-rose-300">
          <AlertCircle className="w-5 h-5 text-rose-400 shrink-0" />
          <span className="text-sm">{error}</span>
        </div>
      )}

      {!loading && !error && stressResults.length > 0 && (
        <>
          {/* 三大情境卡片 */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {stressResults.map((item, idx) => {
              const sc = item.scenario;
              const r = item.result;
              const months = r.monthly.length;
              const yrs = (months / 12).toFixed(1);
              const finalPort = (r.final_portfolio / 10000).toLocaleString(
                undefined,
                { maximumFractionDigits: 0 }
              );
              const isGrowing = r.final_portfolio >= initialAsset;

              return (
                <div
                  key={sc.name}
                  className="glass-card rounded-2xl p-5 border border-slate-800 flex flex-col justify-between space-y-4"
                >
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="font-bold text-base text-white">
                        {sc.name}
                      </span>
                      <span className="text-xs font-mono text-slate-400">
                        {sc.start_ym} 起
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 leading-relaxed min-h-[36px]">
                      {sc.desc}
                    </p>
                  </div>

                  <div className="space-y-3 pt-3 border-t border-slate-800/80">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs text-slate-400 shrink-0">目前資產餘額:</span>
                      <span
                        className={`font-mono font-bold text-base sm:text-lg whitespace-nowrap ${
                          isGrowing ? "text-emerald-400" : "text-amber-400"
                        }`}
                      >
                        {finalPort} 萬元
                      </span>
                    </div>

                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs text-slate-400 shrink-0">目前月提領額:</span>
                      <span className="font-mono font-bold text-xs sm:text-sm text-cyan-300 whitespace-nowrap">
                        NT$ {r.final_monthly_income.toLocaleString()}
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-xs text-slate-500">
                      <span className="shrink-0">歷時年數:</span>
                      <span className="font-mono text-slate-400 whitespace-nowrap">
                        {yrs} 年 ({months} 個月)
                      </span>
                    </div>

                    {item.proxied.length > 0 && (
                      <div className="text-[11px] text-amber-400/90 bg-amber-500/10 px-2 py-1 rounded border border-amber-500/20">
                        ⚠️ 早期以 0050 代理: {item.proxied.join(", ")}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* 護欄觸發事件彙總列表 */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {stressResults.map((item) => {
              const events = item.result.monthly.filter(
                (m) =>
                  m.事件.includes("減") ||
                  m.事件.includes("增") ||
                  m.事件.includes("再平衡")
              );

              return (
                <div
                  key={item.scenario.name}
                  className="glass-panel rounded-2xl p-5 space-y-3 flex flex-col"
                >
                  <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                    <h4 className="text-sm font-semibold text-white">
                      🛡️ {item.scenario.name} 關鍵事件
                    </h4>
                    <span className="text-xs font-mono text-indigo-400">
                      觸發 {events.length} 次
                    </span>
                  </div>

                  <div className="max-h-64 overflow-y-auto space-y-2 pr-1 no-scrollbar text-xs font-mono">
                    {events.length === 0 ? (
                      <div className="text-slate-500 py-4 text-center">
                        此區間無護欄觸發 (資產平穩)
                      </div>
                    ) : (
                      events.map((ev, i) => (
                        <div
                          key={i}
                          className="p-2 rounded-lg bg-slate-900/60 border border-slate-800 flex items-center justify-between"
                        >
                          <div>
                            <span className="text-slate-400 font-bold block">
                              {ev.月份}
                            </span>
                            <span
                              className={`text-[11px] ${
                                ev.事件.includes("減")
                                  ? "text-rose-400"
                                  : "text-emerald-400"
                              }`}
                            >
                              {ev.事件}
                            </span>
                          </div>
                          <div className="text-right">
                            <span className="text-slate-200 block">
                              餘額 {ev["資產餘額 (萬)"]} 萬
                            </span>
                            <span className="text-slate-400 text-[11px]">
                              月領 ${ev.月提領額.toLocaleString()}
                            </span>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
};
