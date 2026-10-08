import React, { useState, useEffect, useMemo } from "react";
import {
  History,
  Calendar,
  RefreshCw,
  Scale,
  ArrowRight,
  TrendingUp,
  Loader2,
  AlertCircle,
} from "lucide-react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";
import { useApp } from "../context/AppContext";
import { fetchAdjustedPrices } from "../services/api";
import { HistoricalTrackingResult, PricePoint } from "../core/types";
import { runGKHistorical } from "../core/simulation";
import { MetricCard } from "../components/MetricCard";
import { PortfolioEditor } from "../components/PortfolioEditor";

export const TrackingView: React.FC = () => {
  const {
    portfolioAllocations,
    initialAsset,
    initialWithdrawalRate,
    guardrailPct,
    inflationRate,
  } = useApp();

  const [startYm, setStartYm] = useState("2015-01");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [trackingResult, setTrackingResult] =
    useState<HistoricalTrackingResult | null>(null);

  useEffect(() => {
    let isMounted = true;
    async function loadHistoricalTracking() {
      setLoading(true);
      setError(null);
      try {
        const closeMap: Record<string, PricePoint[]> = {};
        for (const asset of Object.keys(portfolioAllocations)) {
          if (asset !== "現金" && asset !== "CASH") {
            const p = await fetchAdjustedPrices(asset);
            closeMap[asset] = p;
          }
        }

        if (!isMounted) return;

        const res = runGKHistorical(
          initialAsset,
          portfolioAllocations,
          startYm,
          initialWithdrawalRate,
          guardrailPct,
          inflationRate,
          closeMap
        );

        setTrackingResult(res);
      } catch (err: any) {
        if (isMounted) setError(err.message || "回測追蹤計算失敗");
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    loadHistoricalTracking();
    return () => {
      isMounted = false;
    };
  }, [
    portfolioAllocations,
    startYm,
    initialAsset,
    initialWithdrawalRate,
    guardrailPct,
    inflationRate,
  ]);

  return (
    <div className="space-y-6">
      {/* 標題與起始年月設定 */}
      <div className="glass-panel rounded-2xl p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
            📋 歷史月頻提領動態追蹤
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            模擬自特定歷史起點開始退休，每年一月自動執行「通膨調整」與「資產配置再平衡 (Rebalancing)」
          </p>
        </div>

        {/* 起始年份選擇 */}
        <div className="flex items-center gap-3 bg-slate-900/80 px-4 py-2 rounded-xl border border-slate-800">
          <Calendar className="w-4 h-4 text-indigo-400 shrink-0" />
          <span className="text-xs text-slate-400">起始退休年月:</span>
          <select
            value={startYm}
            onChange={(e) => setStartYm(e.target.value)}
            className="bg-slate-800 border border-slate-700 text-xs font-mono font-bold text-white rounded-lg px-2.5 py-1 focus:outline-none focus:border-indigo-500"
          >
            <option value="2008-01">2008-01 (金融海嘯谷底)</option>
            <option value="2012-01">2012-01 (歐債危機後)</option>
            <option value="2015-01">2015-01 (十年回測)</option>
            <option value="2018-01">2018-01 (中美貿易戰)</option>
            <option value="2020-01">2020-01 (COVID 疫情)</option>
            <option value="2022-01">2022-01 (聯準會升息)</option>
          </select>
        </div>
      </div>

      {/* 提領追蹤持股配置 */}
      <PortfolioEditor
        title="📦 持倉目標配置（提領策略回測）"
        subtitle="自訂要依歷史實際月報酬進行 GK 護欄提領回測的持股配比"
      />

      {loading && (
        <div className="glass-panel rounded-2xl p-16 flex flex-col items-center justify-center gap-3">
          <Loader2 className="w-8 h-8 text-indigo-400 animate-spin" />
          <p className="text-sm text-slate-300 font-medium">
            正在執行歷史逐月動態再平衡回測...
          </p>
        </div>
      )}

      {error && !loading && (
        <div className="glass-panel rounded-2xl p-6 border-rose-500/30 bg-rose-950/20 flex items-center gap-3 text-rose-300">
          <AlertCircle className="w-5 h-5 text-rose-400 shrink-0" />
          <span className="text-sm">{error}</span>
        </div>
      )}

      {!loading && !error && trackingResult && (
        <>
          {/* 指標卡片 */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard
              title="追蹤終端資產餘額"
              value={`NT$ ${(
                trackingResult.final_portfolio / 10000
              ).toLocaleString(undefined, { maximumFractionDigits: 0 })} 萬`}
              subLabel="起始本金"
              subValue={`${(initialAsset / 10000).toFixed(0)} 萬`}
              icon={TrendingUp}
              badge={
                trackingResult.final_portfolio >= initialAsset
                  ? "資產擴大"
                  : "本金回撤"
              }
              badgeColor={
                trackingResult.final_portfolio >= initialAsset
                  ? "green"
                  : "amber"
              }
            />
            <MetricCard
              title="最新月提領金額"
              value={`NT$ ${trackingResult.final_monthly_income.toLocaleString()}`}
              subLabel="首月提領"
              subValue={`NT$ ${Math.round(
                (initialAsset * initialWithdrawalRate) / 12
              ).toLocaleString()}`}
              icon={History}
              badge="動態調整後"
              badgeColor="indigo"
            />
            <MetricCard
              title="執行再平衡次數"
              value={`${trackingResult.rebalances.length} 次`}
              subLabel="頻率"
              subValue="每年 1 月定期執行"
              icon={Scale}
              badge="風險控制"
              badgeColor="slate"
            />
            <MetricCard
              title="總追蹤月份數"
              value={`${trackingResult.monthly.length} 個月`}
              subLabel="歷時"
              subValue={`${(trackingResult.monthly.length / 12).toFixed(1)} 年`}
              icon={Calendar}
              badge="真實歷史"
              badgeColor="cyan"
            />
          </div>

          {/* 資產演化軌跡折線圖 */}
          <div className="glass-panel rounded-2xl p-5 space-y-3">
            <div>
              <h3 className="text-base font-semibold text-white">
                📈 歷史資產餘額與動態月提領額走勢
              </h3>
              <p className="text-xs text-slate-400">
                綠線為資產餘額 (萬元)，青色為每月生活提領額 (元)
              </p>
            </div>

            <div className="h-80 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trackingResult.monthly}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.3} />
                  <XAxis
                    dataKey="月份"
                    stroke="#64748b"
                    tick={{ fontSize: 11 }}
                    minTickGap={40}
                  />
                  <YAxis
                    yAxisId="left"
                    stroke="#10b981"
                    tick={{ fontSize: 11 }}
                    tickFormatter={(v) => `${v}萬`}
                  />
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    stroke="#06b6d4"
                    tick={{ fontSize: 11 }}
                    tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#0f172a",
                      borderColor: "#334155",
                      borderRadius: "12px",
                      color: "#fff",
                      fontSize: "12px",
                    }}
                  />
                  <Legend />
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey="資產餘額 (萬)"
                    stroke="#10b981"
                    strokeWidth={2}
                    dot={false}
                    name="資產餘額 (萬)"
                  />
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="月提領額"
                    stroke="#06b6d4"
                    strokeWidth={1.5}
                    dot={false}
                    name="月提領額 (TWD)"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* 年度再平衡交易紀錄 */}
          {trackingResult.rebalances.length > 0 && (
            <div className="glass-panel rounded-2xl p-5 space-y-3">
              <h3 className="text-base font-semibold text-white flex items-center gap-2">
                <RefreshCw className="w-4 h-4 text-indigo-400" /> 歷年一月再平衡與調倉紀錄
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead>
                    <tr className="border-b border-slate-800 text-slate-400">
                      <th className="py-2.5 px-3">年份</th>
                      <th className="py-2.5 px-3">當前總資產 (萬)</th>
                      <th className="py-2.5 px-3">調倉交易內容 (買進 / 賣出)</th>
                      <th className="py-2.5 px-3 text-right">護欄狀態</th>
                      <th className="py-2.5 px-3 text-right">新年月提領額</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 text-slate-200">
                    {trackingResult.rebalances.map((rb) => (
                      <tr key={rb.month} className="hover:bg-slate-800/40">
                        <td className="py-2.5 px-3 font-semibold text-white">
                          {rb.month}
                        </td>
                        <td className="py-2.5 px-3 text-cyan-300 font-bold">
                          {(rb.portfolio / 10000).toFixed(1)} 萬
                        </td>
                        <td className="py-2.5 px-3">
                          <div className="flex flex-wrap gap-2">
                            {Object.entries(rb.trades).map(([id, amount]) => {
                              if (Math.abs(amount) < 1000) return null;
                              const isBuy = amount > 0;
                              return (
                                <span
                                  key={id}
                                  className={`px-1.5 py-0.5 rounded text-[11px] ${
                                    isBuy
                                      ? "bg-emerald-500/15 text-emerald-400"
                                      : "bg-rose-500/15 text-rose-400"
                                  }`}
                                >
                                  {isBuy ? "買進" : "賣出"} {id}{" "}
                                  {(Math.abs(amount) / 10000).toFixed(1)} 萬
                                </span>
                              );
                            })}
                          </div>
                        </td>
                        <td
                          className={`py-2.5 px-3 text-right font-medium ${
                            rb.gk_trigger === "capital_preservation"
                              ? "text-rose-400"
                              : rb.gk_trigger === "prosperity"
                              ? "text-emerald-400"
                              : "text-slate-400"
                          }`}
                        >
                          {rb.gk_trigger === "capital_preservation"
                            ? "↓ 減10%"
                            : rb.gk_trigger === "prosperity"
                            ? "↑ 加10%"
                            : "通膨微調"}
                        </td>
                        <td className="py-2.5 px-3 text-right font-bold text-white">
                          NT$ {rb.monthly_income.toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};
