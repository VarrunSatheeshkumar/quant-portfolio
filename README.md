# Quant Finance Portfolio

Projects built independently in my own time, alongside an undergraduate degree in maths and economics. The goal was to go beyond coursework and actually implement the models I was reading about — not just understand them conceptually but build them from scratch and see what the numbers say.

P1–P6 were built in spring 2026, across the same period rather than in sequence, and P7–P8 in September 2026; this repository was consolidated and published in September 2026.

---

## Projects

### P1 — Black-Scholes Options Pricing
European call/put pricing, all five Greeks, Newton-Raphson implied volatility solver, and a CRR binomial tree that cross-validates the formula and extends it to American options. The thing I found most interesting: why the stock's expected return doesn't appear in the formula. Includes a stylised volatility skew illustration showing the model's most visible real-world failure.

→ `p1_black_scholes/`

### P2 — Markowitz Portfolio Optimisation
Efficient frontier across five UK-relevant asset classes via constrained quadratic optimisation (SLSQP), with the tangency portfolio and Capital Market Line. Demonstrates the model's central practical problem — optimal weights swing wildly across historical windows because expected returns can't be estimated precisely — then implements Ledoit-Wolf covariance shrinkage as the standard fix, comparing true, sample and shrunk frontiers directly. Also includes a crisis-correlation simulation showing diversification failing exactly when it's needed. Asset parameters are stylised long-run assumptions, not estimated from data.

→ `p2_markowitz/`

### P3 — OLS Regression on UK Macro Data
OLS from the normal equations (no statsmodels) on 2000–2023 ONS/BoE data. Runs the Phillips Curve and Fisher equation regressions with full diagnostics. Main findings: strong positive autocorrelation in residuals (DW = 0.47), corrected with Newey-West HAC standard errors — the intercept SE comes out 47% larger, confirming OLS t-stats were inflated. A Chow test flags a structural break at 2022 (F = 4.97, p = 0.018), though the post-2022 subsample is only 2 observations, so the split coefficients are indicative rather than estimated.

→ `p3_econometrics/`

### P4 — JustWalk Quantitative Model
JustWalk is a real company I founded. We raised £50,000 from Vodafone and installed piezoelectric tiles at their Paddington office. This model answers the three questions investors actually ask: how much energy, is it financially viable, and how do we detect anomalous data. The honest financial answer: electricity revenue alone (~£2/year at the office site) doesn't justify the CapEx. The transit hub scenario shows where it does work — with SaaS analytics revenue, NPV ≈ £125k and P(NPV > 0) ≈ 93% across Monte Carlo scenarios. Footfall is simulated rather than taken from tile telemetry, so the detector can be tested against known ground truth.

→ `p4_justwalk/`

### P5 — Market Insight Report
A research note arguing that the 2022 UK gilt crisis was not primarily caused by the mini-budget, but that the mini-budget acted as a coordination device revealing pre-existing structural fragility: long debt maturity (~15yr average), ~25% index-linked exposure, and concentrated LDI leverage in pension funds. The argument rests on the gilt risk premium over Bunds remaining structurally wider after the fiscal measures were reversed — if it were purely a policy panic, it should have reverted.

→ `p5_market_report/`

### P6 — QRT × ENS Data Challenge 2026
Binary classification of asset allocation returns from 20 days of return and signed-volume history (~527k train rows, shuffled dates). Rank 178 / 1,175 on the public leaderboard (May 2026) and 210 / 1,280 on the private leaderboard (June 2026), against QRT's LightGBM baseline; public accuracy 0.5212 vs the baseline's 0.5079. Challenge ongoing — the public leaderboard updates on every submission and the private one twice a year, so both figures are dated snapshots. Key finding: the signal is dominantly cross-sectional — allocations that persistently underperform their peers keep underperforming, which is statistical arbitrage framing rather than return forecasting. Submission is an equal-weight blend of 10 models: LightGBM/CatBoost variants (two-stage magnitude-then-sign, residual targets) plus a Set Transformer attending across all allocations within a day, trained with pseudo-labels from the confident tail of the test set. CORAL and adversarial reweighting for train/test drift; GroupKFold by time to avoid leakage from cross-sectional features. Hyperparameters and blend weights pre-committed in writing; 18 of 19 audited candidates rejected under a ≥1bp out-of-fold improvement rule. Independent project. Code withheld while the challenge is open.

→ `p6_qrt_challenge/`

P7 and P8 are the first two of three sequential research projects, each one's failure determining the next question. P7 asked whether an effect exists — forced liquidation flow in BTC perpetuals — and failed on economics: the method held, but six basis points of edge against a ten-basis-point round trip made the trade impossible before any signal was found. P8 held the method fixed, inverted the cost ratio, and asked whether known, published effects survive retail costs; it failed on power, with every premium showing its published sign but none clearing a twenty-way correction on 27 markets. The third, equities, follows because breadth turned out to be the binding constraint. Part three is in progress.

### P7 — BTC Forced Flow: Liquidation Maps and the Instrument Ceiling
Reconstructs where leveraged BTC perpetual positions will be force-closed, from public open interest, price and funding, and finds the map is real but not tradeable: forced flow arrives where it predicts, price does not respond, and the one component that generalises — a volatility forecast — is worth less than the cheapest instrument that could express it. Built on a five-minute as-of grid (2020–2026). The map locates real forced flow — every one of the 36 cluster touches on print-covered days coincided with actual liquidations, and mapped levels carried 5.3× the liquidation notional of unmapped ones — but price does not respond to it. Five pre-registered framings of "does price move through a cluster?", each with its placebo; the one adequately powered framing measured −0.3bps against a 6.5bps minimum detectable effect. The same reconstruction does forecast volatility, and how much depends on the benchmark: decisive against GARCH(1,1), but only +0.02–0.05 R² over a horizon-matched HAR-RV in the sealed hold-out blocks, and losing to HAR on QLIKE in three of four cells. Then the instrument ceiling: an idealised variance swap with zero spread, fees or hedging error still has a minimum detectable effect of 81.6bps against a 10bps band, so roughly 309 years of weekly trades would be needed to resolve the edge. The mistake that ended the project: ~6bps of edge against a 10bps round trip, arithmetic available on day one. Public cut of a larger private project; every quoted figure is checked against `reports/results/` by a test.

→ `btc-public/`

### P8 — Futures Trend, Carry and Value Under Retail Costs
Tests whether trend, carry and value survive a retail cost model and a hard drawdown mandate, and finds that they cannot be resolved: every premium shows its published sign at roughly its published size, but none clears an honest twenty-way correction, because 27 markets is too little breadth. 27 markets in six sectors from 2000 on free daily data, with Yahoo's front-month splices located and neutralised, a cost model committed before any return was read, and P7's audit machinery carried over unchanged. The three-signal programme failed: trend earns a Sharpe of 0.24 after costs, carry is unmeasurable on the 13 markets with an observable curve, value is refuted (−0.44), and the combination is 0.06 in training and −1.28 on a two-year hold-out opened once — the −0.47 trend/value correlation cancels the book and the vol layer levers up the residual. Twenty further candidates were then ranked and pre-registered under a Bonferroni correction fixed at N = 20 (t ≥ 3.02). A positive control — SPY's overnight return traded through ES — cleared at t = 4.1, so the pipeline finds real effects; one candidate cleared, crypto funding-rate carry at t = 3.73 and +0.93% per week net of cost, decaying fourfold after 2021; every futures premium returned the predicted sign at roughly its published size, with t between 1.6 and 2.5 against the 3.02 bar. The breadth finding: the one clear came from ~110 instruments against 27 markets, and the design's standard-error estimate was wrong by nearly threefold for exactly that reason. Breadth is the sample size — which is why the next project is equities.

→ `futures-public/`

---

## What's built from scratch

To make sure I understood what was happening:

- OLS via the normal equations `β̂ = (XᵀX)⁻¹Xᵀy`
- Black-Scholes Greeks by analytical differentiation
- Implied volatility via Newton-Raphson (vega as the derivative)
- CRR binomial tree with backward induction
- IRR via Newton-Raphson
- Poisson footfall simulation with time-varying rate
- Monte Carlo NPV under parameter uncertainty
- Z-score anomaly detection with rolling window
- Newey-West HAC standard errors with the Bartlett kernel
- Chow structural break test
- Set Transformer (attention over the set of allocations within a day), implemented from the paper
- CORAL covariance alignment and adversarial sample reweighting for domain shift
- GroupKFold-by-time with a pre-committed pseudo-label chain
- For P7/P8: as-of grids with staleness tolerances, purge-and-embargo walk-forward, block bootstrap, label-shuffle placebos, and minimum-detectable-effect calculation

## Limitations I'm aware of

- OLS residuals show autocorrelation — implemented Newey-West HAC standard errors: SE is 47% larger than OLS, confirming the bias. Chow test also flags a structural break post-2022 (F = 4.97, p = 0.018), but the post-2022 subsample is only n = 2, so the split coefficients are indicative rather than estimated
- Markowitz is very sensitive to estimated returns. Ledoit-Wolf shrinkage addresses the covariance side; the expected-return side is not solved, and the instability demo shows why that matters more.
- Black-Scholes assumes constant vol and lognormal returns — the vol skew shows directly that the market disagrees, though the skew plotted here is a stylised illustration of the characteristic equity shape, not live market quotes
- JustWalk NPV depends heavily on the SaaS analytics revenue assumption
- JustWalk's energy model assumes every visitor traverses the full tile run, so output scales linearly with tile count — an upper bound, not a central case.
- P6's pseudo-labelling trains on the model's own confident predictions, so an early error compounds rather than corrects. The ≥1bp gate and locked blend guard against leaderboard-fitting but do not prove against it. At 0.52 accuracy, rank is partly noise.
- P7's liquidation map infers position cohorts from open-interest changes rather than observing positions, so the leverage mix is fitted rather than known. The calibration is against real liquidation prints, but the inference step is an assumption.
- P8 runs on free daily data with front-month splices that had to be located and neutralised rather than avoided, and 27 markets is too few to resolve most of the premia it tests — which is the project's own finding.

## Dependencies

```bash
# P1-P5
pip install numpy scipy pandas matplotlib scikit-learn

# P6 additionally
pip install lightgbm catboost torch
```

Python 3.10+.
