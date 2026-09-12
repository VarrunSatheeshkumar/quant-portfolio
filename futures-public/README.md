# futures-public

Part two of three. Part one: BTC forced flow (`../btc-public`) · Part three: equities (in progress)

A systematic futures study on free daily data, and the pre-registered candidate screen
that followed it. The question: do well-documented premia — trend, carry, value — survive
a retail cost model and a hard drawdown mandate? The answer, in three sentences:

1. The three-signal programme does not work as specified: trend alone earns a Sharpe of
   0.24 after costs, carry is unmeasurable on the 13 markets where free data exposes a
   curve, value is refuted (−0.44), and the combination is 0.06 in training and −1.28 on a
   two-year hold-out opened once.
2. Twenty further claims were ranked and pre-registered before any test and run in order
   under a fixed twenty-way correction; a positive control cleared at t = 4.1, one
   candidate cleared — crypto funding carry, t = 3.73, +0.93% per week net of cost, decayed
   fourfold after 2021 — and every futures premium showed the predicted sign at roughly its
   published size but could not be resolved at that correction on 24 years of 13 markets.
3. The mandate simulator says what binds: of 500 mandates, 53 are attainable; the daily
   loss limit binds 68% of the time against 4% for the time window; and the volatility
   target that maximises pass probability sits *below* the one that maximises
   risk-adjusted return.

`WRITEUP.md` is the full account. Every number there carries its hold-out look count and
audit status, and every one is reproduced by the code here.

## Running it

```
pip install -r requirements.txt
./reproduce.sh
```

`reproduce.sh` runs `python build.py` (stages s0–s9, each gated, resumable from
`reports/progress.json`; `python build.py --force-from s4` re-runs from a stage), then the
candidate fetch, the splice check, the pre-registration dispersions, the eight tests in
their pre-registered order, and the C18 audit. About an hour on a laptop. All data
sources are keyless: Yahoo Finance, TreasuryDirect, Binance, EIA. `config.END` fixes the
last bar at 2026-09-09 so the numbers match the write-up. `data/` is rebuilt and not
tracked; `reports/` is tracked so the results can be read without running the pipeline,
and a reproduction overwrites it.

The hold-out (`config.SEALED_START`, the last two years) is opened by s9 and counted in
`reports/holdout_looks.json`. In the original run it was opened once, on 2026-09-09; the
reproduction of 2026-09-12 opened it once again and produced the same number, and the
tracked `holdout_looks.json` and `RESULTS.md` carry that reproduction's date and single
look. Re-deriving a recorded result is not a second look; no decision was taken after
either. Do not tune anything on it.

Reproduction note: the original run fetched its data on 2026-09-09 before that session had
closed, so its final bar was a partial print; it reported a hold-out Sharpe of −1.18. With the
settled close the same code gives −1.28, and every training-period number is unchanged to the
printed precision except the randomised diagnostics (placebo and shuffle percentiles), which
move by a few hundredths because the placebo's per-market flip rate is estimated from the
full series. WRITEUP.md carries the settled-close numbers.

## What each module does

| module | role |
|---|---|
| `config.py` | every constant: universe and contract specs, cost inputs, signal parameters, bands, dates |
| `build.py`, `progress.py` | orchestrator and stage bookkeeping; a failed gate halts the run |
| `stages/s0_fetch.py` | daily bars from Yahoo Finance with an `asof_time` per row |
| `stages/rolls.py` | exchange-rule expiry dates per contract family |
| `stages/s0_stitch.py` | Yahoo's `=F` series are unadjusted front-month splices; locates each switch day, drops it, rebuilds Panama and ratio series, and produces the roll-treatment variants for the sensitivity check |
| `stages/s0_grid.py` | the as-of grid: own bars on their date, reference series lagged one day |
| `stages/s0.py`, `tests/` | as-of test on random timestamps, stitching invariants, roll-sign refutation clauses |
| `stages/s1.py` | per-market cost model and the edge/cost ratio, computed before any return is read |
| `stages/s2.py`, `s3.py`, `s5.py` | trend, carry (basis where a spot reference exists; rates from the Treasury curve) and value, each evaluated standalone by `stages/signal_eval.py` with placebo, randomisation and stitching sensitivity |
| `backtest.py` | the one P&L engine: contracts × neutralised dollar changes, costs on every trade and roll, monthly block-bootstrap MDE |
| `portfolio.py`, `stages/s4.py` | sector caps, Ledoit–Wolf shrinkage, portfolio-level vol targeting, effective breadth |
| `stages/s6.py` | the three-signal programme, its correlation matrix, contribution by signal, randomisation and placebo |
| `simulator.py`, `stages/s7.py`, `s8.py` | the drawdown-mandate simulator on the real path, and the feasibility sweep |
| `stages/s9.py` | opens the hold-out once and writes `reports/RESULTS.md` |
| `lib/asof.py`, `holdout.py`, `power.py`, `validate.py` | audit machinery carried from the previous project: as-of joins with tolerances, purge/embargo and the look counter, MDE from block-bootstrap standard errors, placebo and block-shuffle randomisation |
| `candidates/common.py` | the pre-registered designs: event windows, the commodity panel slope with month fixed effects, the C18 weekly funding book, placebos |
| `candidates/prereg.py` | design dispersions and MDEs at N = 20, printed without any mean |
| `candidates/run.py` | one test per invocation, in the pre-registered order; writes `reports/candidates/<key>.md` |
| `candidates/fetch.py`, `splice_check.py`, `audit_c18.py` | the candidate data (SPY, VIX, auctions, Binance), the splice premise check against NYMEX settlements, and the C18 audit |

Python 3.9 or later. No credentials are used anywhere.
