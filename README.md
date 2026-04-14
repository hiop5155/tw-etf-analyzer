# tw-etf-analyzer

台灣 ETF / 股票績效分析工具，Streamlit Web 介面。

資料來源：[FinMind](https://finmindtrade.com/)，自動處理除權息與股票分割還原（總報酬計算）。

## 功能分頁

| 分頁 | 說明 |
|------|------|
| 📊 **績效分析** | 單筆 vs 定期定額逐年績效、圖表、Excel / CSV 下載；支援自訂起始日 |
| 🎯 **目標試算** | 反推「N 年後有 X 萬」每月需投入多少；多情境敏感度分析 |
| 💰 **股利歷史** | 歷年配息、殖利率雙軸圖、明細表 |
| 📈 **多 ETF 比較** | 最多 5 檔，標準化折線圖 + 排序績效比較表 |
| 🏖️ **退休提領模擬** | Guyton-Klinger 動態提領 × 1,000 次 Monte Carlo；自動從 FinMind 計算歷史報酬與波動度；百分位扇形圖 + 存活率 |

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
├── etf_core.py       # 核心邏輯：資料下載、快取、還原股價、績效/模擬計算
├── etf_web.py        # Streamlit Web 介面（5 分頁）
├── requirements.txt  # Python 依賴
├── .streamlit/
│   └── config.toml   # Streamlit 設定（關閉使用統計、最小化工具列）
├── .gitignore
├── .env              # Token（本機用，不推 GitHub）
└── stock_cache/      # 快取目錄（自動建立，不推 GitHub）
```

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
- **預設保守組合**（4 種）：保守配息型、債券優先型、全高股息型、均衡穩健型
- **報酬假設**：自動從 FinMind 歷史資料計算 CAGR + 年化波動度（現金固定 1.5% / 0.5%）
- **警告**：歷史資料不足 10 年的 ETF 會標示 ⚠️，CAGR 可能因短期多頭偏高

## 設定記憶

股票代號、每月定期定額、退休模擬各項參數（起始資產、提領率、護欄寬度等）會自動儲存至瀏覽器 localStorage，重新整理後自動還原，不需後端。

## 注意事項

- FinMind 免費帳號每小時 600 次 API 請求，初次下載一檔約使用 3 次
- 本地快取 24 小時，可用「強制重新下載」按鈕清除
- 還原股價計算方式等同「股利全部再投入」，為標準總報酬計算
- Streamlit Community Cloud 為 serverless，重啟後快取消失（每次重新下載）
