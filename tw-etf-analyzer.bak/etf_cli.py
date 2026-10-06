# -*- coding: utf-8 -*-
"""DEPRECATED — 薄 entry shim,實作已搬至 tw_etf_analyzer.cli。

安裝 package 後請直接用:
    pip install -e .
    twetf perf 0050 10000

若仍以 `python etf_cli.py ...` 呼叫此 shim,功能等效。
"""

from tw_etf_analyzer.cli.main import main


if __name__ == "__main__":
    raise SystemExit(main())
