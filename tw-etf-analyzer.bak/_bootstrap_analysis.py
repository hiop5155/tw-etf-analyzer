"""
一次性分析腳本：區塊重抽樣（Block Bootstrap）比較
  Config A: 00631L 50% + 現金 50%
  Config B: 0050   90% + 現金 10%

00631L 合成方式：0050 每日報酬 × 2（每日重置），自然內化 variance drag。
歷史樣本：0050 上市日 2003-06-30 起的月度報酬。
"""
import numpy as np
import pandas as pd

# ── 退休參數（跟 UI 預設一致）──────────────────────
STARTING_ASSET = 2000 * 10_000   # 2000 萬 TWD
YEARS          = 30
INITIAL_RATE   = 0.05
GUARDRAIL      = 0.20
INFLATION      = 0.02
N_PATHS        = 2000
BLOCK_SIZE     = 12              # 月
SEED           = 42

CONFIGS = {
    "A) 00631L 50% + 現金 50%": {"00631L": 0.50, "現金": 0.50},
    "B) 0050   90% + 現金 10%": {"0050":   0.90, "現金": 0.10},
}

# ── 載入 0050 日資料 ─────────────────────────────
close = pd.read_csv("stock_cache/0050.csv", index_col=0, parse_dates=True).squeeze()
close = close.sort_index().dropna()

daily_0050   = close.pct_change().dropna()
# 合成 00631L：每日 2× 0050 報酬（每日重置 ETF 實際機制）
# 加 floor 避免極端單日 -50%+ 造成 -100% 的數學邊界
daily_00631L = np.maximum(2.0 * daily_0050, -0.99)

# 日報酬 → 月複利報酬
monthly_0050   = ((1 + daily_0050  ).resample("ME").prod() - 1).dropna()
monthly_00631L = ((1 + daily_00631L).resample("ME").prod() - 1).dropna()

df = pd.DataFrame({"0050": monthly_0050, "00631L": monthly_00631L}).dropna()

print(f"樣本期間：{df.index[0].strftime('%Y-%m')} ~ {df.index[-1].strftime('%Y-%m')}"
      f"（{len(df)} 個月）")

# 歷史 CAGR / σ 對照（參考用）
def stats(series):
    yrs  = len(series) / 12
    cum  = (1 + series).prod()
    cagr = cum ** (1/yrs) - 1
    vol  = series.std() * np.sqrt(12)
    return cagr, vol

c0, v0   = stats(df["0050"])
c1, v1   = stats(df["00631L"])
print(f"  0050   歷史 CAGR {c0*100:5.2f}% / σ {v0*100:5.2f}%")
print(f"  00631L 歷史 CAGR {c1*100:5.2f}% / σ {v1*100:5.2f}%")
print(f"  → 隱含 variance drag ≈ {(2*c0 - c1)*100:.2f}% / 年")

# ── Circular Block Bootstrap 取樣 ──────────────────
rng              = np.random.default_rng(SEED)
n_months_total   = YEARS * 12
n_blocks_needed  = (n_months_total + BLOCK_SIZE - 1) // BLOCK_SIZE
sample_size      = len(df)
ret_matrix       = df[["0050", "00631L"]].to_numpy()  # (T, 2)

def sample_path():
    starts = rng.integers(0, sample_size, size=n_blocks_needed)
    idxs   = (starts[:, None] + np.arange(BLOCK_SIZE)) % sample_size
    block  = ret_matrix[idxs.ravel()].reshape(n_blocks_needed * BLOCK_SIZE, 2)
    return block[:n_months_total]

# ── GK 月度模擬 ────────────────────────────────────
def simulate_gk(ret_arr, allocations):
    """ret_arr shape = (n_months, 2) 對應 [0050, 00631L]。"""
    asset_vals       = {a: STARTING_ASSET * w for a, w in allocations.items()}
    annual_wd        = STARTING_ASSET * INITIAL_RATE
    monthly_income   = annual_wd / 12
    prev_jan_port    = STARTING_ASSET
    upper, lower     = INITIAL_RATE*(1+GUARDRAIL), INITIAL_RATE*(1-GUARDRAIL)
    cuts = bumps     = 0
    depleted_month   = None
    port_history     = []
    income_history   = []

    for m in range(n_months_total):
        is_jan = (m % 12 == 0) and (m > 0)
        port_now = sum(asset_vals.values())

        if is_jan and port_now > 0:
            if port_now >= prev_jan_port:
                annual_wd *= (1 + INFLATION)
            monthly_income = annual_wd / 12
            prev_jan_port  = port_now

        if port_now > 0:
            cur_rate = annual_wd / port_now
            if cur_rate > upper:
                annual_wd     *= 0.9
                monthly_income = annual_wd / 12
                cuts          += 1
            elif cur_rate < lower and port_now >= prev_jan_port:
                annual_wd     *= 1.1
                monthly_income = annual_wd / 12
                bumps         += 1

        if is_jan and port_now > 0:
            for a in asset_vals:
                asset_vals[a] = port_now * allocations[a]

        for a in list(asset_vals.keys()):
            if a == "現金":
                ret = 0.0
            elif a == "0050":
                ret = ret_arr[m, 0]
            elif a == "00631L":
                ret = ret_arr[m, 1]
            else:
                ret = 0.0
            asset_vals[a] *= (1 + ret)

        port_after = sum(asset_vals.values())
        eff_wd     = min(monthly_income, port_after)
        if port_after > 0:
            ratio = eff_wd / port_after
            for a in asset_vals:
                asset_vals[a] *= (1 - ratio)

        port_end = max(0.0, port_after - eff_wd)
        port_history.append(port_end)
        income_history.append(monthly_income)

        if port_end <= 0 and depleted_month is None:
            depleted_month = m
            break

    return {
        "final":          sum(asset_vals.values()),
        "depleted_month": depleted_month,
        "final_income":   monthly_income,
        "min_port":       min(port_history) if port_history else 0,
        "cuts":           cuts,
        "bumps":          bumps,
    }

# ── 執行 ──────────────────────────────────────────
print(f"\n跑 {N_PATHS} 條路徑，{YEARS} 年，{BLOCK_SIZE}-月區塊 bootstrap\n")
results = {}
for name, alloc in CONFIGS.items():
    # 重設 rng 讓兩個 config 用相同的抽樣序列 → paired comparison
    rng = np.random.default_rng(SEED)
    outcomes = [simulate_gk(sample_path(), alloc) for _ in range(N_PATHS)]
    results[name] = outcomes

# ── 彙總輸出 ──────────────────────────────────────
def fmt_wan(x):
    return f"{x/10_000:,.0f}"

def summarize(name, outs):
    finals  = np.array([o["final"] for o in outs])
    mins    = np.array([o["min_port"] for o in outs])
    incs    = np.array([o["final_income"] for o in outs])
    dep     = sum(1 for o in outs if o["depleted_month"] is not None)
    succ    = (N_PATHS - dep) / N_PATHS * 100
    cuts_mu = np.mean([o["cuts"]  for o in outs])
    bmp_mu  = np.mean([o["bumps"] for o in outs])

    print(f"━━━ {name} ━━━")
    print(f"  成功率 (未破產)        : {succ:5.1f}%  ({N_PATHS-dep}/{N_PATHS})")
    print(f"  期末資產 (萬) P5/50/95 : {fmt_wan(np.percentile(finals,5)):>8} / "
          f"{fmt_wan(np.percentile(finals,50)):>8} / {fmt_wan(np.percentile(finals,95)):>8}")
    print(f"  期末資產 (萬) 平均     : {fmt_wan(np.mean(finals)):>8}")
    print(f"  路徑最低點 (萬) P5/50  : {fmt_wan(np.percentile(mins,5)):>8} / "
          f"{fmt_wan(np.percentile(mins,50)):>8}")
    print(f"  末期月提領 (萬) P5/50  : {np.percentile(incs,5)/10_000:>7.2f} / "
          f"{np.percentile(incs,50)/10_000:>7.2f}")
    print(f"  平均護欄 ↓ / ↑ 次數    : {cuts_mu:>5.1f} / {bmp_mu:.1f}")
    print()
    return finals, mins, incs

a_fin, a_min, a_inc = summarize("A) 00631L 50% + 現金 50%", results["A) 00631L 50% + 現金 50%"])
b_fin, b_min, b_inc = summarize("B) 0050   90% + 現金 10%", results["B) 0050   90% + 現金 10%"])

# ── Paired 比較（同一條抽樣序列下 A vs B）────────
diff = a_fin - b_fin
print("━━━ Paired diff (A − B) 同抽樣序列下 ━━━")
print(f"  A 期末資產 ≥ B 的比例  : {(diff >= 0).mean()*100:5.1f}%")
print(f"  A − B 中位數 (萬)      : {np.median(diff)/10_000:>+8.0f}")
print(f"  A − B P5/P95 (萬)      : {np.percentile(diff,5)/10_000:>+8.0f} / "
      f"{np.percentile(diff,95)/10_000:>+8.0f}")
