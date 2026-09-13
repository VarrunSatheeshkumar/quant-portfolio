# Quant Finance Portfolio

Projects built independently in my own time, alongside an undergraduate degree in maths and economics. The goal was to go beyond coursework and actually implement the models I was reading about — not just understand them conceptually but build them from scratch and see what the numbers say.

P1–P6 were built in spring 2026, across the same period rather than in sequence, and P7–P8 in September 2026; this repository was consolidated and published in September 2026. The projects are grouped below by what they are, not by when they were built.

---

## Independent research — P7, P8 and the audit

P7 and P8 are two independent research programmes that tested whether specific effects survive retail transaction costs: forced-liquidation flow in BTC perpetual futures, and trend, carry and value in futures on free daily data, followed by a registered screen of twenty further candidate claims. Neither produced a tradeable result: no strategy return is presented net of costs, the one statistic that cleared its registered threshold has not been computed net of costs, and the price-response, mechanism and economic conclusions were withdrawn. Both were then audited claim by claim, to the point where several headline claims were withdrawn; the ledger recording that is linked below.

Every sentence in the two repositories' READMEs and write-ups corresponds to a row of the [claim ledger](audit/CLAIM_LEDGER.md): every numerical and interpretive claim in these two projects, traced to the artefact that produces it, with the wording each source permits — 117 rows, with withdraw and unknown as permitted outcomes. Claims the sources did not support were withdrawn rather than softened. The registration artefacts, the halt-rule record and the sealed-block inspection history are in the [evidence record](audit/EVIDENCE_RECORD.md). Part three, equities, is in progress.

What this work does not demonstrate: readiness to turn research into a trading decision. No strategy return is presented net of costs, and nothing here concerns execution, inventory, adverse selection or continuous quoting.

### P7 — BTC Forced Flow: Liquidation Map, Price Response, Volatility Forecast

P7 asked whether price responds to a liquidation map built from public open interest, price and funding, and whether the map's features forecast realised volatility beyond GARCH(1,1) and HAR-RV; it found a liquidation print somewhere in the market after 100 % of cluster touches and 92.4 % of unmapped ones, continuation after unpredicted prints of −0.3 [−4.8, 4.0] bps at 30 minutes, and point R² differences over the hour/day/week HAR of +0.024 to +0.051 with no uncertainty computed.

**Found.**
- In the touch bar and the next three five-minute bars, on print-covered days, a liquidation print somewhere in the market occurred for 100 % of cluster touches (n 36), 99.9 % of mid touches (n 908) and 92.4 % of empty touches (n 5,164).
- Continuation after unpredicted prints (print unit, day-block bootstrap): −0.9 [−3.5, 1.7] bps at 15 min, −0.3 [−4.8, 4.0] at 30 min, +3.8 [−1.5, 10.3] at 60 min.
- Point R² differences over the hour/day/week HAR of +0.024/+0.026/+0.038/+0.051 in the sealed cells, no uncertainty computed; on QLIKE the intraday HAR is better in three of four sealed cells.

**Not established.** Whether prints at the touched level exceed those at matched unmapped levels; whether the differences over HAR are distinguishable from zero, and which features carry them; whether any option structure could express the forecast — the economic conclusions are withdrawn.

**Audit.** Five framings, each with a hypothesis recorded privately before its result commit. The repository has no look counter and the sealed blocks have been scored repeatedly. The corrections to previously published sentences are itemised in the write-up, with a disposition at the end of each investigation.

**Next time.** With the same data again I would compute the cost ratio before mining for any signal: the private v1 record's six-basis-points-against-ten arithmetic (not reproducible here) was computed after the variant mining, and P8's cost ratio was projected before any signal was evaluated as a result.

→ [btc-public/](btc-public/) · [write-up](btc-public/WRITEUP.md)

### P8 — Futures Trend, Carry and Value on Free Daily Data

P8 asked whether trend, carry and value, specified in advance on 13–27 futures markets with a modelled cost, survive that cost and a drawdown mandate, and whether twenty candidate claims recorded privately before testing clear a corrected threshold; it found net Sharpes of 0.24, 0.08, −0.44 and 0.06 (combined) with no interval computed for any of them, a hold-out of −1.28, and one candidate of eight clearing on its gross statistic with net alpha not computed.

**Found.**
- Net Sharpe 0.24 (trend), 0.08 (carry), −0.44 (value) and 0.06 (combined) on the training period, with no Sharpe interval computed for any of them; hold-out −1.28, scored twice (−1.18 on a partial final bar, −1.28 on the settled close).
- None of the three non-control candidates predicted to clear cleared; three of the four predicted sign-right/not-cleared matched; the fourth, crypto funding-rate carry, cleared on its gross statistic (+1.015 %/wk, t 3.73), and net alpha with costs entered into the weekly series has not been computed.
- Of 500 specified mandates, 53 reach a 50 % pass probability at their best tested volatility target on the training path, before the drawdown-accounting correction.

**Not established.** Whether the funding-carry result survives costs entered into the series; the direction of its survivorship bias; any Sharpe interval.

**Audit.** Four halt conditions were registered. The three-same-reason halt fired after C11; I was advised to run C18 and C15 to complete the scoreable set and chose to; C18 then cleared; C15 ran after it, contrary to the registered clear-halt. The registration is verifiable only as commit order in a private repository. The corrections to previously published sentences are itemised in the write-up, with a disposition at the end of each investigation.

**Next time.** With the same data again I would stop when a registered halt condition fired: the three-same-reason halt fired after C11, I chose to run C18 and C15 anyway, and C15 ran after C18 had cleared, so those two results carry labels rather than standing as registered-rule results.

→ [futures-public/](futures-public/) · [write-up](futures-public/WRITEUP.md)

## Competition — P6

### P6 — QRT × ENS Data Challenge 2026

P6 asked whether the sign of an asset allocation's next-day return can be classified from 20 days of return and signed-volume history (~527k train rows, shuffled dates); it reached rank 178 / 1,175 on the public leaderboard (May 2026) and 210 / 1,280 on the private leaderboard (June 2026), with public accuracy 0.5212 against QRT's LightGBM baseline of 0.5079. Challenge ongoing — the public leaderboard updates on every submission and the private one twice a year, so both figures are dated snapshots. Key finding: the signal is dominantly cross-sectional — allocations that persistently underperform their peers keep underperforming, which is statistical arbitrage framing rather than return forecasting. Submission is an equal-weight blend of 10 models: LightGBM/CatBoost variants (two-stage magnitude-then-sign, residual targets) plus a Set Transformer attending across all allocations within a day, trained with pseudo-labels from the confident tail of the test set. CORAL and adversarial reweighting for train/test drift; GroupKFold by time to avoid leakage from cross-sectional features. Hyperparameters and blend weights pre-committed in writing; 18 of 19 audited candidates rejected under a ≥1bp out-of-fold improvement rule. Independent project. Code withheld while the challenge is open.

→ [p6_qrt_challenge/](p6_qrt_challenge/)

## Applied — P4

### P4 — JustWalk Quantitative Model

P4 asked, for a company I founded that installed piezoelectric tiles at Vodafone's Paddington office after raising £50,000, the three questions investors actually ask — how much energy, is it financially viable, and how to detect anomalous data — and found that electricity revenue alone (~£2/year at the office site) doesn't justify the CapEx, with a positive case only in a transit-hub scenario carrying SaaS analytics revenue (NPV ≈ £125k, P(NPV > 0) ≈ 93% across Monte Carlo scenarios). Footfall is simulated rather than taken from tile telemetry, so the detector can be tested against known ground truth.

→ [p4_justwalk/](p4_justwalk/)

## Foundations — P1, P2, P3, P5

### P1 — Black-Scholes Options Pricing

P1 asked how Black-Scholes prices a European option and where the model fails; it implements the formula, all five Greeks, a Newton-Raphson implied-volatility solver and a CRR binomial tree that cross-validates the formula and extends it to American options, and shows the model's most visible real-world failure as a stylised volatility skew illustration. The thing I found most interesting: why the stock's expected return doesn't appear in the formula.

→ [p1_black_scholes/](p1_black_scholes/)

### P2 — Markowitz Portfolio Optimisation

P2 asked what the efficient frontier across five UK-relevant asset classes looks like and how stable it is; it finds that optimal weights swing wildly across historical windows because expected returns can't be estimated precisely, then implements Ledoit-Wolf covariance shrinkage as the standard fix, comparing true, sample and shrunk frontiers directly. Built on constrained quadratic optimisation (SLSQP) with the tangency portfolio and Capital Market Line; also includes a crisis-correlation simulation showing diversification failing exactly when it's needed. Asset parameters are stylised long-run assumptions, not estimated from data.

→ [p2_markowitz/](p2_markowitz/)

### P3 — OLS Regression on UK Macro Data

P3 asked whether the Phillips Curve and Fisher equation relationships hold in 2000–2023 ONS/BoE data, using OLS from the normal equations (no statsmodels) with full diagnostics; it found strong positive autocorrelation in residuals (DW = 0.47), corrected with Newey-West HAC standard errors — the intercept SE comes out 47% larger, confirming OLS t-stats were inflated — and a Chow test flagging a structural break at 2022 (F = 4.97, p = 0.018), though the post-2022 subsample is only 2 observations, so the split coefficients are indicative rather than estimated.

→ [p3_econometrics/](p3_econometrics/)

### P5 — Market Insight Report

P5 asked what caused the 2022 UK gilt crisis and argues that the mini-budget was not the primary cause but a coordination device revealing pre-existing structural fragility: long debt maturity (~15yr average), ~25% index-linked exposure, and concentrated LDI leverage in pension funds. The argument rests on the gilt risk premium over Bunds remaining structurally wider after the fiscal measures were reversed — if it were purely a policy panic, it should have reverted.

→ [p5_market_report/](p5_market_report/)

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
- P8 runs on free daily data with front-month splices located from exchange-rule expiries and removed; settlement verification of the splice premise covers the four energy contracts only; the registered tests on 13–27 markets did not reach the corrected threshold.

## Dependencies

```bash
# P1-P5
pip install numpy scipy pandas matplotlib scikit-learn

# P6 additionally
pip install lightgbm catboost torch
```

Python 3.10+.
