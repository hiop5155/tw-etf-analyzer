# AGENT_CONTEXT

## Project Identity
- Name: `tw-etf-analyzer`
- Goal: Analyze Taiwan ETF/stock performance and retirement outcomes with:
  - Lump-sum vs DCA backtests
  - Target monthly withdrawal estimation
  - Dividend history views
  - Multi-ETF comparison
  - Retirement simulation (Guyton-Klinger + Monte Carlo + unemployment stress)

## Entry Points
- Web app: `etf_web.py` (Streamlit, 6 tabs)
- Core logic: `etf_core.py` (data fetch, cache, analytics, simulation)
- CLI tool: `etf_cli.py` (`perf`, `target`, `dividend`, `compare`, `retire`, `track`)

## Runtime and Dependencies
- Python packages: `streamlit`, `pandas`, `numpy`, `plotly`, `openpyxl`, `streamlit-local-storage`
- Required secret: `FINMIND_TOKEN` from `.env` or environment variable
- Local cache dir: `stock_cache/` (price/dividend csv)

## Core Architecture
- `etf_core.py`
  - FinMind integration: `fetch_adjusted_close`, `fetch_dividend_history`, `fetch_stock_name`
  - Comparison math: `calc_lump_sum`, `calc_dca`, `calc_comparison`, `calc_multi_compare`
  - Retirement math: `calc_return_vol`, `simulate_gk_montecarlo`, `run_gk_historical`
  - Data containers: `LumpSumResult`, `DCAResult`, `ComparisonResult`, `GKResult` (+ record classes)
- `etf_web.py`
  - Streamlit UI orchestration, tab workflows, plotting, export
  - Uses cached wrappers around core fetch functions
  - Persists user inputs via `streamlit-local-storage`
- `etf_cli.py`
  - Thin command layer over `etf_core.py` for scriptable runs

## Known Workflow Patterns
- Performance analysis:
  1. Pull adjusted close series from FinMind (or cache)
  2. Compute lump-sum + DCA stats
  3. Render/print CAGR and yearly table
- Retirement analysis:
  1. Estimate return/vol from history
  2. Run Monte Carlo with withdrawal rules
  3. Report percentile paths and success rates

## Commands You Can Reuse
- Install deps:
  - `pip install -r requirements.txt`
- Run web:
  - `streamlit run etf_web.py`
- Run CLI examples:
  - `python etf_cli.py perf --ticker 0050 --monthly 10000`
  - `python etf_cli.py target --ticker 0050 --target 50000`
  - `python etf_cli.py compare --tickers 0050,0056,00878`
  - `python etf_cli.py retire --alloc 0050:85,00859B:5,00631L:5,CASH:5 --years 10`

## Working Rules For Future Edits
- Prefer touching `etf_core.py` first for business logic changes.
- Keep `etf_web.py` focused on UI/state/render.
- Preserve cache behavior unless explicitly requested.
- Avoid changing API assumptions without checking FinMind response schema.

## Reusable Task Template
Use this when asked to make changes quickly:

1. Confirm scope (web/cli/core/simulation).
2. Locate affected function(s) in `etf_core.py` or command in `etf_cli.py`.
3. Implement minimal patch.
4. Run targeted smoke check (import/run command).
5. Report:
   - What changed
   - Why
   - Any risk or follow-up test needed

