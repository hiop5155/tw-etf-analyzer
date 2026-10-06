# 📈 台股 ETF 分析器 (tw-etf-analyzer) 遷移至 Cloudflare 架構實施計畫

完整計畫文件請參閱根目錄的 [change_to_cloudflare_plan.md](../change_to_cloudflare_plan.md)。

---

## 快速摘要

本計畫旨在將 `tw-etf-analyzer` 徹底從 **Python Streamlit (Community Cloud)** 搬遷至 **React 19 + TypeScript + Cloudflare 邊緣無伺服器 (Serverless) 架構**：

1. **徹底解決 Streamlit 休眠痛點**：
   - 0ms 冷啟動，24 小時永遠在線秒開。
   - 零主機維護成本。
2. **FinMind API 三層防護與快取設計**：
   - **安全代理**：Token 封裝於 Cloudflare 邊緣 Secrets，前端零洩漏。
   - **邊緣 24 小時快取**：歷史股價一日僅需查詢 1 次，節省 99.9% 請求額度。
   - **邊緣除權息還原**：於 Cloudflare Functions 預先完成還原除權息計算，回傳精簡輕量資料。
3. **8 大功能模組 1:1 完美重構**：
   - 績效分析、目標試算、退休提領模擬（含 Guyton-Klinger 護欄與蒙地卡羅扇形圖）、壓力測試、提領追蹤、多檔比較、股利歷史（二代健保補充保費試算）、純前端 PDF 報表匯出。
