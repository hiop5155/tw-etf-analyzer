# -*- coding: utf-8 -*-
"""ETF 績效分析 — Web UI (Streamlit)"""

import subprocess, sys, io
for pkg in ["streamlit", "pandas", "plotly", "openpyxl"]:
    try:
        __import__(pkg)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from etf_core import load_token, fetch_adjusted_close, calc_comparison

st.set_page_config(page_title="ETF 績效分析", page_icon="📈", layout="wide")
st.title("📈 ETF 績效分析")

# ── Token ─────────────────────────────────────────────────────────────────────
token = load_token()
if not token:
    st.error("找不到 FINMIND_TOKEN，請在 .env 檔設定：`FINMIND_TOKEN=你的token`")
    st.stop()

# ── 輸入區 ────────────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns([2, 2, 1])
stock_id    = c1.text_input("股票代號（不需要 .TW）", value="00631L").upper().removesuffix(".TW")
monthly_dca = c2.number_input("每月定期定額（TWD）", min_value=1000, value=25000, step=1000)
c3.write(""); c3.write("")
refresh = c3.button("🔄 重新下載", width='stretch')

st.divider()

if not stock_id:
    st.info("請輸入股票代號")
    st.stop()

# ── 資料 ──────────────────────────────────────────────────────────────────────
with st.spinner(f"載入 {stock_id} 資料..."):
    try:
        close, _ = fetch_adjusted_close(stock_id, token, force=refresh)
    except Exception as e:
        st.error(str(e)); st.stop()

result = calc_comparison(close, monthly_dca)
lump   = result.lump
dca    = result.dca
f      = dca.final

# ── 摘要卡片 ──────────────────────────────────────────────────────────────────
st.subheader(f"{stock_id}　{lump.inception_date.date()} ～ {lump.last_date.date()}　（{lump.years:.1f} 年）")

c1, c2, c3, c4 = st.columns(4)
c1.metric("單筆總報酬",      f"{lump.total_return_pct:+,.1f}%")
c2.metric("單筆年化報酬",    f"{lump.cagr_pct:+.2f}%")
c3.metric("定期定額總報酬",  f"{f.return_pct:+.1f}%")
c4.metric("定期定額年化報酬",f"{result.dca_cagr_pct:+.2f}%")

# ── 定期定額逐年表 ────────────────────────────────────────────────────────────
st.subheader(f"定期定額每月 {monthly_dca:,.0f} TWD — 逐年績效")
df = pd.DataFrame([{
    "年度"       : r.year,
    "累計投入"   : r.cost_cum,
    "期末市值"   : r.value,
    "未實現損益" : r.gain,
    "累計報酬率%": round(r.return_pct, 1),
} for r in dca.years])

st.dataframe(
    df.style.format({
        "累計投入"  : "{:,.0f}",
        "期末市值"  : "{:,.0f}",
        "未實現損益": "{:,.0f}",
    }).map(
        lambda v: "color: red" if isinstance(v, (int, float)) and v < 0 else "",
        subset=["未實現損益", "累計報酬率%"]
    ),
    width='stretch', hide_index=True
)

# ── 折線圖 ────────────────────────────────────────────────────────────────────
st.subheader("期末市值 vs 累計投入")
fig = go.Figure()
fig.add_trace(go.Scatter(x=df["年度"], y=df["期末市值"], name="期末市值", mode="lines+markers"))
fig.add_trace(go.Scatter(x=df["年度"], y=df["累計投入"], name="累計投入", mode="lines+markers", line=dict(dash="dash")))
fig.update_layout(xaxis_title="年度", yaxis_title="TWD", hovermode="x unified")
st.plotly_chart(fig, width='stretch')

# ── 單筆 vs 定期定額 對照 ─────────────────────────────────────────────────────
st.subheader("單筆 vs 定期定額 對照（同等本金）")
inception = lump.inception_date.strftime("%Y-%m-%d")
cmp = pd.DataFrame([
    {"項目": "開始投入日期",  "單筆投入": inception,                             "定期定額": inception},
    {"項目": "總本金 (TWD)", "單筆投入": f"{f.cost_cum:,.0f}",                  "定期定額": f"{f.cost_cum:,.0f}"},
    {"項目": "終值 (TWD)",   "單筆投入": f"{result.lump_same_cost_final:,.0f}",  "定期定額": f"{f.value:,.0f}"},
    {"項目": "總報酬",       "單筆投入": f"{result.lump_same_cost_ret:.1f}%",    "定期定額": f"{f.return_pct:.2f}%"},
    {"項目": "年化報酬",     "單筆投入": f"{result.lump_same_cost_cagr:.2f}%",   "定期定額": f"{result.dca_cagr_pct:.2f}%"},
])
st.dataframe(cmp, width='stretch', hide_index=True)

# ── 下載 ──────────────────────────────────────────────────────────────────────
st.divider()
st.subheader("下載結果")

def build_excel(stock_id, monthly_dca, lump, result, df, cmp) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        # 摘要
        summary = pd.DataFrame([
            {"項目": "股票代號",       "數值": stock_id},
            {"項目": "資料起始日",     "數值": str(lump.inception_date.date())},
            {"項目": "最新資料日",     "數值": str(lump.last_date.date())},
            {"項目": "持有年數",       "數值": round(lump.years, 2)},
            {"項目": "每月定期定額",   "數值": monthly_dca},
            {"項目": "單筆總報酬%",    "數值": round(lump.total_return_pct, 2)},
            {"項目": "單筆年化報酬%",  "數值": round(lump.cagr_pct, 2)},
            {"項目": "定期定額總報酬%","數值": round(result.dca.final.return_pct, 2)},
            {"項目": "定期定額年化%",  "數值": round(result.dca_cagr_pct, 2)},
        ])
        summary.to_excel(writer, sheet_name="摘要", index=False)
        df.to_excel(writer, sheet_name="逐年績效", index=False)
        cmp.to_excel(writer, sheet_name="單筆vs定期定額", index=False)
    return buf.getvalue()

excel_bytes = build_excel(stock_id, monthly_dca, lump, result, df, cmp)
filename    = f"{stock_id}_ETF分析_{lump.last_date.strftime('%Y%m%d')}.xlsx"

c1, c2 = st.columns(2)

c1.download_button(
    label    = "⬇️ 下載 Excel（含三個工作表）",
    data     = excel_bytes,
    file_name= filename,
    mime     = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    width    = "stretch",
)

csv_bytes = df.to_csv(index=False).encode("utf-8-sig")  # utf-8-sig 讓 Excel 開中文不亂碼
c2.download_button(
    label    = "⬇️ 下載 CSV（逐年績效）",
    data     = csv_bytes,
    file_name= f"{stock_id}_逐年績效_{lump.last_date.strftime('%Y%m%d')}.csv",
    mime     = "text/csv",
    width    = "stretch",
)
