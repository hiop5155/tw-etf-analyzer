# -*- coding: utf-8 -*-
"""track subcommand — 以實際歷史報酬逐月追蹤 GK 策略。"""

from __future__ import annotations

from tw_etf_analyzer.core.simulation import run_gk_historical

from tw_etf_analyzer.cli.commands._format import fetch_multi, hr, parse_alloc, wpad


def cmd_track(args, token: str) -> None:
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
        print("所選月份無歷史資料，請調整起始月份。")
        return

    final_port = result["final_portfolio"]
    final_inc  = result["final_monthly_income"]

    print(f"\n【提領追蹤（{args.start} 起）】")
    print(f"  初始資產   : {args.port:,.0f} 萬 TWD")
    print(f"  提領率     : {args.rate:.1f}%   護欄 ±{args.guard:.0f}%   通膨 {args.inf:.1f}%")
    hr()
    print(f"  最終資產   : {final_port/10_000:,.1f} 萬 TWD")
    print(f"  最終月提領 : {final_inc:,.0f} TWD")
    hr()

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

    if rebalances:
        gk_map = {
            "capital_preservation": "↓ 減提領10%（提領率過高）",
            "prosperity":           "↑ 增提領10%（提領率過低）",
            "":                     "通膨調整（無護欄觸發）",
        }
        print("\n【年度再平衡事件】")
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
