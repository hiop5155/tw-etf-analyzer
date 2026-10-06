# -*- coding: utf-8 -*-
"""target subcommand — 目標試算(反推每月需投入)。"""

from __future__ import annotations

from tw_etf_analyzer.core.performance import calc_target_monthly

from tw_etf_analyzer.cli.commands._format import hr


def cmd_target(args, _token: str) -> None:
    target_twd   = args.target_wan * 10_000
    existing_twd = args.existing * 10_000

    result = calc_target_monthly(
        target          = target_twd,
        years           = args.years,
        annual_cagr_pct = args.cagr,
        existing        = existing_twd,
    )

    print("\n【目標試算】")
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
