# Forced flow and the price of knowing where it is

## The question

Most flow in a market is optional. A trader who decides to sell can change their mind
between the decision and the order, and usually does. Forced flow is the exception:
when a leveraged position moves far enough against its holder, the exchange closes it
automatically, at a price fixed in advance by the size of the position and the margin
behind it. The decision has already been made and written down.

Bitcoin perpetual futures publish the inputs needed to reconstruct where that flow
sits. Open interest, price and funding are all public and continuous. From them it is
possible to infer roughly where leveraged positions were opened, at what leverage, and
therefore the prices at which they will be closed out — a *liquidation map*. The
question this project set out to answer is whether that map is worth anything: if you
know where the forced sellers are, do you know something about what price does when it
reaches them, or something a volatility model does not already know?

The answer is that the map is real, and it is not tradeable. That is the finding, and
the rest of this explains how it was established and what it cost to learn.

## What was built

Everything rests on an **as-of grid**: a five-minute panel spanning 2020 to 2026 in
which a value may appear at time *t* only if it was publicly knowable at *t*. Every
source carries the moment it became knowable, which is not the moment it describes.
Joins are as-of with an explicit tolerance, so a feed that stops updating produces a
gap rather than a flat line, and every joined column has a companion column recording
how stale it is. An automated test rebuilds sampled grid values from the raw sources
by an independent path and refuses the grid if any disagree.

On top of that sits the **liquidation map**. Each bar, the change in open interest and
the sign of the price move imply a cohort of new positions; those are spread across a
leverage ladder, converted to their forced-exit prices, and accumulated into a
histogram of expected forced flow per price bucket, which decays with a seven-day
half-life. The leverage weights are not assumed. They are calibrated against real
tick-level liquidation prints, on a log scale — fitting raw notional collapses the
whole weight onto one rung, because a handful of cascade bars carry the entire squared
error and the fit reduces to "which rung best flags that something big happened".

Two models sit on the map, kept apart by construction: a **volatility model** and a
**direction model**, never allowed to share features, so that a failure in one cannot
be laundered into the other. Around them: a variant-mining pipeline with a
multiple-testing correction, and audit machinery — as-of tests, purge-and-embargo
walk-forward, block bootstraps, label-shuffle placebos, a randomisation test, and a
minimum-detectable-effect calculator run *before* any criterion was committed. Two
sealed hold-out blocks and a live forward window were held out throughout, and each
sealed number below carries the number of times its block was opened.

## The mistake

The edge, when it was finally found, was about six basis points per trade against a
ten-basis-point round trip. That arithmetic needed ten minutes and the fee schedule,
and was computed after 82,152 feature variants had been generated, screened and
deflated.

Nothing that follows is worth reading past that. Cost the trade before you mine for
the signal: the cost sets the size the signal has to clear, and it is a fixed,
knowable number available on day one.

## The finding

The map works as a locator. On the sample days where tick-level liquidation prints
exist, **every one of the 36 cluster touches coincided with real forced selling**, and
mapped price levels carried **5.3 times the liquidation notional** of unmapped ones —
$1.45m against $274k in the twenty minutes around a touch (looks: 0; measured on
sample days inside the training window). *Unmapped* means a level holding under 0.5%
of the map's notional, emptied buckets included — 94% of the control group. Excluding
them gives 2.4x.

Price does not respond to those levels in any way a trader can capture. The hypothesis
was pre-registered in five framings: acceleration through a cluster against matched
empty levels, dose-response in flow-to-depth pressure, cluster age, regime
conditioning, and anticipation ahead of unpredicted liquidations. Each named in
advance the confound it had to separate, and each was paired with a label-shuffle
placebo.

Four were underpowered, which is a fact about the design and not a result. The fifth
was adequately powered: 53,088 touches across 61 print-covered days give a minimum
detectable effect of **6.5bps against a 10bps band**, and the measured level was
**−0.3bps, 95% CI [−4.8, 4.0]** (looks: 0). Its matched difference cleared its placebo
comfortably — real −7.1bps against a shuffled 95th percentile of 1.1bps — so the
machinery was detecting the *structure* it was supposed to. The randomisation test on
the level itself could not distinguish the measured value from shuffled labels, which
is what a real null looks like. Adequate power and a null is a finding.

The mechanism is unsurprising once stated. Every input to the map — open interest,
price, funding — is public and watched. Anyone who wants to know where the
liquidations sit already knows. The flow arrives exactly where the map says it will
and is absorbed at the price the order book was already showing.

## The volatility model

The same reconstruction does forecast volatility, and how much depends entirely on
what it is measured against.

Against GARCH(1,1) the margin looks decisive: sealed-block R² of 0.457 against 0.311
and 0.554 against 0.165 at one hour, 0.464 against 0.232 and 0.540 against −0.233 at
four hours (looks: 1 for each sealed block, taken once).

GARCH is the textbook baseline, though, not the one the realised-volatility literature
uses. That is HAR-RV, which reads realised variance directly instead of inferring it
from squared returns one step at a time. Corsi's standard day/week/month cascade loses
by 0.13 to 0.22 R² in the sealed blocks — but it was built for daily forecasting, and
at a one-hour horizon its shortest input is already a full day stale, which handicaps
it rather than tests it. Shifting the same cascade one scale down, to hour/day/week,
gives the benchmark that matters.

Against that benchmark Model A still wins in both sealed blocks at both horizons, but
by **+0.024 and +0.026 at one hour and +0.038 and +0.051 at four** — roughly a tenth
of what the GARCH comparison advertises. And on QLIKE, which punishes under-forecast
variance, the intraday HAR **beats Model A in three of the four sealed cells**. No
hold-out counter moved to establish this: HAR was fitted on training rows only and
scored against outcomes the single existing look had already revealed.

Converted to money, the improvement is worth **45.7 to 67.3bps per trade** on the
cheapest costed structure — a weekly straddle hedged daily — against that structure's
**measured round trip of 20.1bps** (looks: 0). Every assumption in that conversion
favours the trade. Even so, the structure's own minimum detectable effect is 73.7bps,
larger than the most generous estimate of its edge, so the sample cannot distinguish
+25.7bps of net expectation from zero.

## The instrument ceiling

Eight structures were costed against the forecast: straddles at two hedging
frequencies, two calendar weightings, and 1/K²-weighted option strips at two tenors
and two grid widths (looks: 0, all costed inside the training window). The best of them
resolves 41.8bps against a 10bps band.

The decisive measurement contained no instrument at all. An **idealised variance swap
— zero spread, zero fees, zero hedging error** — still has a minimum detectable effect
of **81.6bps**. Nothing tradeable can beat a costless, perfectly-hedged variance swap,
so that is a floor, and reaching 10bps from it needs 67 times the sample: roughly
**309 years** of non-overlapping weekly trades. Trading more often buys nothing,
because overlapping trades are not independent observations.

The binding constraint was therefore never the instrument and never really the sample.
It is the dispersion of the quantity being measured. Realised variance over a week
varies too much from week to week for a few hundred observations to pin its mean to
trading precision, and no structure reduces the variance of the thing it is measuring.
The same cancellation makes the point sharply: expected edge and minimum detectable
effect both scale with dispersion, so the ratio is independent of the structure
entirely. Only independent trades move it — 521 of them, about ten years of weekly
ones.

## What the audit caught

The audit machinery was not decoration. Five things it caught, none of which would
have announced itself:

**A sign inversion.** The direction model's downside-loss feature was assigned the
up-move magnitude, inverting exactly the asymmetry the system was meant to trade.
Training Sharpe went from −0.108 to positive the moment it was fixed — a bug that
made results look *worse*, which is the kind nobody goes looking for.

**A stale price forward-filled across a month.** Binance publishes monthly archives
weeks late. An unbounded as-of join carried a July price across the whole of August,
inside a sealed window. Bounded tolerances and a daily-file backfill fixed it; without
the staleness columns it would have looked like a quiet month.

**Infinity poisoning.** One zero-variance window produced an infinity that propagated
through an exponentially-weighted mean and truncated a 700,000-row variant panel to
648 rows, yielding a spurious information coefficient of 0.52 that tripped the leakage
gate. The gate is what caught it.

**A walk-forward mask.** Training and prediction shared one mask, so sealed months
never appeared as test rows and the hold-out came back empty rather than failing. It
was disclosed in full, including what the invalid first open had shown and the
statement that no decision was changed in response.

**A result that looked like signal and was a clock.** A news feature appeared to
improve the volatility model. A pre-committed staleness clause put the entire gain in
the six hours after each daily value published and zero elsewhere, and the placebo
named the cause: the feature's companion staleness column is "hours since midnight"
under another name. The model improved because a time-of-day variable had been added
to it.

## In one line

The map is real, the flow arrives where it predicts, the information is already in the
price, and the one component that does generalise is worth less than the cheapest
instrument that could express it.

## What this project determined next

This project asked whether an effect exists. The answer was no, and the mechanism is
known: the liquidation map is computable from public data, so the flow is anticipated
and the impact is arbitraged away before it arrives. But the project did not end on
that finding. It ended on arithmetic. Six basis points of edge against a
ten-basis-point round trip made the strategy impossible before any signal was found.

That distinction set the next question. If the method was sound and the economics were
not, the next project should hold the method fixed and change the cost structure.
Futures cost roughly one to two basis points a round trip against daily moves of fifty
to a hundred — the same ratio inverted. The question type should change too: not "does
this effect exist", which has a low prior and produced only refutations, but "do
known, well-documented effects survive my costs and my constraints", which has a high
prior and a usable answer either way.

The reusable output is the machinery, not the finding: as-of discipline, minimum
detectable effect computed before any criterion is committed, placebo on every result,
randomisation on the pipeline itself, and sealed hold-outs opened once. Five standing
rules, each bought with a specific failure. All of it carried forward unchanged.
