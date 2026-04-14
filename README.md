# tw-etf-analyzer

台灣 ETF / 股票績效分析工具，支援 CLI 與 Web 介面。

資料來源：[FinMind](https://finmindtrade.com/)，自動處理除權息與股票分割還原。

## 功能

- 單筆買進持有：總報酬、年化報酬 (CAGR)
- 定期定額（DCA）：逐年績效、終值、年化報酬
- 單筆 vs 定期定額同等本金對照
- 自動還原股價（分割 + 除權息）
- 本地快取（24h），避免重複拉 API

## 安裝

```bash
pip install -r requirements.txt
```

## Token 設定

到 [finmindtrade.com](https://finmindtrade.com/) 免費註冊取得 API token，擇一設定：

**方法一：`.env` 檔（推薦，跨平台）**
```
FINMIND_TOKEN=你的token
```

**方法二：環境變數**
```bash
# macOS / Linux
export FINMIND_TOKEN=你的token

# Windows PowerShell
$env:FINMIND_TOKEN = "你的token"

# Windows CMD
set FINMIND_TOKEN=你的token
```

## 使用方式

### CLI
```bash
# 互動模式
python etf_cli.py

# 帶參數
python etf_cli.py 00631L 25000

# 強制重新下載（忽略快取）
python etf_cli.py 00631L 25000 --refresh
```

### Web
```bash
python -m streamlit run etf_web.py
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
├── etf_core.py       # 核心邏輯：資料下載、快取、還原股價、績效計算
├── etf_cli.py        # CLI 介面
├── etf_web.py        # Web 介面（Streamlit）
├── requirements.txt  # Python 依賴
├── .gitignore
├── .env              # Token（本機用，不推 GitHub）
└── stock_cache/      # 快取目錄（自動建立，不推 GitHub）
```

## 股票代號格式

輸入代號時不需要加 `.TW`，例如：

| 代號 | 名稱 |
|------|------|
| `00631L` | 富邦台灣加權正2 ETF |
| `00675L` | 富邦臺灣加權正2 ETF |
| `0056` | 元大高股息 ETF |
| `0050` | 元大台灣50 ETF |
| `2330` | 台積電 |

## 注意事項

- FinMind 免費帳號每小時 600 次 API 請求，初次下載一檔約使用 3 次
- Streamlit Community Cloud 為 serverless，重啟後快取會消失（每次重新下載）
- 還原股價計算方式等同「股利全部再投入」，為標準總報酬計算
