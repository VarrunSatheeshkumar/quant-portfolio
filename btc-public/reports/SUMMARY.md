# Summary

## The mistake, first

The edge this project set out to find, when found, was about six basis points per
trade against a ten-basis-point round trip — arithmetic available in ten minutes on
the first afternoon, computed after eighty-two thousand variants had been generated,
screened and deflated. Cost the trade before you mine for the signal: the cost sets
the size the signal must clear.

## The finding

The liquidation map works as a locator. Inferring where leveraged positions were
opened, walking them down a leverage ladder to their forced-exit prices and
accumulating those into a decaying histogram produces levels that really do hold
forced sellers. On the days where tick-level liquidation prints exist,
every one of the 36 cluster touches coincided with real forced selling, and mapped
levels carried 5.3 times the liquidation notional of unmapped ones — $1.45m against
$274k in the twenty minutes around a touch (looks: 0; training-window sample days).
*Unmapped* means under 0.5% of map notional, emptied buckets included — 94% of the
control; excluding them gives 2.4x.

Price does not respond to those levels in any way a trader can capture. The
hypothesis was pre-registered in five framings — acceleration through a cluster
against matched empty levels, dose-response in flow-to-depth pressure, cluster age,
regime conditioning, and anticipation ahead of unpredicted liquidations — each naming
its confound, each with a placebo. Only the last was adequately powered: 53,088 touches over 61 print-covered days
give a minimum detectable effect of 6.5bps against a 10bps band, and the measured
level was −0.3bps, CI [−4.8, 4.0] (looks: 0). Adequate power and a null is a result;
the four underpowered framings are not.

The mechanism is unsurprising: the map's inputs — open interest, price, funding —
are public and watched. The flow arrives where the map says and is absorbed at the
price the book showed.

## The volatility model

The same reconstruction does forecast volatility, and how much depends on the
benchmark. Against GARCH(1,1) the margin is large: sealed-block R² of 0.457 against
0.311 and 0.554 against 0.165 at one hour, 0.464 against 0.232 and 0.540 against
−0.233 at four hours. Against HAR-RV, the benchmark the realised-volatility
literature uses, it is much smaller.

Corsi's textbook HAR, regressing forward volatility on trailing day, week and month
components, loses by 0.13 to 0.22 R² in the sealed blocks — but it was built for
daily forecasting, and at these horizons its shortest input is already a day stale,
so it is handicapped rather than tested. Shifting the cascade down one scale — hour,
day, week — gives the benchmark that matters. Model A still wins
in both sealed blocks at both horizons, but by 0.024 and 0.026 at one hour and 0.038
and 0.051 at four hours: an order of magnitude less than the GARCH comparison
suggests. And on QLIKE the intraday HAR wins three of the four sealed cells.

So the honest claim is narrower than "beats GARCH": the map features carry a few
points of R² beyond what a heterogeneous autoregression of past realised variance
knows, and nothing under a loss that punishes under-forecast variance. Each sealed-block figure rests on one look; the HAR fits use training rows
only and are scored against outcomes that same look revealed, so no counter moves.
The live forward window was never opened.

## The instrument ceiling

A forecast is worth what you can trade it through. Eight structures were costed —
straddles at two hedge frequencies, two calendar weightings, and 1/K²-weighted strips
at two tenors and two widths (looks: 0). The best resolves 41.8bps against a 10bps
band.

Economically: converting the sealed-block improvement over intraday HAR into an
expected P&L, the forecast is worth 45.7 to 67.3bps per trade on the cheapest
structure, a seven-day straddle hedged daily, against its measured round-trip cost of
20.1bps. It is the only one of the eight with a positive net
expectation; the other seven lose more to cost than the forecast can be worth. Its
MDE is 73.7bps, larger than the most generous edge, so the sample cannot tell
+25.7bps from zero. Dispersion cancels in that comparison — edge and MDE both scale
with it — so no choice of structure fixes it. 521 independent trades would: ten
years of weekly ones. Every assumption in the conversion favours the trade.

Nor is a cheaper structure the answer. Removing the instrument entirely — an
idealised variance swap, no spread, no fees, no hedging error — still gives an MDE of
81.6bps.
Nothing tradeable beats a costless perfectly-hedged variance swap, and reaching
10bps needs 67 times the sample: roughly 309 years of weekly non-overlapping trades.
Trading more often buys nothing, since overlapping trades are not independent. The binding constraint is the dispersion of the
measured quantity, and no structure reduces the variance of what it measures.

---

Every figure above is reproduced by `python run.py` and checked against
`reports/results/` by `tests/test_documents.py`.
