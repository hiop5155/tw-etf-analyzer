import React, { useState, useEffect } from "react";
import { Plus, Trash2, Sliders, CheckCircle2, AlertCircle, RefreshCw } from "lucide-react";
import { useApp } from "../context/AppContext";
import { PRESET_PORTFOLIOS } from "../core/constants";
import { fetchStockInfo } from "../services/api";
import { NumericInput } from "./NumericInput";

interface PortfolioEditorProps {
  title?: string;
  subtitle?: string;
  className?: string;
  compact?: boolean;
}

export const PortfolioEditor: React.FC<PortfolioEditorProps> = ({
  title = "🗂️ 投資組合資產配置",
  subtitle = "自由增減 ETF 或個股標的，設定目標配置比例 %",
  className = "",
  compact = false,
}) => {
  const { portfolioAllocations, setPortfolioAllocations, applyPresetPortfolio } = useApp();

  const [activePreset, setActivePreset] = useState<string>("custom");
  const [newStockId, setNewStockId] = useState("");
  const [stockNames, setStockNames] = useState<Record<string, string>>({
    "0050": "元大台灣50",
    "0056": "元大高股息",
    "00878": "國泰永續高股息",
    "006208": "富邦台50",
    "00713": "元大台灣高息低波",
    "00919": "群益精選高息",
    "00929": "復華科技優息",
    "00679B": "元大美債20年",
    "00687B": "國泰20年美債",
    "00720B": "元大投資級公司債",
    "00751B": "元大AAA公司債",
    "2330": "台積電",
    "現金": "現金 / 活存",
    "CASH": "現金 / 活存",
  });

  // 檢查是否符合某個預設組合
  useEffect(() => {
    const assets = Object.keys(portfolioAllocations);
    let matched = "custom";
    for (const p of PRESET_PORTFOLIOS) {
      if (p.holdings.length === assets.length) {
        const isSame = p.holdings.every((h) => {
          const w = portfolioAllocations[h.id];
          return w !== undefined && Math.abs(w * 100 - h.weight) < 0.1;
        });
        if (isSame) {
          matched = p.name;
          break;
        }
      }
    }
    setActivePreset(matched);
  }, [portfolioAllocations]);

  // 非同步載入未知代號的股票名稱
  useEffect(() => {
    const assets = Object.keys(portfolioAllocations);
    assets.forEach(async (id) => {
      if (!stockNames[id] && id !== "現金" && id !== "CASH") {
        try {
          const info = await fetchStockInfo(id);
          if (info && info.stock_name) {
            setStockNames((prev) => ({ ...prev, [id]: info.stock_name }));
          }
        } catch {
          // 忽略失敗
        }
      }
    });
  }, [portfolioAllocations, stockNames]);

  // 計算總比例 %
  const totalWeightPct = Object.values(portfolioAllocations).reduce(
    (sum, w) => sum + w * 100,
    0
  );
  const isBalanced = Math.abs(totalWeightPct - 100) < 0.5;

  // 變更某一檔的權重
  const handleWeightChange = (stockId: string, pct: number) => {
    const clamped = Math.max(0, Math.min(100, isNaN(pct) ? 0 : pct));
    setPortfolioAllocations((prev) => ({
      ...prev,
      [stockId]: clamped / 100,
    }));
  };

  // 刪除某一檔
  const handleRemoveStock = (stockId: string) => {
    setPortfolioAllocations((prev) => {
      const next = { ...prev };
      delete next[stockId];
      return next;
    });
  };

  // 新增標的
  const handleAddStock = async () => {
    const cleanId = newStockId.trim().toUpperCase().replace(".TW", "");
    if (!cleanId) return;

    if (portfolioAllocations[cleanId] !== undefined) {
      alert(`標的 ${cleanId} 已存在投組中！`);
      return;
    }

    setPortfolioAllocations((prev) => ({
      ...prev,
      [cleanId]: 0.1, // 預設 10%
    }));
    setNewStockId("");

    // 查名
    if (cleanId !== "現金" && cleanId !== "CASH") {
      try {
        const info = await fetchStockInfo(cleanId);
        if (info && info.stock_name) {
          setStockNames((prev) => ({ ...prev, [cleanId]: info.stock_name }));
        }
      } catch {
        // ignore
      }
    }
  };

  return (
    <div className={`glass-panel rounded-2xl p-5 space-y-4 ${className}`}>
      {/* 標題與預設組合切換 */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <Sliders className="w-4 h-4 text-indigo-400" />
            {title}
          </h3>
          {subtitle && <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>}
        </div>

        {/* 推薦範本膠囊按鈕 */}
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[11px] text-slate-400 mr-1 hidden sm:inline">套用範本:</span>
          {PRESET_PORTFOLIOS.map((p) => (
            <button
              key={p.name}
              onClick={() => {
                applyPresetPortfolio(p.name);
                setActivePreset(p.name);
              }}
              className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all ${
                activePreset === p.name
                  ? "bg-indigo-600 text-white font-semibold shadow-sm shadow-indigo-600/30"
                  : "bg-slate-800/80 hover:bg-slate-700 text-slate-300 border border-slate-700/50"
              }`}
            >
              {p.name.split(" ")[0]}
            </button>
          ))}
          <button
            onClick={() => setActivePreset("custom")}
            className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all ${
              activePreset === "custom"
                ? "bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 font-semibold"
                : "bg-slate-800/50 hover:bg-slate-700 text-slate-400 border border-slate-750"
            }`}
          >
            自訂組合
          </button>
        </div>
      </div>

      {/* 持股清單表格 */}
      <div className="space-y-2 pt-1">
        <div className="grid grid-cols-12 gap-2 text-xs font-medium text-slate-400 px-3 py-1">
          <div className="col-span-5 sm:col-span-3">標的代號</div>
          <div className="col-span-5 sm:col-span-6">
            <span className="hidden sm:inline">配置比例 (可拖動或手動輸入 %)</span>
            <span className="sm:hidden">配置比例 (%)</span>
          </div>
          <div className="col-span-2 sm:col-span-3 text-right">操作</div>
        </div>

        {Object.entries(portfolioAllocations).map(([stockId, weight]) => {
          const pct = Math.round(weight * 1000) / 10;
          const name = stockNames[stockId] || (stockId === "現金" ? "現金 / 活存" : stockId);

          return (
            <div
              key={stockId}
              className="bg-slate-900/80 border border-slate-800/80 hover:border-slate-700 p-2.5 rounded-xl transition-all space-y-2 sm:space-y-0"
            >
              <div className="grid grid-cols-12 gap-2 items-center">
                {/* 代號與名稱 */}
                <div className="col-span-5 sm:col-span-3 flex flex-col">
                  <span className="font-mono font-bold text-white text-sm">{stockId}</span>
                  <span className="text-[11px] text-slate-400 truncate">{name}</span>
                </div>

                {/* 配置比例 滑桿 (桌機) 與數字輸入 */}
                <div className="col-span-5 sm:col-span-6 flex items-center justify-end sm:justify-start gap-2">
                  <input
                    type="range"
                    min="0"
                    max="100"
                    step="1"
                    value={pct}
                    onChange={(e) => handleWeightChange(stockId, parseFloat(e.target.value) || 0)}
                    className="w-full accent-indigo-500 cursor-pointer hidden sm:block"
                  />
                  <div className="flex items-center gap-1 shrink-0">
                    <NumericInput
                      value={pct}
                      min={0}
                      max={100}
                      step={1}
                      onCommit={(val) => handleWeightChange(stockId, val)}
                      placeholder="0"
                      className="w-14 sm:w-16 bg-slate-950 border border-slate-700 px-2 py-1 rounded-lg text-sm font-mono font-bold text-indigo-300 text-right focus:outline-none focus:border-indigo-500"
                    />
                    <span className="text-xs text-slate-400 font-mono">%</span>
                  </div>
                </div>

                {/* 刪除按鈕 */}
                <div className="col-span-2 sm:col-span-3 flex items-center justify-end">
                  <button
                    onClick={() => handleRemoveStock(stockId)}
                    className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                    title="刪除標的"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* 手機版專屬全寬滑桿 (方便大拇指拖動調節，不擠壓版面) */}
              <div className="pt-1 sm:hidden">
                <input
                  type="range"
                  min="0"
                  max="100"
                  step="1"
                  value={pct}
                  onChange={(e) => handleWeightChange(stockId, parseFloat(e.target.value) || 0)}
                  className="w-full accent-indigo-500 cursor-pointer h-1.5 bg-slate-800 rounded-lg"
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* 新增標的輸入框與總計列 */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 pt-2 border-t border-slate-800/80">
        {/* 新增股票輸入 */}
        <div className="flex items-center gap-2">
          <input
            type="text"
            placeholder="台股代號 (如 00713, 2330, 現金)"
            value={newStockId}
            onChange={(e) => setNewStockId(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAddStock()}
            className="w-52 bg-slate-900 border border-slate-700 px-3 py-1.5 rounded-xl text-xs font-mono text-white placeholder:text-slate-500 focus:outline-none focus:border-indigo-500"
          />
          <button
            onClick={handleAddStock}
            className="px-3 py-1.5 rounded-xl text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center gap-1.5 transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>新增標的</span>
          </button>
        </div>

        {/* 權重總和狀態指示 */}
        <div className="flex items-center gap-2 text-xs font-mono">
          <span className="text-slate-400">配置總計:</span>
          <span
            className={`font-bold ${
              isBalanced ? "text-emerald-400" : "text-amber-400"
            }`}
          >
            {Math.round(totalWeightPct)}%
          </span>
          {isBalanced ? (
            <span className="text-emerald-400 flex items-center gap-1 font-sans">
              <CheckCircle2 className="w-4 h-4" />
              <span>剛好 100%</span>
            </span>
          ) : (
            <span className="text-amber-400 flex items-center gap-1 font-sans">
              <AlertCircle className="w-4 h-4" />
              <span>
                {totalWeightPct < 100
                  ? `尚缺 ${Math.round(100 - totalWeightPct)}%`
                  : `超出 ${Math.round(totalWeightPct - 100)}%`}
                （需剛好 100%）
              </span>
            </span>
          )}
        </div>
      </div>
    </div>
  );
};
