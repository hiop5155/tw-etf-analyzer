# -*- coding: utf-8 -*-
"""FinMind API + 本地快取 + 除權息還原股價。

邊界:
- 僅處理「取資料」與「還原」,不涉及任何績效/模擬計算
- 快取:CSV 存於 config.CACHE_DIR,atomic write 避免讀寫競爭
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

from tw_etf_analyzer.config import CACHE_DIR, CACHE_TTL_H
from tw_etf_analyzer.constants import FINMIND_API


def _atomic_csv(df: "pd.DataFrame | pd.Series", path: Path, **kwargs) -> None:
    """原子寫入:先寫到 .tmp,再 rename,避免讀者看到半寫入的檔案。"""
    tmp = path.with_suffix(".tmp")
    try:
        df.to_csv(tmp, **kwargs)
        os.replace(tmp, path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


# ── FinMind API ───────────────────────────────────────────────────────────────
def _finmind_get(dataset: str, stock_id: str, token: str, start: str = "2000-01-01") -> list[dict]:
    params = {"dataset": dataset, "data_id": stock_id, "start_date": start, "token": token}
    url = f"{FINMIND_API}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=60) as r:
        data = json.loads(r.read())
    if data.get("status") != 200:
        raise RuntimeError(f"FinMind [{dataset}] 錯誤：{data.get('msg')}")
    return data.get("data", [])


# ── 快取 ──────────────────────────────────────────────────────────────────────
def _cache_path(stock_id: str) -> Path:
    return CACHE_DIR / f"{stock_id}.csv"


def _div_cache_path(stock_id: str) -> Path:
    return CACHE_DIR / f"{stock_id}_dividends.csv"


def _is_fresh(path: Path) -> bool:
    return path.exists() and (time.time() - path.stat().st_mtime) / 3600 < CACHE_TTL_H


def clear_cache(stock_id: str) -> None:
    p = _cache_path(stock_id)
    if p.exists():
        p.unlink()


# ── 下載與還原 ────────────────────────────────────────────────────────────────
def fetch_adjusted_close(stock_id: str, token: str, force: bool = False) -> tuple[pd.Series, list[str]]:
    """回傳 (還原收盤價 Series, 調整事件 log list)。

    還原方式:統一套用分割 + 除權息回溯調整。
    """
    stock_id = stock_id.upper().removesuffix(".TW")
    path  = _cache_path(stock_id)
    logs: list[str] = []

    if not force and _is_fresh(path):
        logs.append(f"載入快取：{path.name}（{CACHE_TTL_H}h 內不重拉）")
        close = pd.read_csv(path, index_col=0, parse_dates=True).squeeze()
        return close, logs

    logs.append(f"從 FinMind 下載 {stock_id} 股價...")
    records = _finmind_get("TaiwanStockPrice", stock_id, token)
    if not records:
        raise RuntimeError(f"查無 {stock_id} 資料，請確認股票代號")

    close = (
        pd.DataFrame(records)
        .set_index("date")["close"]
        .pipe(lambda s: s.set_axis(pd.to_datetime(s.index)))
        .sort_index()
        .astype(float)
    )

    # 合併分割 + 除權息事件
    events: list[dict] = []
    splits    = _finmind_get("TaiwanStockSplitPrice",    stock_id, token)
    dividends = _finmind_get("TaiwanStockDividendResult", stock_id, token)

    for s in splits:
        events.append({"date": s["date"], "before": s["before_price"], "after": s["after_price"], "type": "分割"})
    for d in dividends:
        events.append({"date": d["date"], "before": d["before_price"], "after": d["after_price"], "type": "除權息"})

    if events:
        logs.append(f"調整事件：分割 {len(splits)} 筆 + 除權息 {len(dividends)} 筆")
        for ev in sorted(events, key=lambda x: x["date"], reverse=True):
            ratio = ev["after"] / ev["before"]
            mask  = close.index < pd.Timestamp(ev["date"])
            close.loc[mask] = close.loc[mask] * ratio
    else:
        logs.append("無分割/除權息記錄")

    _atomic_csv(close, path)
    if dividends:
        div_df = pd.DataFrame(dividends)[["date", "stock_id", "before_price", "after_price", "stock_and_cache_dividend"]]
        _atomic_csv(div_df, _div_cache_path(stock_id), index=False)

    logs.append(f"已儲存快取：{path.name}")
    return close, logs


_stock_name_cache: dict[str, str] = {}  # process-level cache;stock name 不常變,不需 TTL


def fetch_stock_name(stock_id: str, token: str) -> str:
    """從 FinMind TaiwanStockInfo 查詢股票中文名稱,查不到回傳 stock_id。"""
    key = stock_id.upper()
    if key in _stock_name_cache:
        return _stock_name_cache[key]
    if key == "現金":
        _stock_name_cache[key] = "現金 / 貨幣市場"
        return _stock_name_cache[key]
    try:
        records = _finmind_get("TaiwanStockInfo", stock_id, token)
        if records:
            name = records[0].get("stock_name", stock_id)
            _stock_name_cache[key] = name
            return name
    except Exception:
        pass
    _stock_name_cache[key] = stock_id
    return stock_id


def fetch_dividend_history(stock_id: str, token: str) -> pd.DataFrame:
    """回傳股利歷史 DataFrame。欄位: date, cash_dividend, before_price, after_price, yield_pct, year。"""
    stock_id = stock_id.upper().removesuffix(".TW")
    path = _div_cache_path(stock_id)

    if _is_fresh(path):
        df = pd.read_csv(path, parse_dates=["date"])
    else:
        records = _finmind_get("TaiwanStockDividendResult", stock_id, token)
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(records)[["date", "stock_id", "before_price", "after_price", "stock_and_cache_dividend"]]
        df["date"] = pd.to_datetime(df["date"])
        _atomic_csv(df, path, index=False)

    if df.empty:
        return df

    df = df.rename(columns={"stock_and_cache_dividend": "cash_dividend"})
    df["yield_pct"] = (df["cash_dividend"] / df["before_price"] * 100).round(2)
    df["year"]      = df["date"].dt.year
    return df.sort_values("date").reset_index(drop=True)
