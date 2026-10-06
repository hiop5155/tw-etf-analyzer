import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from "react";
import { TaxFeeConfig } from "../core/types";
import { DEFAULT_BUY_FEE_RATE, DEFAULT_SELL_FEE_RATE, PRESET_PORTFOLIOS } from "../core/constants";
import { getSharedAuth, setSharedAuth, clearSharedAuth } from "../core/cookieAuth";

export type TabKey =
  | "performance"
  | "target"
  | "retirement"
  | "stress"
  | "tracking"
  | "compare"
  | "dividend"
  | "report";

export interface UserProfile {
  email: string;
  name: string;
  avatar?: string;
}

export type SyncStatus = "idle" | "syncing" | "saved" | "error";

export interface SavedPortfolioSettings {
  selectedStock: string;
  monthlyDca: number;
  targetAmount: number;
  targetYears: number;
  existingAsset: number;
  initialAsset: number;
  initialWithdrawalRate: number;
  guardrailPct: number;
  simulationYears: number;
  inflationRate: number;
  isRealMode: boolean;
  taxConfig: TaxFeeConfig;
  portfolioAllocations: Record<string, number>;
  compareStocks: string[];
}

interface AppContextType {
  activeTab: TabKey;
  setActiveTab: (tab: TabKey) => void;

  // 使用者與雲端同步
  user: UserProfile | null;
  token: string | null;
  isLoggedIn: boolean;
  syncStatus: SyncStatus;
  loginWithGoogle: (credential: string) => Promise<boolean>;
  logout: () => void;
  syncNow: () => Promise<void>;

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

const LOCAL_STORAGE_SETTINGS_KEY = "tw_etf_portfolio_settings_v1";
const LOCAL_STORAGE_TOKEN_KEY = "token";
const LOCAL_STORAGE_USER_KEY = "user_profile";

const AppContext = createContext<AppContextType | undefined>(undefined);

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [activeTab, setActiveTab] = useState<TabKey>("performance");

  // 使用者身分認證狀態 (支援跨子網域 SSO 共用 Cookie)
  const [token, setToken] = useState<string | null>(() => {
    const shared = getSharedAuth();
    return shared.token || localStorage.getItem(LOCAL_STORAGE_TOKEN_KEY);
  });
  const [user, setUser] = useState<UserProfile | null>(() => {
    const shared = getSharedAuth();
    if (shared.user) return shared.user;
    try {
      const saved = localStorage.getItem(LOCAL_STORAGE_USER_KEY);
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });
  const [syncStatus, setSyncStatus] = useState<SyncStatus>("idle");
  const isInitialLoadDone = useRef(false);

  // 參數狀態 (先嘗試從 LocalStorage 恢復)
  const initialSaved: Partial<SavedPortfolioSettings> = (() => {
    try {
      const raw = localStorage.getItem(LOCAL_STORAGE_SETTINGS_KEY);
      return raw ? JSON.parse(raw) : {};
    } catch {
      return {};
    }
  })();

  const [selectedStock, setSelectedStock] = useState<string>(initialSaved.selectedStock || "0050");
  const [monthlyDca, setMonthlyDca] = useState<number>(initialSaved.monthlyDca ?? 20_000);

  const [targetAmount, setTargetAmount] = useState<number>(initialSaved.targetAmount ?? 20_000_000);
  const [targetYears, setTargetYears] = useState<number>(initialSaved.targetYears ?? 15);
  const [existingAsset, setExistingAsset] = useState<number>(initialSaved.existingAsset ?? 2_000_000);

  const [initialAsset, setInitialAsset] = useState<number>(initialSaved.initialAsset ?? 20_000_000);
  const [initialWithdrawalRate, setInitialWithdrawalRate] = useState<number>(initialSaved.initialWithdrawalRate ?? 0.05);
  const [guardrailPct, setGuardrailPct] = useState<number>(initialSaved.guardrailPct ?? 0.20);
  const [simulationYears, setSimulationYears] = useState<number>(initialSaved.simulationYears ?? 30);

  const [inflationRate, setInflationRate] = useState<number>(initialSaved.inflationRate ?? 0.02);
  const [isRealMode, setIsRealMode] = useState<boolean>(initialSaved.isRealMode ?? false);

  const [taxConfig, setTaxConfig] = useState<TaxFeeConfig>(initialSaved.taxConfig || {
    enabled: false,
    income_tax_bracket: 0.12,
    buy_fee_rate: DEFAULT_BUY_FEE_RATE,
    sell_fee_rate: DEFAULT_SELL_FEE_RATE,
  });

  const [portfolioAllocations, setPortfolioAllocations] = useState<Record<string, number>>(
    initialSaved.portfolioAllocations || {
      "0056": 0.4,
      "00878": 0.3,
      "00679B": 0.2,
      "現金": 0.1,
    }
  );

  const [compareStocks, setCompareStocks] = useState<string[]>(
    initialSaved.compareStocks || ["0050", "0056", "00878", "006208"]
  );

  // 取得整包投組設定 JSON
  const getCurrentSettings = useCallback((): SavedPortfolioSettings => ({
    selectedStock,
    monthlyDca,
    targetAmount,
    targetYears,
    existingAsset,
    initialAsset,
    initialWithdrawalRate,
    guardrailPct,
    simulationYears,
    inflationRate,
    isRealMode,
    taxConfig,
    portfolioAllocations,
    compareStocks,
  }), [
    selectedStock,
    monthlyDca,
    targetAmount,
    targetYears,
    existingAsset,
    initialAsset,
    initialWithdrawalRate,
    guardrailPct,
    simulationYears,
    inflationRate,
    isRealMode,
    taxConfig,
    portfolioAllocations,
    compareStocks,
  ]);

  // 套用設定到 State
  const applySettings = useCallback((settings: SavedPortfolioSettings) => {
    if (settings.selectedStock) setSelectedStock(settings.selectedStock);
    if (typeof settings.monthlyDca === "number") setMonthlyDca(settings.monthlyDca);
    if (typeof settings.targetAmount === "number") setTargetAmount(settings.targetAmount);
    if (typeof settings.targetYears === "number") setTargetYears(settings.targetYears);
    if (typeof settings.existingAsset === "number") setExistingAsset(settings.existingAsset);
    if (typeof settings.initialAsset === "number") setInitialAsset(settings.initialAsset);
    if (typeof settings.initialWithdrawalRate === "number") setInitialWithdrawalRate(settings.initialWithdrawalRate);
    if (typeof settings.guardrailPct === "number") setGuardrailPct(settings.guardrailPct);
    if (typeof settings.simulationYears === "number") setSimulationYears(settings.simulationYears);
    if (typeof settings.inflationRate === "number") setInflationRate(settings.inflationRate);
    if (typeof settings.isRealMode === "boolean") setIsRealMode(settings.isRealMode);
    if (settings.taxConfig) setTaxConfig(settings.taxConfig);
    if (settings.portfolioAllocations) setPortfolioAllocations(settings.portfolioAllocations);
    if (settings.compareStocks) setCompareStocks(settings.compareStocks);
  }, []);

  // 1. 初始化與 URL Token 檢查
  useEffect(() => {
    const url = new URL(window.location.href);
    const queryToken = url.searchParams.get("token");
    if (queryToken) {
      setToken(queryToken);
      localStorage.setItem(LOCAL_STORAGE_TOKEN_KEY, queryToken);
      url.searchParams.delete("token");
      window.history.replaceState({}, document.title, url.toString());
    }
  }, []);

  // 2. 當有 Token 時，從 D1 雲端抓取投組
  const fetchCloudPortfolio = useCallback(async (authToken: string) => {
    try {
      setSyncStatus("syncing");
      const res = await fetch("/api/portfolio", {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (res.status === 401) {
        // Token 過期或無效
        setToken(null);
        setUser(null);
        localStorage.removeItem(LOCAL_STORAGE_TOKEN_KEY);
        localStorage.removeItem(LOCAL_STORAGE_USER_KEY);
        setSyncStatus("idle");
        return;
      }
      const data = await res.json();
      if (data.exists && data.settings) {
        applySettings(data.settings);
        localStorage.setItem(LOCAL_STORAGE_SETTINGS_KEY, JSON.stringify(data.settings));
        setSyncStatus("saved");
      } else {
        // 雲端尚無資料，將本地目前設定上傳
        const current = getCurrentSettings();
        await fetch("/api/portfolio", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${authToken}`,
          },
          body: JSON.stringify(current),
        });
        setSyncStatus("saved");
      }
    } catch (err) {
      console.error("Failed to load portfolio from D1:", err);
      setSyncStatus("error");
    } finally {
      isInitialLoadDone.current = true;
    }
  }, [applySettings, getCurrentSettings]);

  useEffect(() => {
    if (token) {
      fetchCloudPortfolio(token);
    } else {
      isInitialLoadDone.current = true;
    }
  }, [token, fetchCloudPortfolio]);

  // 3. 變更自動防抖同步至 D1 資料庫與 LocalStorage
  const syncTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (!isInitialLoadDone.current) return;

    const current = getCurrentSettings();
    localStorage.setItem(LOCAL_STORAGE_SETTINGS_KEY, JSON.stringify(current));

    if (token) {
      setSyncStatus("syncing");
      if (syncTimeoutRef.current) clearTimeout(syncTimeoutRef.current);

      syncTimeoutRef.current = setTimeout(async () => {
        try {
          const res = await fetch("/api/portfolio", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify(current),
          });
          if (res.ok) {
            setSyncStatus("saved");
          } else {
            setSyncStatus("error");
          }
        } catch {
          setSyncStatus("error");
        }
      }, 1200);
    }

    return () => {
      if (syncTimeoutRef.current) clearTimeout(syncTimeoutRef.current);
    };
  }, [
    token,
    getCurrentSettings,
    selectedStock,
    monthlyDca,
    targetAmount,
    targetYears,
    existingAsset,
    initialAsset,
    initialWithdrawalRate,
    guardrailPct,
    simulationYears,
    inflationRate,
    isRealMode,
    taxConfig,
    portfolioAllocations,
    compareStocks,
  ]);

  // Google 登入處理
  const loginWithGoogle = async (credential: string): Promise<boolean> => {
    try {
      setSyncStatus("syncing");
      const res = await fetch("/api/auth/google", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ credential }),
      });

      if (!res.ok) {
        throw new Error("Google 登入失敗");
      }

      const data = await res.json();
      setToken(data.token);
      localStorage.setItem(LOCAL_STORAGE_TOKEN_KEY, data.token);

      const profile: UserProfile = {
        email: data.email,
        name: data.name,
        avatar: data.avatar,
      };
      setUser(profile);
      localStorage.setItem(LOCAL_STORAGE_USER_KEY, JSON.stringify(profile));

      // 跨子網域 SSO Cookie 同步 (money-tracker.xyz & calc.money-tracker.xyz)
      setSharedAuth(data.token, profile);

      // 登入後立即載入雲端投組
      await fetchCloudPortfolio(data.token);
      return true;
    } catch (err) {
      console.error(err);
      setSyncStatus("error");
      return false;
    }
  };

  // 登出處理
  const logout = () => {
    setToken(null);
    setUser(null);
    localStorage.removeItem(LOCAL_STORAGE_TOKEN_KEY);
    localStorage.removeItem(LOCAL_STORAGE_USER_KEY);
    clearSharedAuth();
    setSyncStatus("idle");
  };

  // 手動立即同步
  const syncNow = async () => {
    if (!token) return;
    setSyncStatus("syncing");
    try {
      const current = getCurrentSettings();
      const res = await fetch("/api/portfolio", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(current),
      });
      if (res.ok) setSyncStatus("saved");
      else setSyncStatus("error");
    } catch {
      setSyncStatus("error");
    }
  };

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
        user,
        token,
        isLoggedIn: !!token,
        syncStatus,
        loginWithGoogle,
        logout,
        syncNow,
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
