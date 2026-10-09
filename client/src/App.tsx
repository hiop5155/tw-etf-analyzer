import React, { useState } from "react";
import { AppProvider, useApp } from "./context/AppContext";
import { Navbar } from "./components/Navbar";
import { SettingsDrawer } from "./components/SettingsDrawer";
import { PerformanceView } from "./views/PerformanceView";
import { TargetView } from "./views/TargetView";
import { RetirementView } from "./views/RetirementView";
import { StressTestView } from "./views/StressTestView";
import { TrackingView } from "./views/TrackingView";
import { CompareView } from "./views/CompareView";
import { DividendView } from "./views/DividendView";
import { ReportExportView } from "./views/ReportExportView";

const MainContent: React.FC = () => {
  const { activeTab } = useApp();
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-indigo-500 selection:text-white">
      {/* 頂部導航列 */}
      <Navbar onOpenSettings={() => setIsSettingsOpen(true)} />

      {/* 參數與稅費抽屜 */}
      <SettingsDrawer
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
      />

      {/* 主工作區 */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {activeTab === "performance" && <PerformanceView />}
        {activeTab === "target" && <TargetView />}
        {activeTab === "retirement" && <RetirementView />}
        {activeTab === "stress" && <StressTestView />}
        {activeTab === "tracking" && <TrackingView />}
        {activeTab === "compare" && <CompareView />}
        {activeTab === "dividend" && <DividendView />}
        {activeTab === "report" && <ReportExportView />}
      </main>

      {/* 頁尾 Footer */}
      <footer className="border-t border-slate-900 bg-slate-950/80 py-6 text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex flex-col sm:flex-row items-center gap-2 sm:gap-3 text-center sm:text-left">
            <span className="font-semibold text-slate-300">Money Tracker AI Studio</span>
            <span className="hidden sm:inline text-slate-800">|</span>
            <span>📈 台股 ETF 分析與動態退休提領系統</span>
            <span className="hidden sm:inline text-slate-800">|</span>
            <span>© {new Date().getFullYear()} All rights reserved.</span>
          </div>

          <div className="flex flex-wrap items-center justify-center gap-4 text-slate-400">
            <a
              href={(typeof window !== 'undefined' && window.location.pathname.startsWith('/calc')) ? '/' : 'https://money-tracker.xyz'}
              className="hover:text-indigo-400 transition-colors"
            >
              Money Tracker App
            </a>
            <a
              href={(typeof window !== 'undefined' && window.location.pathname.startsWith('/calc')) ? '/blog' : 'https://money-tracker.xyz/blog'}
              className="hover:text-indigo-400 transition-colors"
            >
              理財知識庫
            </a>
            <a
              href={(typeof window !== 'undefined' && window.location.pathname.startsWith('/calc')) ? '/privacy' : 'https://money-tracker.xyz/privacy'}
              className="hover:text-indigo-400 transition-colors"
            >
              隱私權政策
            </a>
            <a href="mailto:contact@money-tracker.xyz" className="hover:text-indigo-400 transition-colors">
              聯絡我們 (contact@money-tracker.xyz)
            </a>
          </div>
        </div>
        <div className="mt-3 text-center text-[11px] text-slate-600">
          Powered by Anthropic Claude 3.5 &amp; Cloudflare Edge
        </div>
      </footer>
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <AppProvider>
      <MainContent />
    </AppProvider>
  );
};

export default App;
