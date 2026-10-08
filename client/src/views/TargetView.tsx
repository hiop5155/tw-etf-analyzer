import React, { useState, useMemo } from "react";
import {
  Target,
  Calendar,
  Wallet,
  TrendingUp,
  Coins,
  ArrowRight,
  Calculator,
  PieChart as PieIcon,
  Sparkles,
  CheckCircle2,
} from "lucide-react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";
import { useApp } from "../context/AppContext";
import {
  calcTargetMonthly,
  calcTargetAssetsFromExpense,
} from "../core/performance";
import { MetricCard } from "../components/MetricCard";
import { HoldingsEditor } from "../components/HoldingsEditor";
import { NumericInput } from "../components/NumericInput";

export const TargetView: React.FC = () => {
  const {
    targetAmount,
    setTargetAmount,
    targetYears,
    setTargetYears,
    existingAsset,
    setExistingAsset,
    inflationRate,
    isRealMode,
  } = useApp();

  const [expectedCagr, setExpectedCagr] = useState<number>(8.0); // 未來定期定額預期年化報酬率 %
  const [holdingsCagr, setHoldingsCagr] = useState<number>(8.0); // 目前已持有組合加權年化 %
  const [monthlyExpense, setMonthlyExpense] = useState<number>(60_000); // 預期月支出
  const [swr, setSwr] = useState<number>(4.0); // 提領率 %

  // 給定月支出與 SWR 反推目標資產
  const handleApplyFromExpense = () => {
    const assets = calcTargetAssetsFromExpense(monthlyExpense, swr / 100);
    setTargetAmount(Math.round(assets));
  };

  // 核心反推計算 (包含實質購買力、現有資產持股組合專屬加權年化)
  const result = useMemo(() => {
    return calcTargetMonthly(
      targetAmount,
      targetYears,
      expectedCagr,
      existingAsset,
      inflationRate,
      isRealMode,
      holdingsCagr
    );
  }, [targetAmount, targetYears, expectedCagr, existingAsset, inflationRate, isRealMode, holdingsCagr]);

  // 生成逐年本金 vs 獲利階梯圖數據
  const trajectoryData = useMemo(() => {
    const rA_exist = result.effective_existing_cagr / 100;
    const rM_exist = Math.pow(1 + rA_exist, 1 / 12) - 1;

    const rA_dca = result.effective_cagr / 100;
    const rM_dca = Math.pow(1 + rA_dca, 1 / 12) - 1;
    const monthly = result.monthly;

    const data: {
      year: number;
      principal: number;
      existingFv: number;
      totalValue: number;
      gain: number;
    }[] = [];

    let currentExisting = existingAsset;
    let currentDca = 0;
    let totalDcaPrincipal = 0;

    data.push({
      year: 0,
      principal: Math.round(existingAsset / 10000),
      existingFv: Math.round(existingAsset / 10000),
      totalValue: Math.round(existingAsset / 10000),
      gain: 0,
    });

    for (let yr = 1; yr <= targetYears; yr++) {
      for (let m = 0; m < 12; m++) {
        // 現有資產依「持股組合加權年化」月複利成長
        currentExisting = currentExisting * (1 + rM_exist);
        // 定期定額每期先計息再存入 (期末年金，精確對齊公式)
        currentDca = currentDca * (1 + rM_dca) + monthly;
        totalDcaPrincipal += monthly;
      }
      const totalVal = currentExisting + currentDca;
      const totalCost = existingAsset + totalDcaPrincipal;
      const gain = Math.max(0, totalVal - totalCost);

      data.push({
        year: yr,
        principal: Math.round(totalCost / 10000),
        existingFv: Math.round(currentExisting / 10000),
        totalValue: Math.round(totalVal / 10000),
        gain: Math.round(gain / 10000),
      });
    }

    return data;
  }, [result.effective_existing_cagr, result.effective_cagr, result.monthly, targetYears, existingAsset]);

  const gainRatio =
    result.terminal_value > 0
      ? Math.round((result.total_gain / result.terminal_value) * 100)
      : 0;

  return (
    <div className="space-y-6">
      {/* 標題與簡介 */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 px-1">
        <div>
          <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
            🎯 目標資產反推與複利試算
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            設定理想退休財富目標，精確倒推每月定期定額投入額度與本利成長曲線
          </p>
        </div>
      </div>

      {/* 目前持股明細編輯區 (自動計算現有資產與年化報酬) */}
      <HoldingsEditor
        onApplyCagr={(c) => setExpectedCagr(c)}
        onWeightedCagrChange={(c) => setHoldingsCagr(c)}
      />

      {/* 輸入控制面板 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左側 2 欄: 主要目標設定 */}
        <div className="lg:col-span-2 glass-panel rounded-2xl p-5 space-y-5">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <Calculator className="w-4 h-4 text-indigo-400" /> 目標與年限參數
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* 目標金額 */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-300">
                目標資產總額 (萬元)
              </label>
              <div className="flex items-center gap-2">
                <NumericInput
                  value={Math.round(targetAmount / 10000)}
                  min={10}
                  onCommit={(val) => setTargetAmount(val * 10000)}
                  placeholder="2000"
                  className="w-full bg-slate-900 border border-slate-700 px-3 py-2 rounded-xl text-sm font-mono font-bold text-white focus:outline-none focus:border-indigo-500"
                />
                <span className="text-xs text-slate-400 whitespace-nowrap">萬 TWD</span>
              </div>
              <div className="flex gap-1.5 pt-1">
                {[1000, 1500, 2000, 3000].map((v) => (
                  <button
                    key={v}
                    onClick={() => setTargetAmount(v * 10000)}
                    className="px-2 py-0.5 rounded text-[11px] bg-slate-800 hover:bg-slate-700 text-slate-300"
                  >
                    {v}萬
                  </button>
                ))}
              </div>
            </div>

            {/* 現有已持有本金 */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-300">
                目前已有資產市值 (萬元)
              </label>
              <div className="flex items-center gap-2">
                <NumericInput
                  value={Math.round(existingAsset / 10000)}
                  min={0}
                  onCommit={(val) => setExistingAsset(val * 10000)}
                  placeholder="0"
                  className="w-full bg-slate-900 border border-slate-700 px-3 py-2 rounded-xl text-sm font-mono font-bold text-white focus:outline-none focus:border-indigo-500"
                />
                <span className="text-xs text-slate-400 whitespace-nowrap">萬 TWD</span>
              </div>
              <p className="text-[11px] text-slate-500 pt-1">
                已有資金將一同以預期報酬率複利成長
              </p>
            </div>

            {/* 達成年限 */}
            <div className="space-y-1.5">
              <div className="flex justify-between">
                <label className="text-xs font-medium text-slate-300">預計達成年限</label>
                <span className="text-xs font-mono font-bold text-indigo-400">
                  {targetYears} 年
                </span>
              </div>
              <input
                type="range"
                min="3"
                max="35"
                step="1"
                value={targetYears}
                onChange={(e) => setTargetYears(parseInt(e.target.value) || 1)}
                className="w-full accent-indigo-500 bg-slate-800 h-2 rounded-lg cursor-pointer"
              />
              <div className="flex justify-between text-[10px] text-slate-500">
                <span>3年</span>
                <span>15年</span>
                <span>35年</span>
              </div>
            </div>

            {/* 預期年化報酬率 */}
            <div className="space-y-1.5">
              <div className="flex justify-between">
                <label className="text-xs font-medium text-slate-300">
                  預期年化報酬 (CAGR)
                </label>
                <span className="text-xs font-mono font-bold text-emerald-400">
                  {expectedCagr.toFixed(1)}%
                </span>
              </div>
              <input
                type="range"
                min="3.0"
                max="15.0"
                step="0.5"
                value={expectedCagr}
                onChange={(e) => setExpectedCagr(parseFloat(e.target.value) || 0)}
                className="w-full accent-emerald-500 bg-slate-800 h-2 rounded-lg cursor-pointer"
              />
              <div className="flex justify-between text-[10px] text-slate-500">
                <span>3% (保守)</span>
                <span>8% (大盤均值)</span>
                <span>15% (強勢)</span>
              </div>
            </div>
          </div>
        </div>

        {/* 右側 1 欄: 從生活費快捷反推目標 */}
        <div className="glass-panel rounded-2xl p-5 flex flex-col justify-between space-y-4">
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <Coins className="w-4 h-4 text-cyan-400" /> 由退休月支出反推
            </h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              根據 4% 法則或目標提領率，快速計算需要多少本金退休：
            </p>

            <div className="space-y-3 pt-2">
              <div>
                <label className="text-xs text-slate-300 block mb-1">
                  退休每月預期生活費 (TWD)
                </label>
                <NumericInput
                  value={monthlyExpense}
                  min={1000}
                  onCommit={(val) => setMonthlyExpense(val)}
                  placeholder="60000"
                  className="w-full bg-slate-900 border border-slate-700 px-3 py-1.5 rounded-xl text-xs font-mono text-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <div className="flex justify-between items-center mb-1">
                  <label className="text-xs font-medium text-slate-300">
                    安全提領率 (SWR %)
                  </label>
                  <div className="flex items-center gap-1">
                    <NumericInput
                      value={swr}
                      min={0.5}
                      max={20.0}
                      step="0.1"
                      onCommit={(val) => setSwr(val)}
                      placeholder="4.0"
                      className="w-16 bg-slate-950 border border-slate-700 px-2 py-0.5 rounded-lg text-xs font-mono font-bold text-cyan-400 text-right focus:outline-none focus:border-cyan-500"
                    />
                    <span className="text-xs font-mono text-slate-400">%</span>
                  </div>
                </div>
                <div className="flex gap-1.5 pt-1">
                  {[3.0, 3.5, 4.0, 4.5, 5.0].map((r) => (
                    <button
                      key={r}
                      type="button"
                      onClick={() => setSwr(r)}
                      className={`flex-1 py-1 rounded-lg text-xs font-mono font-semibold transition-colors ${
                        swr === r
                          ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                          : "bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-750"
                      }`}
                    >
                      {r}%
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <button
            onClick={handleApplyFromExpense}
            className="w-full py-2.5 rounded-xl bg-gradient-to-r from-cyan-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 text-white font-semibold text-xs transition-all shadow-md shadow-indigo-600/20 flex items-center justify-center gap-2"
          >
            <span>帶入此目標金額</span>
            <span className="font-mono font-bold">
              ({((monthlyExpense * 12) / (swr / 100) / 10000).toFixed(0)} 萬)
            </span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* 目標達成路徑拆解橫幅 (清晰透明展示：現有資產終值 vs 剩餘目標定額) */}
      <div className="glass-panel rounded-2xl p-4 sm:p-5 border border-indigo-500/25 bg-gradient-to-r from-indigo-950/40 via-slate-900/80 to-slate-950/90 space-y-3">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                公式透明解析
              </span>
              <h3 className="text-sm font-bold text-white flex items-center gap-1.5">
                目標資產路徑拆解（先將現有資產算終值，再推算差額定投）
              </h3>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              系統已將您現有的 <span className="text-white font-mono font-semibold">NT$ {(existingAsset / 10000).toLocaleString(undefined, { maximumFractionDigits: 1 })} 萬</span> 市值，
              以持股組合加權年化 <span className="text-indigo-300 font-mono font-bold">{result.effective_existing_cagr.toFixed(1)}%</span>
              {isRealMode && <span className="text-cyan-300">（實質購買力已扣通膨）</span>}
              複利成長 {targetYears} 年，
              預估屆時終值為 <span className="text-emerald-400 font-mono font-bold">NT$ {(result.existing_fv / 10000).toLocaleString(undefined, { maximumFractionDigits: 1 })} 萬</span>。
              {result.remaining > 0 && (
                <span className="text-slate-400 ml-1">
                  扣除終值後尚需補足 <strong className="text-amber-400 font-mono">NT$ {(result.remaining / 10000).toLocaleString(undefined, { maximumFractionDigits: 1 })} 萬</strong>，以定期定額預期年化 <strong className="text-indigo-300 font-mono">{result.effective_cagr.toFixed(1)}%</strong> 倒推每月定投額度。
                </span>
              )}
            </p>
          </div>

          {result.remaining === 0 ? (
            <div className="p-3 rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 text-xs flex items-center gap-2 shrink-0">
              <Sparkles className="w-4 h-4 shrink-0 text-emerald-400" />
              <span>
                🎉 現有持股終值已超越目標（{Math.round(result.existing_fv / 10000)}萬 ≥ {Math.round(targetAmount / 10000)}萬），無需再定投！
              </span>
            </div>
          ) : (
            <div className="flex items-center gap-3 bg-slate-900/90 px-3.5 py-2.5 rounded-xl border border-slate-800 shrink-0 text-xs font-mono">
              <div>
                <span className="text-slate-400 block text-[11px]">扣除終值後缺口</span>
                <span className="text-amber-400 font-bold text-sm">
                  NT$ {(result.remaining / 10000).toLocaleString(undefined, { maximumFractionDigits: 1 })} 萬
                </span>
              </div>
              <ArrowRight className="w-3.5 h-3.5 text-slate-600" />
              <div>
                <span className="text-slate-400 block text-[11px]">每月定額提撥</span>
                <span className="text-emerald-400 font-bold text-sm">
                  NT$ {result.monthly.toLocaleString()}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* 輔助單筆投入提示 */}
        <div className="text-[11px] text-slate-500 border-t border-slate-800/80 pt-2 flex items-center justify-between">
          <span>
            {result.lump_sum_today > 0 ? (
              <>💡 若不每月定投，今天直接一次性單筆到位需再投入 <strong className="text-slate-300 font-mono">NT$ {(result.lump_sum_today / 10000).toLocaleString(undefined, { maximumFractionDigits: 1 })} 萬元</strong></>
            ) : (
              <>💡 現有資產折現後已全額滿足目標現值，無需額外補入單筆本金</>
            )}
          </span>
          <span className="text-slate-600 font-mono hidden sm:inline">
            終值公式: FV = PV × (1 + r)^n
          </span>
        </div>
      </div>

      {/* 試算結果指標卡 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="每月需定期定額"
          value={result.monthly === 0 ? "已達標免定投" : `NT$ ${result.monthly.toLocaleString()}`}
          subLabel="扣除終值後缺口"
          subValue={`NT$ ${(result.remaining / 10000).toLocaleString(undefined, { maximumFractionDigits: 1 })} 萬`}
          icon={Calendar}
          badge={result.monthly === 0 ? "已達標" : `${targetYears}年共${targetYears * 12}期`}
          badgeColor={result.monthly === 0 ? "green" : "indigo"}
        />
        <MetricCard
          title="現有持股屆時終值"
          value={`NT$ ${(result.existing_fv / 10000).toLocaleString(undefined, {
            maximumFractionDigits: 1,
          })} 萬`}
          subLabel="持股加權年化"
          subValue={`${result.effective_existing_cagr.toFixed(1)}% (${targetYears}年複利)`}
          icon={Wallet}
          badge={`${Math.min(100, Math.round((result.existing_fv / targetAmount) * 100))}% 佔比`}
          badgeColor="cyan"
        />
        <MetricCard
          title="累計實付本金"
          value={`NT$ ${(
            (result.total_invested + existingAsset) /
            10000
          ).toLocaleString(undefined, { maximumFractionDigits: 1 })} 萬`}
          subLabel="含現有市值"
          subValue={`${(existingAsset / 10000).toFixed(0)} 萬`}
          icon={Coins}
          badge="自備資金"
          badgeColor="slate"
        />
        <MetricCard
          title="複利獲利收益"
          value={`NT$ ${(result.total_gain / 10000).toLocaleString(undefined, {
            maximumFractionDigits: 1,
          })} 萬`}
          subLabel="獲利佔比"
          subValue={`${gainRatio}%`}
          icon={TrendingUp}
          badge={isRealMode ? "實質純益" : "複利魔法"}
          badgeColor="green"
        />
      </div>

      {/* 複利資產成長階梯圖 */}
      <div className="glass-panel rounded-2xl p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h3 className="text-base font-semibold text-white">
              📈 資產複利累積軌跡 (本金 vs 獲利膨脹)
            </h3>
            <p className="text-xs text-slate-400">
              隨時間推移，藍色本金線維持平穩斜率，綠色獲利區塊呈現指數加速擴大
            </p>
          </div>
          <div className="flex items-center gap-4 text-xs font-mono">
            <span className="flex items-center gap-1.5 text-slate-400">
              <span className="w-3 h-3 rounded-sm bg-slate-600 inline-block" />
              累積投入本金
            </span>
            <span className="flex items-center gap-1.5 text-emerald-400">
              <span className="w-3 h-3 rounded-sm bg-emerald-500 inline-block" />
              累積複利獲利
            </span>
          </div>
        </div>

        <div className="h-80 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={trajectoryData}>
              <defs>
                <linearGradient id="gainGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.6} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0.1} />
                </linearGradient>
                <linearGradient id="principalGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#475569" stopOpacity={0.6} />
                  <stop offset="95%" stopColor="#475569" stopOpacity={0.2} />
                </linearGradient>
              </defs>
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
                formatter={(val: any, name: any) => [
                  `${val} 萬元`,
                  name === "principal" ? "累積本金" : name === "gain" ? "累積獲利" : "總資產",
                ]}
                labelFormatter={(l) => `第 ${l} 年`}
              />
              <Area
                type="monotone"
                dataKey="principal"
                stackId="1"
                stroke="#64748b"
                fill="url(#principalGradient)"
              />
              <Area
                type="monotone"
                dataKey="gain"
                stackId="1"
                stroke="#10b981"
                fill="url(#gainGradient)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};
