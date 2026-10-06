# -*- coding: utf-8 -*-
"""dividend subcommand — 股利歷史查詢。"""

from __future__ import annotations

from tw_etf_analyzer.core.data import fetch_dividend_history

from tw_etf_analyzer.cli.commands._format import hr, wlen, wpad


def cmd_dividend(args, token: str) -> None:
    print(f"\n下載 {args.stock_id} 股利資料...", end=" ", flush=True)
    df = fetch_dividend_history(args.stock_id, token)
    print("完成")

    if df is None or df.empty:
        print("無股利資料。")
        return

    show_cols  = ["year", "date", "cash_dividend", "before_price", "after_price", "yield_pct"]
    col_labels = {
        "year": "年度", "date": "除息日", "cash_dividend": "現金股利",
        "before_price": "除息前價", "after_price": "除息後價", "yield_pct": "殖利率%",
    }
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
