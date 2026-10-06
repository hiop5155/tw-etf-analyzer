# -*- coding: utf-8 -*-
"""perf subcommand — 績效分析(單筆 vs 定期定額逐年)。"""

from __future__ import annotations

from tw_etf_analyzer.core.data import fetch_adjusted_close
from tw_etf_analyzer.core.performance import calc_comparison

from tw_etf_analyzer.cli.commands._format import hr, wpad


def cmd_perf(args, token: str) -> None:
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

    W_YEAR = 6
    W_NUM  = 16
    W_PCT  = 10
    SEP    = "  "
    TOTAL  = W_YEAR + W_NUM * 3 + W_PCT + len(SEP) * 4

    print()
    print(f"【定期定額 每月 {args.dca_amount:,.0f} TWD — 逐年績效】")
    hr(width=TOTAL)
    print(
        wpad("年度",       W_YEAR, "right") + SEP +
        wpad("累計投入",   W_NUM,  "right") + SEP +
        wpad("期末市值",   W_NUM,  "right") + SEP +
        wpad("未實現損益", W_NUM,  "right") + SEP +
        wpad("累計報酬率", W_PCT,  "right")
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
    LW = 14
    f = dca.final
    print(f"  {wpad('終值',    LW)}  {f.value:>18,.0f} TWD")
    print(f"  {wpad('總投入',  LW)}  {f.cost_cum:>18,.0f} TWD")
    print(f"  {wpad('總報酬',  LW)}  {f.return_pct:>17.2f}%")
    print(f"  {wpad('年化報酬',LW)}  {result.dca_cagr_pct:>17.2f}%  （終值/本金）^(1/{lump.years:.2f}年）")
    hr(width=TOTAL)

    CW  = 16
    LBW = 16
    TW2 = LBW + (CW + 2) * 2 + 4
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
