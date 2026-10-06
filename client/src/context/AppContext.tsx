import React, { createContext, useContext, useState, useEffect } from "react";
import { TaxFeeConfig } from "../core/types";
import { DEFAULT_BUY_FEE_RATE, DEFAULT_SELL_FEE_RATE, PRESET_PORTFOLIOS } from "../core/constants";

export type TabKey =
  | "performance"
  | "target"
  | "retirement"
  | "stress"
  | "tracking"
  | "compare"
  | "dividend"
  | "report";

interface AppContextType {
  activeTab: TabKey;
  setActiveTab: (tab: TabKey) => void;

  // 單檔分析參數
  selectedStock: string;
  setSelectedStock: (stock: string) => void;
  monthlyDca: number;
  setMonthlyDca: (dca: number) => void;

  // 退休與目標參數
  targetAmount: number;
  setTargetAmount: (amount: number) => void;
  targetYears: number;
  setTargetYears: (years: number) => void;
  existingAsset: number;
  setExistingAsset: (asset: number) => void;

  initialAsset: number;
  setInitialAsset: (asset: number) => void;
  initialWithdrawalRate: number;
  setInitialWithdrawalRate: (rate: number) => void;
  guardrailPct: number;
  setGuardrailPct: (pct: number) => void;
  simulationYears: number;
  setSimulationYears: (years: number) => void;

  // 全域參數
  inflationRate: number;
  setInflationRate: (rate: number) => void;
  isRealMode: boolean;
  setIsRealMode: (isReal: boolean) => void;

  // 稅費設定
  taxConfig: TaxFeeConfig;
  setTaxConfig: React.Dispatch<React.SetStateAction<TaxFeeConfig>>;

  // 多標的投組
  portfolioAllocations: Record<string, number>;
  setPortfolioAllocations: React.Dispatch<React.SetStateAction<Record<string, number>>>;
  applyPresetPortfolio: (presetName: string) => void;

  // 多檔比較標的
  compareStocks: string[];
  setCompareStocks: React.Dispatch<React.SetStateAction<string[]>>;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [activeTab, setActiveTab] = useState<TabKey>("performance");
  const [selectedStock, setSelectedStock] = useState<string>("0050");
  const [monthlyDca, setMonthlyDca] = useState<number>(20_000);

  const [targetAmount, setTargetAmount] = useState<number>(20_000_000);
  const [targetYears, setTargetYears] = useState<number>(15);
  const [existingAsset, setExistingAsset] = useState<number>(2_000_000);

  const [initialAsset, setInitialAsset] = useState<number>(20_000_000);
  const [initialWithdrawalRate, setInitialWithdrawalRate] = useState<number>(0.05);
  const [guardrailPct, setGuardrailPct] = useState<number>(0.20);
  const [simulationYears, setSimulationYears] = useState<number>(30);

  const [inflationRate, setInflationRate] = useState<number>(0.02);
  const [isRealMode, setIsRealMode] = useState<boolean>(false);

  const [taxConfig, setTaxConfig] = useState<TaxFeeConfig>({
    enabled: false,
    income_tax_bracket: 0.12,
    buy_fee_rate: DEFAULT_BUY_FEE_RATE,
    sell_fee_rate: DEFAULT_SELL_FEE_RATE,
  });

  // 預設為保守配息型投組
  const [portfolioAllocations, setPortfolioAllocations] = useState<Record<string, number>>({
    "0056": 0.4,
    "00878": 0.3,
    "00679B": 0.2,
    "現金": 0.1,
  });

  const [compareStocks, setCompareStocks] = useState<string[]>([
    "0050",
    "0056",
    "00878",
    "006208",
  ]);

  const applyPresetPortfolio = (presetName: string) => {
    const found = PRESET_PORTFOLIOS.find((p) => p.name.includes(presetName) || p.name === presetName);
    if (found) {
      const newAlloc: Record<string, number> = {};
      for (const h of found.holdings) {
        newAlloc[h.id] = h.weight / 100;
      }
      setPortfolioAllocations(newAlloc);
    }
  };

  return (
    <AppContext.Provider
      value={{
        activeTab,
        setActiveTab,
        selectedStock,
        setSelectedStock,
        monthlyDca,
        setMonthlyDca,
        targetAmount,
        setTargetAmount,
        targetYears,
        setTargetYears,
        existingAsset,
        setExistingAsset,
        initialAsset,
        setInitialAsset,
        initialWithdrawalRate,
        setInitialWithdrawalRate,
        guardrailPct,
        setGuardrailPct,
        simulationYears,
        setSimulationYears,
        inflationRate,
        setInflationRate,
        isRealMode,
        setIsRealMode,
        taxConfig,
        setTaxConfig,
        portfolioAllocations,
        setPortfolioAllocations,
        applyPresetPortfolio,
        compareStocks,
        setCompareStocks,
      }}
    >
      {children}
    </AppContext.Provider>
  );
};

export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error("useApp must be used within an AppProvider");
  }
  return context;
};
