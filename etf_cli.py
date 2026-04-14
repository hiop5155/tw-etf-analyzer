# -*- coding: utf-8 -*-
"""台股績效分析 — CLI"""

import sys, io, argparse, unicodedata
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from etf_core import load_token, fetch_adjusted_close, calc_comparison

# ── 對齊工具 ──────────────────────────────────────────────────────────────────
def wlen(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in str(s))

def wpad(s: str, width: int, align: str = "left") -> str:
    s = str(s); pad = max(0, width - wlen(s))
    return (s + " " * pad) if align == "left" else (" " * pad + s)

def token_missing():
    print("找不到 FINMIND_TOKEN，請擇一設定：")
    print()
    print("  方法一：建立 .env 檔（推薦）")
    print("    內容：FINMIND_TOKEN=你的token")
    print()
    print("  方法二：環境變數")
    print("    PowerShell ： $env:FINMIND_TOKEN = \"你的token\"")
    print("    CMD        ： set FINMIND_TOKEN=你的token")
    print("    macOS/Linux： export FINMIND_TOKEN=你的token")

def main():
    parser = argparse.ArgumentParser(description="台股績效分析")
    parser.add_argument("stock_id",   nargs="?")
    parser.add_argument("dca_amount", nargs="?", type=float)
    parser.add_argument("--refresh",  action="store_true", help="強制重新下載（忽略快取）")
    args = parser.parse_args()

    token = load_token()
    if not token:
        token_missing(); sys.exit(1)

    stock_id = args.stock_id or input("股票代號（例如 00631L，不需要 .TW）: ").strip().upper()
    stock_id = stock_id.upper().removesuffix(".TW")

    if args.dca_amount:
        monthly_dca = args.dca_amount
    else:
        monthly_dca = float(input("每月定期定額金額（TWD，例如 25000）: ").strip().replace(",", ""))

    print()

    close, logs = fetch_adjusted_close(stock_id, token, force=args.refresh)
    for log in logs:
        print(log)

    result = calc_comparison(close, monthly_dca)
    lump   = result.lump
    dca    = result.dca

    print(f"\n股票代號            : {stock_id}")
    print(f"成立日期（首筆資料）: {lump.inception_date.date()}")
    print(f"最新資料日期        : {lump.last_date.date()}")
    print(f"成立時股價（還原後）: {lump.p0:.4f}")
    print(f"最新股價（還原後）  : {lump.p_last:.4f}")

    # 單筆
    print()
    print("=" * 60)
    print("【單筆買進持有 — 成立日至今】")
    print(f"  總報酬    : {lump.total_return_pct:+,.1f}%  （共 {lump.years:.2f} 年）")
    print(f"  年化報酬  : {lump.cagr_pct:+.2f}%")
    print("=" * 60)

    # 定期定額逐年
    W_YEAR=6; W_NUM=16; W_PCT=10; SEP="  "
    TOTAL = W_YEAR + W_NUM*3 + W_PCT + len(SEP)*4

    print()
    print(f"【定期定額 每月 {monthly_dca:,.0f} TWD — 逐年績效】")
    print("=" * TOTAL)
    print(
        wpad("年度",      W_YEAR,"right") + SEP +
        wpad("累計投入",  W_NUM, "right") + SEP +
        wpad("期末市值",  W_NUM, "right") + SEP +
        wpad("未實現損益",W_NUM, "right") + SEP +
        wpad("累計報酬率",W_PCT, "right")
    )
    print("-" * TOTAL)
    for r in dca.years:
        print(
            f"{r.year:>{W_YEAR}}{SEP}"
            f"{r.cost_cum:>{W_NUM},.0f}{SEP}"
            f"{r.value:>{W_NUM},.0f}{SEP}"
            f"{r.gain:>{W_NUM},.0f}{SEP}"
            f"{r.return_pct:>{W_PCT-1}.1f}%"
        )
    print("=" * TOTAL)
    LW = 14
    f  = dca.final
    print(f"  {wpad('終值',    LW)}  {f.value:>18,.0f} TWD")
    print(f"  {wpad('總投入',  LW)}  {f.cost_cum:>18,.0f} TWD")
    print(f"  {wpad('總報酬',  LW)}  {f.return_pct:>17.2f}%")
    print(f"  {wpad('年化報酬',LW)}  {result.dca_cagr_pct:>17.2f}%  （終值/本金）^(1/{lump.years:.2f}年）")
    print("=" * TOTAL)

    # 對照
    CW=16; LBW=16; TW2 = LBW + (CW+2)*2 + 4
    lump_label = lump.inception_date.strftime("%Y-%m-%d")
    dca_label  = f"每月 {monthly_dca:,.0f}"
    print()
    print("【單筆 vs 定期定額 對照（同等本金）】")
    print("=" * TW2)
    print(f"  {wpad('',        LBW)}  {wpad('單筆投入',CW,'right')}  {wpad('定期定額',CW,'right')}")
    print(f"  {wpad('投入方式',LBW)}  {wpad(lump_label,CW,'right')}  {wpad(dca_label, CW,'right')}")
    print(f"  {wpad('總本金',  LBW)}  {f.cost_cum:>{CW},.0f}  {f.cost_cum:>{CW},.0f}")
    print(f"  {wpad('終值',    LBW)}  {result.lump_same_cost_final:>{CW},.0f}  {f.value:>{CW},.0f}")
    print(f"  {wpad('總報酬',  LBW)}  {result.lump_same_cost_ret:>{CW-1}.1f}%  {f.return_pct:>{CW-1}.2f}%")
    print(f"  {wpad('年化報酬',LBW)}  {result.lump_same_cost_cagr:>{CW-1}.2f}%  {result.dca_cagr_pct:>{CW-1}.2f}%")
    print("=" * TW2)

if __name__ == "__main__":
    main()
