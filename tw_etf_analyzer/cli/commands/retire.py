# -*- coding: utf-8 -*-
"""retire subcommand — 退休 Monte Carlo × GK 動態提領。"""

from __future__ import annotations

from tw_etf_analyzer.constants import CASH_RETURN, CASH_VOL
from tw_etf_analyzer.core.metrics import calc_return_vol
from tw_etf_analyzer.core.simulation import simulate_gk_montecarlo

from tw_etf_analyzer.cli.commands._format import fetch_multi, hr, parse_alloc, wpad


def cmd_retire(args, token: str) -> None:
    try:
        alloc = parse_alloc(args.alloc)
    except ValueError as e:
        print(f"錯誤：{e}")
        return

    total_w = sum(alloc.values())
    if abs(total_w - 1.0) > 0.015:
        print(f"錯誤：配置比例總和 {total_w*100:.0f}%，應為 100%。")
        return

    print()
    closes = fetch_multi(list(alloc.keys()), token, force=args.refresh)

    w_ret, w_vol = 0.0, 0.0
    print()
    hr("-")
    print("  標的報酬估算（來自歷史資料）：")
    for sid, weight in alloc.items():
        if sid == "現金":
            r, v = CASH_RETURN, CASH_VOL
            print(f"    現金  {weight*100:>4.0f}%：固定 {r*100:.2f}% / 波動 {v*100:.2f}%")
        else:
            if sid not in closes:
                print(f"    {sid}：無資料，跳過")
                continue
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

    LABELS = {1: "P1  極端悲觀", 10: "P10 悲觀", 50: "P50 中位", 90: "P90 樂觀"}
    W3 = [14, 16, 14, 10]
    TOTAL3 = sum(W3) + len(W3) * 2
    print("  " + "  ".join(wpad(h, W3[i], "right") for i, h in enumerate(
        ["路徑", f"第{args.years}年末資產(萬)", f"第{args.years}年月提領", "狀態"]
    )))
    print("  " + "-" * TOTAL3)
    for pct in (1, 10, 50, 90):
        if pct not in mc["rep_paths"]:
            continue
        last = mc["rep_paths"][pct][-1]
        asset_str  = str(last.get("年末資產 (萬)", "—"))
        income_str = str(last.get("月提領額",      "—"))
        status     = "💀 耗盡" if asset_str == "0" else "✓ 存活"
        print("  " + "  ".join(wpad(v, W3[i], "right") for i, v in enumerate(
            [LABELS[pct], asset_str, income_str, status]
        )))
    hr("-")

    print("\n  逐年存活率：")
    for yr, sr in zip(mc["years"], mc["survival_rate"]):
        if yr == 1 or yr % 5 == 0:
            bar = "█" * int(sr / 5)
            print(f"    第 {yr:2d} 年  {sr:5.1f}%  {bar}")
    hr()
