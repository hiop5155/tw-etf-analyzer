import React, { useState } from "react";
import {
  FileText,
  Printer,
  Download,
  CheckCircle,
  ShieldCheck,
  Calendar,
  Wallet,
  TrendingUp,
  AlertTriangle,
} from "lucide-react";
import { useApp } from "../context/AppContext";

export const ReportExportView: React.FC = () => {
  const {
    selectedStock,
    monthlyDca,
    initialAsset,
    initialWithdrawalRate,
    guardrailPct,
    simulationYears,
    inflationRate,
    portfolioAllocations,
    taxConfig,
  } = useApp();

  const handlePrint = () => {
    window.print();
  };

  const currentDate = new Date().toISOString().split("T")[0];
  const initialMonthlyIncome = Math.round(
    (initialAsset * initialWithdrawalRate) / 12
  );

  return (
    <div className="space-y-6">
      {/* 頂部操作列 (列印時自動隱藏) */}
      <div className="print:hidden glass-panel rounded-2xl p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
            📄 綜合分析報告匯出
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            一鍵產生符合 A4 規格的高品質分析報告，支援直接列印或另存為 PDF 文件
          </p>
        </div>

        <button
          onClick={handlePrint}
          className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-600 hover:from-indigo-500 hover:to-cyan-500 text-white font-semibold text-xs transition-all shadow-lg shadow-indigo-600/30 flex items-center gap-2 self-start sm:self-auto"
        >
          <Printer className="w-4 h-4" />
          <span>列印或存為 PDF</span>
        </button>
      </div>

      {/* A4 報告本體 (適用 Print) */}
      <div className="glass-panel print:bg-white print:text-black print:border-none print:shadow-none rounded-2xl p-6 sm:p-10 space-y-8 max-w-4xl mx-auto bg-slate-900/90 border border-slate-800">
        {/* 報告標題與產生日期 */}
        <div className="border-b border-slate-800 print:border-slate-300 pb-6 flex flex-col sm:flex-row sm:items-end justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-indigo-400 print:text-indigo-600 font-bold text-xs uppercase tracking-wider mb-1">
              <span>Taiwan ETF & Retirement Strategy Report</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white print:text-slate-900 tracking-tight">
              台股 ETF 資產配置與動態提領報告書
            </h1>
          </div>
          <div className="text-xs font-mono text-slate-400 print:text-slate-600 sm:text-right">
            <div>報告生成日期: {currentDate}</div>
            <div>架構: Guyton-Klinger 動態護欄策略</div>
          </div>
        </div>

        {/* 1. 核心投組配置摘要 */}
        <div className="space-y-3">
          <h3 className="text-base font-bold text-white print:text-slate-900 border-l-4 border-indigo-500 pl-2">
            一、資產配置權重規劃 (Target Allocation)
          </h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {Object.entries(portfolioAllocations).map(([id, weight]) => (
              <div
                key={id}
                className="p-3 rounded-xl bg-slate-800/60 print:bg-slate-100 border border-slate-700/60 print:border-slate-300"
              >
                <div className="text-xs text-slate-400 print:text-slate-600 font-mono">
                  {id}
                </div>
                <div className="text-lg font-bold font-mono text-cyan-400 print:text-indigo-700">
                  {(weight * 100).toFixed(0)}%
                </div>
                <div className="text-[11px] text-slate-500 print:text-slate-500">
                  配置金額: {((initialAsset * weight) / 10000).toFixed(0)} 萬
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* 2. 退休提領規劃與護欄參數 */}
        <div className="space-y-3">
          <h3 className="text-base font-bold text-white print:text-slate-900 border-l-4 border-indigo-500 pl-2">
            二、退休提領規劃與護欄參數
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="p-4 rounded-xl bg-slate-800/40 print:bg-slate-50 border border-slate-800 print:border-slate-200">
              <span className="text-xs text-slate-400 print:text-slate-600 block">
                起始退休本金總額
              </span>
              <span className="text-xl font-bold font-mono text-white print:text-black">
                NT$ {(initialAsset / 10000).toLocaleString()} 萬元
              </span>
            </div>

            <div className="p-4 rounded-xl bg-slate-800/40 print:bg-slate-50 border border-slate-800 print:border-slate-200">
              <span className="text-xs text-slate-400 print:text-slate-600 block">
                初始首年月生活費
              </span>
              <span className="text-xl font-bold font-mono text-emerald-400 print:text-emerald-700">
                NT$ {initialMonthlyIncome.toLocaleString()} 元/月
              </span>
              <span className="text-[11px] text-slate-500 block mt-1">
                年提領率 {(initialWithdrawalRate * 100).toFixed(1)}%
              </span>
            </div>

            <div className="p-4 rounded-xl bg-slate-800/40 print:bg-slate-50 border border-slate-800 print:border-slate-200">
              <span className="text-xs text-slate-400 print:text-slate-600 block">
                Guyton-Klinger 護欄閥值
              </span>
              <span className="text-xl font-bold font-mono text-amber-400 print:text-amber-700">
                ±{(guardrailPct * 100).toFixed(0)}%
              </span>
              <span className="text-[11px] text-slate-500 block mt-1">
                規劃壽命 {simulationYears} 年 (通膨 {(inflationRate * 100).toFixed(1)}%)
              </span>
            </div>
          </div>
        </div>

        {/* 3. 策略實施指引與防禦手冊 */}
        <div className="space-y-3">
          <h3 className="text-base font-bold text-white print:text-slate-900 border-l-4 border-indigo-500 pl-2">
            三、Guyton-Klinger 動態提領執行守則
          </h3>
          <div className="space-y-2 text-xs leading-relaxed text-slate-300 print:text-slate-700">
            <div className="p-3 rounded-lg bg-slate-800/40 print:bg-slate-100 border border-slate-800 print:border-slate-300">
              <strong className="text-indigo-400 print:text-indigo-700">
                1. 資本保護規則 (Capital Preservation Rule):
              </strong>{" "}
              當市場發生大跌，導致當前「年度提領額 ÷ 總資產」高於初始提領率的{" "}
              {(1 + guardrailPct).toFixed(2)} 倍時，下年度提領額主動調降 10%，保全剩餘本金。
            </div>
            <div className="p-3 rounded-lg bg-slate-800/40 print:bg-slate-100 border border-slate-800 print:border-slate-300">
              <strong className="text-emerald-400 print:text-emerald-700">
                2. 繁榮規則 (Prosperity Rule):
              </strong>{" "}
              當市場迎來大牛市，資產大幅膨脹使得提領率低於初始提領率的{" "}
              {(1 - guardrailPct).toFixed(2)} 倍時，下年度提領額主動調升 10%，享受財富生活。
            </div>
            <div className="p-3 rounded-lg bg-slate-800/40 print:bg-slate-100 border border-slate-800 print:border-slate-300">
              <strong className="text-cyan-400 print:text-cyan-700">
                3. 通膨旁路保護 (Inflation Bypass):
              </strong>{" "}
              若前一年度總資產淨值較上一年度縮水，則該年度跳過通膨增額調整，避免在虧損年度擴大失血。
            </div>
          </div>
        </div>

        {/* 4. 免責聲明 */}
        <div className="pt-4 border-t border-slate-800 print:border-slate-300 text-[11px] text-slate-500 print:text-slate-500 space-y-1">
          <div className="font-semibold text-slate-400 print:text-slate-600">
            免責聲明與風險提示:
          </div>
          <p>
            本報告書之計算模型（含蒙地卡羅模擬與歷史回測）係基於過去歷史數據演繹而成，過去之績效表現不保證未來獲利。投資人應依個人財務狀況、風險承受度自行審慎評估。
          </p>
        </div>
      </div>
    </div>
  );
};
