# -*- coding: utf-8 -*-
"""CLI 共用格式化工具與輸入解析。

- wlen / wpad:中英混排寬度計算與 padding
- hr:水平分隔線
- parse_alloc:解析 "0050:90,00859B:5,現金:5" 配置字串
- fetch_multi:批次下載多檔 close
- token_missing:FINMIND_TOKEN 缺失時的提示訊息
"""

from __future__ import annotations

import unicodedata


def wlen(s: str) -> int:
    """East Asian Wide/Full 字元視為寬度 2,其餘視為 1。"""
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in str(s))


def wpad(s: str, width: int, align: str = "left") -> str:
    s = str(s)
    pad = max(0, width - wlen(s))
    return (s + " " * pad) if align == "left" else (" " * pad + s)


def hr(char: str = "=", width: int = 64) -> None:
    print(char * width)


def token_missing() -> None:
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
    """解析 '0050:90,00859B:5,現金:5' 格式,回傳 {代號: 比例(小數)}。"""
    result: dict[str, float] = {}
    for part in alloc_str.split(","):
        part = part.strip()
        if ":" not in part:
            raise ValueError(f"配置格式錯誤：{part!r}，應為「代號:整數比例」")
        sid, w = part.split(":", 1)
        sid = sid.strip()
        if sid.isascii():
            sid = sid.upper().removesuffix(".TW")
        result[sid] = float(w.strip()) / 100
    return result


def fetch_multi(stock_ids: list[str], token: str, force: bool = False) -> dict:
    """批次下載多檔收盤價(略過現金),回傳 {sid: pd.Series}。"""
    from tw_etf_analyzer.core.data import fetch_adjusted_close

    closes: dict = {}
    for sid in stock_ids:
        if sid == "現金":
            continue
        print(f"  下載 {sid}...", end=" ", flush=True)
        close, _logs = fetch_adjusted_close(sid, token, force=force)
        print("完成")
        closes[sid] = close
    return closes
