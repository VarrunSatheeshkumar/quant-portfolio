# Quant Finance Portfolio

Five projects built independently in my own time, alongside first-year Maths and Economics at Nottingham. The goal was to go beyond coursework and actually implement the models I was reading about — not just understand them conceptually but build them from scratch and see what the numbers say.

---

## Projects

### P1 — Black-Scholes Options Pricing
European call/put pricing, all five Greeks, Newton-Raphson implied volatility solver, and a CRR binomial tree that cross-validates the formula and extends it to American options. The thing I found most interesting: why the stock's expected return doesn't appear in the formula. Includes a volatility smile demonstration showing the model's most visible real-world failure.

→ `p1_black_scholes/`

### P2 — Markowitz Portfolio Optimisation
Efficient frontier across five UK asset classes via constrained quadratic optimisation. Includes the tangency portfolio, Capital Market Line, and a demonstration of the model's central practical problem: estimated returns are so noisy that the "optimal" portfolio swings dramatically between different historical windows. The code shows this concretely rather than just mentioning it.

→ `p2_markowitz/`

### P3 — OLS Regression on UK Macro Data
OLS from the normal equations (no statsmodels) on 2000–2023 ONS/BoE data. Runs the Phillips Curve and Fisher equation regressions with full diagnostics. Main findings: strong positive autocorrelation in residuals (DW = 0.47, meaning standard errors are understated), and the Phillips Curve slope steepened markedly after 2022 — the pre/post split shows the intercept shifted up by about 4.5 percentage points.

→ `p3_econometrics/`

### P4 — JustWalk Quantitative Model
JustWalk is a real company I founded. We raised £50,000 from Vodafone and installed piezoelectric tiles at their Paddington office. This model answers the three questions investors actually ask: how much energy, is it financially viable, and how do we detect anomalous data. The honest financial answer: electricity revenue alone (~£2/year at the office site) doesn't justify the CapEx. The transit hub scenario shows where it does work — with SaaS analytics revenue, NPV ≈ £125k and P(NPV > 0) ≈ 93% across Monte Carlo scenarios.

→ `p4_justwalk/`

### P5 — Market Insight Report
A research note arguing that the 2022 UK gilt crisis was not primarily caused by the mini-budget, but that the mini-budget acted as a coordination device revealing pre-existing structural fragility: long debt maturity (~15yr average), ~25% index-linked exposure, and concentrated LDI leverage in pension funds. The key evidence is that the UK-Bund spread remained wider even after the mini-budget was reversed — if it were just a policy panic, it should have reverted.

→ `p5_market_report/`

### P6 — QRT × ENS Data Challenge 2026
Binary classification of daily asset allocation returns. Given 20 days of return and volume history per allocation, predict whether the next-day return is positive or negative. Rank 339 / 1,106. Accuracy: 0.5177 (QRT LightGBM baseline: 0.5079). The key finding: cross-sectional momentum — allocations that consistently underperform relative to peers in training stay underperforming — maps directly onto statistical arbitrage framing. Implementation uses CORAL domain adaptation, adversarial sample reweighting, a sequence transformer, and magnitude-weighted gradient boosting. Code not shared while the challenge is open.

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

- OLS residuals show autocorrelation — implemented Newey-West HAC standard errors: SE is 47% larger than OLS, confirming the bias. Chow test also flags a structural break post-2022 (F = 4.97, p = 0.018)
- Markowitz is very sensitive to estimated returns — the code demonstrates this problem rather than solving it
- Black-Scholes assumes constant vol and lognormal returns — the vol smile shows directly that the market disagrees
- JustWalk NPV depends heavily on the SaaS analytics revenue assumption

## Dependencies

```bash
pip install numpy scipy pandas matplotlib
```

Python 3.10+. No exotic dependencies.
