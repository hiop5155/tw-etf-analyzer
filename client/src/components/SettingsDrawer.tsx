import React from "react";
import { X, HelpCircle, RotateCcw } from "lucide-react";
import { useApp } from "../context/AppContext";
import { DEFAULT_BUY_FEE_RATE, DEFAULT_SELL_FEE_RATE } from "../core/constants";

interface SettingsDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

export const SettingsDrawer: React.FC<SettingsDrawerProps> = ({ isOpen, onClose }) => {
  const {
    taxConfig,
    setTaxConfig,
    inflationRate,
    setInflationRate,
    isRealMode,
    setIsRealMode,
  } = useApp();

  if (!isOpen) return null;

  const handleReset = () => {
    setTaxConfig({
      enabled: false,
      income_tax_bracket: 0.12,
      buy_fee_rate: DEFAULT_BUY_FEE_RATE,
      sell_fee_rate: DEFAULT_SELL_FEE_RATE,
    });
    setInflationRate(0.02);
    setIsRealMode(false);
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* 遮罩背景 */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-md bg-slate-900 border-l border-slate-800 shadow-2xl flex flex-col">
          {/* Drawer Header */}
          <div className="px-6 py-5 border-b border-slate-800 flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-white">⚙️ 全域參數與稅費設定</h2>
              <p className="text-xs text-slate-400 mt-0.5">自訂模擬情境下的稅率與通膨模型</p>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Drawer Content */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {/* 通膨設定 */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <label className="text-sm font-semibold text-slate-200">
                  預期長期年通膨率 (%)
                </label>
                <span className="text-sm font-mono font-bold text-indigo-400">
                  {(inflationRate * 100).toFixed(1)}%
                </span>
              </div>
              <input
                type="range"
                min="0.0"
                max="5.0"
                step="0.1"
                value={inflationRate * 100}
                onChange={(e) => setInflationRate(parseFloat(e.target.value) / 100)}
                className="w-full accent-indigo-500 bg-slate-800 h-2 rounded-lg cursor-pointer"
              />
              <p className="text-xs text-slate-500">
                主計總處長期平均約 1.5%~2.0%，提領階段將按此每年調整生活開銷。
              </p>
            </div>

            {/* 實質 vs 名目切換 */}
            <div className="glass-card rounded-xl p-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-slate-200">
                  實質購買力模式 (Real Mode)
                </span>
                <input
                  type="checkbox"
                  checked={isRealMode}
                  onChange={(e) => setIsRealMode(e.target.checked)}
                  className="w-4 h-4 rounded text-indigo-600 bg-slate-800 border-slate-700 focus:ring-indigo-500"
                />
              </div>
              <p className="text-xs text-slate-400">
                開啟後，未來 10~30 年的所有資產與提領額皆會折現扣除通膨，呈現「相當於今日購買力」的真實價值。
              </p>
            </div>

            <hr className="border-slate-800" />

            {/* 稅費拖累模組 */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-slate-200">台灣稅費與手續費計算</h3>
                  <p className="text-xs text-slate-400">含股利稅、二代健保 2.11% 與證交稅</p>
                </div>
                <input
                  type="checkbox"
                  checked={taxConfig.enabled}
                  onChange={(e) =>
                    setTaxConfig((prev) => ({ ...prev, enabled: e.target.checked }))
                  }
                  className="w-4 h-4 rounded text-indigo-600 bg-slate-800 border-slate-700 focus:ring-indigo-500"
                />
              </div>

              {taxConfig.enabled && (
                <div className="space-y-4 pt-2 border-t border-slate-800/80">
                  {/* 綜所稅級距 */}
                  <div>
                    <label className="text-xs font-medium text-slate-300 block mb-1.5">
                      個人綜合所得稅率級距
                    </label>
                    <select
                      value={taxConfig.income_tax_bracket}
                      onChange={(e) =>
                        setTaxConfig((prev) => ({
                          ...prev,
                          income_tax_bracket: parseFloat(e.target.value),
                        }))
                      }
                      className="w-full bg-slate-800 border border-slate-700 text-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-indigo-500"
                    >
                      <option value={0.05}>5% (小資族，合併課稅享 8.5% 實質退稅)</option>
                      <option value={0.12}>12% (一般上班族，系統自動擇優)</option>
                      <option value={0.20}>20% (中高收入族群)</option>
                      <option value={0.30}>30% (高所得族群，自動分離課稅 28%)</option>
                      <option value={0.40}>40% (頂級富裕族群)</option>
                    </select>
                  </div>

                  {/* 買進手續費率 */}
                  <div>
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="text-slate-300">買進券商手續費率</span>
                      <span className="text-slate-400 font-mono">
                        {(taxConfig.buy_fee_rate * 100).toFixed(4)}%
                      </span>
                    </div>
                    <select
                      value={taxConfig.buy_fee_rate}
                      onChange={(e) =>
                        setTaxConfig((prev) => ({
                          ...prev,
                          buy_fee_rate: parseFloat(e.target.value),
                        }))
                      }
                      className="w-full bg-slate-800 border border-slate-700 text-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-indigo-500"
                    >
                      <option value={0.001425}>0.1425% (原價無打折)</option>
                      <option value={0.0007125}>0.0713% (五折，一般券商預設)</option>
                      <option value={0.000399}>0.0399% (二八折，常見電子下單)</option>
                      <option value={0.000285}>0.0285% (二折，大戶優惠)</option>
                    </select>
                  </div>

                  {/* 賣出手續費率 */}
                  <div>
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="text-slate-300">賣出費率 (含 ETF 證交稅 0.1%)</span>
                      <span className="text-slate-400 font-mono">
                        {(taxConfig.sell_fee_rate * 100).toFixed(4)}%
                      </span>
                    </div>
                    <select
                      value={taxConfig.sell_fee_rate}
                      onChange={(e) =>
                        setTaxConfig((prev) => ({
                          ...prev,
                          sell_fee_rate: parseFloat(e.target.value),
                        }))
                      }
                      className="w-full bg-slate-800 border border-slate-700 text-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-indigo-500"
                    >
                      <option value={0.002425}>0.2425% (手續費無折 + 證交稅 0.1%)</option>
                      <option value={0.0017125}>0.1713% (手續費五折 + 證交稅 0.1%)</option>
                      <option value={0.001399}>0.1399% (手續費二八折 + 證交稅 0.1%)</option>
                    </select>
                  </div>

                  <div className="p-3 bg-indigo-950/40 border border-indigo-500/20 rounded-lg text-xs text-indigo-300">
                    <p className="font-semibold mb-1 flex items-center gap-1">
                      <HelpCircle className="w-3.5 h-3.5" /> 健保與所得稅自動精算：
                    </p>
                    <p className="text-indigo-400/90 leading-relaxed">
                      單次股利 ≥ 20,000 元系統自動扣繳 2.11% 二代健保。綜合所得稅自動在「合併 8.5% 可抵減 (上限 8 萬)」與「分離課稅 28%」中自動擇優。
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Drawer Footer */}
          <div className="p-5 border-t border-slate-800 bg-slate-950/50 flex items-center justify-between">
            <button
              onClick={handleReset}
              className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 px-3 py-2 rounded-lg hover:bg-slate-800/80 transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>恢復預設值</span>
            </button>
            <button
              onClick={onClose}
              className="px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs transition-colors shadow-lg shadow-indigo-600/30"
            >
              完成設定
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
