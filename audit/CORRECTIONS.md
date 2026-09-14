# Corrections to previously published figures and sentences

This record preserves the full correction lists formerly in the two write-ups. The lists distinguish withdrawal from replacement or qualification; their count conventions below refer only to explicitly withdrawn assertions. The highlighted examples in the write-ups are editorial selections.

<a id="btc-p7"></a>

## BTC (P7)

References such as "above" in the preserved list below refer to the [BTC write-up](../btc-public/WRITEUP.md).

The count is **14 explicitly withdrawn assertions across 12 bullets** in the original correction section below. Each separately quoted assertion followed by “withdrawn” counts once: the bullet beginning “Four were underpowered” contains three assertions. Statements described only as corrected, replaced, qualified or newly reported are excluded. This is a count of explicit withdrawals in this correction section, not a count of all corrections or all withdrawals elsewhere in the write-up.

The three examples retained in the write-up are an editorial choice, not a ranking established by the audit.

### Corrections to previously published figures and sentences

The [claim ledger](../audit/CLAIM_LEDGER.md) records the sources and permitted interpretations behind these corrections. Its scope and private-source limitations are described in the [audit guide](../audit/README.md); it is not an exhaustive certification. The historical registration and inspection evidence is in the [evidence record](../audit/EVIDENCE_RECORD.md).

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


## Futures (P8)

References such as "above" in the preserved list below refer to the [futures write-up](../futures-public/WRITEUP.md).

<a id="futures-p8"></a>

Withdrawal-count convention: the list below explicitly marks 10 quoted assertions as withdrawn, across nine bullets. The paired design-SE and breadth assertions count separately; replacements and qualifications are not counted as withdrawals. The three examples highlighted in the write-up are an editorial selection.

### Corrections to previously published figures and sentences

The [claim ledger](../audit/CLAIM_LEDGER.md) records the sources and permitted interpretations behind these corrections. Its scope and private-source limitations are described in the [audit guide](../audit/README.md); it is not an exhaustive certification. The historical registration and inspection evidence is in the [evidence record](../audit/EVIDENCE_RECORD.md).

- "timing +0.44 against a standing tilt of −0.22" attributed to trend: those are the combined book's figures; trend's own are 0.22 and 0.13, one draw, the code's labels.
- "Trend alone had life": withdrawn.
- "Carry was unmeasurable" and "value is refuted": replaced by the estimates with the design's mean-return MDE in Sharpe units; no Sharpe intervals exist.
- "the vol layer levers the residual to about twice, and the doubled costs eat what trend made": only the median scale factor 2.01 survives.
- "effective breadth 8.6 bets": diversification ratio squared.
- "trend contributing +0.45 and value −0.28": leave-one-signal-out Sharpe differences.
- "indistinguishable from its placebo" (WRITEUP) and "placebo cleared" (RESULTS): replaced by the operational statement of each vintage against its implemented 40-draw threshold.
- "two-year standard error 0.71": the consistency check's training-based calculation; no hold-out interval exists.
- "opened once" and "produced the same number": two scorings, −1.18 and −1.28.
- "The ranking was committed to git before any test": qualified as commit order in a private repository.
- "halt rules: control fails, a candidate clears, or three consecutive failures for one reason": four conditions were registered; the first-person record above replaces the passive account, and C18 and C15 carry the labels stated there.
- "The pipeline finds real effects and makes nothing from noise": withdrawn.
- "+0.93 % per week net of a 20-basis-point round trip at 41 % weekly turnover": withdrawn; the cost basis is stated instead.
- "what remains is the funding accrual itself": the funding leg is future funding received on a book selected by trailing funding.
- "The audit was pre-registered": the five clauses are post hoc.
- "the price leg is zero": estimate +0.08, SE 0.20.
- "29 names a leg": up to 29, mean 22.
- "My design estimate for the funding book's standard error was 0.74 % a week … wrong by nearly threefold" and "Breadth is the sample size": withdrawn; the 0.74 figure in the private candidate list is labelled as an unadjusted MDE, not a standard error.
- "Every published premium replicated in sign … at roughly its published size": withdrawn; value and C2 have the opposite sign, and no reference magnitudes exist.
- "both predicted 'right sign, not cleared' were right": three of four.
- "two would have cleared without the correction": stated as an explicitly unadjusted diagnostic.
- "the daily loss limit binds in 68 % of mandates": replaced by the classification definition.
- "the gap is −15 points": restricted to the tested grid with its endpoint maximum.
- "A 60-day pass rate is set by volatility, not by Sharpe": withdrawn.
- "That is a power failure, not an absence, and the project can prove the distinction": withdrawn.
- "Every signal that failed on power here … becomes testable at proper power there": withdrawn.
- "Twelve pre-registered versions said no": withdrawn.
- "computed before any return was read": the return panel was read to compute dollar volatility.
- "verified against NYMEX settlements": inferred from price matching, for the four energy contracts.
- "a 35 % sector cap": realised maxima exceed 35 %.
- "the whole study re-run under five roll treatments": the sensitivity recomputes the specified Sharpes.
