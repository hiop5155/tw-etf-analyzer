# -*- coding: utf-8 -*-
"""compare subcommand — 多檔同期績效對比。"""

from __future__ import annotations

from tw_etf_analyzer.core.performance import calc_multi_compare

from tw_etf_analyzer.cli.commands._format import fetch_multi, hr, wpad


def cmd_compare(args, token: str) -> None:
    if len(args.stocks) < 2:
        print("錯誤：至少需要 2 檔。")
        return
    if len(args.stocks) > 5:
        print("錯誤：最多支援 5 檔。")
        return

    stock_ids = [s.upper().removesuffix(".TW") for s in args.stocks]
    print()
    closes = fetch_multi(stock_ids, token, force=args.refresh)
    if len(closes) < 2:
        print("有效資料不足 2 檔，無法比較。")
        return

    records = calc_multi_compare(closes, args.dca)

    W  = [8, 12, 8, 12, 10, 14, 10, 12]
    CH = [
        "代號", "共同起始", "年數", "單筆總報酬%", "單筆年化%",
        f"定投終值(萬)\n每月{args.dca:,.0f}", "定投年化%", "上市日",
    ]
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
