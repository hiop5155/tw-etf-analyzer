# -*- coding: utf-8 -*-
"""
台股核心邏輯：資料下載、快取、還原股價、績效計算
不含任何 UI / 輸出邏輯，CLI 與 Web 共用此模組。
"""

import os, json, time, urllib.request, urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd


def _atomic_csv(df: "pd.DataFrame | pd.Series", path: Path, **kwargs) -> None:
    """Write *df* to *path* atomically: write to a .tmp sibling first,
    then os.replace() so readers never see a partial file."""
    tmp = path.with_suffix(".tmp")
    try:
        df.to_csv(tmp, **kwargs)
        os.replace(tmp, path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def _safe_cagr(end_val: float, start_val: float, years: float) -> float:
    """Return CAGR % safely; returns 0.0 on any zero/negative input."""
    if start_val <= 0 or years <= 0 or end_val < 0:
        return 0.0
    return ((end_val / start_val) ** (1.0 / years) - 1) * 100

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

def _div_cache_path(stock_id: str) -> Path:
    return CACHE_DIR / f"{stock_id}_dividends.csv"

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

    _atomic_csv(close, path)
    # 同時快取股利資料
    if dividends:
        div_df = pd.DataFrame(dividends)[["date", "stock_id", "before_price", "after_price", "stock_and_cache_dividend"]]
        _atomic_csv(div_df, _div_cache_path(stock_id), index=False)

    logs.append(f"已儲存快取：{path.name}")
    return close, logs


_stock_name_cache: dict[str, str] = {}  # process-level cache；stock name 不常變，不需 TTL

def fetch_stock_name(stock_id: str, token: str) -> str:
    """
    從 FinMind TaiwanStockInfo 查詢股票中文名稱。
    查不到或失敗時直接回傳 stock_id。
    結果快取在 process 記憶體中，避免每次 Streamlit rerun 都打 API。
    """
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
    """
    回傳股利發放歷史 DataFrame。
    欄位：date, cash_dividend, before_price, after_price, yield_pct
    會優先讀快取（與股價快取共用 TTL）。
    """
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


# ── 目標終值試算 ──────────────────────────────────────────────────────────────
def calc_target_monthly(target: float, years: int, annual_cagr_pct: float) -> dict:
    """
    反推：要在 N 年後達到目標金額，每月需投入多少？
    同時計算一次性投入需要多少本金。
    """
    r_a = annual_cagr_pct / 100
    r_m = (1 + r_a) ** (1 / 12) - 1
    n   = years * 12

    monthly  = target * r_m / ((1 + r_m) ** n - 1) if r_m > 0 else target / n
    lump_sum = target / (1 + r_a) ** years
    total_invested = monthly * n

    return {
        "monthly"        : monthly,
        "lump_sum_today" : lump_sum,
        "total_invested" : total_invested,
        "total_gain"     : target - total_invested,
    }


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
    close  = close.replace(0, float("nan")).dropna()
    p0     = float(close.iloc[0])
    p_last = float(close.iloc[-1])
    years  = (close.index[-1] - close.index[0]).days / 365.25
    return LumpSumResult(
        total_return_pct = (p_last / p0 - 1) * 100 if p0 > 0 else 0.0,
        cagr_pct         = _safe_cagr(p_last, p0, years),
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
        yr = ts.year
        if price <= 0:
            continue
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


@dataclass
class ETFCompareRecord:
    stock_id: str
    inception_date: pd.Timestamp   # 原始成立日
    common_start: pd.Timestamp     # 對齊後共同起始日
    years: float                   # 共同起始至今年數
    total_return_pct: float        # 總報酬 %
    cagr_pct: float                # 年化報酬 %
    dca_final: float               # DCA 終值
    dca_cagr_pct: float            # DCA 年化報酬 %
    normalized: pd.Series          # 標準化價格（起始=100）


def calc_multi_compare(
    closes: dict[str, pd.Series],
    monthly_dca: float,
) -> list[ETFCompareRecord]:
    """
    多檔績效比較。
    以各標的中上市最晚的日期為共同起始點，統一比較。
    """
    # 共同起始日 = 最晚的第一筆資料日期
    common_start = max(s.index[0] for s in closes.values())

    records = []
    for sid, close in closes.items():
        sliced = close[close.index >= common_start].dropna()
        if len(sliced) < 2:
            continue

        p0     = float(sliced.iloc[0])
        p_last = float(sliced.iloc[-1])
        years  = (sliced.index[-1] - sliced.index[0]).days / 365.25

        total_ret = (p_last / p0 - 1) * 100 if p0 > 0 else 0.0
        cagr      = _safe_cagr(p_last, p0, years)

        # DCA 模擬（從共同起始日）
        dca = calc_dca(sliced, monthly_dca)
        f   = dca.final
        dca_cagr = _safe_cagr(f.value, f.cost_cum, years)

        records.append(ETFCompareRecord(
            stock_id        = sid,
            inception_date  = close.index[0],
            common_start    = common_start,
            years           = years,
            total_return_pct= total_ret,
            cagr_pct        = cagr,
            dca_final       = f.value,
            dca_cagr_pct    = dca_cagr,
            normalized      = (sliced / p0 * 100),
        ))

    return sorted(records, key=lambda r: r.cagr_pct, reverse=True)


# ── Guyton-Klinger 動態提領模擬 ───────────────────────────────────────────────
@dataclass
class GKYearRecord:
    year:             int
    portfolio_start:  float   # 年初資產
    growth:           float   # 年度成長
    withdrawal:       float   # 本年提領額
    portfolio_end:    float   # 年末資產
    withdrawal_rate:  float   # 實際提領率 %
    monthly_income:   float   # 月提領額
    trigger:          str     # "" / "capital_preservation" / "prosperity"

@dataclass
class GKResult:
    records:          list[GKYearRecord]
    depleted_year:    int | None   # None = 撐過全期
    final_portfolio:  float
    initial_monthly:  float


def simulate_gk(
    initial_portfolio:     float,
    initial_rate:          float = 0.06,   # 初始提領率
    guardrail_pct:         float = 0.20,   # 護欄寬度（±20%）
    annual_return:         float = 0.0475, # 投資組合加權報酬
    inflation_rate:        float = 0.02,
    years:                 int   = 30,
) -> GKResult:
    """
    Guyton-Klinger 動態提領模擬。

    規則（每年起點執行）：
    1. 通膨調整提領額，但若上年資產下滑則跳過。
    2. 資本保護規則：若當前提領率 > init_rate × (1+guardrail)，提領額 ×0.90。
    3. 繁榮規則：若當前提領率 < init_rate × (1-guardrail)，提領額 ×1.10。
    """
    portfolio    = initial_portfolio
    withdrawal   = initial_portfolio * initial_rate
    init_rate_pct = initial_rate
    upper_guard  = init_rate_pct * (1 + guardrail_pct)
    lower_guard  = init_rate_pct * (1 - guardrail_pct)

    records:      list[GKYearRecord] = []
    depleted_year = None
    prev_end      = initial_portfolio   # 上年年末資產（用於通膨調整判斷）

    for yr in range(1, years + 1):
        if portfolio <= 0:
            break

        # 年末資產（先成長）
        growth          = portfolio * annual_return
        portfolio_grown = portfolio + growth

        # 1. 通膨調整（若上年資產未下滑）
        if portfolio_grown >= prev_end:
            withdrawal *= (1 + inflation_rate)

        # 2 & 3. 護欄規則
        current_rate = withdrawal / portfolio_grown if portfolio_grown > 0 else float("inf")
        trigger = ""
        if current_rate > upper_guard:
            withdrawal *= 0.90
            trigger     = "capital_preservation"
            current_rate = withdrawal / portfolio_grown
        elif current_rate < lower_guard:
            withdrawal *= 1.10
            trigger     = "prosperity"
            current_rate = withdrawal / portfolio_grown

        portfolio_end = portfolio_grown - withdrawal

        records.append(GKYearRecord(
            year            = yr,
            portfolio_start = portfolio,
            growth          = growth,
            withdrawal      = withdrawal,
            portfolio_end   = max(0.0, portfolio_end),
            withdrawal_rate = current_rate * 100,
            monthly_income  = withdrawal / 12,
            trigger         = trigger,
        ))

        prev_end  = portfolio_grown
        portfolio = max(0.0, portfolio_end)

        if portfolio_end <= 0:
            depleted_year = yr
            break

    return GKResult(
        records         = records,
        depleted_year   = depleted_year,
        final_portfolio = portfolio,
        initial_monthly = initial_portfolio * initial_rate / 12,
    )


def calc_return_vol(close: pd.Series) -> tuple[float, float]:
    """
    從日收盤價計算年化報酬（CAGR）與年化波動度（日 log return std × √252）。
    回傳 (cagr, annual_vol)，均為小數（非百分比）。
    """
    # 移除 0 值與 NaN（停牌日或資料缺漏會造成 log(0) 錯誤）
    close = close.replace(0, float("nan")).dropna()
    if len(close) < 2:
        return 0.0, 0.0
    years      = (close.index[-1] - close.index[0]).days / 365.25
    cagr       = float((close.iloc[-1] / close.iloc[0]) ** (1 / years) - 1)
    ratio      = (close / close.shift(1)).replace(0, float("nan")).dropna()
    log_ret    = np.log(ratio).dropna()
    annual_vol = float(log_ret.std() * np.sqrt(252))
    return cagr, annual_vol


def simulate_gk_montecarlo(
    initial_portfolio: float,
    initial_rate:      float,
    guardrail_pct:     float,
    annual_return:     float,      # 加權平均報酬（小數）
    annual_volatility: float,      # 加權平均波動（小數）
    inflation_rate:    float,
    years:             int,
    n_sims:            int  = 1000,
    seed:              int  = 42,
) -> dict:
    """
    Monte Carlo Guyton-Klinger 模擬。
    回傳各年度資產餘額、月提領額的百分位數，以及存活率。
    """
    rng = np.random.default_rng(seed)

    port_mat = np.zeros((n_sims, years))
    wd_mat   = np.zeros((n_sims, years))   # 月提領額

    for sim in range(n_sims):
        portfolio  = initial_portfolio
        withdrawal = initial_portfolio * initial_rate
        prev_end   = initial_portfolio
        upper      = initial_rate * (1 + guardrail_pct)
        lower      = initial_rate * (1 - guardrail_pct)

        for yr in range(years):
            if portfolio <= 0:
                break  # 後續年度維持 0

            r               = float(rng.normal(annual_return, annual_volatility))
            portfolio_grown = portfolio * (1 + r)

            # 通膨調整（上年資產未下滑才執行）
            if portfolio_grown >= prev_end:
                withdrawal *= (1 + inflation_rate)

            # 護欄
            cur_rate = withdrawal / portfolio_grown if portfolio_grown > 0 else float("inf")
            if cur_rate > upper:
                withdrawal *= 0.90
            elif cur_rate < lower:
                withdrawal *= 1.10

            portfolio_end = portfolio_grown - withdrawal
            prev_end      = portfolio_grown
            portfolio     = max(0.0, portfolio_end)

            port_mat[sim, yr] = portfolio
            wd_mat[sim, yr]   = withdrawal / 12   # 轉月

    # 每年存活率（資產 > 0）
    survived  = port_mat > 0
    surv_rate = survived.mean(axis=0) * 100

    pcts = [10, 25, 50, 75, 90]
    years_arr = np.arange(1, years + 1)

    port_pct = {p: np.percentile(port_mat, p, axis=0) for p in pcts}
    wd_pct   = {p: np.percentile(wd_mat,   p, axis=0) for p in pcts}

    return {
        "years":            years_arr,
        "port_pct":         port_pct,
        "wd_pct":           wd_pct,
        "survival_rate":    surv_rate,
        "survival_final":   float(surv_rate[-1]),
        "depleted_pct":     100 - float(surv_rate[-1]),
        "n_sims":           n_sims,
        "initial_monthly":  initial_portfolio * initial_rate / 12,
    }


def calc_comparison(close: pd.Series, monthly_dca: float) -> ComparisonResult:
    lump = calc_lump_sum(close)
    dca  = calc_dca(close, monthly_dca)
    f    = dca.final

    lump_final = (f.cost_cum / lump.p0 * lump.p_last) if lump.p0 > 0 else 0.0
    dca_cagr   = _safe_cagr(f.value, f.cost_cum, lump.years)

    return ComparisonResult(
        lump                 = lump,
        dca                  = dca,
        lump_same_cost_final = lump_final,
        lump_same_cost_ret   = (lump_final / f.cost_cum - 1) * 100 if f.cost_cum > 0 else 0.0,
        lump_same_cost_cagr  = _safe_cagr(lump_final, f.cost_cum, lump.years),
        dca_cagr_pct         = dca_cagr,
    )
