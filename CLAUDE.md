# CLAUDE.md — tw-etf-analyzer

## 語言設定

所有回覆（包含思考過程與輸出）一律使用**繁體中文**。

## 架構

- `etf_core.py` — 純計算邏輯（資料下載、快取、還原股價、績效/模擬），無 UI
- `etf_web.py` — Streamlit 5 分頁介面，所有 `st.*` 在這裡

## 啟動

```bash
streamlit run etf_web.py   # 預設 8501，被佔用時自動遞增
```

## Token 讀取順序

Streamlit Secrets → `.env` 檔 → 環境變數 `FINMIND_TOKEN`

## 設定持久化（localStorage）

使用 `streamlit-local-storage` 套件，透過瀏覽器 localStorage 記住使用者設定。

**運作流程**：
1. 頁面載入時，`LocalStorage.getItem()` 非同步讀取 — 第一次 render 回傳 `None`
2. JS component 載入完成後觸發 rerun，第二次 render 拿到值
3. 用 `st.session_state["_ls_applied"]` 旗標確保只套用一次（避免蓋掉使用者後續輸入）
4. 儲存時比對上次存的值（`_lsprev_*`），只有變動才呼叫 `setItem`（避免無限 rerun）

**localStorage 鍵值對應**：

| localStorage key | 對應 widget key | 說明 |
|-----------------|----------------|------|
| `etf_sid` | `_w_sid` | 股票代號 |
| `etf_dca` | `_w_dca` | 每月定期定額 |
| `etf_r_asset` | `_w_rasset` | 退休起始資產 |
| `etf_r_years` | `_w_ryears` | 模擬年數 |
| `etf_r_inf` | `_w_rinf` | 通膨率 |
| `etf_r_rate` | `_w_rrate` | 初始提領率 |
| `etf_r_guard` | `_w_rguard` | 護欄寬度 |
| `etf_r_preset` | `preset_choice` | 預設組合選擇 |

## 設計慣例

**數字格式化**：Streamlit Arrow renderer 不保證 `Styler.format()` 對小數有效。
需要控制小數位的欄位直接在 DataFrame 建立時預格式化為字串（`f"{v:.2f}"`）；
只有需要顏色 highlight 的欄位才保留 float 搭配 `.style.map()`。

**短歷史警告**：歷史資料不足 10 年的標的標示 ⚠️，CAGR 可能因短期多頭偏高。

**現金假設**：`現金` 無代號，固定 return=1.5%、vol=0.5%（`_CASH_RETURN` / `_CASH_VOL`）。

**多檔比較**：以最晚上市的日期為共同起始點。

## 常見修改位置

| 需求 | 位置 |
|------|------|
| 新增退休預設組合 | `etf_web.py` → `_PRESETS` |
| GK 護欄邏輯 | `etf_core.py` → `simulate_gk()` / `simulate_gk_montecarlo()` |
| 短歷史警告閾值 | `etf_web.py` → `yrs < 10`（共 2 處）|
| 快取 TTL | `etf_core.py` → `CACHE_TTL_H` |
