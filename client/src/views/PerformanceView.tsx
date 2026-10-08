import React, { useState, useEffect } from "react";
import {
  TrendingUp,
  Percent,
  Activity,
  ArrowDownRight,
  ShieldCheck,
  Calendar,
  Wallet,
  DollarSign,
  Loader2,
  AlertCircle,
} from "lucide-react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  BarChart,
  Bar,
  Legend,
} from "recharts";
import { useApp } from "../context/AppContext";
import { fetchAdjustedPrices, fetchStockInfo } from "../services/api";
import { PricePoint, RiskMetrics, ComparisonResult } from "../core/types";
import { calcRiskMetrics } from "../core/metrics";
import { calcComparison } from "../core/performance";
import { NumericInput } from "../components/NumericInput";
import { MetricCard } from "../components/MetricCard";

const POPULAR_STOCKS = [
  { id: "0050", label: "0050 元大台灣50" },
  { id: "0056", label: "0056 元大高股息" },
  { id: "00878", label: "00878 國泰永續高股息" },
  { id: "006208", label: "006208 富邦台50" },
  { id: "00713", label: "00713 元大高息低波" },
  { id: "00919", label: "00919 群益精選高息" },
  { id: "2330", label: "2330 台積電" },
];

export const PerformanceView: React.FC = () => {
  const { selectedStock, setSelectedStock, monthlyDca, setMonthlyDca } = useApp();

  const [inputStock, setInputStock] = useState(selectedStock);
  const [stockName, setStockName] = useState("");
  const [prices, setPrices] = useState<PricePoint[]>([]);
  const [metrics, setMetrics] = useState<RiskMetrics | null>(null);
  const [comparison, setComparison] = useState<ComparisonResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 載入股價與計算指標
  useEffect(() => {
    let isMounted = true;
    async function loadData() {
      setLoading(true);
      setError(null);
      try {
        const [priceData, infoData] = await Promise.all([
          fetchAdjustedPrices(selectedStock),
          fetchStockInfo(selectedStock),
        ]);

        if (!isMounted) return;

        if (!priceData || priceData.length < 2) {
          setError(`查無 ${selectedStock} 足夠歷史股價資料`);
          setLoading(false);
          return;
        }

        setPrices(priceData);
        setStockName(infoData.stock_name);

        // 核心財務計算 (純前端毫秒級完成)
        const risk = calcRiskMetrics(priceData);
        const comp = calcComparison(priceData, monthlyDca);

        setMetrics(risk);
        setComparison(comp);
      } catch (err: any) {
        if (isMounted) {
          setError(err.message || "載入資料失敗");
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    loadData();
    return () => {
      isMounted = false;
    };
  }, [selectedStock, monthlyDca]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputStock.trim()) {
      setSelectedStock(inputStock.trim().toUpperCase());
    }
  };

  // 生成水下回撤序列 (Underwater Drawdown)
  const drawdownData = React.useMemo(() => {
    if (prices.length === 0) return [];
    let max = -Infinity;
    return prices.map((p) => {
      if (p.close > max) max = p.close;
      const dd = max > 0 ? ((p.close - max) / max) * 100 : 0;
      return {
        date: p.date,
        drawdown: Math.round(dd * 10) / 10,
      };
    });
  }, [prices]);

  return (
    <div className="space-y-6">
      {/* 標的選擇列與定期定額控制 */}
      <div className="glass-panel rounded-2xl p-4 sm:p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
        {/* 常用標的快速點擊膠囊 */}
        <div className="flex flex-wrap items-center gap-2">
          {POPULAR_STOCKS.map((s) => (
            <button
              key={s.id}
              onClick={() => {
                setSelectedStock(s.id);
                setInputStock(s.id);
              }}
              className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all ${
                selectedStock === s.id
                  ? "bg-indigo-600 text-white font-semibold shadow-md shadow-indigo-600/30"
                  : "bg-slate-800/80 hover:bg-slate-700/80 text-slate-300 border border-slate-700/50"
              }`}
            >
              {s.label}
            </button>
          ))}

          {/* 自訂代號搜尋輸入框 */}
          <form onSubmit={handleSearch} className="flex items-center gap-1.5 ml-1">
            <input
              type="text"
              placeholder="自訂代號 (如 00687B)"
              value={inputStock}
              onChange={(e) => setInputStock(e.target.value)}
              className="w-36 bg-slate-900 border border-slate-700 px-3 py-1.5 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 uppercase font-mono"
            />
            <button
              type="submit"
              className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-indigo-400 rounded-xl text-xs font-medium border border-slate-700"
            >
              查詢
            </button>
          </form>
        </div>

        {/* 定期定額投入額度設定 */}
        <div className="flex items-center gap-3 bg-slate-900/80 px-4 py-2 rounded-xl border border-slate-800">
          <DollarSign className="w-4 h-4 text-emerald-400 shrink-0" />
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400 whitespace-nowrap">每月定期定額:</span>
            <NumericInput
              value={monthlyDca}
              min={500}
              onCommit={(val) => setMonthlyDca(val)}
              placeholder="20000"
              className="w-24 bg-slate-800 border border-slate-700 px-2 py-1 rounded text-xs font-mono font-bold text-white text-right focus:outline-none focus:border-indigo-500"
            />
            <span className="text-xs text-slate-400">元</span>
          </div>
        </div>
      </div>

      {loading && (
        <div className="glass-panel rounded-2xl p-16 flex flex-col items-center justify-center gap-3">
          <Loader2 className="w-8 h-8 text-indigo-400 animate-spin" />
          <p className="text-sm text-slate-300 font-medium">
            正在安全載入 {selectedStock} 歷史除權息還原資料...
          </p>
        </div>
      )}

      {error && !loading && (
        <div className="glass-panel rounded-2xl p-6 border-rose-500/30 bg-rose-950/20 flex items-center gap-3 text-rose-300">
          <AlertCircle className="w-5 h-5 text-rose-400 shrink-0" />
          <span className="text-sm">{error}</span>
        </div>
      )}

      {!loading && !error && metrics && comparison && (
        <>
          {/* 標的資訊標題卡 */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 px-1">
            <div className="flex items-center gap-3">
              <h2 className="text-2xl font-bold text-white tracking-tight">
                {selectedStock} {stockName}
              </h2>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                已還原除權息 (Total Return)
              </span>
            </div>
            <p className="text-xs text-slate-400 font-mono">
              區間: {prices[0]?.date} ~ {prices[prices.length - 1]?.date} (共{" "}
              {comparison.lump.years.toFixed(1)} 年 / {prices.length.toLocaleString()} 個交易日)
            </p>
          </div>

          {/* 核心指標卡片格 (CAGR, MDD, Volatility, Sharpe, Sortino) */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 sm:gap-4">
            <MetricCard
              title="年化報酬 (CAGR)"
              value={`${metrics.cagr_pct > 0 ? "+" : ""}${metrics.cagr_pct.toFixed(2)}%`}
              subLabel="總報酬"
              subValue={`${comparison.lump.total_return_pct.toFixed(1)}%`}
              icon={TrendingUp}
              badge="複利年化"
              badgeColor="green"
            />
            <MetricCard
              title="年化波動度"
              value={`${metrics.vol_pct.toFixed(2)}%`}
              subLabel="日 log return"
              subValue="× √252"
              icon={Activity}
              badge="風險值"
              badgeColor="amber"
            />
            <MetricCard
              title="最大回撤 (MDD)"
              value={`${metrics.mdd_pct.toFixed(2)}%`}
              subLabel="波谷"
              subValue={metrics.mdd_trough_date || "—"}
              icon={ArrowDownRight}
              badge="歷史最慘"
              badgeColor="red"
            />
            <MetricCard
              title="夏普值 (Sharpe)"
              value={metrics.sharpe.toFixed(2)}
              subLabel="超額/波動"
              subValue="Rf=0%"
              icon={ShieldCheck}
              badge={metrics.sharpe > 0.8 ? "優秀" : "一般"}
              badgeColor="indigo"
            />
            <MetricCard
              title="索提諾 (Sortino)"
              value={metrics.sortino.toFixed(2)}
              subLabel="下行風險"
              subValue="超額/下行"
              icon={Percent}
              badge="防禦力"
              badgeColor="indigo"
            />
            <MetricCard
              title="卡瑪比率 (Calmar)"
              value={metrics.calmar.toFixed(2)}
              subLabel="CAGR / |MDD|"
              subValue={metrics.calmar > 0.5 ? "穩健" : "偏弱"}
              icon={Wallet}
              badge="性價比"
              badgeColor="slate"
            />
          </div>

          {/* 歷史還原價格走勢圖表 */}
          <div className="glass-panel rounded-2xl p-5 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-semibold text-white">📈 還原收盤價歷史走勢</h3>
                <p className="text-xs text-slate-400">
                  將歷史所有現金股息與股票股利完整再投入回溯計算
                </p>
              </div>
              <div className="text-right">
                <span className="text-xs text-slate-400 block">最新還原價格</span>
                <span className="text-lg font-bold font-mono text-emerald-400">
                  {prices[prices.length - 1]?.close.toFixed(2)} 元
                </span>
              </div>
            </div>

            <div className="h-80 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={prices}>
                  <defs>
                    <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#6366f1" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#6366f1" stopOpacity={0.0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.4} />
                  <XAxis
                    dataKey="date"
                    stroke="#64748b"
                    tick={{ fontSize: 11 }}
                    minTickGap={60}
                  />
                  <YAxis
                    domain={["auto", "auto"]}
                    stroke="#64748b"
                    tick={{ fontSize: 11 }}
                    tickFormatter={(v) => `$${v}`}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#0f172a",
                      borderColor: "#334155",
                      borderRadius: "12px",
                      color: "#fff",
                      fontSize: "12px",
                    }}
                    formatter={(val: any) => [`${val} 元`, "還原收盤價"]}
                    labelFormatter={(label) => `日期: ${label}`}
                  />
                  <Area
                    type="monotone"
                    dataKey="close"
                    stroke="#6366f1"
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#priceGradient)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* 水下回撤圖 (Underwater Chart) */}
          <div className="glass-panel rounded-2xl p-5 space-y-3">
            <div>
              <h3 className="text-base font-semibold text-white">🌊 水下回撤歷程 (Drawdown)</h3>
              <p className="text-xs text-slate-400">
                顯示歷史自波段高點滑落之幅度，低於 0% 為處於回撤修復階段
              </p>
            </div>

            <div className="h-48 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={drawdownData}>
                  <defs>
                    <linearGradient id="ddGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.05} />
                      <stop offset="95%" stopColor="#f43f5e" stopOpacity={0.4} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.3} />
                  <XAxis
                    dataKey="date"
                    stroke="#64748b"
                    tick={{ fontSize: 11 }}
                    minTickGap={60}
                  />
                  <YAxis
                    domain={[-60, 0]}
                    stroke="#64748b"
                    tick={{ fontSize: 11 }}
                    tickFormatter={(v) => `${v}%`}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#0f172a",
                      borderColor: "#334155",
                      borderRadius: "12px",
                      color: "#fff",
                      fontSize: "12px",
                    }}
                    formatter={(val: any) => [`${val}%`, "回撤幅度"]}
                  />
                  <Area
                    type="monotone"
                    dataKey="drawdown"
                    stroke="#f43f5e"
                    strokeWidth={1.5}
                    fillOpacity={1}
                    fill="url(#ddGradient)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* 定期定額 (DCA) 逐年累積柱狀圖與損益表 */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* 左側 2 欄: 逐年累積柱狀圖 */}
            <div className="lg:col-span-2 glass-panel rounded-2xl p-5 space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-base font-semibold text-white">
                    📊 定期定額逐年累積本金 vs 總資產
                  </h3>
                  <p className="text-xs text-slate-400">
                    每月定期定額投入 NT$ {monthlyDca.toLocaleString()} 元之長線複利效果
                  </p>
                </div>
                <div className="text-right">
                  <span className="text-xs text-slate-400 block">期末總市值</span>
                  <span className="text-lg font-bold font-mono text-cyan-400">
                    {(comparison.dca.final.value / 10000).toLocaleString(undefined, {
                      maximumFractionDigits: 1,
                    })}{" "}
                    萬元
                  </span>
                </div>
              </div>

              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={comparison.dca.years}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.3} />
                    <XAxis dataKey="year" stroke="#64748b" tick={{ fontSize: 11 }} />
                    <YAxis
                      stroke="#64748b"
                      tick={{ fontSize: 11 }}
                      tickFormatter={(v) => `${(v / 10000).toFixed(0)}萬`}
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
                        `${(val / 10000).toLocaleString(undefined, {
                          maximumFractionDigits: 1,
                        })} 萬元`,
                        name === "cost_cum" ? "累積投入本金" : "期末總市值",
                      ]}
                    />
                    <Legend
                      formatter={(value) =>
                        value === "cost_cum" ? "累積投入本金" : "期末總市值"
                      }
                    />
                    <Bar dataKey="cost_cum" fill="#475569" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="value" fill="#06b6d4" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* 右側 1 欄: 單筆 vs DCA 對比卡 */}
            <div className="glass-panel rounded-2xl p-5 flex flex-col justify-between space-y-4">
              <div>
                <h3 className="text-base font-semibold text-white mb-1">
                  ⚖️ 單筆 vs 定期定額比較
                </h3>
                <p className="text-xs text-slate-400 mb-4">
                  假設投入相同本金 (NT$ {comparison.dca.final.cost_cum.toLocaleString()} 元)
                </p>

                <div className="space-y-4">
                  <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
                    <div className="flex justify-between items-center mb-1">
                      <span className="text-xs font-semibold text-slate-300">
                        定期定額 (DCA)
                      </span>
                      <span className="text-xs font-bold text-cyan-400 font-mono">
                        CAGR {comparison.dca_cagr_pct.toFixed(2)}%
                      </span>
                    </div>
                    <div className="text-xl font-bold font-mono text-white">
                      {(comparison.dca.final.value / 10000).toFixed(1)} 萬元
                    </div>
                    <div className="text-xs text-slate-400 mt-1">
                      獲利 +{(comparison.dca.final.gain / 10000).toFixed(1)} 萬 (+
                      {comparison.dca.final.return_pct.toFixed(1)}%)
                    </div>
                  </div>

                  <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
                    <div className="flex justify-between items-center mb-1">
                      <span className="text-xs font-semibold text-slate-300">
                        期初單筆投入 (Lump Sum)
                      </span>
                      <span className="text-xs font-bold text-indigo-400 font-mono">
                        CAGR {comparison.lump_same_cost_cagr.toFixed(2)}%
                      </span>
                    </div>
                    <div className="text-xl font-bold font-mono text-white">
                      {(comparison.lump_same_cost_final / 10000).toFixed(1)} 萬元
                    </div>
                    <div className="text-xs text-slate-400 mt-1">
                      獲利 +
                      {(
                        (comparison.lump_same_cost_final - comparison.dca.final.cost_cum) /
                        10000
                      ).toFixed(1)}{" "}
                      萬 (+{comparison.lump_same_cost_ret.toFixed(1)}%)
                    </div>
                  </div>
                </div>
              </div>

              <div className="text-[11px] text-slate-500 leading-relaxed bg-slate-950/40 p-3 rounded-lg border border-slate-800/60">
                💡 統計經驗：在長期多頭市場中，單筆資金由於資金全時參與市場複利，終端金額通常高於分批定額；但在高檔震盪或熊市時，定期定額能大幅分散擇時風險。
              </div>
            </div>
          </div>

          {/* DCA 逐年明細表格 */}
          <div className="glass-panel rounded-2xl p-5 space-y-3 overflow-hidden">
            <h3 className="text-base font-semibold text-white">📋 定期定額歷年累積數據表</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400">
                    <th className="py-2.5 px-3">年份</th>
                    <th className="py-2.5 px-3 text-right">累計投入本金</th>
                    <th className="py-2.5 px-3 text-right">期末市值</th>
                    <th className="py-2.5 px-3 text-right">累計損益</th>
                    <th className="py-2.5 px-3 text-right">累積報酬率 %</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-slate-200">
                  {comparison.dca.years.map((y) => (
                    <tr key={y.year} className="hover:bg-slate-800/40 transition-colors">
                      <td className="py-2.5 px-3 font-semibold text-white whitespace-nowrap">{y.year}</td>
                      <td className="py-2.5 px-3 text-right text-slate-400 whitespace-nowrap font-mono">
                        {y.cost_cum.toLocaleString()} 元
                      </td>
                      <td className="py-2.5 px-3 text-right font-semibold text-cyan-300 whitespace-nowrap font-mono">
                        {y.value.toLocaleString()} 元
                      </td>
                      <td
                        className={`py-2.5 px-3 text-right font-semibold whitespace-nowrap font-mono ${
                          y.gain >= 0 ? "text-emerald-400" : "text-rose-400"
                        }`}
                      >
                        {y.gain >= 0 ? "+" : ""}
                        {y.gain.toLocaleString()} 元
                      </td>
                      <td
                        className={`py-2.5 px-3 text-right font-bold whitespace-nowrap font-mono ${
                          y.return_pct >= 0 ? "text-emerald-400" : "text-rose-400"
                        }`}
                      >
                        {y.return_pct >= 0 ? "+" : ""}
                        {y.return_pct.toFixed(2)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
