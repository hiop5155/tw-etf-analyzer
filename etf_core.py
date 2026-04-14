# -*- coding: utf-8 -*-
"""
ETF 核心邏輯：資料下載、快取、還原股價、績效計算
不含任何 UI / 輸出邏輯，CLI 與 Web 共用此模組。
"""

import os, json, time, urllib.request, urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

# ── 路徑 ──────────────────────────────────────────────────────────────────────
_HERE      = Path(__file__).parent
CACHE_DIR  = _HERE / "stock_cache"
CACHE_TTL_H = 24
CACHE_DIR.mkdir(exist_ok=True)

FINMIND_API = "https://api.finmindtrade.com/api/v4/data"

# ── Token ─────────────────────────────────────────────────────────────────────
def load_token() -> str:
    """
    FINMIND_TOKEN 讀取優先順序：
    1. Streamlit Secrets（部署到 Streamlit Cloud 時）
    2. .env 檔（本機開發）
    3. 環境變數
    """
    # 1. Streamlit Secrets
    try:
        import streamlit as st
        token = st.secrets.get("FINMIND_TOKEN", "")
        if token:
            return token
    except Exception:
        pass

    # 2. .env 檔
    env_file = _HERE / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            if key.strip() == "FINMIND_TOKEN":
                return val.strip().strip('"').strip("'")

    # 3. 環境變數
    return os.environ.get("FINMIND_TOKEN", "")

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

def _is_fresh(path: Path) -> bool:
    return path.exists() and (time.time() - path.stat().st_mtime) / 3600 < CACHE_TTL_H

def clear_cache(stock_id: str):
    p = _cache_path(stock_id)
    if p.exists():
        p.unlink()

# ── 下載與還原 ────────────────────────────────────────────────────────────────
def fetch_adjusted_close(stock_id: str, token: str, force: bool = False) -> tuple[pd.Series, list[str]]:
    """
    回傳 (還原收盤價 Series, 調整事件 log list)
    還原方式：統一套用分割 + 除權息回溯調整
    """
    stock_id = stock_id.upper().removesuffix(".TW")
    path  = _cache_path(stock_id)
    logs: list[str] = []

    if not force and _is_fresh(path):
        logs.append(f"載入快取：{path.name}（{CACHE_TTL_H}h 內不重拉）")
        close = pd.read_csv(path, index_col=0, parse_dates=True).squeeze()
        return close, logs

    # 下載原始股價
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

    close.to_csv(path)
    logs.append(f"已儲存快取：{path.name}")
    return close, logs

# ── 績效計算 ──────────────────────────────────────────────────────────────────
@dataclass
class LumpSumResult:
    total_return_pct: float   # 總報酬 %
    cagr_pct: float           # 年化報酬 %
    years: float
    inception_date: pd.Timestamp
    last_date: pd.Timestamp
    p0: float
    p_last: float

@dataclass
class DCAYearRecord:
    year: int
    cost_cum: float           # 累計投入
    value: float              # 期末市值
    gain: float               # 未實現損益
    return_pct: float         # 累計報酬率 %

@dataclass
class DCAResult:
    monthly_dca: float
    years: list[DCAYearRecord] = field(default_factory=list)

    @property
    def final(self) -> DCAYearRecord:
        return self.years[-1]

    @property
    def cagr_pct(self) -> float:
        f = self.final
        yrs = self.years[-1].year  # placeholder; needs full years
        return 0.0  # calculated externally via calc_comparison

@dataclass
class ComparisonResult:
    lump: LumpSumResult
    dca: DCAResult
    lump_same_cost_final: float   # 單筆投入（同等本金）的終值
    lump_same_cost_ret:   float   # 單筆總報酬 %
    lump_same_cost_cagr:  float   # 單筆年化報酬 %
    dca_cagr_pct:         float   # 定期定額年化報酬 %


def calc_lump_sum(close: pd.Series) -> LumpSumResult:
    p0     = float(close.iloc[0])
    p_last = float(close.iloc[-1])
    years  = (close.index[-1] - close.index[0]).days / 365.25
    return LumpSumResult(
        total_return_pct = (p_last / p0 - 1) * 100,
        cagr_pct         = ((p_last / p0) ** (1 / years) - 1) * 100,
        years            = years,
        inception_date   = close.index[0],
        last_date        = close.index[-1],
        p0               = p0,
        p_last           = p_last,
    )


def calc_dca(close: pd.Series, monthly_dca: float) -> DCAResult:
    monthly_first = close.resample("MS").first().dropna()
    units_total = 0.0
    cost_total  = 0.0
    result      = DCAResult(monthly_dca=monthly_dca)

    for i, (ts, price) in enumerate(monthly_first.items()):
        yr           = ts.year
        units_total += monthly_dca / price
        cost_total  += monthly_dca

        is_last   = (i == len(monthly_first) - 1)
        next_ts   = monthly_first.index[i + 1] if not is_last else None
        year_ends = is_last or (next_ts is not None and next_ts.year != yr)

        if year_ends:
            yr_prices = close[close.index.year == yr]
            end_price = float(yr_prices.iloc[-1]) if not yr_prices.empty else price
            end_value = units_total * end_price
            result.years.append(DCAYearRecord(
                year       = yr,
                cost_cum   = cost_total,
                value      = end_value,
                gain       = end_value - cost_total,
                return_pct = (end_value / cost_total - 1) * 100,
            ))
    return result


def calc_comparison(close: pd.Series, monthly_dca: float) -> ComparisonResult:
    lump = calc_lump_sum(close)
    dca  = calc_dca(close, monthly_dca)
    f    = dca.final

    lump_final = f.cost_cum / lump.p0 * lump.p_last
    dca_cagr   = ((f.value / f.cost_cum) ** (1 / lump.years) - 1) * 100

    return ComparisonResult(
        lump                 = lump,
        dca                  = dca,
        lump_same_cost_final = lump_final,
        lump_same_cost_ret   = (lump_final / f.cost_cum - 1) * 100,
        lump_same_cost_cagr  = ((lump_final / f.cost_cum) ** (1 / lump.years) - 1) * 100,
        dca_cagr_pct         = dca_cagr,
    )
