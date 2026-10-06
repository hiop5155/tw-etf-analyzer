# 📈 台股 ETF 分析器 (tw-etf-analyzer) 遷移至 Cloudflare 架構實施計畫

> **目標**：將原以 Python Streamlit 構建的台股 ETF 績效與退休提領分析器，完整重構為 **React + TypeScript + Cloudflare 邊緣無伺服器 (Serverless) 現代架構**。  
> **核心效益**：
> - ⚡ **0ms 秒開、永不休眠**：徹底告別 Streamlit Community Cloud 閒置休眠與 30~60 秒開機等待。
> - 🚀 **60 FPS 極致流暢**：純前端毫秒級高頻矩陣計算，拉桿滑動圖表即時動態變形。
> - 🛡️ **FinMind API 安全守護與額度節省 99.9%**：透過 Cloudflare 邊緣快取保護 Token 並大幅降低請求量。

---

## 一、FinMind API 的核心挑戰與 Cloudflare 終極解法

在純前端架構中呼叫 FinMind API 會面臨四大硬傷，我們在 Cloudflare 上設計了**「三層防護與快取架構」**完美解決：

### 1. 核心痛點分析

| 痛點維度 | 直接在前端呼叫的問題 | 帶來的後果 |
| :--- | :--- | :--- |
| **Token 外洩風險** | `FINMIND_TOKEN` 必須寫在客戶端 JS 代碼中 | 任何訪客打開瀏覽器 F12 就能直接盜用你的付費/免費 Token |
| **CORS 跨域阻擋** | FinMind API 預設不保證允許任意前端 Origin 跨域呼叫 | 瀏覽器直接攔截，請求失敗 |
| **額度瞬間耗盡 (Rate Limit)** | 每位訪客每次分析都要拉取 20 年（約 5,000 筆）日 K 線 | 50 人同時使用就會耗盡 API 上限，系統直接癱瘓 |
| **重複傳輸開銷** | 歷史股價動輒數 MB 的原始 JSON，重複下載緩慢 | 首次載入時間長，行動網路流量浪費 |

---

### 2. Cloudflare 三層快取與代理防護架構

```
[使用者瀏覽器 (React SPA)]
         │
         │ 1. 請求 /api/stock/adjusted?id=0050 (免附 Token、無 CORS 問題)
         ▼
┌──────────────────────────────────────────────────────────────┐
│ Cloudflare Edge (Pages Functions 邊緣運算層)                  │
│                                                              │
│  [第一道：Cloudflare 邊緣快取 (Cache API / KV / D1)]          │
│      ├── 今日已快取過？ ──(命中快取, <10ms 秒回)─────────────┐ │
│      │                                                    │ │
│      └── 未快取？ ──(每日僅需呼叫 1 次)──┐                 │ │
│                                         │                 │ │
│  [第二道：安全邊緣代理 Worker]            ▼                 │ │
│      ├── 安全注入環境變數: env.FINMIND_TOKEN               │ │
│      ├── 向 FinMind API 抓取股價、除權息、分割資料            │ │
│      ├── 在邊緣直接完成「除權息還原收盤價」運算                 │ │
│      └── 寫入快取，並設置 Cache-Control: max-age=86400      │ │
└─────────────────────────────────────────┬────────────────────┘ │
                                          │                      │
                                          ▼ (HTTPS)              │
                          [FinMind API 官方伺服器]                │
                                                                 │
         ┌───────────────────────────────────────────────────────┘
         ▼ (回傳乾淨輕量的精簡數組)
[前端瀏覽器 LocalStorage / IndexedDB (第三道：本機離線快取)]
         │
         ▼
[TypeScript 核心計算引擎 (純前端 1,000 次蒙地卡羅模擬)]
```

#### 解決方案的技術細節：
1. **Token 永不落地（安全性 100%）**：
   - 前端發起請求至自家同源路徑：`/api/stock/adjusted?id=0050`。
   - `FINMIND_TOKEN` 妥善保存在 Cloudflare Dashboard 的加密環境變數（Secrets）中，前端代碼完全零憑證。
2. **邊緣 24 小時快取（節省 99.9% 請求額度）**：
   - 歷史股價是不變的！昨日以前的收盤價永遠不會變動。
   - 透過 Cloudflare Cache API，每支股票**一天最多只會呼叫 FinMind 1 次**。
   - 之後全球 10,000 名訪客訪問 `0050`，全部直接從台灣 Anycast CDN 節點在 10ms 內吐出資料，**零額度消耗**！
3. **邊緣預算除權息（Edge Pre-Adjustment）**：
   - 原版 Python 在本地執行的「分割與除權息回溯調整」，直接移至 Cloudflare Function 在邊緣處理完成，前端拿到的直接是**乾淨的日期與還原價格數組**，資料體積減少 70%。

---

## 二、功能模組 1:1 遷移對照表

原 `tw-etf-analyzer` 的 8 大核心功能將完整保留並升級：

| 原 Streamlit 分頁 | 核心 Python 檔案 | 重構後 React 組件 | 視覺與互動升級重點 |
| :--- | :--- | :--- | :--- |
| **📊 績效分析** | `views/performance.py`<br>`core/performance.py` | `PerformanceView.tsx` | Recharts 雙軸面積圖、單筆 vs 定期定額 (DCA)、股息再投入開關、CAGR / Sharpe / MDD 即時指標卡片。 |
| **🎯 目標試算** | `views/target.py` | `TargetView.tsx` | 目標資產複利累積階梯圖、每月投入倒推計算、自訂通膨率即時調整。 |
| **🏖️ 退休提領模擬** | `views/retirement.py`<br>`core/simulation.py` | `RetirementView.tsx` | 4% 法則 vs **Guyton-Klinger 護欄法則**（繁榮條款/資本保護條款）、**蒙地卡羅 1,000 次扇形機率圖**。 |
| **⚠️ 壓力測試** | `views/stress.py` | `StressTestView.tsx` | 歷史極端危機回測（2008 金融海嘯、2000 網路泡沫、2020 疫情、2022 升息大回撤），資產抗跌能力壓力測試。 |
| **📋 提領追蹤** | `views/tracking.py` | `TrackingView.tsx` | 退休後每年實質購買力柱狀圖、提領率歷年走勢、破產風險警告指標。 |
| **📈 多檔比較** | `views/compare.py` | `CompareView.tsx` | 自由加入 0050、0056、00878、006208、美股 VT/VOO 走勢疊圖比較與相關係數矩陣。 |
| **💰 股利歷史** | `views/dividend.py` | `DividendView.tsx` | 歷年配息柱狀圖、現金殖利率統計、自動試算**二代健保補充保費 (2.11%)** 與 **8.5% 扣抵稅額**後的實際淨額。 |
| **📄 報表匯出** | `views/pdf_export.py`<br>`pdf/*.py` | `ReportExportView.tsx` | 免經伺服器，前端直接使用 `@react-pdf/renderer` 或 `jspdf` 一鍵產生高品質分析報告 PDF。 |

---

## 三、前端技術選型

- **核心框架**：React 19 + TypeScript + Vite 7。
- **樣式系統**：Tailwind CSS v4（支援深色/淺色主題切換，與 Money Tracker 風格統一）。
- **圖表函式庫**：Recharts（支援響應式、流暢 Tooltip、平滑貝茲曲線動畫）。
- **圖標庫**：Lucide React。
- **狀態保存**：LocalStorage + IndexedDB（使用者自訂配置完全存於本機，隱私安全）。

---

## 四、分階段實施路線圖 (Implementation Roadmap)

### 階段一：專案基礎與邊緣 API 代理建立（Day 1）
- [ ] 在 `tw-etf-analyzer` 建立 `client/` Vite 前端專案骨架與 TypeScript 配置。
- [ ] 建立 Cloudflare Pages Functions 代理端點：
  - `GET /api/stock/adjusted`：抓取並還原除權息收盤價（整合 Cloudflare Cache）。
  - `GET /api/stock/dividends`：抓取除權息紀錄。
  - `GET /api/stock/info`：股票中文名稱快取。
- [ ] 驗證邊緣快取行為與 FinMind Token 隱私安全。

### 階段二：核心財務計算引擎移植 (TypeScript)（Day 2）
- [ ] 將 Python `core/metrics.py` 翻譯為 `src/core/metrics.ts`（CAGR、Sharpe、Sortino、MDD）。
- [ ] 將 Python `core/tax.py` 翻譯為 `src/core/tax.ts`（證交稅、二代健保、股利抵減）。
- [ ] 將 Python `core/simulation.py` 翻譯為 `src/core/simulation.ts`：
  - Guyton-Klinger 護欄規則引擎。
  - 蒙地卡羅隨機路徑產生器（Box-Muller 變換演算法，純前端高效運算）。
- [ ] 撰寫單元測試驗證 TypeScript 計算結果與原 Python 完全一致（零誤差）。

### 階段三：8 大分頁視圖與互動圖表開發（Day 3 ~ 4）
- [ ] 實作現代化頂部/側邊欄導航（支援 8 大功能切換）。
- [ ] 實作 📊 績效分析與資產配置再平衡視圖。
- [ ] 實作 🏖️ 退休提領模擬與蒙地卡羅可視化扇形圖。
- [ ] 實作 ⚠️ 壓力測試、💰 股利歷史與 📈 多檔比較。
- [ ] 實作 📄 純前端 PDF 報表匯出功能。

### 階段四：全端整合、測試與 Cloudflare 部署（Day 5）
- [ ] 設定 `wrangler.toml` 與 Cloudflare Pages CI/CD。
- [ ] 本地執行完整端到端驗證（E2E）。
- [ ] 部署上線，並無縫綁定子網域 `https://calc.money-tracker.xyz` 或整併入 `https://money-tracker.xyz/calc`。
