import React, { useState, useEffect, useMemo } from "react";
import {
  Coins,
  Receipt,
  ShieldCheck,
  TrendingUp,
  Percent,
  Calendar,
  Calculator,
  Loader2,
  AlertCircle,
} from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";
import { useApp } from "../context/AppContext";
import { fetchDividends, fetchStockInfo, fetchAdjustedPrices } from "../services/api";
import { DividendRecord } from "../core/types";
import {
  effectiveDividendTaxRate,
  dividendNetRatio,
} from "../core/tax";
import { NHI_RATE, NHI_THRESHOLD } from "../core/constants";
import { NumericInput } from "../components/NumericInput";
import { MetricCard } from "../components/MetricCard";

export const DividendView: React.FC = () => {
  const { selectedStock, setSelectedStock, taxConfig } = useApp();

  const [inputCode, setInputCode] = useState(selectedStock);
  const [stockName, setStockName] = useState("");
  const [dividends, setDividends] = useState<DividendRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 稅務試算持有張數與所得稅級距
  const [holdingLots, setHoldingLots] = useState<number>(30); // 30 張 (30,000 股)
  const [taxBracket, setTaxBracket] = useState<number>(taxConfig.income_tax_bracket);

  useEffect(() => {
    let isMounted = true;
    async function loadDivData() {
      setLoading(true);
      setError(null);
      try {
        const [divData, infoData] = await Promise.all([
          fetchDividends(selectedStock),
          fetchStockInfo(selectedStock),
        ]);

        if (!isMounted) return;

        setDividends(divData);
        setStockName(infoData.stock_name);
      } catch (err: any) {
        if (isMounted) setError(err.message || "股利資料載入失敗");
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    loadDivData();
    return () => {
      isMounted = false;
    };
  }, [selectedStock]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputCode.trim()) {
      setSelectedStock(inputCode.trim().toUpperCase());
    }
  };

  // 依年度聚合現金股利加總
  const annualDividends = useMemo(() => {
    const map = new Map<number, { year: number; totalDiv: number; avgYield: number; count: number }>();
    for (const d of dividends) {
      if (!map.has(d.year)) {
        map.set(d.year, { year: d.year, totalDiv: 0, avgYield: 0, count: 0 });
      }
      const item = map.get(d.year)!;
      item.totalDiv += d.cash_dividend;
      item.avgYield += d.yield_pct;
      item.count += 1;
    }

    const list = Array.from(map.values()).map((item) => ({
      year: item.year,
      totalDiv: Math.round(item.totalDiv * 100) / 100,
      avgYield: Math.round((item.avgYield / item.count) * 10) / 10,
    }));

    return list.sort((a, b) => a.year - b.year);
  }, [dividends]);

  // 最新一次配息資料
  const latestDiv = dividends.length > 0 ? dividends[dividends.length - 1] : null;

  // 試算持股張數下的稅務試算
  const taxSim = useMemo(() => {
    if (!latestDiv) return null;
    const totalShares = holdingLots * 1000;
    const grossDividend = totalShares * latestDiv.cash_dividend;

    // 二代健保判斷
    const isNhiTriggered = grossDividend >= NHI_THRESHOLD;
    const nhiFee = isNhiTriggered ? Math.round(grossDividend * NHI_RATE) : 0;

    // 綜合所得稅
    const [effRate, method] = effectiveDividendTaxRate(grossDividend, taxBracket);
    const incomeTax = Math.round(grossDividend * effRate);

    const netReceived = grossDividend - nhiFee - incomeTax;
    const effectiveTotalRate =
      grossDividend > 0
        ? Math.round(((nhiFee + incomeTax) / grossDividend) * 1000) / 10
        : 0;

    return {
      grossDividend: Math.round(grossDividend),
      isNhiTriggered,
      nhiFee,
      method,
      incomeTax,
      netReceived: Math.round(netReceived),
      effectiveTotalRate,
    };
  }, [latestDiv, holdingLots, taxBracket]);

  return (
    <div className="space-y-6">
      {/* 標的選擇與搜尋列 */}
      <div className="glass-panel rounded-2xl p-4 sm:p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-2">
          {["0056", "00878", "00713", "00919", "0050", "2330"].map((id) => (
            <button
              key={id}
              onClick={() => {
                setSelectedStock(id);
                setInputCode(id);
              }}
              className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all ${
                selectedStock === id
                  ? "bg-indigo-600 text-white font-semibold"
                  : "bg-slate-800 text-slate-300 hover:bg-slate-700"
              }`}
            >
              {id}
            </button>
          ))}

          <form onSubmit={handleSearch} className="flex items-center gap-1.5 ml-1">
            <input
              type="text"
              placeholder="輸入股票代號"
              value={inputCode}
              onChange={(e) => setInputCode(e.target.value)}
              className="w-32 bg-slate-900 border border-slate-700 px-3 py-1.5 rounded-xl text-xs text-white uppercase font-mono"
            />
            <button
              type="submit"
              className="px-3 py-1.5 bg-slate-800 text-indigo-400 rounded-xl text-xs font-semibold"
            >
              查詢
            </button>
          </form>
        </div>

        <div className="text-right">
          <span className="text-sm font-bold text-white">
            {selectedStock} {stockName}
          </span>
          <span className="text-xs text-slate-400 block font-mono">
            共 {dividends.length} 次除權息歷史紀錄
          </span>
        </div>
      </div>

      {loading && (
        <div className="glass-panel rounded-2xl p-16 flex flex-col items-center justify-center gap-3">
          <Loader2 className="w-8 h-8 text-indigo-400 animate-spin" />
          <p className="text-sm text-slate-300 font-medium">
            正在載入 {selectedStock} 歷年除權息紀錄...
          </p>
        </div>
      )}

      {error && !loading && (
        <div className="glass-panel rounded-2xl p-6 border-rose-500/30 bg-rose-950/20 flex items-center gap-3 text-rose-300">
          <AlertCircle className="w-5 h-5 text-rose-400 shrink-0" />
          <span className="text-sm">{error}</span>
        </div>
      )}

      {!loading && !error && dividends.length > 0 && (
        <>
          {/* 歷年配息柱狀圖 */}
          <div className="glass-panel rounded-2xl p-5 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-semibold text-white">
                  💰 歷年現金股利發放總額 (每股 TWD)
                </h3>
                <p className="text-xs text-slate-400">
                  統計各年度發放之現金股利加總 (青色) 與年均單次現金殖利率 % (黃色)
                </p>
              </div>
            </div>

            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={annualDividends}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.3} />
                  <XAxis dataKey="year" stroke="#64748b" tick={{ fontSize: 11 }} />
                  <YAxis
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
                    formatter={(val: any, name: any) => [
                      name === "totalDiv" ? `${val} 元/股` : `${val}%`,
                      name === "totalDiv" ? "每股總股息" : "平均殖利率",
                    ]}
                  />
                  <Legend />
                  <Bar
                    dataKey="totalDiv"
                    fill="#06b6d4"
                    name="每股現金股息"
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* 台灣稅制精算器 (二代健保 + 綜所稅 8.5% 扣抵) */}
          {taxSim && latestDiv && (
            <div className="glass-panel rounded-2xl p-5 space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
                <div>
                  <h3 className="text-base font-semibold text-white flex items-center gap-2">
                    <Receipt className="w-4 h-4 text-emerald-400" /> 台灣股利所得稅與二代健保試算器
                  </h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    以最新單次配息 (每股 NT$ {latestDiv.cash_dividend.toFixed(2)} 元) 精算實際到手金額
                  </p>
                </div>

                {/* 張數與稅級選擇 */}
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-2 bg-slate-900 px-3 py-1.5 rounded-xl border border-slate-800">
                    <span className="text-xs text-slate-400">持有張數:</span>
                    <NumericInput
                      value={holdingLots}
                      min={1}
                      onCommit={(val) => setHoldingLots(val)}
                      placeholder="1"
                      className="w-16 bg-slate-800 text-xs font-mono font-bold text-white px-2 py-0.5 rounded text-right focus:outline-none focus:border-indigo-500"
                    />
                    <span className="text-xs text-slate-400">張</span>
                  </div>

                  <div className="flex items-center gap-2 bg-slate-900 px-3 py-1.5 rounded-xl border border-slate-800">
                    <span className="text-xs text-slate-400">綜所稅級距:</span>
                    <select
                      value={taxBracket}
                      onChange={(e) => setTaxBracket(parseFloat(e.target.value))}
                      className="bg-slate-800 text-xs text-white px-2 py-0.5 rounded"
                    >
                      <option value={0.05}>5% (享8.5%退稅)</option>
                      <option value={0.12}>12% (一般)</option>
                      <option value={0.20}>20%</option>
                      <option value={0.30}>30% (分離課稅28%)</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* 試算卡片成果 */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 pt-1">
                <MetricCard
                  title="應領毛股利 (Gross)"
                  value={`NT$ ${taxSim.grossDividend.toLocaleString()}`}
                  subLabel="持股股數"
                  subValue={`${(holdingLots * 1000).toLocaleString()} 股`}
                  icon={Coins}
                  badge="未扣稅費"
                  badgeColor="slate"
                />
                <MetricCard
                  title="二代健保補充保費 (2.11%)"
                  value={
                    taxSim.isNhiTriggered
                      ? `-NT$ ${taxSim.nhiFee.toLocaleString()}`
                      : "免扣繳 (NT$ 0)"
                  }
                  subLabel="起扣門檻"
                  subValue="單次 ≥ 20,000 元"
                  icon={ShieldCheck}
                  badge={taxSim.isNhiTriggered ? "已達門檻" : "未達門檻"}
                  badgeColor={taxSim.isNhiTriggered ? "amber" : "green"}
                />
                <MetricCard
                  title="所得稅 (8.5%抵減 vs 分離28%)"
                  value={
                    taxSim.incomeTax <= 0
                      ? `退稅 +NT$ ${Math.abs(taxSim.incomeTax).toLocaleString()}`
                      : `-NT$ ${taxSim.incomeTax.toLocaleString()}`
                  }
                  subLabel="課稅方案"
                  subValue={taxSim.method === "combined" ? "合併課稅(享抵減)" : "分離課稅 28%"}
                  icon={Receipt}
                  badge={taxSim.incomeTax <= 0 ? "實質退稅" : "應納稅額"}
                  badgeColor={taxSim.incomeTax <= 0 ? "green" : "indigo"}
                />
                <MetricCard
                  title="實際入帳淨額 (Net)"
                  value={`NT$ ${taxSim.netReceived.toLocaleString()}`}
                  subLabel="有效實質稅費率"
                  subValue={`${taxSim.effectiveTotalRate}%`}
                  icon={Calculator}
                  badge="實拿到手"
                  badgeColor="green"
                />
              </div>
            </div>
          )}

          {/* 歷年除權息詳細列表 */}
          <div className="glass-panel rounded-2xl p-5 space-y-3">
            <h3 className="text-base font-semibold text-white">📋 歷次除權息明細清單</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400">
                    <th className="py-2.5 px-3">除息日期</th>
                    <th className="py-2.5 px-3 text-right">每股現金股利 (TWD)</th>
                    <th className="py-2.5 px-3 text-right">除息前股價</th>
                    <th className="py-2.5 px-3 text-right">除息後股價</th>
                    <th className="py-2.5 px-3 text-right">單次現金殖利率 %</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-slate-200">
                  {dividends.map((d) => (
                    <tr key={d.date} className="hover:bg-slate-800/40">
                      <td className="py-2 px-3 font-semibold text-white">{d.date}</td>
                      <td className="py-2 px-3 text-right font-bold text-cyan-300">
                        {d.cash_dividend.toFixed(2)} 元
                      </td>
                      <td className="py-2 px-3 text-right text-slate-400">
                        {d.before_price.toFixed(2)} 元
                      </td>
                      <td className="py-2 px-3 text-right text-slate-400">
                        {d.after_price.toFixed(2)} 元
                      </td>
                      <td className="py-2 px-3 text-right font-semibold text-emerald-400">
                        {d.yield_pct.toFixed(2)}%
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
