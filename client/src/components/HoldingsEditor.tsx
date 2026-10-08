import React, { useState, useEffect, useMemo } from "react";
import { Plus, Trash2, Wallet, RefreshCw, TrendingUp, Sparkles } from "lucide-react";
import { useApp } from "../context/AppContext";
import { fetchStockInfo, fetchAdjustedPrices } from "../services/api";
import { calcLumpSum } from "../core/performance";
import { NumericInput } from "./NumericInput";

interface QuoteData {
  name: string;
  price: number | null;
  cagr: number | null;
}

export const HoldingsEditor: React.FC<{ onApplyCagr?: (cagr: number) => void }> = ({ onApplyCagr }) => {
  const { userHoldings, setUserHoldings, setExistingAsset } = useApp();

  const [newStockId, setNewStockId] = useState("");
  const [newShares, setNewShares] = useState<number>(1000);
  const [quotes, setQuotes] = useState<Record<string, QuoteData>>({
    "現金": { name: "現金 / 活存", price: 1.0, cagr: 0.0 },
    "CASH": { name: "現金 / 活存", price: 1.0, cagr: 0.0 },
  });
  const [loading, setLoading] = useState(false);

  // 查詢各持股的最新股價與歷史 CAGR
  useEffect(() => {
    let isMounted = true;
    async function loadQuotes() {
      setLoading(true);
      const newQuotes: Record<string, QuoteData> = { ...quotes };

      for (const h of userHoldings) {
        const id = h.stockId.trim().toUpperCase();
        if (id === "現金" || id === "CASH") {
          newQuotes[id] = { name: "現金 / 活存", price: 1.0, cagr: 0.0 };
          continue;
        }

        try {
          // 查詢名稱
          let name = id;
          const info = await fetchStockInfo(id);
          if (info?.stock_name) name = info.stock_name;

          // 查詢價格與報酬
          const prices = await fetchAdjustedPrices(id);
          let latestPrice: number | null = null;
          let cagr: number | null = null;

          if (prices.length > 0) {
            latestPrice = prices[prices.length - 1].close;
            if (prices.length >= 2) {
              const lump = calcLumpSum(prices);
              cagr = lump.cagr_pct;
            }
          }

          newQuotes[id] = { name, price: latestPrice, cagr };
        } catch {
          newQuotes[id] = { name: id, price: null, cagr: null };
        }
      }

      if (isMounted) {
        setQuotes(newQuotes);
        setLoading(false);
      }
    }

    loadQuotes();
    return () => {
      isMounted = false;
    };
  }, [userHoldings]);

  // 計算每筆市值與總市值
  const { totalMarketValue, weightedCagr } = useMemo(() => {
    let totalVal = 0;
    let weightedRetSum = 0;

    userHoldings.forEach((h) => {
      const q = quotes[h.stockId];
      const price = q?.price ?? (h.stockId === "現金" ? 1.0 : 0);
      const val = h.shares * price;
      totalVal += val;

      if (q?.cagr !== null && q?.cagr !== undefined) {
        weightedRetSum += q.cagr * val;
      }
    });

    const wCagr = totalVal > 0 ? weightedRetSum / totalVal : 8.0;
    return {
      totalMarketValue: totalVal,
      weightedCagr: Math.round(wCagr * 10) / 10,
    };
  }, [userHoldings, quotes]);

  // 當總市值算出時，自動更新 AppContext 中的 existingAsset (現有資產)
  useEffect(() => {
    if (totalMarketValue > 0) {
      setExistingAsset(Math.round(totalMarketValue));
    }
  }, [totalMarketValue, setExistingAsset]);

  // 修改股數
  const handleSharesChange = (index: number, shares: number) => {
    const clamped = Math.max(0, isNaN(shares) ? 0 : shares);
    setUserHoldings((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], shares: clamped };
      return next;
    });
  };

  // 刪除持股
  const handleRemove = (index: number) => {
    setUserHoldings((prev) => prev.filter((_, i) => i !== index));
  };

  // 新增持股
  const handleAdd = () => {
    const cleanId = newStockId.trim().toUpperCase().replace(".TW", "");
    if (!cleanId) return;

    setUserHoldings((prev) => [...prev, { stockId: cleanId, shares: newShares || 1000 }]);
    setNewStockId("");
    setNewShares(1000);
  };

  return (
    <div className="glass-panel rounded-2xl p-5 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <Wallet className="w-4 h-4 text-emerald-400" />
            目前持股明細（自動換算現有資產與市值）
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            輸入已持有的 ETF 或個股與股數，系統自動抓取現價計算總市值
          </p>
        </div>

        {loading && (
          <div className="flex items-center gap-1.5 text-xs text-indigo-400">
            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            <span>查詢即時行情中...</span>
          </div>
        )}
      </div>

      {/* 持股清單 */}
      <div className="space-y-2">
        <div className="grid grid-cols-12 gap-2 text-xs font-medium text-slate-400 px-3 py-1">
          <div className="col-span-3 sm:col-span-3">標的代號</div>
          <div className="col-span-3 sm:col-span-3">持有股數 (股)</div>
          <div className="col-span-3 sm:col-span-3 text-right">最新股價 / 市值</div>
          <div className="col-span-3 sm:col-span-3 text-right">年化報酬 / 操作</div>
        </div>

        {userHoldings.map((h, idx) => {
          const q = quotes[h.stockId];
          const price = q?.price;
          const val = price !== null && price !== undefined ? h.shares * price : 0;
          const name = q?.name || h.stockId;

          return (
            <div
              key={`${h.stockId}-${idx}`}
              className="grid grid-cols-12 gap-2 items-center bg-slate-900/80 border border-slate-800/80 hover:border-slate-700 p-2.5 rounded-xl transition-all"
            >
              {/* 代號與名稱 */}
              <div className="col-span-3 sm:col-span-3 flex flex-col">
                <span className="font-mono font-bold text-white text-sm">{h.stockId}</span>
                <span className="text-[11px] text-slate-400 truncate">{name}</span>
              </div>

              {/* 股數輸入 */}
              <div className="col-span-3 sm:col-span-3">
                <NumericInput
                  value={h.shares}
                  min={0}
                  step={100}
                  onCommit={(val) => handleSharesChange(idx, val)}
                  placeholder="0"
                  className="w-full bg-slate-950 border border-slate-700 px-2.5 py-1.5 rounded-lg text-sm font-mono font-semibold text-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              {/* 價格與市值 */}
              <div className="col-span-3 sm:col-span-3 flex flex-col items-end">
                <span className="text-sm font-mono font-bold text-emerald-400">
                  ${Math.round(val).toLocaleString()}
                </span>
                <span className="text-[11px] font-mono text-slate-500">
                  {price !== null && price !== undefined ? `@ $${price.toFixed(2)}` : "載入中"}
                </span>
              </div>

              {/* 年化報酬與刪除 */}
              <div className="col-span-3 sm:col-span-3 flex items-center justify-end gap-2">
                {q?.cagr !== null && q?.cagr !== undefined && (
                  <span className="text-xs font-mono text-indigo-300 hidden sm:inline">
                    {q.cagr > 0 ? "+" : ""}{q.cagr.toFixed(1)}%
                  </span>
                )}
                <button
                  onClick={() => handleRemove(idx)}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                  title="刪除"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* 新增持股與加總列 */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 pt-3 border-t border-slate-800/80">
        {/* 新增欄位 */}
        <div className="flex items-center gap-2">
          <input
            type="text"
            placeholder="代號 (如 0050, 現金)"
            value={newStockId}
            onChange={(e) => setNewStockId(e.target.value)}
            className="w-36 bg-slate-900 border border-slate-700 px-3 py-1.5 rounded-xl text-xs font-mono text-white placeholder:text-slate-500 focus:outline-none focus:border-indigo-500"
          />
          <input
            type="number"
            placeholder="股數"
            value={newShares}
            onChange={(e) => setNewShares(parseInt(e.target.value, 10) || 0)}
            onKeyDown={(e) => e.key === "Enter" && handleAdd()}
            className="w-24 bg-slate-900 border border-slate-700 px-3 py-1.5 rounded-xl text-xs font-mono text-white focus:outline-none focus:border-indigo-500"
          />
          <button
            onClick={handleAdd}
            className="px-3 py-1.5 rounded-xl text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center gap-1 transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>新增</span>
          </button>
        </div>

        {/* 總市值與加權報酬統計 */}
        <div className="flex flex-wrap items-center gap-4 bg-slate-900/60 px-4 py-2 rounded-xl border border-slate-800">
          <div className="flex items-center gap-1.5 text-xs font-mono">
            <span className="text-slate-400">目前持股總額:</span>
            <span className="font-bold text-emerald-400 text-sm">
              ${Math.round(totalMarketValue).toLocaleString()} 元
            </span>
          </div>

          <div className="flex items-center gap-1.5 text-xs font-mono">
            <span className="text-slate-400">加權年化:</span>
            <span className="font-bold text-indigo-400">
              {weightedCagr > 0 ? "+" : ""}{weightedCagr.toFixed(1)}%
            </span>
            {onApplyCagr && (
              <button
                onClick={() => onApplyCagr(weightedCagr)}
                className="ml-1 text-[11px] text-indigo-300 hover:underline flex items-center gap-0.5"
                title="套用此加權報酬率至下方試算"
              >
                <Sparkles className="w-3 h-3" />
                <span>套用</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
