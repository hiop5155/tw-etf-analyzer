import React from "react";
import {
  BarChart3,
  Target,
  Umbrella,
  AlertTriangle,
  History,
  TrendingUp,
  Coins,
  FileSpreadsheet,
  SlidersHorizontal,
  ExternalLink,
} from "lucide-react";
import { TabKey, useApp } from "../context/AppContext";
import { GoogleAuthButton } from "./GoogleAuthButton";

interface NavbarProps {
  onOpenSettings: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ onOpenSettings }) => {
  const { activeTab, setActiveTab, isRealMode, setIsRealMode, taxConfig } = useApp();

  const navItems: { key: TabKey; label: string; icon: React.FC<{ className?: string }> }[] = [
    { key: "performance", label: "績效分析", icon: BarChart3 },
    { key: "target", label: "目標試算", icon: Target },
    { key: "retirement", label: "退休提領", icon: Umbrella },
    { key: "stress", label: "壓力測試", icon: AlertTriangle },
    { key: "tracking", label: "提領追蹤", icon: History },
    { key: "compare", label: "多檔比較", icon: TrendingUp },
    { key: "dividend", label: "股利歷史", icon: Coins },
    { key: "report", label: "報表匯出", icon: FileSpreadsheet },
  ];

  return (
    <header className="sticky top-0 z-40 w-full glass-panel border-b border-slate-800/80 bg-slate-950/85">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & 標題 */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-cyan-400 p-0.5 shadow-lg shadow-indigo-500/20 flex items-center justify-center">
              <div className="w-full h-full bg-slate-950 rounded-[10px] flex items-center justify-center">
                <span className="text-xl">📈</span>
              </div>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="font-bold text-base sm:text-lg text-white tracking-tight">
                  台股 ETF 分析器
                </h1>
                <span className="px-1.5 py-0.5 text-[10px] font-mono font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 rounded">
                  Cloudflare Edition
                </span>
              </div>
              <p className="text-xs text-slate-400 hidden sm:block">
                0ms 永不休眠 · Guyton-Klinger 護欄 · 蒙地卡羅千次模擬
              </p>
            </div>
          </div>

          {/* 右側快捷控制開關 */}
          <div className="flex items-center gap-2 sm:gap-3">
            {/* 返回記帳助手 */}
            <a
              href="https://money-tracker.xyz"
              className="px-2.5 py-1.5 rounded-lg text-xs font-medium text-slate-300 hover:text-white bg-slate-900 border border-slate-800 hover:border-slate-700 transition-colors hidden sm:flex items-center gap-1.5"
            >
              <span>💰 記帳助手</span>
              <ExternalLink className="w-3 h-3 text-slate-400" />
            </a>

            {/* Google 登入與雲端同步 */}
            <GoogleAuthButton />

            {/* 實質/名目快速切換鈕 */}
            <button
              onClick={() => setIsRealMode(!isRealMode)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 border ${
                isRealMode
                  ? "bg-cyan-500/15 text-cyan-300 border-cyan-500/30"
                  : "bg-slate-800/60 text-slate-400 border-slate-700/60 hover:text-slate-200"
              }`}
              title="切換名目值 vs 扣除通膨實質值"
            >
              <span>{isRealMode ? "🛡️ 實質購買力" : "💵 名目金流"}</span>
            </button>

            {/* 稅率狀態徽章 */}
            {taxConfig.enabled && (
              <span className="px-2 py-1 rounded-lg text-xs font-medium bg-amber-500/15 text-amber-300 border border-amber-500/30 hidden md:inline-flex">
                已扣稅費
              </span>
            )}

            {/* 參數設定抽屜按鈕 */}
            <button
              onClick={onOpenSettings}
              className="p-2 rounded-xl bg-slate-800/80 hover:bg-slate-700 text-slate-200 border border-slate-700/80 transition-colors shadow-sm"
              title="開啟全域參數與稅費設定"
            >
              <SlidersHorizontal className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* 8 大功能分頁 Tabs (橫向滾動) */}
        <div className="flex items-center space-x-1 overflow-x-auto no-scrollbar pb-2 pt-1 -mx-4 px-4 sm:mx-0 sm:px-0">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.key;
            return (
              <button
                key={item.key}
                onClick={() => setActiveTab(item.key)}
                className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs sm:text-sm font-medium transition-all whitespace-nowrap ${
                  isActive
                    ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/25 font-semibold"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? "text-white" : "text-slate-400"}`} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>
      </div>
    </header>
  );
};
