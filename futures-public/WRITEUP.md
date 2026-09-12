# Do known premia survive retail costs and a hard risk mandate?

Every number below is tagged with the period it comes from, how many times the sealed hold-out had been looked at when it was produced, and what audit it passed. "Training" means 2002-01 to 2024-08 with the last two years sealed; "hold-out" means those two years, opened once, on 2026-09-09. `reproduce.sh` regenerates all of them.

## The question

The previous project asked whether forced liquidation flow predicts Bitcoin's price. Twelve pre-registered versions said no, and the reason the project ended was arithmetic rather than method: the best direction model had six basis points of edge per trade against ten of round-trip cost, computed after eighty-two thousand signal variants had been mined. The method — as-of discipline, minimum detectable effects before criteria, placebos, refutation clauses — was sound. What failed was the economics.

Futures invert that ratio. The modelled round trip across 27 liquid markets is 2.7 basis points at the median, about 4% of a typical daily move, against roughly a third in Bitcoin perpetuals. So the natural next question was the opposite kind: not whether an unknown effect exists, but whether three effects documented for decades — trend, carry, value — survive a retail cost model and a hard drawdown mandate.

## What was built

Twenty-seven markets in six sectors from 2000, free data throughout. Yahoo's continuous futures are unadjusted front-month splices — crude prints −37.63 on 20 April 2020 and $32 in 2000 — so every contract switch leaks the calendar spread as a fake return, 11% a year in natural gas and −12% in gasoline. No free source has individual contracts. The switch days were located from exchange expiry rules, verified against NYMEX settlements republished by EIA (98.4–98.8% of days match from 2002; 91–96% of expiries are held to the last trading day), dropped, and the whole study re-run under five roll treatments and two adjustment methods as a gate.

The cost model came before any signal: commission, half-spread plus impact per side, one spread crossing per roll, per market. Expected edge at the band midpoint against modelled cost was 2.3 [training; computed before any return was read], after the literal daily-rebalanced rule failed at 0.85 and a monthly-signal, weekly-size schedule was pre-registered instead.

Then trend (the sign of price against 20, 50, 100 and 200-day averages), carry (the basis where a spot or cash reference exists — FX, equity indices, US Treasuries, 13 of 27 markets; commodities have no observable curve on free data and carry nothing rather than zero), and value (price against its own five-year mean, inverted). Sizing in three layers: per-position volatility scaling; portfolio-level volatility targeting under a Ledoit–Wolf shrunk covariance so that the book's implied vol, not the sum of its parts, hits 15%; and a 35% sector cap with the effective number of independent bets reported. Finally a mandate simulator that takes the backtest's real daily path, starts on every date, and records whether a profit target is reached before a daily-loss limit, a drawdown limit or the clock; and a sweep of 500 mandates at seven volatility targets.

## What happened

The programme failed. Trend alone had life: Sharpe 0.24 after costs, 10.0 basis points gross per side traded against 3.24 of cost, timing +0.44 against a standing tilt of −0.22 [training, 0 looks; placebo cleared, stitching stable, inside its 0.2–0.6 band]. Carry was unmeasurable: Sharpe 0.08 on the 13 covered markets with a minimum detectable effect of 0.61 [training, 0 looks; placebo not cleared]. Value was actively negative: Sharpe −0.44, −31.8 basis points gross per side, a rule that was short equities and bonds through the long rises of 2010–2020 [training, 0 looks; placebo not cleared].

Its correlation with trend was −0.47 — exactly the property the specification wanted, and exactly the cancellation the previous project's failure log warns about: two disagreeing signals shrink the book toward zero, the vol layer levers the residual to about twice, and the doubled costs eat what trend made.

Combined, equal-weighted, through the portfolio layer: Sharpe 0.06, realised vol 16.6% against the 15% target, maximum drawdown −53%, effective breadth 8.6 bets from 27 markets, trend contributing +0.45 and value −0.28 [training, 0 looks; randomisation ≈ 0, stitching stable; the 40-draw placebo's 95th percentile is 0.05–0.08 depending on the data vintage, so the book is indistinguishable from its placebo]. The sealed hold-out: −1.28, annual return −21%, with trend −0.70, carry +0.69, value −0.72 [2024-09 to 2026-09; opened once, on 2026-09-09, when it read −1.18 because that fetch caught the final session as a partial intraday print; re-scored on the settled close for this write-up; two-year standard error 0.71].

## What was done about it

Twenty candidate claims were written down in six lines each — claim, mechanism, data, cost ratio, minimum detectable effect, refutation — and scored on expected return, novelty and answerability. The ranking was committed to git before any test as a prediction to be scored. Then all twenty criteria were pre-registered at once: the statistic, its direction, the confound and how the design separates it, the placebo, and the effect size detectable at 80% power under a Bonferroni correction fixed at N = 20 from the start, so that a directional claim clears only at t ≥ 3.02. Tests ran in ranked order, a known effect first as a positive control, with halt rules: control fails, a candidate clears, or three consecutive failures for one reason.

## The result

The control — SPY's close-to-open return, traded through ES — cleared at 3.04 basis points a day, t = 4.13, with a sign-flipped block shuffle at t = −0.24 [2002–2026, 0 looks; machinery check passed]. The pipeline finds real effects and makes nothing from noise.

One candidate cleared the corrected threshold: crypto funding-rate carry. A weekly book long the bottom quintile of Binance perpetuals by trailing funding and short the top earns an alpha over Bitcoin of +1.02% per week, standard error 0.27, t = 3.73, placebo 95th percentile +0.40, and +0.93% per week net of a 20-basis-point round trip at 41% weekly turnover [2020-02 to 2026-08, 342 weeks; no hold-out exists; audit passed]. The audit was pre-registered because the result sat above its plausible band: five refutation clauses — price leg against funding, 2020–21 only, names vanishing mid-week, a 50-basis-point cost, beta doing the work — and none fired. The caveat is not small. The premium fell fourfold after 2021: +2.25% per week in 2020–21, +0.55% from 2022 on, and in that later period the price leg is zero (+0.08%, t 0.4) — what remains is the funding accrual itself, +0.47% per week. The post-2021 sub-sample alone, t = 2.69, would not clear at N = 20. Survivorship — only perpetuals still listed — is a limitation of unknown sign. The first run was void: the fetcher had kept only the most recent 500 funding rows per symbol, the signal was zero and the two legs were the same names. Logged, fixed, re-run with the criterion untouched.

Two candidates were refuted outright. A VIX-regime exposure cap, ranked first, moved the daily-loss breach share by −0.5 points, t = −0.32, inside its placebo band: at equal realised vol the days it removes carry no more tail than the days it keeps. Expiring-contract pressure, ranked second, returned the wrong sign, +0.05σ, t = 0.87.

## Why the futures candidates failed

The rest failed on power, not absence. Skewness premium: slope +0.18, t = 2.12, placebo cleared, long–short +0.53σ a month against 0.06σ of cost. Roll-gap carry — commodity carry recovered from the calendar spreads the splice leaks — +0.20, t = 2.48, placebo cleared, surviving a momentum control. The Treasury auction concession: +0.17σ, t = 1.72, pre-auction −0.11σ and post +0.06σ as the literature says, but two round trips cost 0.25σ. Post-EIA-report drift in energy: +0.06σ, t = 1.58, above every pseudo-release weekday [all 2002–2026, 0 looks; placebos cleared]. Every sign was the predicted one at roughly the published magnitude; every t fell between 1.6 and 2.5 against a bar of 3.02; two would have cleared without the correction. The same machinery returned 4.1 on the control and 3.7 on funding carry. At the observed slopes the futures panel would need about 2.8 times its sample to clear.

## The breadth lesson

The one clear came from 342 weeks across roughly 110 instruments, 29 names a leg. The futures panel had 13 commodities. My design estimate for the funding book's standard error was 0.74% a week; the design achieved 0.27 — wrong by nearly threefold, because a wide cross-section diversifies far more than my prior assumed, and that is why its answerability was scored 3 out of 10 and it was ranked seventh. Breadth is the sample size.

## The calibration finding

The ranking was a prediction and it can be scored. The two most novel candidates — novelty 8 and 9 of 10 — failed hardest: one refuted, one wrong-signed. Every published premium replicated in sign: trend, carry, skewness, roll-gap carry, the auction cycle, the report drift, the overnight control and funding carry. Of three candidates predicted to clear, none did; both predicted "right sign, not cleared" were right; the clear came from a candidate predicted to fail on power. Priors about novelty were the least informed part of the judgement, and ranking on them put the least-evidenced claims on top.

## The mandate result

Of 500 mandates — daily-loss limit, drawdown limit, profit target and window — 53 are attainable at any volatility target, a pass probability of at least a half [training path, 0 looks; overlapping starts, no interval claimed]. The daily loss limit binds in 68% of mandates, the drawdown limit in 28%, and the time window in 4%; the specification predicted the window would bind. On the specification's example mandate — 8% target before 10% drawdown or a 3% day, inside 60 days — the pass-maximising volatility target is 25%, while the target that maximises return over drawdown is 40%: the gap is −15 points, opposite in sign to the prediction, because a daily limit punishes volatility directly while risk-adjusted return keeps rising toward the growth-optimal level. A 60-day pass rate is set by volatility, not by Sharpe: this path, Sharpe 0.06, passes 22.3% of the time at 15% vol, against the specification's synthetic prior of 23% for a Sharpe of 0.8.

## In one line

The premia are real — every one returned its published sign at roughly its published size — but on 27 markets and 24 years none can be resolved under an honest twenty-way correction, and the one claim that cleared did so on a breadth the futures panel does not have.

## What this project determined next

The previous project asked whether an effect exists and found that it did not, for a reason that was economic rather than statistical. This project asked the opposite kind of question — whether known, published effects survive retail costs and a hard risk mandate — and got an opposite kind of answer. The effects are there. Trend, carry, skewness, roll-gap carry, auction-cycle: every one returned the published sign at roughly the published size. None reached significance under an honest correction at twenty tests.

That is a power failure, not an absence, and the project can prove the distinction rather than assert it. The same pipeline detected the positive control at t = 4.1 and crypto funding carry at t = 3.73. The futures premia returned t between 2.1 and 2.5 on the same machinery. What separates them is breadth: roughly 110 instruments against 27 markets. The answerability of the one candidate that cleared was under-scored by nearly threefold for exactly that reason, and the standard error the design actually achieved was a third of what was estimated in advance.

So the next question is not which signal to try but where the sample is large enough to establish one. Equities: roughly four thousand names against twenty-seven markets, with decades of survivorship-free history available for around ten pounds a month. Every signal that failed on power here — cross-sectional momentum, value, skewness, carry — becomes testable at proper power there, using the same machinery, the same pre-registration discipline, and the same positive control. The constraint was never the idea. It was the number of independent bets.
