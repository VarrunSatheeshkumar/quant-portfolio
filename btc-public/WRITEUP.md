# Forced flow in BTC perpetuals: the measurements

The claim ledger ([`audit/CLAIM_LEDGER.md`](../audit/CLAIM_LEDGER.md)) records the 2026-09-12 audit and the presentation provenance added on 2026-09-13. Where the ledger records a figure as unknown, this document says unknown.

## What was asked

Five framings of "does price respond to the liquidation map?" were tested, each with a hypothesis recorded privately before its result commit; the public statistics for framing 1 are not the registered statistic. The registered v2 statistic was a ratio of mean signed continuations after cluster touches to the same after matched empty touches; neither absolute-move regression reported below is the registered statistic.

For the volatility comparison against HAR-RV (private v13), hypothesis, code and result were committed together; commit order is silent on sequence. For v2 through v12, a commit recording the hypothesis precedes the commit recording the result (author-dated, local, unpushed). Nothing may be said about when the v13 criterion was written.

## What was built

An automated test checks, at 20 sampled timestamps, that grid values match the raw files under the raw files' own as-of timestamps and tolerances, and that forward targets are null at the series tail. The window after 2026-09-01 contains no data and has not been scored.

The liquidation map accumulates inferred forced-exit prices into a histogram with a 3.5-day half-life. The leverage mix is calibrated once on training print days (log-scale correlation 0.30) and applied to all periods, including the 2022 sealed block.

The ridge model is refitted monthly on a trailing year; its GARCH and map-feature inputs are fitted once on all training rows (2020-09 to 2025-08) and supplied to every month, including the 2022 sealed block. It is a 24-feature ridge model including map-derived features, DVOL, GARCH, funding, premium index, OI ratio and time-of-day. The HAR-RV benchmark uses three trailing realised-volatility features; Corsi's shortest component is a trailing one-day average ending at the current bar.

Option entry prices are amount-weighted averages of buy-flagged and sell-flagged fills over the four-hour entry window, with missing sides imputed from the other leg's half-spread. Eight structures were costed; the smallest stored MDE is 41.8 bps, computed as 2.80 × SD(long − short)/√(2n) on weekly entries treated as independent.

52 selected literal phrases in this document and the README are checked for presence against `reports/results/` by `tests/test_documents.py`, without validating their interpretation. Default `run.py` runs skip stages whose artefacts exist; `--only` and `--force-from` recompute them.

## What the measurements are

### The locator

In the touch bar and the next three five-minute bars, on print-covered days, a liquidation print somewhere in the market occurred for 100 % of cluster touches (n 36), 99.9 % of mid touches (n 908) and 92.4 % of empty touches (n 5,164).

Mean market-wide liquidation notional in the touch bar and the next three five-minute bars: cluster $1.45m (n 36), mid $1.54m (n 908), empty $0.27m (n 5,164); 94 % of empty touches are zero-mass buckets; cluster/empty = 5.3, cluster/non-zero-mass empty = 2.4. Computed on all 73 OI-covered print days, of which 26 fall inside the sealed blocks including their ±3-day purge.

**Disposition.**
- Question: whether liquidation prints occur at mapped levels more than at unmapped ones.
- Established: in the touch bar and the next three five-minute bars, a print occurred somewhere in the market after 100 % of cluster touches, 99.9 % of mid touches and 92.4 % of empty touches; mean notional cluster $1.45m, mid $1.54m, empty $0.27m; computed on all 73 OI-covered print days, 26 of them inside the sealed blocks including their ±3-day purge.
- Unresolved: whether prints at the touched level and side exceed those at matched unmapped levels — the statistic does not condition on the touched level or its side.
- Decision: stopped. The "100 %" and "5.3×" headline is withdrawn and the bucket figures are kept as descriptions; no level-specific statistic was built, because the existing statistic does not condition on the touched level, a print follows 92.4 % of empty touches, and the sample includes sealed-block days.

### One touch, from map state to measurement

Take the first print-covered cluster touch produced by the cached grid and stored leverage mix: **2020-09-01 06:00 UTC**. This illustrates row construction using the calibration described above. Grid timestamps label bar ends: the 06:00 touch bar is the exchange candle opened at 05:55, and its liquidation total covers 05:55:00–05:59:59 UTC.

1. **Find the bucket and direction.** Buckets use `floor(log(price / 1000) / log(1.0025))`. The previous close, $11,759.39, is in bucket 987; this bar's high, $11,810.93, reaches bucket 988, whose lower edge is $11,786.06. The collector records an upward touch (`is_down = False`). The edge is 0.2268% from the previous close, inside the 5% distance limit; this bucket has no earlier accepted touch.
2. **Classify the pre-touch state.** Before applying the touch bar, bucket 988 contains $995,398.09 of map mass against $17,341,431.20 across both maps: `995398.09 / 17341431.20 = 5.7400%`. This exceeds the 5% cluster threshold. These are modelled masses; the label does not identify an observed liquidation at that level.
3. **Measure the outcome.** The market-wide liquidation totals at 06:00, 06:05, 06:10 and 06:15 are $300,841.56839, $320,055.80572, $0 and $0: $620,897.37411 altogether. Separately, the touch-bar close is $11,805.78 and the 07:00 close is $11,869.83, giving signed 60-minute continuation `10000 × log(11869.83 / 11805.78) = +54.11 bps`; upward touches use sign +1.
4. **Locate its contribution.** This supplies one of the 36 cluster windows, one positive liquidation indicator, and $620,897.37 to the sum used for their mean market-wide notional. Its continuation belongs to the bucket-touch stream; it is not an observation in the unpredicted-print continuation table below. Prints in the touch bar are not ordered relative to the crossing within that bar.

Construction: [`collect` and `_outcomes`](src/event_study.py), [`run_map` and `bucket_of`](src/liquidation_map.py); inputs in `data/grid/grid.parquet` and `data/interim/leverage_mix.json`. The [example inputs](../audit/WORKED_EXAMPLES.json) are preserved without requiring those data files. Ledger H1 records this instance; A20–A21 constrain the locator interpretation and B17 describes the calibration.

### Price after liquidation prints

53,088 prints on 61 day-blocks (47 first-of-month training days); day-block bootstrap MDE 6.5 bps. The three stored continuation estimates are:

| Horizon | Continuation (bps) | 95% interval (bps) | What the estimate is conditioned on |
| --- | ---: | --- | --- |
| 15 min | −0.9 | [−3.5, 1.7] | Unpredicted prints in the training sample; print unit; day-block bootstrap. |
| 30 min | −0.3 | [−4.8, 4.0] | Unpredicted prints in the training sample; print unit; day-block bootstrap. |
| 60 min | +3.8 | [−1.5, 10.3] | Unpredicted prints in the training sample; print unit; day-block bootstrap. |

The 30-minute interval [−4.8, 4.0] lies inside ±10 bps; the design's MDE is 6.5 bps. These are the stored intervals in ledger B4–B5 and B8, with the observation-unit and day-block limitations below.

The matched difference is −7.1 bps; under independent per-print relabelling (min cell 3; 300 draws) the 95th percentile of absolute deviations from the placebo mean is 1.1 bps; the real difference uses min cell 15.

**Disposition.**
- Question: whether price continues after liquidation prints the map did not predict.
- Established: the three intervals above at the print unit; the 30-minute interval lies inside ±10 bps with a design MDE of 6.5 bps; the matched difference −7.1 bps under the placebo procedure described.
- Unresolved: the observation unit (53,088 prints share bars and days on 61 day-blocks, and the origin of the 14 blocks beyond the 47 first-of-month days was not verified); the placebo's null (independent per-print relabelling, min cell 3 against 15 for the real difference); why price does not respond — anticipation was tested privately through two implications and both were inconclusive.
- Decision: preserved as unresolved. The three intervals stand as the measurement at the print unit; the randomisation sentence and the mechanism sentence are withdrawn. Resolution would require recomputing the interval with prints sharing a bar counted once, on the same day blocks; that has not been done.

### The other four framings

Framing 1 = matched difference without an interval plus an absolute-move slope with one; framing 2 = null with an interval, MDE above the registered band; framing 3 = raw effect with an interval, controlled effect without one; framing 4 = point differences without intervals.

Framing 1's matched difference (+8.7 bps over 11 cells) has no interval; its absolute-move slope has an interval [197, 446] and MDE 172. The public within-cell regression of absolute 60-minute move (bps) on map share has slope +332 [197, 446]; the private v2 regression of absolute move (decimal) on log share had slope −0.00053 [−0.00065, −0.00004]. The specifications differ and do not support a common directional conclusion.

Framing 2: slope −0.09 [−0.63, 0.42], MDE 0.75 bps per unit log-pressure, n 4,036 on 70 book days.

Framing 3: raw slope −11.6 [−17.7, −6.4] bps per unit log-age, MDE 8.0, n 28,220 on 1,373 days; the momentum-controlled slope is −2.8 with no interval. The momentum control is not in the v3 registration and is present in the completed analysis; the docstring gives its rationale.

Framing 4's differences (weekend −1.4 bps over 178 cells; Asia +1.2 bps over 45 cells) have no intervals.

**Disposition.**
- Question: whether the response appears through a cluster relative to matched empty levels (1), when flow is scaled by the depth waiting for it (2), by cluster age (3), or when liquidity providers are thin (4).
- Established: the per-framing statement above — 1 = matched difference without an interval plus an absolute-move slope with one; 2 = null with an interval; 3 = raw effect with an interval, controlled effect without one; 4 = point differences without intervals.
- Unresolved: framing 1's direction (the two stored regressions differ in specification and the registered v2 statistic is not among them); framing 3's controlled slope has no interval and the control is not in the v3 registration.
- Decision: framings 1, 2 and 4 stopped — nothing further was computed: the registered v2 statistic was a ratio that is not among the stored statistics, framing 2's interval includes zero on 70 book days, and framing 4 has no intervals. Framing 3 preserved as unresolved; resolution would require an interval for the momentum-controlled contrast, which has not been computed.

### The volatility forecast

R² in the sealed blocks: 0.457 against 0.311 and 0.554 against 0.165 at one hour, 0.464 against 0.232 and 0.540 against −0.233 at four hours, Model A against GARCH(1,1); the GARCH parameters coincide with arch's starting-value grid and convergence status is not preserved in the reported output; on QLIKE GARCH is better in three of four sealed cells.

Corsi's day/week/month HAR loses by 0.13 to 0.22 R² in the sealed blocks. Point R² differences over the hour/day/week HAR of +0.024/+0.026/+0.038/+0.051 on 87,552 and 87,264 evaluated rows per block (304 and 303 complete-day equivalents out of 365); no uncertainty was computed. On QLIKE the intraday HAR beats Model A in three of the four sealed cells. By arithmetic from the minimum-training-rows rule, the last two months of each block have no forecasts.

**Disposition.**
- Question: whether Model A forecasts realised volatility better than GARCH(1,1) and HAR-RV, and whether the map-derived features carry the difference.
- Established: the R² and QLIKE values above; point differences over the hour/day/week HAR of +0.024/+0.026/+0.038/+0.051 with no uncertainty computed; the intraday HAR better on QLIKE in three of four sealed cells; two of Model A's inputs fitted once on all training rows and supplied to every month.
- Unresolved: whether the differences over HAR are distinguishable from zero (no uncertainty computed); which features carry them (not tested); whether the GARCH optimiser converged (not preserved in the output).
- Decision: preserved as unresolved. The point differences stand; "the map features carry a few points of R²" is withdrawn. Resolution would require an interval for the paired loss differences and a comparison without the map-derived features on the same evaluation rows; neither has been computed.

### The option structures

On the 2021-onward subsample (190 weekly strips) the stored idealised MDE is 81.6 bps (137.3 on the full sample); (81.6/10)² = 67; 67 × 4.6 years = 309. Cost of 20.1 bps for the daily-hedged straddle comprises fees and hedge fees; the option bid-ask spread is not included. The stored MDE for the daily-hedged straddle is 73.7 bps; the stored edge range is 45.7–67.3 bps. That range is the output of the formula √ΔR² × √(2/π) × stored dispersion, under the assumptions that the correlation equals the square root of the incremental R² measured on 1h/4h log volatility, that it applies unchanged to a 7-day variance payoff and to hedging noise, and that the stored dispersion convention is the intended one. 521 independent trades, about ten years of weekly ones, is arithmetic under the same formula and independence.

**Disposition.**
- Question: whether any option structure could express the forecast at the 10 bps band, and what the measured difference over HAR would be worth per trade.
- Established: eight stored MDEs, the smallest 41.8 bps; the idealised MDE 81.6 bps on the 2021-onward subsample and 137.3 bps on the full sample; a cost of 20.1 bps that excludes the bid-ask spread; the formula outputs above under their listed assumptions; entry prices that are four-hour transaction-side averages with imputed sides.
- Unresolved: which per-trade dispersion convention was intended; how the option-fill file was acquired; whether the same correlation applies to every structure (assumed, unsupported).
- Decision: stopped. The economic conclusions are withdrawn and no repair was undertaken, because each input to them is unresolved — the dispersion convention, the cost basis and the file's provenance — and the formula's assumptions have no support in the artefacts.

## Relevance to a research or trading role

The relevant work here is constructing event rows from timestamped market data, comparing volatility forecasts with explicit benchmarks, and reporting intervals alongside their observation unit and assumptions. I would present this as research machinery and inference practice, with the limitations above; it is not evidence of live trading, execution or inventory management.

## What could not be established

Whether within-cell absolute movement rises or falls with map share: unknown. Whether the GARCH optimiser converged: unknown. Which per-trade dispersion convention was intended (one side of the trade, or the paired difference): unknown. Whether the difference over HAR-RV is attributable to the map-derived features rather than to DVOL, GARCH, funding, premium index, OI ratio, liquidation counts or time-of-day: not tested. No uncertainty was computed for the differences over HAR-RV. The option-fill file in the archive was not produced by the fetch code as written; its acquisition schedule is unknown. The origin of the 14 day-blocks beyond the 47 first-of-month training days was not verified.

Anticipation of forced flow was tested privately through two implications; both were inconclusive. The six-basis-point edge against a ten-basis-point round trip, and the 82,152 variants, are the author's account from the private v1 record and are not reproducible here. Five audit episodes are documented in the private decision log; the consequences attributed to each are the author's retrospective account.

## What the audit found

### Registration

The public repository re-implements four analyses of a private project; its figures differ from the private figures. For v2 through v12, a commit recording the hypothesis precedes the commit recording the result (author-dated, local, unpushed). For v13, hypothesis, code and result were committed together; commit order is silent on sequence.

### Sealed-block scoring history

HAR was fitted on training rows and scored on the sealed outcomes; the repository has no look counter; the sealed blocks have been scored repeatedly: 2026-09-02 (twice, the first with a single-mask defect disclosed privately), 2026-09-06, 2026-09-07, and 2026-09-12 (twice). The "looks" values in `reports/results/` are literals written by the code. The locator statistics were computed on all 73 OI-covered print days, 26 of which fall inside the sealed blocks including their ±3-day purge.

### Corrections to previously published figures and sentences

Each correction below is a row of the [claim ledger](../audit/CLAIM_LEDGER.md): every numerical and interpretive claim in these two projects, traced to the artefact that produces it, with the wording each source permits. Claims the sources did not support were withdrawn rather than softened. The registration artefacts, the halt-rule record and the inspection history behind the rows are in the [evidence record](../audit/EVIDENCE_RECORD.md).

- "seven-day half-life" → 3.5-day half-life (the configured value).
- "(looks: 0; measured on sample days inside the training window)" on the locator result: withdrawn; the sample includes sealed-block days.
- "every one of the 36 cluster touches coincided with real forced selling": replaced by the base-rate statement above (92.4 % of empty touches also had a print).
- "5.3× the liquidation notional of unmapped ones": replaced by the three-bucket statement; mid-share levels carry a higher mean than clusters, and 94 % of the control are zero-mass buckets.
- "53,088 touches": prints, not touches.
- The 30-minute result quoted alone: all three registered horizons are now reported.
- "cleared its placebo comfortably": withdrawn; the placebo procedure is described instead.
- "The randomisation test on the level itself could not distinguish the measured value from shuffled labels": withdrawn.
- "Four were underpowered" and "each was paired with a label-shuffle placebo" and "each named in advance the confound": withdrawn.
- "comfortably against a GARCH(1,1) baseline": withdrawn; the QLIKE comparison against GARCH is now stated.
- "Model A still wins": point differences with no uncertainty.
- "No hold-out counter moved … the single existing look": withdrawn.
- "Each sealed-block number carries the number of times that block was looked at": withdrawn.
- "the map features carry a few points of R²": withdrawn; no ablation exists.
- "worth 45.7 to 67.3 bps per trade", "measured round trip", "every assumption favours the trade": replaced by the formula-output statement with its assumptions; the bid-ask spread is not in the cost.
- "no structure reduces the variance of the thing it is measuring": withdrawn.
- 81.6 bps identified as the 2021-onward subsample; the full-sample figure (137.3) is now stated.
- "at a one-hour horizon its shortest input is already a full day stale": withdrawn.
- "walk-forward monthly on a trailing year": qualified; two inputs are fitted once on all training rows.
- "reproduces four results": re-implements; the figures differ from the private ones.
- "so the prose cannot drift from the run": withdrawn; the test checks selected literal phrases.
- "a value may appear at time t only if it was publicly knowable at t": withdrawn as a description of what the test establishes.
