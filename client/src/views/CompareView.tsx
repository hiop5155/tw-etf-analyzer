import React, { useState, useEffect } from "react";
import {
  TrendingUp,
  Plus,
  Trash2,
  Scale,
  Calendar,
  Grid,
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
} from "recharts";
import { useApp } from "../context/AppContext";
import { fetchAdjustedPrices, fetchStockInfo } from "../services/api";
import { ETFCompareRecord, PricePoint } from "../core/types";
import { calcCorrelationMatrix } from "../core/metrics";
import { calcMultiCompare } from "../core/performance";

const COLORS = [
  "#6366f1", // indigo
  "#06b6d4", // cyan
  "#10b981", // emerald
  "#f59e0b", // amber
  "#ec4899", // pink
  "#8b5cf6", // purple
  "#3b82f6", // blue
];

export const CompareView: React.FC = () => {
  const { compareStocks, setCompareStocks, monthlyDca } = useApp();

  const [inputCode, setInputCode] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [compareRecords, setCompareRecords] = useState<ETFCompareRecord[]>([]);
  const [corrMatrix, setCorrMatrix] = useState<{
    ids: string[];
    matrix: number[][];
  }>({ ids: [], matrix: [] });

  // 載入多檔標的數據
  useEffect(() => {
    let isMounted = true;
    async function loadMultiData() {
      if (compareStocks.length < 2) return;
      setLoading(true);
      setError(null);
      try {
        const closeMap: Record<string, PricePoint[]> = {};
        const nameMap: Record<string, string> = {};

        await Promise.all(
          compareStocks.map(async (id) => {
            const [prices, info] = await Promise.all([
              fetchAdjustedPrices(id),
              fetchStockInfo(id),
            ]);
            if (prices.length >= 2) {
              closeMap[id] = prices;
              nameMap[id] = info.stock_name;
            }
          })
        );

        if (!isMounted) return;

        const records = calcMultiCompare(closeMap, nameMap, monthlyDca);
        const matrix = calcCorrelationMatrix(closeMap);

        setCompareRecords(records);
        setCorrMatrix(matrix);
      } catch (err: any) {
        if (isMounted) setError(err.message || "多檔標的載入失敗");
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    loadMultiData();
    return () => {
      isMounted = false;
    };
  }, [compareStocks, monthlyDca]);

  const handleAddStock = (e: React.FormEvent) => {
    e.preventDefault();
    const clean = inputCode.trim().toUpperCase();
    if (clean && !compareStocks.includes(clean)) {
      setCompareStocks([...compareStocks, clean]);
      setInputCode("");
    }
  };

  const handleRemoveStock = (id: string) => {
    if (compareStocks.length > 2) {
      setCompareStocks(compareStocks.filter((s) => s !== id));
    }
  };

  // 整合 Recharts 時間序列圖表數據 (基期 100)
  const chartData = React.useMemo(() => {
    if (compareRecords.length === 0) return [];
    const dateMap = new Map<string, Record<string, number>>();

    for (const r of compareRecords) {
      for (const p of r.normalized) {
        if (!dateMap.has(p.date)) {
          dateMap.set(p.date, { date: p.date as any });
        }
        dateMap.get(p.date)![r.stock_id] = p.close;
      }
    }

    const sortedDates = Array.from(dateMap.keys()).sort();
    return sortedDates.map((d) => dateMap.get(d)!);
  }, [compareRecords]);

  return (
    <div className="space-y-6">
      {/* 標題與標的標籤列 */}
      <div className="glass-panel rounded-2xl p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
              📈 多檔 ETF 走勢疊圖與相關係數分析
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              自動依「最晚成立標的之上市日」精確切齊共同歷史，消除時間偏誤
            </p>
          </div>

          {/* 新增標的輸入框 */}
          <form onSubmit={handleAddStock} className="flex items-center gap-1.5">
            <input
              type="text"
              placeholder="新增代號 (如 00713)"
              value={inputCode}
              onChange={(e) => setInputCode(e.target.value)}
              className="w-36 bg-slate-900 border border-slate-700 px-3 py-1.5 rounded-xl text-xs text-white uppercase font-mono focus:outline-none focus:border-indigo-500"
            />
            <button
              type="submit"
              className="p-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold"
            >
              <Plus className="w-4 h-4" />
            </button>
          </form>
        </div>

        {/* 標籤清單 */}
        <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-800">
          {compareStocks.map((id, idx) => (
            <div
              key={id}
              className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900/80 border border-slate-700 text-xs font-mono"
            >
              <span
                className="w-2.5 h-2.5 rounded-full"
                style={{ backgroundColor: COLORS[idx % COLORS.length] }}
              />
              <span className="font-bold text-white">{id}</span>
              {compareStocks.length > 2 && (
                <button
                  onClick={() => handleRemoveStock(id)}
                  className="text-slate-500 hover:text-rose-400"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              )}
            </div>
          ))}
        </div>
      </div>

      {loading && (
        <div className="glass-panel rounded-2xl p-16 flex flex-col items-center justify-center gap-3">
          <Loader2 className="w-8 h-8 text-indigo-400 animate-spin" />
          <p className="text-sm text-slate-300 font-medium">
            正在安全對齊各檔標的歷史收盤資料與相關矩陣...
          </p>
        </div>
      )}

      {error && !loading && (
        <div className="glass-panel rounded-2xl p-6 border-rose-500/30 bg-rose-950/20 flex items-center gap-3 text-rose-300">
          <AlertCircle className="w-5 h-5 text-rose-400 shrink-0" />
          <span className="text-sm">{error}</span>
        </div>
      )}

      {!loading && !error && compareRecords.length > 0 && (
        <>
          {/* 共同起點標準化走勢圖 (基期 100) */}
          <div className="glass-panel rounded-2xl p-5 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <h3 className="text-base font-semibold text-white">
                  📊 共同起點還原走勢疊圖 (基期 = 100)
                </h3>
                <p className="text-xs text-slate-400">
                  共同起始日期: {compareRecords[0]?.common_start} (共{" "}
                  {compareRecords[0]?.years} 年)
                </p>
              </div>
            </div>

            <div className="h-80 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.3} />
                  <XAxis
                    dataKey="date"
                    stroke="#64748b"
                    tick={{ fontSize: 11 }}
                    minTickGap={50}
                  />
                  <YAxis
                    stroke="#64748b"
                    tick={{ fontSize: 11 }}
                    domain={["auto", "auto"]}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#0f172a",
                      borderColor: "#334155",
                      borderRadius: "12px",
                      color: "#fff",
                      fontSize: "12px",
                    }}
                    labelFormatter={(l) => `日期: ${l}`}
                  />
                  <Legend />
                  {compareRecords.map((r, idx) => (
                    <Line
                      key={r.stock_id}
                      type="monotone"
                      dataKey={r.stock_id}
                      stroke={COLORS[idx % COLORS.length]}
                      strokeWidth={2}
                      dot={false}
                      name={`${r.stock_id} ${r.name}`}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* 各標的績效排行榜表格 */}
          <div className="glass-panel rounded-2xl p-5 space-y-3">
            <h3 className="text-base font-semibold text-white">🏆 共同區間績效指標綜合排行</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400">
                    <th className="py-2.5 px-3">標的名稱</th>
                    <th className="py-2.5 px-3">上市起始日</th>
                    <th className="py-2.5 px-3 text-right">累計總報酬 %</th>
                    <th className="py-2.5 px-3 text-right">年化報酬 (CAGR)</th>
                    <th className="py-2.5 px-3 text-right">DCA 期末市值 (萬)</th>
                    <th className="py-2.5 px-3 text-right">DCA 年化報酬</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-slate-200">
                  {compareRecords.map((r, idx) => (
                    <tr key={r.stock_id} className="hover:bg-slate-800/40">
                      <td className="py-2.5 px-3 font-semibold text-white flex items-center gap-2">
                        <span
                          className="w-2.5 h-2.5 rounded-full shrink-0"
                          style={{ backgroundColor: COLORS[idx % COLORS.length] }}
                        />
                        <span>
                          {r.stock_id} {r.name}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-slate-400">{r.inception_date}</td>
                      <td className="py-2.5 px-3 text-right font-bold text-emerald-400">
                        +{r.total_return_pct.toFixed(1)}%
                      </td>
                      <td className="py-2.5 px-3 text-right font-bold text-indigo-400 text-sm">
                        +{r.cagr_pct.toFixed(2)}%
                      </td>
                      <td className="py-2.5 px-3 text-right text-cyan-300 font-bold">
                        {(r.dca_final / 10000).toLocaleString(undefined, {
                          maximumFractionDigits: 1,
                        })}{" "}
                        萬
                      </td>
                      <td className="py-2.5 px-3 text-right text-slate-300">
                        +{r.dca_cagr_pct.toFixed(2)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* 月報酬相關係數矩陣熱圖 */}
          {corrMatrix.matrix.length > 0 && (
            <div className="glass-panel rounded-2xl p-5 space-y-3">
              <div>
                <h3 className="text-base font-semibold text-white flex items-center gap-2">
                  <Grid className="w-4 h-4 text-indigo-400" /> 月報酬相關係數矩陣 (Correlation
                  Matrix)
                </h3>
                <p className="text-xs text-slate-400">
                  數值介於 -1.0 到 +1.0。數值越低代表兩檔標的互補性越佳，能大幅發揮降波動之資產配置效果。
                </p>
              </div>

              <div className="overflow-x-auto pt-2">
                <table className="text-center text-xs font-mono">
                  <thead>
                    <tr>
                      <th className="p-2 text-left text-slate-400">代號</th>
                      {corrMatrix.ids.map((id) => (
                        <th key={id} className="p-2 font-bold text-slate-300">
                          {id}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {corrMatrix.ids.map((idX, i) => (
                      <tr key={idX}>
                        <td className="p-2 text-left font-bold text-slate-300">{idX}</td>
                        {corrMatrix.ids.map((idY, j) => {
                          const val = corrMatrix.matrix[i]?.[j] ?? 0;
                          // 根據相關度給予色彩 (高: 橘/紅, 中: 藍, 低/負: 綠)
                          let bg = "bg-slate-800/80";
                          let text = "text-slate-300";
                          if (i === j) {
                            bg = "bg-slate-800 text-slate-500";
                          } else if (val >= 0.8) {
                            bg = "bg-rose-500/20 text-rose-300 font-bold";
                          } else if (val >= 0.5) {
                            bg = "bg-amber-500/20 text-amber-300";
                          } else if (val >= 0) {
                            bg = "bg-cyan-500/20 text-cyan-300";
                          } else {
                            bg = "bg-emerald-500/25 text-emerald-300 font-bold";
                          }

                          return (
                            <td key={idY} className="p-1">
                              <div className={`p-2 rounded-lg ${bg} transition-colors`}>
                                {val.toFixed(2)}
                              </div>
                            </td>
                          );
                        })}
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
