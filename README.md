# Quant Finance Portfolio

Projects built independently in my own time, alongside first-year Maths and Economics at Nottingham. The goal was to go beyond coursework and actually implement the models I was reading about — not just understand them conceptually but build them from scratch and see what the numbers say.

---

## Projects

### P1 — Black-Scholes Options Pricing
European call/put pricing, all five Greeks, Newton-Raphson implied volatility solver, and a CRR binomial tree that cross-validates the formula and extends it to American options. The thing I found most interesting: why the stock's expected return doesn't appear in the formula. Includes a volatility smile demonstration showing the model's most visible real-world failure.

→ `p1_black_scholes/`

### P2 — Markowitz Portfolio Optimisation
Efficient frontier across five UK-relevant asset classes via constrained quadratic optimisation (SLSQP), with the tangency portfolio and Capital Market Line. Demonstrates the model's central practical problem — optimal weights swing wildly across historical windows because expected returns can't be estimated precisely — then implements Ledoit-Wolf covariance shrinkage as the standard fix, comparing true, sample and shrunk frontiers directly. Also includes a crisis-correlation simulation showing diversification failing exactly when it's needed. Asset parameters are stylised long-run assumptions, not estimated from data.

→ `p2_markowitz/`

### P3 — OLS Regression on UK Macro Data
OLS from the normal equations (no statsmodels) on 2000–2023 ONS/BoE data. Runs the Phillips Curve and Fisher equation regressions with full diagnostics. Main findings: strong positive autocorrelation in residuals (DW = 0.47), corrected with Newey-West HAC standard errors — the intercept SE comes out 47% larger, confirming OLS t-stats were inflated. A Chow test flags a structural break at 2022 (F = 4.97, p = 0.018), though the post-2022 subsample is only 2 observations, so the split coefficients are indicative rather than estimated.

→ `p3_econometrics/`

### P4 — JustWalk Quantitative Model
JustWalk is a real company I founded. We raised £50,000 from Vodafone and installed piezoelectric tiles at their Paddington office. This model answers the three questions investors actually ask: how much energy, is it financially viable, and how do we detect anomalous data. The honest financial answer: electricity revenue alone (~£2/year at the office site) doesn't justify the CapEx. The transit hub scenario shows where it does work — with SaaS analytics revenue, NPV ≈ £125k and P(NPV > 0) ≈ 93% across Monte Carlo scenarios.

→ `p4_justwalk/`

### P5 — Market Insight Report
A research note arguing that the 2022 UK gilt crisis was not primarily caused by the mini-budget, but that the mini-budget acted as a coordination device revealing pre-existing structural fragility: long debt maturity (~15yr average), ~25% index-linked exposure, and concentrated LDI leverage in pension funds. The argument rests on the gilt risk premium over Bunds remaining structurally wider after the fiscal measures were reversed — if it were purely a policy panic, it should have reverted.

→ `p5_market_report/`

### P6 — QRT × ENS Data Challenge 2026
Binary classification of asset allocation returns from 20 days of return and signed-volume history (~527k train rows, shuffled dates). Rank 178 / 1,175 on the public leaderboard (May 2026) and 210 / 1,280 on the private leaderboard (June 2026), against QRT's LightGBM baseline; public accuracy 0.5212 vs the baseline's 0.5079. Challenge ongoing — the public leaderboard updates on every submission and the private one twice a year, so both figures are dated snapshots. Key finding: the signal is dominantly cross-sectional — allocations that persistently underperform their peers keep underperforming, which is statistical arbitrage framing rather than return forecasting. Submission is an equal-weight blend of 10 models: LightGBM/CatBoost variants (two-stage magnitude-then-sign, residual targets) plus a Set Transformer attending across all allocations within a day, trained with pseudo-labels from the confident tail of the test set. CORAL and adversarial reweighting for train/test drift; GroupKFold by time to avoid leakage from cross-sectional features. Hyperparameters and blend weights pre-committed in writing; 18 of 19 audited candidates rejected under a ≥1bp out-of-fold improvement rule. Independent project. Code withheld while the challenge is open.

→ `p6_qrt_challenge/`

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

## Limitations I'm aware of

- OLS residuals show autocorrelation — implemented Newey-West HAC standard errors: SE is 47% larger than OLS, confirming the bias. Chow test also flags a structural break post-2022 (F = 4.97, p = 0.018), but the post-2022 subsample is only n = 2, so the split coefficients are indicative rather than estimated
- Markowitz is very sensitive to estimated returns. Ledoit-Wolf shrinkage addresses the covariance side; the expected-return side is not solved, and the instability demo shows why that matters more.
- Black-Scholes assumes constant vol and lognormal returns — the vol smile shows directly that the market disagrees
- JustWalk NPV depends heavily on the SaaS analytics revenue assumption
- JustWalk's energy model assumes every visitor traverses the full tile run, so output scales linearly with tile count — an upper bound, not a central case.

## Dependencies

```bash
# P1-P5
pip install numpy scipy pandas matplotlib scikit-learn

# P6 additionally
pip install lightgbm catboost torch
```

Python 3.10+.
