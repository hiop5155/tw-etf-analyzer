# -*- coding: utf-8 -*-
"""台股績效分析 — CLI"""

import sys, io, argparse, unicodedata
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from etf_core import (
    load_token, fetch_adjusted_close, fetch_dividend_history,
    calc_comparison, calc_multi_compare, calc_target_monthly,
    simulate_gk_montecarlo, run_gk_historical, calc_return_vol,
    CASH_RETURN, CASH_VOL,
)

# ── 格式化工具 ─────────────────────────────────────────────────────────────────
def wlen(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in str(s))

def wpad(s: str, width: int, align: str = "left") -> str:
    s = str(s); pad = max(0, width - wlen(s))
    return (s + " " * pad) if align == "left" else (" " * pad + s)

def hr(char="=", width=64):
    print(char * width)

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


def parse_alloc(alloc_str: str) -> dict[str, float]:
    """
    解析 '0050:90,00859B:5,現金:5' 格式。
    回傳 {股票代號: 比例（小數）}，比例總和應為 1.0。
    """
    result: dict[str, float] = {}
    for part in alloc_str.split(","):
        part = part.strip()
        if ":" not in part:
            raise ValueError(f"配置格式錯誤：{part!r}，應為「代號:整數比例」")
        sid, w = part.split(":", 1)
        sid = sid.strip()
        # 非中文標的才轉大寫，避免破壞 "現金" 等保留字
        if sid.isascii():
            sid = sid.upper().removesuffix(".TW")
        result[sid] = float(w.strip()) / 100
    return result


def fetch_multi(
    stock_ids: list[str], token: str, force: bool = False
) -> dict:
    """批次下載多檔收盤價（略過現金），回傳 {sid: pd.Series}。"""
    closes: dict = {}
    for sid in stock_ids:
        if sid == "現金":
            continue
        print(f"  下載 {sid}...", end=" ", flush=True)
        close, logs = fetch_adjusted_close(sid, token, force=force)
        print("完成")
        closes[sid] = close
    return closes


# ════════════════════════════════════════════════════════════════════════════
# perf — 績效分析
# ════════════════════════════════════════════════════════════════════════════
def cmd_perf(args, token):
    close, logs = fetch_adjusted_close(args.stock_id, token, force=args.refresh)
    for log in logs:
        print(log)

    result = calc_comparison(close, args.dca_amount)
    lump   = result.lump
    dca    = result.dca

    print(f"\n股票代號            : {args.stock_id}")
    print(f"成立日期（首筆資料）: {lump.inception_date.date()}")
    print(f"最新資料日期        : {lump.last_date.date()}")
    print(f"成立時股價（還原後）: {lump.p0:.4f}")
    print(f"最新股價（還原後）  : {lump.p_last:.4f}")

    print()
    hr()
    print("【單筆買進持有 — 成立日至今】")
    print(f"  總報酬    : {lump.total_return_pct:+,.1f}%  （共 {lump.years:.2f} 年）")
    print(f"  年化報酬  : {lump.cagr_pct:+.2f}%")
    hr()

    W_YEAR=6; W_NUM=16; W_PCT=10; SEP="  "
    TOTAL = W_YEAR + W_NUM * 3 + W_PCT + len(SEP) * 4

    print()
    print(f"【定期定額 每月 {args.dca_amount:,.0f} TWD — 逐年績效】")
    hr(width=TOTAL)
    print(
        wpad("年度",      W_YEAR, "right") + SEP +
        wpad("累計投入",  W_NUM,  "right") + SEP +
        wpad("期末市值",  W_NUM,  "right") + SEP +
        wpad("未實現損益",W_NUM,  "right") + SEP +
        wpad("累計報酬率",W_PCT,  "right")
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
    hr(width=TOTAL)
    LW = 14; f = dca.final
    print(f"  {wpad('終值',    LW)}  {f.value:>18,.0f} TWD")
    print(f"  {wpad('總投入',  LW)}  {f.cost_cum:>18,.0f} TWD")
    print(f"  {wpad('總報酬',  LW)}  {f.return_pct:>17.2f}%")
    print(f"  {wpad('年化報酬',LW)}  {result.dca_cagr_pct:>17.2f}%  （終值/本金）^(1/{lump.years:.2f}年）")
    hr(width=TOTAL)

    CW=16; LBW=16; TW2 = LBW + (CW + 2) * 2 + 4
    lump_label = lump.inception_date.strftime("%Y-%m-%d")
    dca_label  = f"每月 {args.dca_amount:,.0f}"
    print()
    print("【單筆 vs 定期定額 對照（同等本金）】")
    hr(width=TW2)
    print(f"  {wpad('',        LBW)}  {wpad('單筆投入', CW,'right')}  {wpad('定期定額', CW,'right')}")
    print(f"  {wpad('投入方式',LBW)}  {wpad(lump_label, CW,'right')}  {wpad(dca_label,  CW,'right')}")
    print(f"  {wpad('總本金',  LBW)}  {f.cost_cum:>{CW},.0f}  {f.cost_cum:>{CW},.0f}")
    print(f"  {wpad('終值',    LBW)}  {result.lump_same_cost_final:>{CW},.0f}  {f.value:>{CW},.0f}")
    print(f"  {wpad('總報酬',  LBW)}  {result.lump_same_cost_ret:>{CW-1}.1f}%  {f.return_pct:>{CW-1}.2f}%")
    print(f"  {wpad('年化報酬',LBW)}  {result.lump_same_cost_cagr:>{CW-1}.2f}%  {result.dca_cagr_pct:>{CW-1}.2f}%")
    hr(width=TW2)


# ════════════════════════════════════════════════════════════════════════════
# target — 目標試算
# ════════════════════════════════════════════════════════════════════════════
def cmd_target(args, _token):
    target_twd   = args.target_wan * 10_000
    existing_twd = args.existing * 10_000

    result = calc_target_monthly(
        target          = target_twd,
        years           = args.years,
        annual_cagr_pct = args.cagr,
        existing        = existing_twd,
    )

    print(f"\n【目標試算】")
    hr()
    print(f"  目標金額     : {args.target_wan:>10,.0f} 萬 TWD")
    print(f"  投資年限     : {args.years:>10} 年")
    print(f"  預估年化報酬 : {args.cagr:>10.1f} %")
    if existing_twd > 0:
        print(f"  現有持倉     : {args.existing:>10,.0f} 萬 TWD")
        print(f"    └ {args.years} 年後終值 : {result['existing_fv']/10_000:>6,.0f} 萬")
    hr("-")
    if result["monthly"] == 0:
        print("  現有持倉已足夠達成目標，不需額外定投。")
    else:
        print(f"  每月定投     : {result['monthly']:>10,.0f} TWD")
        print(f"  總投入       : {result['total_invested']/10_000:>10,.1f} 萬 TWD")
        print(f"  預估報酬     : {result['total_gain']/10_000:>10,.1f} 萬 TWD")
    hr()


# ════════════════════════════════════════════════════════════════════════════
# dividend — 股利歷史
# ════════════════════════════════════════════════════════════════════════════
def cmd_dividend(args, token):
    print(f"\n下載 {args.stock_id} 股利資料...", end=" ", flush=True)
    df = fetch_dividend_history(args.stock_id, token)
    print("完成")

    if df is None or df.empty:
        print("無股利資料。")
        return

    # 只顯示關鍵欄位
    show_cols  = ["year", "date", "cash_dividend", "before_price", "after_price", "yield_pct"]
    col_labels = {"year": "年度", "date": "除息日", "cash_dividend": "現金股利",
                  "before_price": "除息前價", "after_price": "除息後價", "yield_pct": "殖利率%"}
    df_show = df[[c for c in show_cols if c in df.columns]].copy()
    df_show["date"] = df_show["date"].dt.strftime("%Y-%m-%d")

    headers = [col_labels.get(c, c) for c in df_show.columns]
    col_w   = [max(wlen(h), df_show[c].astype(str).map(wlen).max()) + 2
               for h, c in zip(headers, df_show.columns)]
    TOTAL   = sum(col_w)

    print(f"\n【{args.stock_id} 股利歷史】（共 {len(df_show)} 筆）")
    hr(width=TOTAL)
    print("".join(wpad(h, col_w[i], "right") for i, h in enumerate(headers)))
    print("-" * TOTAL)
    for _, row in df_show.iterrows():
        print("".join(wpad(str(v), col_w[i], "right") for i, v in enumerate(row)))
    hr(width=TOTAL)
    avg_yield = df_show["yield_pct"].astype(float).mean() if "yield_pct" in df_show.columns else 0
    print(f"  平均殖利率：{avg_yield:.2f}%")


# ════════════════════════════════════════════════════════════════════════════
# compare — 多檔比較
# ════════════════════════════════════════════════════════════════════════════
def cmd_compare(args, token):
    if len(args.stocks) < 2:
        print("錯誤：至少需要 2 檔。"); return
    if len(args.stocks) > 5:
        print("錯誤：最多支援 5 檔。"); return

    stock_ids = [s.upper().removesuffix(".TW") for s in args.stocks]
    print()
    closes = fetch_multi(stock_ids, token, force=args.refresh)
    if len(closes) < 2:
        print("有效資料不足 2 檔，無法比較。"); return

    records = calc_multi_compare(closes, args.dca)

    # 欄位寬度
    W  = [8, 12, 8, 12, 10, 14, 10, 12]
    CH = ["代號", "共同起始", "年數", "單筆總報酬%", "單筆年化%",
          f"定投終值(萬)\n每月{args.dca:,.0f}", "定投年化%", "上市日"]
    TOTAL = sum(W) + len(W) * 2

    print(f"\n【多檔績效比較（每月定投 {args.dca:,.0f} TWD）】")
    hr(width=TOTAL)
    print("  ".join(wpad(h.split("\n")[0], W[i], "right") for i, h in enumerate(CH)))
    print("-" * TOTAL)
    for r in records:
        print("  ".join(wpad(v, W[i], "right") for i, v in enumerate([
            r.stock_id,
            r.common_start.strftime("%Y-%m-%d"),
            f"{r.years:.1f}",
            f"{r.total_return_pct:+.1f}%",
            f"{r.cagr_pct:+.2f}%",
            f"{r.dca_final/10_000:,.0f}",
            f"{r.dca_cagr_pct:+.2f}%",
            r.inception_date.strftime("%Y-%m-%d"),
        ])))
    hr(width=TOTAL)
    print("  ※ 共同起始日 = 各標的中上市最晚的日期")


# ════════════════════════════════════════════════════════════════════════════
# retire — 退休模擬（Monte Carlo，不含圖表）
# ════════════════════════════════════════════════════════════════════════════
def cmd_retire(args, token):
    try:
        alloc = parse_alloc(args.alloc)
    except ValueError as e:
        print(f"錯誤：{e}"); return

    total_w = sum(alloc.values())
    if abs(total_w - 1.0) > 0.015:
        print(f"錯誤：配置比例總和 {total_w*100:.0f}%，應為 100%。"); return

    print()
    closes = fetch_multi(list(alloc.keys()), token, force=args.refresh)

    # 計算加權報酬與波動
    w_ret = 0.0; w_vol = 0.0
    print()
    hr("-")
    print("  標的報酬估算（來自歷史資料）：")
    for sid, weight in alloc.items():
        if sid == "現金":
            r, v = CASH_RETURN, CASH_VOL
            print(f"    現金  {weight*100:>4.0f}%：固定 {r*100:.2f}% / 波動 {v*100:.2f}%")
        else:
            if sid not in closes:
                print(f"    {sid}：無資料，跳過"); continue
            r, v = calc_return_vol(closes[sid])
            print(f"    {sid}  {weight*100:>4.0f}%：CAGR {r*100:+.2f}%  波動 {v*100:.2f}%")
        w_ret += weight * r
        w_vol += weight * v
    print(f"  加權結果：報酬 {w_ret*100:.2f}%  波動 {w_vol*100:.2f}%")
    hr("-")

    print(f"\n  模擬中（{args.sims:,} 次）...", end=" ", flush=True)
    mc = simulate_gk_montecarlo(
        initial_portfolio = args.asset * 10_000,
        initial_rate      = args.rate / 100,
        guardrail_pct     = args.guard / 100,
        annual_return     = w_ret,
        annual_volatility = w_vol,
        inflation_rate    = args.inf / 100,
        years             = args.years,
        n_sims            = args.sims,
    )
    print("完成")

    init_monthly = mc["initial_monthly"]
    surv_final   = mc["survival_final"]

    print(f"\n【退休模擬（Monte Carlo {args.sims:,} 次）】")
    print(f"  起始資產  : {args.asset:,.0f} 萬 TWD")
    print(f"  初始月提領: {init_monthly:,.0f} TWD（年率 {args.rate:.1f}%）")
    print(f"  護欄寬度  : ±{args.guard:.0f}%   通膨率：{args.inf:.1f}%")
    print(f"  模擬年數  : {args.years} 年")
    hr()
    print(f"  最終存活率（第 {args.years} 年）: {surv_final:.1f}%")
    hr("-")

    # 代表性路徑摘要
    LABELS = {1: "P1  極端悲觀", 10: "P10 悲觀", 50: "P50 中位", 90: "P90 樂觀"}
    W3 = [14, 16, 14, 10]
    TOTAL3 = sum(W3) + len(W3) * 2
    print("  " + "  ".join(wpad(h, W3[i], "right") for i, h in enumerate(
        ["路徑", f"第{args.years}年末資產(萬)", f"第{args.years}年月提領", "狀態"]
    )))
    print("  " + "-" * (TOTAL3))
    for pct in (1, 10, 50, 90):
        if pct not in mc["rep_paths"]: continue
        last = mc["rep_paths"][pct][-1]
        asset_str  = str(last.get("年末資產 (萬)", "—"))
        income_str = str(last.get("月提領額",      "—"))
        status     = "💀 耗盡" if asset_str == "0" else "✓ 存活"
        print("  " + "  ".join(wpad(v, W3[i], "right") for i, v in enumerate(
            [LABELS[pct], asset_str, income_str, status]
        )))
    hr("-")

    # 逐年存活率（每 5 年）
    print(f"\n  逐年存活率：")
    for yr, sr in zip(mc["years"], mc["survival_rate"]):
        if yr == 1 or yr % 5 == 0:
            bar = "█" * int(sr / 5)
            print(f"    第 {yr:2d} 年  {sr:5.1f}%  {bar}")
    hr()


# ════════════════════════════════════════════════════════════════════════════
# track — 提領追蹤（歷史實際報酬）
# ════════════════════════════════════════════════════════════════════════════
def cmd_track(args, token):
    try:
        alloc = parse_alloc(args.alloc)
    except ValueError as e:
        print(f"錯誤：{e}"); return

    total_w = sum(alloc.values())
    if abs(total_w - 1.0) > 0.015:
        print(f"錯誤：配置比例總和 {total_w*100:.0f}%，應為 100%。"); return

    print()
    closes = fetch_multi(list(alloc.keys()), token, force=args.refresh)

    result = run_gk_historical(
        initial_portfolio = args.port * 10_000,
        allocations       = alloc,
        start_ym          = args.start,
        initial_rate      = args.rate / 100,
        guardrail_pct     = args.guard / 100,
        inflation_rate    = args.inf / 100,
        close_series      = closes,
    )

    for dw in result.get("data_warnings", []):
        print(f"  ⚠ {dw}")

    monthly    = result["monthly"]
    rebalances = result["rebalances"]

    if not monthly:
        print("所選月份無歷史資料，請調整起始月份。"); return

    final_port = result["final_portfolio"]
    final_inc  = result["final_monthly_income"]

    print(f"\n【提領追蹤（{args.start} 起）】")
    print(f"  初始資產   : {args.port:,.0f} 萬 TWD")
    print(f"  提領率     : {args.rate:.1f}%   護欄 ±{args.guard:.0f}%   通膨 {args.inf:.1f}%")
    hr()
    print(f"  最終資產   : {final_port/10_000:,.1f} 萬 TWD")
    print(f"  最終月提領 : {final_inc:,.0f} TWD")
    hr()

    # 逐月明細
    W_M = [8, 9, 13, 11, 9, 16]
    TOTAL_M = sum(W_M) + len(W_M) * 2
    print()
    print("  " + "  ".join(wpad(h, W_M[i], "right") for i, h in enumerate(
        ["月份", "月報酬%", "資產餘額(萬)", "月提領(TWD)", "提領率%", "事件"]
    )))
    print("  " + "-" * TOTAL_M)
    for row in monthly:
        event = row["事件"] if row["事件"] != "—" else ""
        print("  " + "  ".join(wpad(v, W_M[i], "right") for i, v in enumerate([
            row["月份"],
            f"{row['月報酬 %']:+.2f}",
            f"{row['資產餘額 (萬)']:,.1f}",
            f"{row['月提領額']:,.0f}",
            f"{row['提領率 %']:.2f}",
            event,
        ])))

    # 再平衡事件
    if rebalances:
        gk_map = {
            "capital_preservation": "↓ 減提領10%（提領率過高）",
            "prosperity":           "↑ 增提領10%（提領率過低）",
            "":                     "通膨調整（無護欄觸發）",
        }
        print(f"\n【年度再平衡事件】")
        for rb in rebalances:
            hr("─")
            print(f"  {rb['year']} 年一月　"
                  f"資產 {rb['portfolio']/10_000:,.1f} 萬　"
                  f"新月提領 {rb['monthly_income']:,.0f} TWD")
            print(f"  GK 調整：{gk_map.get(rb['gk_trigger'], rb['gk_trigger'])}")
            W_A = [8, 8, 8, 8, 16]
            TOTAL_A = sum(W_A) + len(W_A) * 2
            print("  " + "  ".join(wpad(h, W_A[i], "right") for i, h in enumerate(
                ["標的", "目標%", "漂移%", "偏差", "再平衡建議(萬)"]
            )))
            print("  " + "-" * TOTAL_A)
            for a in rb["target_alloc"]:
                tgt   = rb["target_alloc"][a] * 100
                drift = rb["drift_alloc"].get(a, 0.0) * 100
                trade = rb["trades"].get(a, 0.0)
                trade_str = (
                    f"{'買入' if trade > 0 else '賣出'} {abs(trade)/10_000:,.1f}"
                    if abs(trade) > 500 else "—"
                )
                print("  " + "  ".join(wpad(v, W_A[i], "right") for i, v in enumerate([
                    a, f"{tgt:.1f}", f"{drift:.1f}", f"{drift-tgt:+.1f}", trade_str,
                ])))
        hr("─")
    else:
        print("\n  尚無再平衡事件（提領開始後的第一個一月才會觸發）。")


# ════════════════════════════════════════════════════════════════════════════
# 主程式
# ════════════════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(
        prog        = "etf_cli",
        description = "台股 ETF / 股票績效分析工具（資料來源：FinMind）",
        formatter_class = argparse.RawDescriptionHelpFormatter,
        epilog = """\
範例：
  etf_cli.py perf 0050 10000
  etf_cli.py target 1000 20 --cagr 7
  etf_cli.py dividend 0056
  etf_cli.py compare 0050 00878 2330 --dca 15000
  etf_cli.py retire --alloc 0050:90,00859B:5,現金:5 --asset 2000 --rate 4 --years 30
  etf_cli.py track  --alloc 0050:90,00859B:5,現金:5 --port 2000 --start 2020-01
""",
    )
    sub = parser.add_subparsers(dest="cmd", metavar="命令")
    sub.required = True

    # ── perf ──────────────────────────────────────────────────────────────
    p_perf = sub.add_parser("perf",
        help        = "績效分析：單筆 vs 定期定額逐年績效",
        description = "下載指定股票的還原股價，計算單筆與定期定額的歷史績效。",
    )
    p_perf.add_argument("stock_id",
        help = "股票代號，例如 0050、00631L（不需要 .TW）")
    p_perf.add_argument("dca_amount", type=float,
        help = "每月定期定額金額（TWD），例如 10000")
    p_perf.add_argument("--refresh", action="store_true",
        help = "強制重新下載，忽略本地快取")

    # ── target ────────────────────────────────────────────────────────────
    p_tgt = sub.add_parser("target",
        help        = "目標試算：反推「N 年後有 X 萬」每月需投入多少",
        description = "根據目標金額、年限與預估報酬率，反推每月所需定投金額。",
    )
    p_tgt.add_argument("target_wan", type=float,
        help = "目標金額（萬 TWD），例如 1000")
    p_tgt.add_argument("years", type=int,
        help = "投資年限（年），例如 20")
    p_tgt.add_argument("--cagr", type=float, required=True, metavar="RATE",
        help = "預估年化報酬率 %%（例如 7.5）")
    p_tgt.add_argument("--existing", type=float, default=0.0, metavar="WAN",
        help = "目前已持有市值（萬 TWD），預設 0")

    # ── dividend ──────────────────────────────────────────────────────────
    p_div = sub.add_parser("dividend",
        help        = "股利歷史：歷年配息與殖利率明細",
        description = "列出指定股票的除息日、現金股利金額與殖利率。",
    )
    p_div.add_argument("stock_id",
        help = "股票代號，例如 0056")
    p_div.add_argument("--refresh", action="store_true",
        help = "強制重新下載，忽略本地快取")

    # ── compare ───────────────────────────────────────────────────────────
    p_cmp = sub.add_parser("compare",
        help        = "多檔比較：2～5 檔股票同期績效對照",
        description = "以最晚上市的日期為共同起始點，比較多檔的單筆與定投績效。",
    )
    p_cmp.add_argument("stocks", nargs="+", metavar="代號",
        help = "2～5 個股票代號，例如 0050 00878 2330")
    p_cmp.add_argument("--dca", type=float, default=10000, metavar="TWD",
        help = "每月定投金額（TWD），預設 10000")
    p_cmp.add_argument("--refresh", action="store_true",
        help = "強制重新下載，忽略本地快取")

    # ── retire ────────────────────────────────────────────────────────────
    p_ret = sub.add_parser("retire",
        help        = "退休模擬：Monte Carlo × GK 動態提領策略（不含圖表）",
        description = "從歷史資料計算投資組合 CAGR 與波動，執行 Monte Carlo 模擬，\n輸出存活率與 P1/P10/P50/P90 代表性路徑結果。",
    )
    p_ret.add_argument("--alloc", required=True, metavar="代號:比例,...",
        help = "投資組合，格式：代號:整數比例，以逗號分隔，例如 0050:90,00859B:5,現金:5（比例總和須為 100）")
    p_ret.add_argument("--asset", type=float, required=True, metavar="WAN",
        help = "退休起始資產（萬 TWD）")
    p_ret.add_argument("--rate",  type=float, default=4.0,  metavar="PCT",
        help = "初始提領率 %%，預設 4.0")
    p_ret.add_argument("--guard", type=float, default=20.0, metavar="PCT",
        help = "護欄寬度 %%，預設 20.0（上護欄 = 初始率×1.2，下護欄 = 初始率×0.8）")
    p_ret.add_argument("--inf",   type=float, default=2.0,  metavar="PCT",
        help = "通膨率 %%，預設 2.0")
    p_ret.add_argument("--years", type=int,   default=30,   metavar="N",
        help = "模擬年數，預設 30")
    p_ret.add_argument("--sims",  type=int,   default=1000, metavar="N",
        help = "Monte Carlo 模擬次數，預設 1000")
    p_ret.add_argument("--refresh", action="store_true",
        help = "強制重新下載，忽略本地快取")

    # ── track ─────────────────────────────────────────────────────────────
    p_trk = sub.add_parser("track",
        help        = "提領追蹤：以歷史實際報酬逐月追蹤 GK 策略",
        description = "輸入開始提領的時間與初始條件，以 FinMind 歷史資料\n逐月執行 GK 提領策略，並顯示每年一月的再平衡建議。",
    )
    p_trk.add_argument("--alloc", required=True, metavar="代號:比例,...",
        help = "投資組合，格式同 retire，例如 0050:90,00859B:5,現金:5")
    p_trk.add_argument("--port",  type=float, required=True, metavar="WAN",
        help = "初始資產（萬 TWD）")
    p_trk.add_argument("--start", required=True, metavar="YYYY-MM",
        help = "開始提領月份，例如 2020-01")
    p_trk.add_argument("--rate",  type=float, default=4.0,  metavar="PCT",
        help = "初始提領率 %%，預設 4.0")
    p_trk.add_argument("--guard", type=float, default=20.0, metavar="PCT",
        help = "護欄寬度 %%，預設 20.0")
    p_trk.add_argument("--inf",   type=float, default=2.0,  metavar="PCT",
        help = "通膨率 %%，預設 2.0")
    p_trk.add_argument("--refresh", action="store_true",
        help = "強制重新下載，忽略本地快取")

    args = parser.parse_args()

    token = load_token()
    if not token:
        token_missing(); sys.exit(1)

    # 標準化 stock_id（perf / dividend 適用）
    if hasattr(args, "stock_id"):
        args.stock_id = args.stock_id.upper().removesuffix(".TW")

    dispatch = {
        "perf":     cmd_perf,
        "target":   cmd_target,
        "dividend": cmd_dividend,
        "compare":  cmd_compare,
        "retire":   cmd_retire,
        "track":    cmd_track,
    }
    dispatch[args.cmd](args, token)


if __name__ == "__main__":
    main()
