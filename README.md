# Quantitative Finance Portfolio

I'm an undergraduate in mathematics and economics, applying for quantitative trading roles. These projects are the work I've done outside coursework: foundations, a scored competition entry, and two independent research programmes with a published audit of both.

Neither research programme established a tradable strategy from its results. Both were then audited — by independent review and against a claim ledger — and several previously published findings were withdrawn; the corrections are published in full.

## Selected work

| Project | Question and result | Where to start |
| --- | --- | --- |
| **P8 — Futures signals and portfolio risk** | How do trend, carry and value perform after modelled costs? The combined training net Sharpe is 0.06, without a computed interval. The futures programme stopped; a separate crypto funding candidate remains unresolved. | [Strategy results](futures-public/WRITEUP.md#the-three-signals) · [One crypto week](futures-public/WRITEUP.md#worked-example-constructing-one-c18-week) |
| **P7 — BTC forced flow and volatility** | Does price respond to inferred liquidation levels, and do map-derived features improve forecasts? Event measurements and forecast comparisons remain; the map's contribution to forecast differences is unresolved. | [Continuation table](btc-public/WRITEUP.md#price-after-liquidation-prints) · [One cluster touch](btc-public/WRITEUP.md#one-touch-from-map-state-to-measurement) |
| **P6 — QRT × ENS Data Challenge** | Predict the sign of an allocation's next-day return. Reported ranks: **178 / 1,175 public** (May 2026), **210 / 1,280 private** (June 2026). Code is withheld; the challenge is still running. | [Method and dated results](p6_qrt_challenge/) |
| **P4 — JustWalk investment model** | For a company I founded, which secured £50,000 and installed tiles at Vodafone's Paddington office: the office model yields about £2/year in electricity revenue. The positive hub scenario depends on assumed SaaS revenue; footfall is simulated. | [Business question and assumptions](p4_justwalk/) |

Research sequence: BTC (P7) → futures (P8) → equities (in progress; no result presented). Project numbers remain identifiers; the most substantial work is presented first.

## Research results and judgement

### P8 — From signals to a costed portfolio

Across 13–27 futures markets, the reported training net Sharpes are **0.24 trend, 0.08 carry, −0.44 value and 0.06 combined**. No Sharpe intervals were computed. The historical hold-out net Sharpe was −1.28. It was scored twice and was also read by upstream roll-switch selection and cost normalisation.

The crypto funding candidate C18 reports **gross alpha +1.015%/week**, month-block SE 0.27 and t = 3.73. Net alpha with weekly costs entered into the return series remains uncomputed; the universe is survivor-conditioned. I ran C18 after overriding the three-same-reason halt, then C15 after C18 cleared, contrary to the clear-halt rule.

**Decision:** stop the futures programme and preserve C18 as unresolved. In future I would stop when a registered halt fired and label subsequent work as a separate exploratory continuation.

→ [Check one portfolio week by hand](futures-public/WRITEUP.md#worked-example-constructing-one-c18-week) · [Code and running instructions](futures-public/) · [Full write-up](futures-public/WRITEUP.md)

### P7 — From a liquidation map to measured outcomes

Continuation after unpredicted prints at 30 minutes is **−0.3 [−4.8, 4.0] bps**, at the print unit with a day-block bootstrap. The [three-horizon table](btc-public/WRITEUP.md#price-after-liquidation-prints) includes the 15- and 60-minute estimates and their sampling limitations. The locator's market-wide liquidation counts do not establish activity at the touched level and side.

The model including map-derived features has point R² differences of **+0.024/+0.026/+0.038/+0.051** over the hour/day/week HAR benchmark, without computed uncertainty. The intraday HAR has lower forecast loss (QLIKE) in three of four sealed cells. Calibration and repeated-inspection limitations are recorded in the write-up.

**Decision:** retain the measurements, leave forecast attribution unresolved, and withdraw the option-economics conclusions. In future I would specify the cost assumptions and effect worth investigating before searching for signals; P8's initial cost screen illustrates that process under its assumed gross Sharpe and cost model.

→ [Check one cluster touch by hand](btc-public/WRITEUP.md#one-touch-from-map-state-to-measurement) · [Code and running instructions](btc-public/) · [Full write-up](btc-public/WRITEUP.md)

## Foundations

- **[P1 — Options pricing](p1_black_scholes/):** European pricing, five Greeks, Newton–Raphson implied volatility and a CRR binomial tree; tree/formula comparisons and stylised volatility-skew inputs.
- **[P2 — Portfolio optimisation](p2_markowitz/):** efficient frontiers and weight sensitivity across simulated estimation windows. Covariance shrinkage does not resolve uncertainty in expected returns.
- **[P3 — UK macro regressions](p3_econometrics/):** OLS from the normal equations and residual diagnostics. Dependence limits inference; the later subsample of the 2022 split has only two observations.
- **[P5 — UK gilt crisis](p5_market_report/market_insight_report.md):** an interpretive report on the fiscal announcement, LDI leverage and pre-existing market fragility; no separately identified causal estimate.

## Evidence and reproduction

P7/P8 demonstrate research construction and inference practice; neither establishes a tradable strategy from these results. They provide no record of live execution or inventory management. The [claim ledger](audit/CLAIM_LEDGER.md) records sources, qualifications and withdrawn wording; coverage is not an exhaustive certification. The [audit guide](audit/README.md) explains private-source limitations, and the [reproduction record](audit/REPRODUCTION.md) distinguishes regenerated outputs from retained historical reports.

P1–P6 were built in spring 2026 and P7–P8 in September 2026. Methods, dependencies and available outputs are documented within each project.
