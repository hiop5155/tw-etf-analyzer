# tw-etf-analyzer

台灣 ETF / 股票績效分析工具，Streamlit Web 介面。

資料來源：[FinMind](https://finmindtrade.com/)，自動處理除權息與股票分割還原（總報酬計算）。

## 功能分頁

| 分頁 | 說明 |
|------|------|
| 📊 **績效分析** | 單筆 vs 定期定額逐年績效、圖表、Excel / CSV 下載；支援自訂起始日 |
| 🎯 **目標試算** | 反推「N 年後有 X 萬」每月需投入多少；多情境敏感度分析 |
| 💰 **股利歷史** | 歷年配息、殖利率雙軸圖、明細表 |
| 📈 **多檔比較** | 最多 5 檔股票／ETF，標準化折線圖 + 排序績效比較表 |
| 🏖️ **退休提領模擬** | Guyton-Klinger 動態提領 × 1,000 次 Monte Carlo；自動從 FinMind 計算歷史報酬與波動度；百分位扇形圖 + 存活率 |
| 📋 **提領追蹤** | GK 策略歷史回測，月頻再平衡與提領明細追蹤 |

## 安裝

```bash
pip install -r requirements.txt
```

## Token 設定

到 [finmindtrade.com](https://finmindtrade.com/) 免費註冊取得 API token，擇一設定：

**方法一：`.env` 檔（推薦）**
```
FINMIND_TOKEN=你的token
```

**方法二：環境變數**
```bash
# macOS / Linux
export FINMIND_TOKEN=你的token

# Windows PowerShell
$env:FINMIND_TOKEN = "你的token"
```

## 啟動 Web 介面

```bash
streamlit run etf_web.py
```

開啟 http://localhost:8501

## 部署到 Streamlit Community Cloud

1. 將專案（不含 `.env`、`stock_cache/`）推上 GitHub
2. 前往 [share.streamlit.io](https://share.streamlit.io)，連結 repo
3. Main file：`etf_web.py`
4. Advanced settings → Secrets 填入：
   ```toml
   FINMIND_TOKEN = "你的token"
   ```
5. Deploy

## 檔案結構

```
tw-etf-analyzer/
├── etf_core.py       # 核心邏輯：資料下載、快取、還原股價、績效/模擬計算（無 UI）
├── etf_web.py        # Streamlit Web 介面（6 分頁）
├── requirements.txt  # Python 依賴
├── .streamlit/
│   └── config.toml   # Streamlit 設定（關閉使用統計、最小化工具列）
├── .gitignore
├── .env              # Token（本機用，不推 GitHub）
└── stock_cache/      # 快取目錄（自動建立，不推 GitHub）
```

## 程式架構

### 模組職責

| 模組 | 職責 |
|------|------|
| `etf_core.py` | 純計算邏輯，不含任何 UI。負責 FinMind API 資料下載、CSV 快取（TTL 24h）、除權息還原股價、績效計算、GK 退休模擬、Monte Carlo 模擬 |
| `etf_web.py` | Streamlit 介面層，所有 `st.*` 呼叫在此。負責分頁佈局、使用者輸入、圖表繪製、localStorage 持久化 |

### 資料流

```
FinMind API ──→ fetch_adjusted_close() ──→ stock_cache/*.csv（本地快取）
                        │
                        ▼
                還原股價 Series（除權息 + 股票分割調整）
                        │
        ┌───────────────┼───────────────────────┐
        ▼               ▼                       ▼
  calc_lump_sum()  calc_dca()          calc_multi_compare()
  calc_comparison() calc_target_monthly()
                        │
                        ▼
              simulate_gk_montecarlo()
              run_gk_historical()
```

### Web 分頁對應

| 分頁 | 核心函式 |
|------|----------|
| 📊 績效分析 | `calc_comparison()` → `calc_lump_sum()` + `calc_dca()` |
| 🎯 目標試算 | `calc_target_monthly()` |
| 💰 股利歷史 | `fetch_dividend_history()` |
| 📈 多檔比較 | `calc_multi_compare()` |
| 🏖️ 退休提領模擬 | `simulate_gk_montecarlo()` + `calc_return_vol()` |
| 📋 提領追蹤 | `run_gk_historical()` |

### 核心函式

| 函式 | 說明 |
|------|------|
| `fetch_adjusted_close()` | 下載並快取除權息還原股價，回傳 `pd.Series` |
| `fetch_dividend_history()` | 取得歷年股利明細與殖利率 |
| `fetch_stock_name()` | 查詢股票中文名稱（process-level 快取） |
| `calc_lump_sum()` | 單筆買進績效：總報酬 %、CAGR % |
| `calc_dca()` | 定期定額逐年績效：累積成本、市值、報酬率 |
| `calc_comparison()` | 單筆 vs 定期定額比較 |
| `calc_target_monthly()` | 反推每月需投入金額以達目標終值 |
| `calc_multi_compare()` | 多檔 ETF 標準化比較（以最晚上市日為共同起點） |
| `calc_return_vol()` | 計算年化 CAGR 與波動度（log return × √252） |
| `simulate_gk_montecarlo()` | Guyton-Klinger × 1,000 次 Monte Carlo 模擬 |
| `run_gk_historical()` | GK 策略歷史回測（月頻再平衡） |

### 資料類別（Dataclass）

| 類別 | 用途 |
|------|------|
| `LumpSumResult` | 單筆績效結果：總報酬、CAGR、期間、起訖價 |
| `DCAYearRecord` | 定期定額逐年紀錄：累積成本、市值、損益 |
| `DCAResult` | 定期定額完整結果 + 自動計算 CAGR |
| `ComparisonResult` | 單筆 vs 定期定額比較結果 |
| `ETFCompareRecord` | 多檔比較中單檔紀錄：績效 + 標準化序列 |
| `GKYearRecord` | GK 模擬逐年紀錄：資產、提領額、護欄觸發 |
| `GKResult` | GK 模擬完整結果：耗盡年、最終資產、月提領 |

### 持久化機制（localStorage）

使用 `streamlit-local-storage` 將所有使用者設定打包為單一 JSON 存入瀏覽器 `localStorage["etf_all"]`。

- 頁面載入時非同步讀取，第二次 render 後套用（`_ls_applied` 旗標防止重複覆寫）
- 每次 rerun 比對差異，僅在值變動時寫入（避免無限 rerun）
- 支援日期序列化、配置陣列（自訂投資組合）等複雜型別

## 股票代號範例

輸入代號時不需要加 `.TW`：

| 代號 | 名稱 |
|------|------|
| `0050` | 元大台灣50 ETF |
| `0056` | 元大高股息 ETF |
| `00878` | 國泰永續高股息 ETF |
| `00631L` | 富邦台灣加權正2 ETF |
| `2330` | 台積電 |

## 退休模擬說明

- **策略**：Guyton-Klinger (GK) 動態提領
  - 初始提領率 6%（可調）
  - 護欄 ±20%：超過觸發提領額 ×0.90 或 ×1.10
  - 每年自動通膨調整
- **預設組合**（5 種）：保守配息型、債券優先型、全高股息型、均衡穩健型、槓桿平衡型（00631L 50% + 現金 50%）
- **報酬假設**：自動從 FinMind 歷史資料計算 CAGR + 年化波動度（現金固定 0% / 0%，視為純現金；需要貨幣市場收益請改用短期債券 ETF）
- **警告**：歷史資料不足 10 年的標的會標示 ⚠️，CAGR 可能因短期多頭偏高

## 設定記憶

股票代號、每月定期定額、退休模擬各項參數（起始資產、提領率、護欄寬度等）會自動儲存至瀏覽器 localStorage，重新整理後自動還原，不需後端。

## 注意事項

- FinMind 免費帳號每小時 600 次 API 請求，初次下載一檔約使用 3 次
- 本地快取 24 小時，可用「強制重新下載」按鈕清除
- 還原股價計算方式等同「股利全部再投入」，為標準總報酬計算
- Streamlit Community Cloud 為 serverless，重啟後快取消失（每次重新下載）
