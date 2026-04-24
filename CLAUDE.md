# CLAUDE.md — tw-etf-analyzer

## 語言設定

所有回覆(包含思考過程與輸出)一律使用**繁體中文**。

## Package 架構

重構為正式 Python package `tw_etf_analyzer`:

```
tw_etf_analyzer/
├── config.py             # 路徑、Token、cache TTL(統一以 PROJECT_ROOT = cwd 為基準)
├── constants.py          # 現金假設、稅費常數、FinMind URL
├── core/                 # 純計算(零 UI / IO 邊界)
│   ├── data.py           # FinMind API + 快取 + 還原股價
│   ├── performance.py    # calc_comparison / calc_multi_compare / calc_target_*
│   ├── metrics.py        # MDD / Sharpe / Sortino / Calmar / 相關性矩陣
│   ├── simulation.py     # GK 單次 / Monte Carlo(Normal/t-dist/Bootstrap) / 歷史月頻
│   └── tax.py            # TaxFeeConfig + 股利稅 + 二代健保 + 手續費
├── web/                  # Streamlit UI
│   ├── app.py            # (未使用,邏輯在根目錄 etf_web.py)
│   ├── bootstrap.py      # 執行期依賴補裝
│   ├── cache.py          # @st.cache_data 包裝(multi-view 共用)
│   ├── context.py        # AppContext dataclass
│   ├── display.py        # 名目↔實質換算
│   ├── presets.py        # 投組預設(保守配息型等 5 種)
│   ├── sidebar.py        # 全域側邊欄(稅費 + 顯示模式)
│   ├── storage.py        # localStorage 持久化
│   └── views/            # 一分頁一檔
│       ├── performance.py
│       ├── target.py
│       ├── retirement.py
│       ├── stress.py
│       ├── tracking.py
│       ├── compare.py
│       ├── dividend.py
│       └── pdf_export.py
├── cli/                  # CLI(`twetf` console_script)
│   ├── main.py           # argparse dispatcher
│   └── commands/         # 一 subcommand 一檔
│       ├── _format.py    # wlen / wpad / hr / parse_alloc / fetch_multi
│       ├── perf.py
│       ├── target.py
│       ├── dividend.py
│       ├── compare.py
│       ├── retire.py
│       └── track.py
└── pdf/
    └── builder.py        # PDFReportBuilder(weasyprint + Noto Sans CJK TC)
```

根目錄保留 **薄 entry shim** 以相容既有部署:
- `etf_web.py` → Streamlit Cloud main file(10 行 dispatcher)
- `etf_cli.py` → 向後相容 `python etf_cli.py ...`
- `etf_core.py` → re-export shim(新程式直接 `from tw_etf_analyzer.core import ...`)
- `etf_pdf.py` → re-export shim

## 啟動

```bash
# Streamlit(Web)
streamlit run etf_web.py   # 預設 8501,被佔用時自動遞增

# CLI(安裝 package 後)
pip install -e .
twetf perf 0050 10000
twetf retire --alloc 0050:90,00859B:5,現金:5 --asset 2000 --rate 4 --years 30

# 或不安裝,直接 shim
python etf_cli.py perf 0050 10000
```

## Token 讀取順序

`tw_etf_analyzer.config.load_token()`:
Streamlit Secrets → `PROJECT_ROOT/.env` → 環境變數 `FINMIND_TOKEN`

## 設定持久化(localStorage)

`tw_etf_analyzer.web.storage`:
- 所有使用者設定打包為單一 JSON 存入 `localStorage["etf_all"]`
- 頁面載入時 async 讀取(第二次 render 才拿到值)
- 用 `_ls_applied` 旗標防止 render-1 預設值蓋掉已存值

## 設計慣例

**路徑**:絕不使用 `Path(__file__).parent`(package 化會指到 site-packages)。
所有路徑從 `tw_etf_analyzer.config` 取,以 `cwd` 或 `TWETF_ROOT` 環境變數為基準。

**AppContext**:每個 view 的 `render(ctx: AppContext)` 透過 dataclass 接收
token / stock_id / close_full / tax_cfg / is_real / inflation。
不直接讀 `st.session_state` 的全域狀態(僅讀 widget key 的本地輸入)。

**數字格式化**:Streamlit Arrow renderer 不保證 `Styler.format()` 對小數有效。
需要控制小數位的欄位直接在 DataFrame 建立時預格式化為字串(`f"{v:.2f}"`);
只有需要顏色 highlight 的欄位才保留 float 搭配 `.style.map()`。

**短歷史警告**:歷史資料不足 10 年的標的標示 ⚠️,CAGR 可能因短期多頭偏高。

**現金假設**:`現金` 無代號,固定 return=0%、vol=0%(`constants.CASH_RETURN` / `CASH_VOL`)。
代表實際現金(活存/抽屜),不含貨幣市場收益;想納入短期收益請改用短期債券 ETF。

**多檔比較**:以最晚上市的日期為共同起始點。

## 常見修改位置

| 需求 | 位置 |
|------|------|
| 新增退休預設組合 | `tw_etf_analyzer/web/presets.py` → `PRESETS` |
| GK 護欄邏輯 | `tw_etf_analyzer/core/simulation.py` → `simulate_gk*` / `run_gk_historical` |
| 稅費計算 | `tw_etf_analyzer/core/tax.py` |
| 新增分頁 | 建立 `tw_etf_analyzer/web/views/X.py` 並在 `etf_web.py` 註冊 |
| 新增 CLI subcommand | 建立 `tw_etf_analyzer/cli/commands/X.py`,在 `cli/main.py` 的 DISPATCH 註冊 |
| 短歷史警告閾值 | `tw_etf_analyzer/web/views/retirement.py` → `yrs < 10` |
| 快取 TTL | `tw_etf_analyzer/config.py` → `CACHE_TTL_H` |

## 測試

```bash
pytest tests/ -v
```

測試覆蓋:
- `tests/test_tax.py` — 合併 vs 分離課稅、NHI 閾值、到手比率
- `tests/test_metrics.py` — MDD / Sharpe / Sortino / Calmar / 相關性
- `tests/test_simulation.py` — GK 護欄觸發、Bootstrap 分配
- `tests/test_performance.py` — calc_comparison / calc_target_monthly
