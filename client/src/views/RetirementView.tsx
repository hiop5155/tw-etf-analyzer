import React, { useState, useMemo, useEffect } from "react";
import {
  Umbrella,
  ShieldCheck,
  AlertTriangle,
  Flame,
  Percent,
  Sliders,
  Play,
  RotateCcw,
  Sparkles,
  Info,
  DollarSign,
} from "lucide-react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";
import { useApp } from "../context/AppContext";
import { PRESET_PORTFOLIOS } from "../core/constants";
import { simulateGK, simulateGKMonteCarlo } from "../core/simulation";
import { fetchAdjustedPrices } from "../services/api";
import { calcReturnVol } from "../core/metrics";
import { MetricCard } from "../components/MetricCard";
import { PortfolioEditor } from "../components/PortfolioEditor";
import { NumericInput } from "../components/NumericInput";

export const RetirementView: React.FC = () => {
  const {
    initialAsset,
    setInitialAsset,
    initialWithdrawalRate,
    setInitialWithdrawalRate,
    guardrailPct,
    setGuardrailPct,
    simulationYears,
    setSimulationYears,
    inflationRate,
    portfolioAllocations,
    setPortfolioAllocations,
    applyPresetPortfolio,
  } = useApp();

  const [activePreset, setActivePreset] = useState("保守配息型 (股債均衡)");
  const [distModel, setDistModel] = useState<"normal" | "bootstrap">("normal");
  const [customReturn, setCustomReturn] = useState<number>(6.5); // 加權年化報酬 %
  const [customVol, setCustomVol] = useState<number>(12.0); // 加權年化波動度 %
  const [loadingStats, setLoadingStats] = useState(false);

  // 當投組配比變更時，自動計算歷史加權平均 CAGR 與波動度
  useEffect(() => {
    let isMounted = true;
    async function estimatePortfolioStats() {
      setLoadingStats(true);
      try {
        const assets = Object.keys(portfolioAllocations);
        let weightedRet = 0;
        let weightedVol = 0;

        for (const id of assets) {
          const weight = portfolioAllocations[id];
          if (id === "現金" || id === "CASH") {
            weightedRet += 0.0 * weight;
            weightedVol += 0.0 * weight;
          } else {
            const prices = await fetchAdjustedPrices(id);
            if (prices.length >= 2) {
              const [cagr, vol] = calcReturnVol(prices);
              weightedRet += cagr * weight;
              weightedVol += vol * weight;
            } else {
              weightedRet += 0.06 * weight;
              weightedVol += 0.12 * weight;
            }
          }
        }

        if (isMounted) {
          setCustomReturn(Math.round(weightedRet * 1000) / 10);
          setCustomVol(Math.round(weightedVol * 1000) / 10);
        }
      } catch (e) {
        // 保持預設
      } finally {
        if (isMounted) setLoadingStats(false);
      }
    }

    estimatePortfolioStats();
    return () => {
      isMounted = false;
    };
  }, [portfolioAllocations]);

  // 1. 確定性 Guyton-Klinger 計算
  const deterministicGK = useMemo(() => {
    return simulateGK(
      initialAsset,
      initialWithdrawalRate,
      guardrailPct,
      customReturn / 100,
      inflationRate,
      simulationYears
    );
  }, [
    initialAsset,
    initialWithdrawalRate,
    guardrailPct,
    customReturn,
    inflationRate,
    simulationYears,
  ]);

  // 2. 蒙地卡羅 1,000 次隨機路徑模擬 (純前端毫秒級高頻計算)
  const mcResult = useMemo(() => {
    return simulateGKMonteCarlo(
      initialAsset,
      initialWithdrawalRate,
      guardrailPct,
      customReturn / 100,
      customVol / 100,
      inflationRate,
      simulationYears,
      1000,
      42,
      distModel
    );
  }, [
    initialAsset,
    initialWithdrawalRate,
    guardrailPct,
    customReturn,
    customVol,
    inflationRate,
    simulationYears,
    distModel,
  ]);

  // 蒙地卡羅資產扇形圖數據格式化 (P10, P25, P50, P75, P90)
  const fanChartData = useMemo(() => {
    return mcResult.years.map((yr, idx) => ({
      year: yr,
      p10: Math.round(mcResult.port_pct.p10[idx] / 10000),
      p25: Math.round(mcResult.port_pct.p25[idx] / 10000),
      p50: Math.round(mcResult.port_pct.p50[idx] / 10000),
      p75: Math.round(mcResult.port_pct.p75[idx] / 10000),
      p90: Math.round(mcResult.port_pct.p90[idx] / 10000),
    }));
  }, [mcResult]);

  // 月提領額歷年走勢圖數據
  const wdChartData = useMemo(() => {
    return mcResult.years.map((yr, idx) => ({
      year: yr,
      p10: Math.round(mcResult.wd_pct.p10[idx]),
      p25: Math.round(mcResult.wd_pct.p25[idx]),
      p50: Math.round(mcResult.wd_pct.p50[idx]),
      p75: Math.round(mcResult.wd_pct.p75[idx]),
      p90: Math.round(mcResult.wd_pct.p90[idx]),
    }));
  }, [mcResult]);

  const [repPct, setRepPct] = useState<number>(50);

  return (
    <div className="space-y-6">
      {/* 標題與簡介 */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 px-1">
        <div>
          <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
            🏖️ Guyton-Klinger 動態退休提領與蒙地卡羅模擬
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            結合「繁榮條款」與「資本保護規則」，讓退休金在最長壽命下永不歸零並極大化生活品質
          </p>
        </div>
      </div>

      {/* 退休後投資組合配置編輯器 (支援自訂標的與自由配比) */}
      <PortfolioEditor
        title="🗂️ 退休後投資組合配置"
        subtitle="選擇推薦策略範本，或自由新增 ETF、調整配置比例 %"
      />

      {/* 退休提領參數設定面板 */}
      <div className="glass-panel rounded-2xl p-5 space-y-5">
        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
          <Sliders className="w-4 h-4 text-indigo-400" /> 提領護欄核心參數設定
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* 起始退休資產 */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-300">
              起始退休本金 (萬元)
            </label>
            <div className="flex items-center gap-2">
              <NumericInput
                value={Math.round(initialAsset / 10000)}
                min={10}
                onCommit={(val) => setInitialAsset(val * 10000)}
                placeholder="2000"
                className="w-full bg-slate-900 border border-slate-700 px-3 py-2 rounded-xl text-sm font-mono font-bold text-white focus:outline-none focus:border-indigo-500"
              />
              <span className="text-xs text-slate-400 whitespace-nowrap">萬 TWD</span>
            </div>
            <div className="flex gap-1.5 pt-1">
              {[1500, 2000, 2500, 3000].map((v) => (
                <button
                  key={v}
                  onClick={() => setInitialAsset(v * 10000)}
                  className="px-2 py-0.5 rounded text-[11px] bg-slate-800 hover:bg-slate-700 text-slate-300"
                >
                  {v}萬
                </button>
              ))}
            </div>
          </div>

          {/* 初始提領率 */}
          <div className="space-y-1.5">
            <div className="flex justify-between items-center">
              <label className="text-xs font-medium text-slate-300">
                初始提領率 (Initial SWR)
              </label>
              <div className="flex items-center gap-1">
                <NumericInput
                  value={Math.round(initialWithdrawalRate * 1000) / 10}
                  min={0.5}
                  max={20.0}
                  step="0.1"
                  onCommit={(val) => setInitialWithdrawalRate(val / 100)}
                  placeholder="5.0"
                  className="w-16 bg-slate-950 border border-slate-700 px-2 py-0.5 rounded-lg text-xs font-mono font-bold text-cyan-400 text-right focus:outline-none focus:border-cyan-500"
                />
                <span className="text-xs font-mono font-bold text-cyan-400">%</span>
              </div>
            </div>
            <input
              type="range"
              min="1.0"
              max="12.0"
              step="0.25"
              value={initialWithdrawalRate * 100}
              onChange={(e) =>
                setInitialWithdrawalRate(parseFloat(e.target.value) / 100)
              }
              className="w-full accent-cyan-500 bg-slate-800 h-2 rounded-lg cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-slate-500">
              <span>3% (超安全)</span>
              <span>4% (經典)</span>
              <span>5% (GK推薦)</span>
              <span>7%+</span>
            </div>
          </div>

          {/* 護欄寬度 */}
          <div className="space-y-1.5">
            <div className="flex justify-between">
              <label className="text-xs font-medium text-slate-300">
                動態護欄寬度 (Guardrails)
              </label>
              <span className="text-xs font-mono font-bold text-amber-400">
                ±{(guardrailPct * 100).toFixed(0)}%
              </span>
            </div>
            <input
              type="range"
              min="10"
              max="35"
              step="5"
              value={guardrailPct * 100}
              onChange={(e) => setGuardrailPct(parseInt(e.target.value) / 100)}
              className="w-full accent-amber-500 bg-slate-800 h-2 rounded-lg cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-slate-500">
              <span>±10% (高頻微調)</span>
              <span>±20% (標準GK)</span>
              <span>±30% (高彈性)</span>
            </div>
          </div>

          {/* 退休年限 */}
          <div className="space-y-1.5">
            <div className="flex justify-between items-center">
              <label className="text-xs font-medium text-slate-300">退休規劃年限</label>
              <div className="flex items-center gap-1">
                <NumericInput
                  value={simulationYears}
                  min={5}
                  max={80}
                  step={1}
                  onCommit={(val) => setSimulationYears(Math.max(5, Math.min(80, Math.round(val))))}
                  placeholder="30"
                  className="w-16 bg-slate-950 border border-slate-700 px-2 py-0.5 rounded-lg text-xs font-mono font-bold text-indigo-400 text-right focus:outline-none focus:border-indigo-500"
                />
                <span className="text-xs font-mono font-bold text-indigo-400">年</span>
              </div>
            </div>
            <input
              type="range"
              min="10"
              max="70"
              step="1"
              value={simulationYears}
              onChange={(e) => setSimulationYears(parseInt(e.target.value) || 30)}
              className="w-full accent-indigo-500 bg-slate-800 h-2 rounded-lg cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-slate-500">
              <span>10年</span>
              <span>30年</span>
              <span>50年</span>
              <span>70年</span>
            </div>
            <div className="flex flex-wrap gap-1.5 pt-0.5">
              {[20, 30, 40, 50, 60, 70].map((v) => (
                <button
                  key={v}
                  onClick={() => setSimulationYears(v)}
                  className={`px-2 py-0.5 rounded text-[11px] transition-colors ${simulationYears === v
                    ? "bg-indigo-600 text-white font-semibold"
                    : "bg-slate-800 hover:bg-slate-700 text-slate-300"
                    }`}
                >
                  {v}年
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* 蒙地卡羅加權參數自訂 */}
        <div className="pt-3 border-t border-slate-800/80 flex flex-wrap items-center justify-between gap-4 text-xs">
          <div className="flex items-center gap-4">
            <span className="text-slate-400">投組模擬參數 (歷史加權):</span>
            <div className="flex items-center gap-1.5">
              <span className="text-slate-500">年化報酬:</span>
              <span className="font-mono font-bold text-emerald-400">
                {customReturn.toFixed(1)}%
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-slate-500">年化波動:</span>
              <span className="font-mono font-bold text-amber-400">
                {customVol.toFixed(1)}%
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-slate-400">隨機抽樣模型:</span>
            <button
              onClick={() => setDistModel("normal")}
              className={`px-2.5 py-1 rounded-lg ${distModel === "normal"
                ? "bg-indigo-600 text-white font-semibold"
                : "bg-slate-800 text-slate-400"
                }`}
            >
              標準常態分佈 N(μ,σ)
            </button>
            <button
              onClick={() => setDistModel("bootstrap")}
              className={`px-2.5 py-1 rounded-lg ${distModel === "bootstrap"
                ? "bg-indigo-600 text-white font-semibold"
                : "bg-slate-800 text-slate-400"
                }`}
            >
              歷史月報酬拔靴法 (Bootstrap)
            </button>
          </div>
        </div>
      </div>

      {/* 蒙地卡羅與提領成果卡片 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="首年月提領生活費"
          value={`NT$ ${mcResult.initial_monthly.toLocaleString()}`}
          subLabel="第一年年支出"
          subValue={`NT$ ${(
            mcResult.initial_monthly * 12
          ).toLocaleString()}`}
          icon={DollarSign}
          badge="生活品質"
          badgeColor="indigo"
        />
        <MetricCard
          title={`${simulationYears} 年存活率`}
          value={`${mcResult.survival_final.toFixed(1)}%`}
          subLabel="破產歸零機率"
          subValue={`${mcResult.depleted_pct.toFixed(1)}%`}
          icon={ShieldCheck}
          badge={mcResult.survival_final >= 95 ? "極度安全" : "需謹慎"}
          badgeColor={mcResult.survival_final >= 95 ? "green" : "amber"}
        />
        <MetricCard
          title="P50 期末資產中位數"
          value={`NT$ ${(
            (mcResult.port_pct.p50[simulationYears - 1] ?? 0) / 10000
          ).toLocaleString(undefined, { maximumFractionDigits: 0 })} 萬`}
          subLabel="基準路徑"
          subValue={`起點 ${(initialAsset / 10000).toFixed(0)} 萬`}
          icon={Sparkles}
          badge="本金遺產"
          badgeColor="cyan"
        />
        <MetricCard
          title="P10 悲觀情境月提領"
          value={`NT$ ${(mcResult.wd_pct.p10[simulationYears - 1] ?? 0).toLocaleString()}`}
          subLabel="護欄減額底限"
          subValue={`第 ${simulationYears} 年`}
          icon={AlertTriangle}
          badge="壓力耐受"
          badgeColor="slate"
        />
      </div>

      {/* 蒙地卡羅資產扇形圖 (Percentile Fan Chart) */}
      <div className="glass-panel rounded-2xl p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h3 className="text-base font-semibold text-white">
              🌈 蒙地卡羅 1,000 次模擬資產走勢扇形圖 (萬元)
            </h3>
            <p className="text-xs text-slate-400">
              各色階代表不同市場情境：P90 極佳多頭、P50 中位數基準、P10 極端熊市
            </p>
          </div>
          <div className="flex items-center gap-3 text-xs font-mono">
            <span className="text-indigo-400">P90: 90%分位</span>
            <span className="text-emerald-400">P50: 中位數</span>
            <span className="text-rose-400">P10: 10%最差</span>
          </div>
        </div>

        <div className="h-80 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={fanChartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.3} />
              <XAxis
                dataKey="year"
                stroke="#64748b"
                tick={{ fontSize: 11 }}
                tickFormatter={(v) => `第 ${v} 年`}
              />
              <YAxis
                stroke="#64748b"
                tick={{ fontSize: 11 }}
                tickFormatter={(v) => `${v}萬`}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#0f172a",
                  borderColor: "#334155",
                  borderRadius: "12px",
                  color: "#fff",
                  fontSize: "12px",
                }}
                formatter={(val: any, name: any) => [`${val} 萬元`, name.toUpperCase()]}
                labelFormatter={(l) => `第 ${l} 年`}
              />
              <Legend />
              <Line
                type="monotone"
                dataKey="p90"
                stroke="#818cf8"
                strokeWidth={2}
                dot={false}
                name="p90 (牛市)"
              />
              <Line
                type="monotone"
                dataKey="p75"
                stroke="#38bdf8"
                strokeWidth={1.5}
                dot={false}
                strokeDasharray="4 4"
                name="p75 (良好)"
              />
              <Line
                type="monotone"
                dataKey="p50"
                stroke="#10b981"
                strokeWidth={3}
                dot={false}
                name="p50 (中位數基準)"
              />
              <Line
                type="monotone"
                dataKey="p25"
                stroke="#fbbf24"
                strokeWidth={1.5}
                dot={false}
                strokeDasharray="4 4"
                name="p25 (震盪)"
              />
              <Line
                type="monotone"
                dataKey="p10"
                stroke="#f43f5e"
                strokeWidth={2}
                dot={false}
                name="p10 (熊市)"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* 每月提領額變化走勢圖 */}
      <div className="glass-panel rounded-2xl p-5 space-y-4">
        <div>
          <h3 className="text-base font-semibold text-white">
            💵 Guyton-Klinger 動態月提領額歷年變化 (TWD)
          </h3>
          <p className="text-xs text-slate-400">
            展示護欄如何動態反應：多頭時啟動繁榮條款增加零用錢，空頭時扣減 10% 保全本金
          </p>
        </div>

        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={wdChartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.3} />
              <XAxis
                dataKey="year"
                stroke="#64748b"
                tick={{ fontSize: 11 }}
                tickFormatter={(v) => `第 ${v} 年`}
              />
              <YAxis
                stroke="#64748b"
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
                formatter={(val: any, name: any) => [
                  `NT$ ${val.toLocaleString()}`,
                  name.toUpperCase(),
                ]}
                labelFormatter={(l) => `第 ${l} 年`}
              />
              <Legend />
              <Line
                type="monotone"
                dataKey="p90"
                stroke="#818cf8"
                strokeWidth={1.5}
                dot={false}
                name="p90"
              />
              <Line
                type="monotone"
                dataKey="p50"
                stroke="#06b6d4"
                strokeWidth={2.5}
                dot={false}
                name="p50 (月收入)"
              />
              <Line
                type="monotone"
                dataKey="p10"
                stroke="#f43f5e"
                strokeWidth={1.5}
                dot={false}
                name="p10"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* 代表性路徑明細表格 */}
      <div className="glass-panel rounded-2xl p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-white">
              🔍 代表性路徑實戰推演
            </h3>
            <p className="text-xs text-slate-400">
              點擊查看不同市場命運下的逐年提領、資產與護欄觸發紀錄
            </p>
          </div>

          <div className="flex items-center gap-2">
            {[
              { p: 1, label: "💀 1% 極端崩盤" },
              { p: 10, label: "⚠️ 10% 嚴重熊市" },
              { p: 50, label: "🟢 50% 典型路徑" },
              { p: 90, label: "🚀 90% 繁榮大牛市" },
            ].map((item) => (
              <button
                key={item.p}
                onClick={() => setRepPct(item.p)}
                className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all ${repPct === item.p
                  ? "bg-indigo-600 text-white font-semibold"
                  : "bg-slate-800 text-slate-400 hover:text-slate-200"
                  }`}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400">
                <th className="py-2.5 px-3">年度</th>
                <th className="py-2.5 px-3">當年度報酬 %</th>
                <th className="py-2.5 px-3 text-right">年末資產 (萬)</th>
                <th className="py-2.5 px-3 text-right">月提領額 (TWD)</th>
                <th className="py-2.5 px-3 text-right">實際提領率 %</th>
                <th className="py-2.5 px-3 text-right">護欄狀態</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-200">
              {(mcResult.rep_paths[repPct] || []).map((row: any) => (
                <tr key={row.年度} className="hover:bg-slate-800/40">
                  <td className="py-2 px-3 font-semibold text-white">{row.年度}</td>
                  <td
                    className={`py-2 px-3 ${row["年化報酬 %"].startsWith("-")
                      ? "text-rose-400"
                      : "text-emerald-400"
                      }`}
                  >
                    {row["年化報酬 %"]}
                  </td>
                  <td className="py-2 px-3 text-right font-semibold text-cyan-300">
                    {row["年末資產 (萬)"]} 萬
                  </td>
                  <td className="py-2 px-3 text-right font-mono text-white">
                    NT$ {row.月提領額}
                  </td>
                  <td className="py-2 px-3 text-right text-slate-300">
                    {row["提領率 %"]}
                  </td>
                  <td
                    className={`py-2 px-3 text-right font-medium ${row.護欄觸發.includes("減")
                      ? "text-amber-400"
                      : row.護欄觸發.includes("加")
                        ? "text-emerald-400"
                        : row.護欄觸發.includes("耗盡")
                          ? "text-rose-500 font-bold"
                          : "text-slate-500"
                      }`}
                  >
                    {row.護欄觸發}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
