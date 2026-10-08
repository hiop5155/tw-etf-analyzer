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
      <footer className="border-t border-slate-900 bg-slate-950/60 py-6 text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span>📈 台股 ETF 分析與動態退休提領系統</span>
            <span className="text-slate-700">|</span>
          </div>
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
