# Quant Finance Portfolio

Research and modelling projects built independently alongside an undergraduate degree in maths and economics. The focus is implementing models, checking the observations they produce, and deciding what the evidence supports.

Start with P7 or P8 for the research work, P6 for the competition entry, or P4 for a model used to examine a business decision. P1–P6 were built in spring 2026 and P7–P8 in September 2026; the project numbers are retained as identifiers.

## Independent research — P7 and P8

P7 studies forced-liquidation flow in BTC perpetuals and volatility forecasting; P8 studies futures signals, modelled costs and portfolio constraints, followed by a screen of further candidate claims. The retained results include event measurements, forecast comparisons and returns after modelled costs, with unresolved statistical and economic questions. Neither programme establishes a tradable strategy from these results.

### P7 — BTC Forced Flow: Liquidation Map, Price Response, Volatility Forecast

P7 asked whether price responds to inferred liquidation levels and whether a model including map-derived features improves volatility forecasts. It retains price-response estimates and benchmark comparisons; the map's contribution to the forecast differences has not been isolated.

- **Price response:** continuation after unpredicted prints is −0.9 [−3.5, 1.7] bps at 15 minutes, −0.3 [−4.8, 4.0] at 30 minutes and +3.8 [−1.5, 10.3] at 60 minutes (print unit, day-block bootstrap).
- **Forecast comparison:** point R² differences over the hour/day/week HAR are +0.024/+0.026/+0.038/+0.051, without computed uncertainty. The intraday HAR has lower QLIKE in three of four sealed cells. The write-up states the calibration and repeated-inspection limitations.
- **Decision:** retain these measurements, leave attribution unresolved, and withdraw the option-economics conclusions. The locator's market-wide counts do not establish liquidation activity at the touched level and side.

**Next time:** I would make the cost assumptions and the effect worth investigating explicit before searching for signals. P8's initial cost screen illustrates that process, conditional on its assumed gross Sharpe and cost model.

→ [Project and results](btc-public/) · [One event worked through by hand](btc-public/WRITEUP.md#one-touch-from-map-state-to-measurement) · [Full write-up](btc-public/WRITEUP.md)

### P8 — Futures Trend, Carry and Value on Free Daily Data

P8 asked how trend, carry and value perform after modelled costs and portfolio construction on 13–27 futures markets. The reported training net Sharpes are 0.24, 0.08, −0.44 and 0.06 for the combined book; no Sharpe intervals were computed.

- **Historical hold-out:** net Sharpe −1.28, scored twice; upstream roll-switch selection and cost normalisation also read the designated hold-out period.
- **Candidate screen:** none of the futures candidates met the registered corrected threshold. The crypto funding candidate C18 has gross alpha +1.015 %/week, month-block SE 0.27 and t = 3.73; net alpha with weekly costs entered into the series remains uncomputed, and the universe is survivor-conditioned.
- **Decision:** stop the futures programme and retain C18 as unresolved. C18 was run after I overrode the three-same-reason halt; C15 was then run after C18 cleared, contrary to the clear-halt rule. Those departures are part of the result's interpretation.

**Next time:** I would stop when a registered halt condition fired and label any subsequent work as a separate exploratory continuation.

→ [Project and results](futures-public/) · [One portfolio week worked through by hand](futures-public/WRITEUP.md#worked-example-constructing-one-c18-week) · [Full write-up](futures-public/WRITEUP.md)

The [claim ledger](audit/CLAIM_LEDGER.md) records sources, qualifications and withdrawn wording; its coverage is not an exhaustive certification. The [audit guide](audit/README.md) distinguishes public evidence from references to the unpublished private archive, and the [reproduction record](audit/REPRODUCTION.md) distinguishes regenerated outputs from retained historical reports. These projects demonstrate research construction and inference practice; they provide no record of live execution, inventory management or continuous quoting. An equities project is in progress and has no result presented here.

## Competition — P6

### P6 — QRT × ENS Data Challenge 2026

P6 predicts the sign of an allocation's next-day return from return and signed-volume histories. Reported leaderboard snapshots are rank 178 / 1,175 with accuracy 0.5212 publicly (May 2026), and rank 210 / 1,280 privately (June 2026); the reported baseline accuracy is 0.5079. The submission blends tree models and a Set Transformer, with pseudo-labelling and folds grouped by day. Code and an independently reproducible training run are not included in this portfolio.

→ [Method and dated results](p6_qrt_challenge/)

## Applied — P4

### P4 — JustWalk Quantitative Model

For a company I founded, P4 models energy generation, investment returns and anomaly detection for piezoelectric floor tiles installed at Vodafone's Paddington office after £50,000 of funding. The office scenario yields about £2/year of electricity revenue; the positive transit-hub scenario depends on assumed SaaS analytics revenue. Footfall and the Monte Carlo scenarios are simulated, so their outputs are conditional model results.

→ [Business question, assumptions and model](p4_justwalk/)

## Foundations — P1, P2, P3 and P5

### P1 — Black-Scholes Options Pricing

P1 implements European option pricing, five Greeks, a Newton–Raphson implied-volatility solver and a CRR binomial tree. It compares tree and formula prices and illustrates volatility skew using stylised inputs.

→ [Derivatives implementation](p1_black_scholes/)

### P2 — Markowitz Portfolio Optimisation

P2 builds efficient frontiers and shows optimal weights changing across two simulated estimation windows. Ledoit–Wolf shrinkage addresses covariance estimation; it does not solve uncertainty in expected returns. Asset parameters are stylised assumptions.

→ [Optimisation and estimation sensitivity](p2_markowitz/)

### P3 — OLS Regression on UK Macro Data

P3 implements OLS and diagnostics on 2000–2023 UK macro data. It reports residual autocorrelation (Durbin–Watson 0.47) and a Newey–West intercept standard error 47% above the conventional estimate. The 2022 split has only two observations afterwards, limiting what can be inferred from the split regressions.

→ [Regressions and diagnostic limitations](p3_econometrics/)

### P5 — Market Insight Report

P5 examines the 2022 UK gilt crisis and argues that the fiscal announcement exposed pre-existing fragility involving LDI leverage and the gilt market. This is an interpretive market report; its argument is not a separately identified causal estimate.

→ [Market report](p5_market_report/market_insight_report.md)

## Implementation

The projects include OLS from the normal equations, analytical option Greeks, iterative implied-volatility and IRR solvers, binomial-tree pricing, constrained optimisation, simulation and HAC standard errors. P7/P8 add event construction, volatility benchmarks, explicit cost units and dependence-aware inference procedures whose limitations are documented in the write-ups. Running instructions and dependencies are in each project.
