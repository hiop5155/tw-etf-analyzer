# tw-etf-analyzer

台灣 ETF / 股票績效分析 + 退休規劃工具。Streamlit Web 介面 + CLI + PDF 報告匯出。

資料來源:[FinMind](https://finmindtrade.com/),自動處理除權息與股票分割還原(總報酬計算)。

## ✨ 核心功能

### 📊 績效與分析(8 分頁)

| 分頁 | 說明 |
|------|------|
| **績效分析** | 單筆 vs 定期定額逐年績效 + 風險指標(MDD / Sharpe / Sortino / Calmar) + 稅費淨值 |
| **目標試算** | 正推(目標 → 月投)+ 反推(月支出 → 資產,4% 法則 + SWR 對照) |
| **退休提領模擬** | Guyton-Klinger × Monte Carlo × 2000 路徑 + Sequence-of-Returns 視覺化 |
| **壓力測試** | 3 歷史情境起點式回測(2008 金融海嘯 / 2020 COVID / 2022 升息),0050 代理 |
| **提領追蹤** | 歷史月頻 GK 單次追蹤 + Rolling(多起始年)回測 + 再平衡建議 |
| **多檔比較** | 2–5 檔標準化走勢 + 風險指標 + 月報酬相關性熱圖 |
| **股利歷史** | 歷年配息、殖利率雙軸圖、明細 |
| **PDF 匯出** | 勾選式多分頁組裝,內嵌 Noto Sans CJK TC |

### 全域設定

- **稅費建模**:綜所稅率(5/12/20/30/40%)+ 自動合併/分離課稅擇優 + 二代健保 + 手續費
- **實質/名目切換**:全頁數字依通膨折現
- **3 種 MC 分配**:常態 / Student-t 肥尾(df=5)/ Bootstrap(歷史月報酬)

## 安裝

### 方法一:開發模式(推薦)

```bash
# 建議使用 venv
python3 -m venv .venv
source .venv/bin/activate   # Linux/Mac
# .venv\Scripts\activate    # Windows PowerShell

# 安裝本 package 為可編輯模式
pip install -e .

# CLI 即可使用
twetf --help
```

### 方法二:僅跑 Streamlit(不安裝)

```bash
pip install -r requirements.txt
streamlit run etf_web.py
```

## Token 設定

到 [finmindtrade.com](https://finmindtrade.com/) 免費註冊取得 API token,擇一:

**`.env` 檔(推薦)**
```
FINMIND_TOKEN=你的token
```

**環境變數**
```bash
export FINMIND_TOKEN=你的token                # Linux/Mac
$env:FINMIND_TOKEN = "你的token"              # Windows PowerShell
```

## 啟動

### Web 介面

```bash
streamlit run etf_web.py   # 預設 8501,被佔用自動遞增
# 開 http://localhost:8501
```

### CLI(安裝 package 後)

```bash
twetf perf 0050 10000                         # 績效分析
twetf target 1000 20 --cagr 7                 # 目標試算
twetf dividend 0056                           # 股利歷史
twetf compare 0050 00878 2330 --dca 15000     # 多檔比較
twetf retire --alloc 0050:90,00859B:5,現金:5 --asset 2000 --rate 4 --years 30
twetf track  --alloc 0050:90,00859B:5,現金:5 --port 2000 --start 2020-01
```

未安裝時也可直接跑 shim:`python etf_cli.py perf 0050 10000`

## 部署到 Streamlit Community Cloud

1. 推 GitHub(`.env` / `.venv/` / `stock_cache/` 已在 `.gitignore`)
2. 前往 [share.streamlit.io](https://share.streamlit.io),連結 repo
3. **Main file:`etf_web.py`**
4. Advanced settings → Secrets:
   ```toml
   FINMIND_TOKEN = "你的token"
   ```
5. Deploy

系統相依性透過 `packages.txt` 自動安裝(pango / cairo 給 weasyprint)。

## 檔案結構

```
tw-etf-analyzer/
├── etf_web.py                # Streamlit entry(~100 行 dispatcher)
├── etf_cli.py                # CLI entry shim(~10 行)
├── etf_core.py / etf_pdf.py  # 向後相容 re-export shim
├── pyproject.toml            # package metadata + console_scripts
├── requirements.txt          # Streamlit Cloud 用(pyproject 不被讀)
├── packages.txt              # apt 依賴(libpango 等)
├── fonts/                    # Noto Sans CJK TC(PDF 字體)
├── .streamlit/config.toml
│
├── tw_etf_analyzer/          # 主 package
│   ├── config.py             # 路徑、Token
│   ├── constants.py          # 全域常數
│   ├── core/                 # 純計算(零 UI / IO 邊界)
│   │   ├── data.py           # FinMind + 快取 + 還原股價
│   │   ├── performance.py    # LumpSum / DCA / Compare / Target
│   │   ├── metrics.py        # MDD / Sharpe / Sortino / Calmar / Correlation
│   │   ├── simulation.py     # GK(deterministic / MC / historical)
│   │   └── tax.py            # TaxFeeConfig + 股利稅 + 二代健保
│   ├── web/                  # Streamlit UI
│   │   ├── bootstrap.py      # runtime pip install 保險
│   │   ├── cache.py          # @st.cache_data 包裝
│   │   ├── context.py        # AppContext dataclass
│   │   ├── display.py        # 名目↔實質換算
│   │   ├── presets.py        # 投組預設(5 種)
│   │   ├── sidebar.py        # 全域側邊欄
│   │   ├── storage.py        # localStorage 持久化
│   │   └── views/            # 一分頁一檔
│   │       ├── performance.py / target.py / retirement.py
│   │       ├── stress.py     / tracking.py / compare.py
│   │       ├── dividend.py   / pdf_export.py
│   ├── cli/                  # CLI(twetf console_script)
│   │   ├── main.py           # argparse dispatcher
│   │   └── commands/         # 一 subcommand 一檔
│   │       ├── _format.py    / perf.py / target.py
│   │       ├── dividend.py   / compare.py / retire.py / track.py
│   └── pdf/
│       └── builder.py        # PDFReportBuilder(weasyprint + Noto CJK TC)
│
└── tests/                    # pytest(41 tests,全綠)
    ├── conftest.py           # synthetic fixtures
    ├── test_tax.py           # 稅費
    ├── test_metrics.py       # 風險指標
    ├── test_simulation.py    # GK 模擬
    └── test_performance.py   # 績效計算
```

## 開發

```bash
# 安裝 dev extras
pip install -e ".[dev]"

# 跑測試
pytest tests/ -v

# 格式化 / lint(選配,repo 目前無設定)
```

## 股票代號範例

輸入代號時不需要加 `.TW`:

| 代號 | 名稱 |
|------|------|
| `0050` | 元大台灣50 ETF |
| `0056` | 元大高股息 ETF |
| `00878` | 國泰永續高股息 ETF |
| `00631L` | 富邦台灣加權正2 ETF |
| `00679B` | 元大美債20年 ETF |
| `2330` | 台積電 |

## 退休模擬說明

- **策略**:Guyton-Klinger (GK) 動態提領
  - 初始提領率 5%(可調,推薦 4-6%)
  - 護欄 ±20%:超過觸發提領額 ×0.90 或 ×1.10
  - 每年自動通膨調整(若資產未縮水)
- **預設組合**(5 種):保守配息型、債券優先型、全高股息型、均衡穩健型、槓桿平衡型
- **報酬假設**:自動從 FinMind 歷史資料計算 CAGR + 年化波動度
- **分配模型**:3 種可切換 — 常態、Student-t 肥尾、Bootstrap(歷史月報酬)
- **警告**:歷史資料不足 10 年的標的標示 ⚠️,CAGR 可能因短期多頭偏高

## 設定記憶

所有參數自動儲存至瀏覽器 localStorage(單一 JSON key `etf_all`),重新整理後還原,不需後端。

## 注意事項

- FinMind 免費帳號每小時 600 次 API 請求,初次下載一檔約使用 3 次
- 本地快取 24 小時,可用「強制重新下載」按鈕清除
- 還原股價計算方式等同「股利全部再投入」,為標準總報酬計算(未扣稅)
- 啟用稅費建模後會在淨值顯示扣稅結果,但 raw 歷史數據維持毛值
- Streamlit Community Cloud 為 serverless,重啟後 cache 消失(每次重新下載)
- PDF 匯出需 32MB Noto Sans CJK TC 字體(位於 `fonts/`,已 commit 進 repo)

## 重構歷史

- **0.2.0**:重構為正式 Python package,`etf_web.py` 從 2487 → 104 行
- **0.1.x**:初版單檔結構
