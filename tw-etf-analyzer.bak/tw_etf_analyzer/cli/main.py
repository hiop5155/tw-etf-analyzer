# -*- coding: utf-8 -*-
"""CLI 進入點:argparse + subcommand dispatch。

使用:
    python -m tw_etf_analyzer.cli         # 同等 `twetf`(安裝後)
    python etf_cli.py perf 0050 10000     # 向後相容 shim
"""

from __future__ import annotations

import argparse
import io
import sys

from tw_etf_analyzer.config import load_token

from tw_etf_analyzer.cli.commands._format import token_missing
from tw_etf_analyzer.cli.commands.compare import cmd_compare
from tw_etf_analyzer.cli.commands.dividend import cmd_dividend
from tw_etf_analyzer.cli.commands.perf import cmd_perf
from tw_etf_analyzer.cli.commands.retire import cmd_retire
from tw_etf_analyzer.cli.commands.target import cmd_target
from tw_etf_analyzer.cli.commands.track import cmd_track


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog        = "twetf",
        description = "台股 ETF / 股票績效分析工具（資料來源：FinMind）",
        formatter_class = argparse.RawDescriptionHelpFormatter,
        epilog = """\
範例：
  twetf perf 0050 10000
  twetf target 1000 20 --cagr 7
  twetf dividend 0056
  twetf compare 0050 00878 2330 --dca 15000
  twetf retire --alloc 0050:90,00859B:5,現金:5 --asset 2000 --rate 4 --years 30
  twetf track  --alloc 0050:90,00859B:5,現金:5 --port 2000 --start 2020-01
""",
    )
    sub = parser.add_subparsers(dest="cmd", metavar="命令")
    sub.required = True

    # perf
    p_perf = sub.add_parser("perf",
        help        = "績效分析：單筆 vs 定期定額逐年績效",
        description = "下載指定股票的還原股價，計算單筆與定期定額的歷史績效。",
    )
    p_perf.add_argument("stock_id", help="股票代號，例如 0050、00631L（不需要 .TW）")
    p_perf.add_argument("dca_amount", type=float, help="每月定期定額金額（TWD），例如 10000")
    p_perf.add_argument("--refresh", action="store_true", help="強制重新下載，忽略本地快取")

    # target
    p_tgt = sub.add_parser("target",
        help        = "目標試算：反推「N 年後有 X 萬」每月需投入多少",
        description = "根據目標金額、年限與預估報酬率，反推每月所需定投金額。",
    )
    p_tgt.add_argument("target_wan", type=float, help="目標金額（萬 TWD），例如 1000")
    p_tgt.add_argument("years", type=int, help="投資年限（年），例如 20")
    p_tgt.add_argument("--cagr", type=float, required=True, metavar="RATE",
                       help="預估年化報酬率 %%（例如 7.5）")
    p_tgt.add_argument("--existing", type=float, default=0.0, metavar="WAN",
                       help="目前已持有市值（萬 TWD），預設 0")

    # dividend
    p_div = sub.add_parser("dividend",
        help        = "股利歷史：歷年配息與殖利率明細",
        description = "列出指定股票的除息日、現金股利金額與殖利率。",
    )
    p_div.add_argument("stock_id", help="股票代號，例如 0056")
    p_div.add_argument("--refresh", action="store_true", help="強制重新下載，忽略本地快取")

    # compare
    p_cmp = sub.add_parser("compare",
        help        = "多檔比較:2～5 檔股票同期績效對照",
        description = "以最晚上市的日期為共同起始點，比較多檔的單筆與定投績效。",
    )
    p_cmp.add_argument("stocks", nargs="+", metavar="代號",
                       help="2～5 個股票代號，例如 0050 00878 2330")
    p_cmp.add_argument("--dca", type=float, default=10000, metavar="TWD",
                       help="每月定投金額（TWD），預設 10000")
    p_cmp.add_argument("--refresh", action="store_true", help="強制重新下載，忽略本地快取")

    # retire
    p_ret = sub.add_parser("retire",
        help        = "退休模擬:Monte Carlo × GK 動態提領策略(不含圖表)",
        description = "從歷史資料計算投資組合 CAGR 與波動，執行 Monte Carlo 模擬，\n輸出存活率與 P1/P10/P50/P90 代表性路徑結果。",
    )
    p_ret.add_argument("--alloc", required=True, metavar="代號:比例,...",
                       help="投資組合，格式:代號:整數比例，以逗號分隔，例如 0050:90,00859B:5,現金:5（比例總和須為 100）")
    p_ret.add_argument("--asset", type=float, required=True, metavar="WAN",
                       help="退休起始資產（萬 TWD）")
    p_ret.add_argument("--rate",  type=float, default=4.0,  metavar="PCT",
                       help="初始提領率 %%，預設 4.0")
    p_ret.add_argument("--guard", type=float, default=20.0, metavar="PCT",
                       help="護欄寬度 %%，預設 20.0(上護欄 = 初始率×1.2，下護欄 = 初始率×0.8)")
    p_ret.add_argument("--inf",   type=float, default=2.0,  metavar="PCT",
                       help="通膨率 %%，預設 2.0")
    p_ret.add_argument("--years", type=int,   default=30,   metavar="N",
                       help="模擬年數，預設 30")
    p_ret.add_argument("--sims",  type=int,   default=1000, metavar="N",
                       help="Monte Carlo 模擬次數，預設 1000")
    p_ret.add_argument("--refresh", action="store_true", help="強制重新下載，忽略本地快取")

    # track
    p_trk = sub.add_parser("track",
        help        = "提領追蹤:以歷史實際報酬逐月追蹤 GK 策略",
        description = "輸入開始提領的時間與初始條件，以 FinMind 歷史資料\n逐月執行 GK 提領策略，並顯示每年一月的再平衡建議。",
    )
    p_trk.add_argument("--alloc", required=True, metavar="代號:比例,...",
                       help="投資組合，格式同 retire，例如 0050:90,00859B:5,現金:5")
    p_trk.add_argument("--port",  type=float, required=True, metavar="WAN",
                       help="初始資產（萬 TWD）")
    p_trk.add_argument("--start", required=True, metavar="YYYY-MM",
                       help="開始提領月份，例如 2020-01")
    p_trk.add_argument("--rate",  type=float, default=4.0,  metavar="PCT",
                       help="初始提領率 %%，預設 4.0")
    p_trk.add_argument("--guard", type=float, default=20.0, metavar="PCT",
                       help="護欄寬度 %%，預設 20.0")
    p_trk.add_argument("--inf",   type=float, default=2.0,  metavar="PCT",
                       help="通膨率 %%，預設 2.0")
    p_trk.add_argument("--refresh", action="store_true", help="強制重新下載，忽略本地快取")

    return parser


DISPATCH = {
    "perf":     cmd_perf,
    "target":   cmd_target,
    "dividend": cmd_dividend,
    "compare":  cmd_compare,
    "retire":   cmd_retire,
    "track":    cmd_track,
}


def main(argv: list[str] | None = None) -> int:
    # 強制 UTF-8 輸出(中文在 Windows cmd 會亂碼)
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    parser = _build_parser()
    args = parser.parse_args(argv)

    token = load_token()
    if not token:
        token_missing()
        return 1

    # 標準化 stock_id(perf / dividend 適用)
    if hasattr(args, "stock_id"):
        args.stock_id = args.stock_id.upper().removesuffix(".TW")

    DISPATCH[args.cmd](args, token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
