# RESULTS

Generated 2026-09-12. Training period 2002-01-01 to 2024-08-02; sealed hold-out 2024-09-01 to 2026-09-09, opened once on 2026-09-12. 27 markets, six sectors, daily data, all free sources; see DECISIONS.md for every choice and s0's report for what the data is.

## 1. Cost ratio (computed first, before any return was read)

* **edge / cost = 2.3** — favourable (pre-registered: >= 2.0 favourable, >= 1 marginal, < 1 halt)
* modelled round trip: universe median 2.69 bp of notional, 4.1% of a daily move; the 2-year note is the outlier at 22.3%
* the literal daily-rebalanced SPEC §5a rule failed this check (edge/cost 0.85); the pre-registered monthly-signal / weekly-size schedule passes (DECISIONS.md)

## 2. Signals standalone (training period)

| signal | Sharpe after costs | turnover ×/yr | gross bp per side traded | cost bp per side | avg abs score | coverage | audit |
|---|---|---|---|---|---|---|---|
| trend | 0.24 | 70.6 | 10.0 | 3.24 | 0.73 | 96% | placebo cleared; stitching stable; band in; shuffled -0.11 |
| carry | 0.08 | 15.1 | 6.2 | 2.81 | 0.29 | 45% | placebo NOT cleared; stitching stable; band OUT (MDE 0.61); shuffled -0.25 |
| value | -0.44 | 17.3 | -31.8 | 5.59 | 0.59 | 84% | placebo NOT cleared; stitching stable; band OUT (MDE 0.57); shuffled 0.12 |

Carry covers 13 markets (FX, equity, US rates); commodity carry is unobservable on free data and is NaN, not zero. Standalone MDEs are 0.55–0.62 Sharpe-equivalent: no single signal can be distinguished from zero at 80% power over 23 years, which is the annualised-ratio arithmetic from FAILURES.md; the standalone criteria are band and placebo.

## 3. Pairwise correlation of the signals' returns

Daily:

|       |   trend |   carry |   value |
|:------|--------:|--------:|--------:|
| trend |   1     |  -0.067 |  -0.474 |
| carry |  -0.067 |   1     |  -0.131 |
| value |  -0.474 |  -0.131 |   1     |

Monthly:

|       |   trend |   carry |   value |
|:------|--------:|--------:|--------:|
| trend |   1     |  -0.016 |  -0.483 |
| carry |  -0.016 |   1     |  -0.177 |
| value |  -0.483 |  -0.177 |   1     |

## 4. Portfolio construction

* realised vol 16.59% against target 15% (s4 gate: within ±20%)
* effective breadth median **8.6** independent bets from 27 markets (band 8–15)
* sector risk shares (mean / max): ags 28%/45%, energy 19%/36%, equity 11%/24%, fx 16%/35%, metals 14%/29%, rates 12%/29%

## 5. Combined programme (training period)

* Sharpe after costs **0.06** (gross 0.21); band 0.5–1.0: OUT; audit: placebo cleared (p95 0.05), shuffled returns -0.17, stitching stable (max dev 0.09)
* annual return 1.07%, max drawdown -52.6%, longest flat period 5314 trading days, 4.7 bp gross per side traded against 3.31 bp cost
* distribution: worst day -4.73%, best day 7.22%, skew 0.17, excess kurtosis 2.3, monthly hit rate 51%, worst month -12.4%
* contribution by signal (combined minus without): trend +0.45, carry +0.03, value -0.28

## 6. Stitching sensitivity

Yahoo `=F` series are unadjusted front-month splices; no contract chain exists on free data, so the SPEC §4 Panama-vs-ratio test is run on adjusted series rebuilt from roll-neutralised changes, and the roll treatment itself is varied (raw / switch day / ±1 / ±3 / roll-early-3). Combined programme:

* returns:raw: 0.01
* returns:w0: 0.06
* returns:w1: -0.02
* returns:w3: 0.05
* returns:early3: 0.02
* prices:ratio: 0.07

* raw − neutralised = -0.05 (a positive value above 0.15 would mark the raw result an artefact)

## 7. Drawdown-mandate simulator (real s6 path, 8% target / 10% DD / 3% daily / 60 days)

* at 15% vol: pass **22.3%**, median 30 days to pass, breach by DD 12.2%, by daily loss 15.6%, timeout **49.9%**

|     |    n |   pass_prob |   median_days_to_pass |   breach_dd |   breach_daily |   timeout |
|:----|-----:|------------:|----------------------:|------------:|---------------:|----------:|
| 5%  | 5834 |       0.006 |                    48 |       0     |          0     |     0.994 |
| 10% | 5834 |       0.115 |                    37 |       0.034 |          0     |     0.851 |
| 15% | 5834 |       0.223 |                    30 |       0.122 |          0.156 |     0.499 |
| 20% | 5834 |       0.305 |                    24 |       0.191 |          0.309 |     0.195 |
| 25% | 5834 |       0.307 |                    17 |       0.147 |          0.498 |     0.048 |
| 30% | 5834 |       0.291 |                    12 |       0.106 |          0.6   |     0.004 |
| 40% | 5834 |       0.258 |                     7 |       0.074 |          0.668 |     0     |

## 8. Mandate feasibility sweep

* 53 of 500 mandates attainable (pass ≥ 50% at the best vol target)
* overall (at each mandate's best vol): breach_daily 68%, breach_dd 28%, timeout 4%
* vol target maximising risk-adjusted return (Calmar = return / |max DD| on the real path): **40%** (Calmar by vol: 5%: 0.02, 10%: 0.02, 15%: 0.02, 20%: 0.02, 25%: 0.02, 30%: 0.02, 40%: 0.03)
* vol target maximising pass probability, across all mandates: median **40%**, across attainable ones 30%
* SPEC example mandate: pass-maximising vol 25% vs Calmar-maximising 40% — gap -15%

## 9. Sealed hold-out (opened once)

* opened 2026-09-12; combined Sharpe after costs **-1.28** on 2024-09-01–2026-09-09 (training 0.06; 2-year SE 0.71; consistent: True)
* vol 16.39%, max drawdown -40.9%, breadth 7.5; standalone: trend -0.70, carry 0.69, value -0.72

## 10. Audit status

| number | value | status |
|---|---|---|
| cost ratio | 2.3** | computed before any return; schedule chosen on cost only |
| trend Sharpe | 0.24 | placebo cleared; stitching stable; band in; shuffled -0.11 |
| carry Sharpe | 0.08 | placebo NOT cleared; stitching stable; band OUT (MDE 0.61); shuffled -0.25 |
| value Sharpe | -0.44 | placebo NOT cleared; stitching stable; band OUT (MDE 0.57); shuffled 0.12 |
| combined Sharpe | 0.06 | placebo cleared; shuffled -0.17; stitching stable; band OUT |
| breadth | 8.6 | diversification ratio squared under the shrunk covariance |
| pass probability | 22.3% | real path, overlapping starts, no interval |
| hold-out Sharpe | -1.28 | one look; SE 0.71 |

## 11. Plain English

_(written after the run; see below)_
