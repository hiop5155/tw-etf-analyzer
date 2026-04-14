# CLAUDE.md — tw-etf-analyzer

## 架構

- `etf_core.py` — 純計算邏輯（資料下載、快取、還原股價、績效/模擬），無 UI
- `etf_web.py` — Streamlit 5 分頁介面，所有 `st.*` 在這裡

## 啟動

```bash
streamlit run etf_web.py   # 預設 8501，被佔用時自動遞增
```

## Token 讀取順序

Streamlit Secrets → `.env` 檔 → 環境變數 `FINMIND_TOKEN`

## 設計慣例

**數字格式化**：Streamlit Arrow renderer 不保證 `Styler.format()` 對小數有效。
需要控制小數位的欄位直接在 DataFrame 建立時預格式化為字串（`f"{v:.2f}"`）；
只有需要顏色 highlight 的欄位才保留 float 搭配 `.style.map()`。

**短歷史警告**：歷史資料不足 10 年的 ETF 標示 ⚠️，CAGR 可能因短期多頭偏高。

**現金假設**：`現金` 無代號，固定 return=1.5%、vol=0.5%（`_CASH_RETURN` / `_CASH_VOL`）。

**多 ETF 比較**：以最晚成立的 ETF 日期為共同起始點。

## 常見修改位置

| 需求 | 位置 |
|------|------|
| 新增退休預設組合 | `etf_web.py` → `_PRESETS` |
| GK 護欄邏輯 | `etf_core.py` → `simulate_gk()` / `simulate_gk_montecarlo()` |
| 短歷史警告閾值 | `etf_web.py` → `yrs < 10`（共 2 處）|
| 快取 TTL | `etf_core.py` → `CACHE_TTL_H` |
