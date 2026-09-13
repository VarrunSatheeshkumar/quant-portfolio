# Evidence record for the audit of btc-public and futures-public

This is the evidence record behind [`CLAIM_LEDGER.md`](CLAIM_LEDGER.md): the archive taken before anything was recomputed, the registration artefacts recovered from the author's private repositories, the halt-rule record, the inspection history of every sealed block, and the provenance of each published number. It cites private artefacts by file name and commit hash; those repositories and the archive are not published, so citations to them cannot be followed by a reader. What a reader can check is everything cited to `btc-public/` or `futures-public/`.

Written 2026-09-12 as "Stage 0" of a staged remediation plan; corrected the same day. The stage numbers that appear below (2.x, 3.x) refer to that plan's later stages, none of which has been run.


Supersedes the first version of this record. Corrections: the halt-rule finding (0.3), the commit-order and mtime language (0.2, 0.3), the per-version pre-commitment claim for btc-project (0.2, 0.3), the scope of "inspected" (0.4), and the future-window boundaries (0.4). Nothing in either public repository was modified. Evidence classes: (a) direct measurement, (b) estimate conditional on assumptions, (c) documentary evidence, (d) user decision.

## 0.1 Archive — class (c)

| item | value |
|---|---|
| archive path | a read-only directory outside the working tree (not published) |
| working-tree commit | `69899dc145dac61767fda51b2053516269af7bb2`, 2026-09-12 11:45:09 +0100 |
| archived at | 2026-09-12T12:08:10Z (public tree), 2026-09-12T12:14Z (private artefacts added) |
| contents | `btc-public/` and `futures-public/` including `data/` (raw, grid, interim) and `reports/`; top-level README; the three run logs from the verification pass; archived (private) (38 files from the private projects, listed in 0.2; not published) |
| size | 424 MB public + 580 KB private artefacts |
| integrity | `SHA256SUMS.txt`, 538 + 38 entries; `chmod -R a-w` applied |
| note | the archived tracked state equals commit `69899dc`. The verification-pass reruns produced byte-identical `reports/results/*.json` and candidate reports; the two run-state files they touched (`progress.json`, `LOG.md`) were restored before archiving. |

The private projects (the private btc-project repository, 1.6 GB, 74 commits; the private futures-project repository, 97 MB, 31 commits; the private btc-export directory; the author's local btc-public copy; the author's local futures-public copy) were left in place, unmodified. Only their registration and decision artefacts were copied.

## 0.2 Recovered registration artefacts — class (c)

All from local git repositories with no remote, no signed tags and no external timestamp anchor. Commit dates are author-set. Commit order establishes the order in which files were *recorded*, not the order in which code was *executed*. File modification times are observations about the filesystem at the time of inspection and are reported as such.

### futures-project (private repository, branch `main`, 31 commits, 2026-09-09 12:17 to 2026-09-11 17:43)

| artefact | first committed | later edits | archived as |
|---|---|---|---|
| `SPEC.md` / `SPEC_FUTURES.md` | not in a commit before the run; mtime 2026-09-09 11:24 (observation) | none | archived (private) |
| `DECISIONS.md` (28 dated entries) | 2026-09-09 | through 2026-09-11 17:43 | same dir |
| `FAILURES.md` | 2026-09-09 | none | same dir |
| `reports/CANDIDATES.md` — 20 candidates with E/N/A scores, ranking, predictions | `429601d` 2026-09-09 13:22:27 | `7145117` 2026-09-10 10:26:31 (what the ranking ranks; C14 as control; C5 suspicion rule; splice-check gate; the text says "added on review, before any test") | same dir |
| `reports/candidates/PREREG.md` — per-candidate statistic, threshold, placebo, refutation clause, halt rules; `prereg_design.json`; test code (`common.py`, `run.py`, `prereg.py`, `write_prereg.py`) | `bb9f1b9` 2026-09-10 10:40:23 | `5b2801a` 2026-09-11 17:40:41 — C18 design line only (SE 0.033→0.272, clearing alpha 0.099→0.822 %/wk, turnover 0.033→0.415, cost 0.007→0.083) after the void first run | archived (private): the current file and the version as committed in `bb9f1b9` |
| `reports/candidates/LOG.md` — 10 timestamped entries incl. the C18 void run | `ed9498a` 2026-09-10 10:40:40 | appended through 2026-09-11 17:42 | same dir |
| `reports/candidates/PHASE4_REPORT.md` | `ed42f14` 2026-09-10 10:43:38 (title: "halted after C11") | `b7cd128` 2026-09-11 17:43:37 (title: "complete: nine tests, one cleared") | both versions archived |
| `reports/holdout_looks.json` (private) | `78a2e67` 2026-09-09 12:45:16 | — | same dir |
| stage commits s0–s9 | 2026-09-09 12:17–12:45, two chains | — | the archived commit log (private) |

### btc-project (private repository, branches `v2-map-test` … `v13-har-baseline`, tags `v1`…`v13`, 74 commits, 2026-09-02 08:58 to 2026-09-07 19:33)

| artefact | what it establishes | archived as |
|---|---|---|
| `VERSIONS.md` (112 KB) | one entry per version with hypothesis, statistic, expected band and refutation clause; hold-out ledger at the top | archived (private) |
| `DECISIONS.md` (102 KB) | dated decisions incl. the sealed-block disclosure (2026-09-02) and the "no look counter incremented for HAR" decision (2026-09-07) | same dir |
| `SPEC.md` | founding specification, GARCH named as baseline | same dir |
| `reports/sealed_opened.json` | both sealed blocks opened `2026-09-02T07:58:57Z` | same dir |
| private btc-export `README.md`, `FAILURES.md` | reusable library and the narrative of the five framings | archived (private) |

**Per-version commit structure (version-specific, not blanket).** For v2 through v12 the commit log shows a commit whose message records the hypothesis and criteria *before* a separate commit recording the result (v2: `a92f5e5` 10:06:20 → `1241700` 10:21:30; v3: `d01ab16` 10:31:48 → `8f943a1` 10:52:08; v4: `a8e363a` → `fe845ba`; v5: `6633ef9` → `6d66d4f`; v6: `1836ae1` → `66e13ae`; v7: `0cab80e` → `dca1346`; v8-prep: `5147562` → `c7ea11c`; v9: `21a7a31` → `b6c1485`; v10: `50f7632` → `ae9d7a7`; v11: `c33205e` → `fecdafd`; v12: `dce7f8d` → `96d2d03`). **For v13 there is one commit** (`4c8adf8`, 2026-09-07 19:33:53) containing the VERSIONS entry, `stages/v13_har_baseline.py`, `reports/v13/`, `tests/test_documents.py` and the DECISIONS entries together. The v13 criterion ("supported if Model A's R² exceeds both HAR specifications in every cell") therefore has no commit-order evidence of having been written before the result. This does not establish that it was written after the result; it establishes that the commit log cannot say either way for v13.

The public `btc-public` is a re-implementation of v1, v2/v3/v10 (event study), v5/v6/v8-prep (instruments) and v13 (HAR, economics). Its numbers differ from the private versions' (0.5), so the public repository does not carry the private registration and its figures are not the registered runs' figures.

## 0.3 The two matters of record — class (c)

### The halt rule

**Rules as registered** (`PREREG.md` line 109, commit `bb9f1b9` 2026-09-10 10:40:23): "control fails → halt and diagnose; **a candidate clears → halt and report**; **three consecutive failures for the same reason → halt (class dead)**; data source unavailable → halt." Order registered: C14, C19, C2, C9, C1, C11, C18, C15, C5. `candidates/run.py` line 6: "halting rules are applied by the operator between runs, not here" — no rule is implemented in code.

**Sequence, from the private LOG and commits.**

| time (2026) | event | source |
|---|---|---|
| 09-10 10:40–10:42 | C14 cleared; C19, C2 not cleared; C9, C1, C11 not cleared, each classified at the time as "underpowered" | private `LOG.md`; commits `ed9498a`…`4d99b46` |
| 09-10 10:43:38 | commit `ed42f14`. `PHASE4_REPORT.md` as committed: "Halt rule triggered: C9, C1 and C11 all failed the same way … C18, C15 and C5 were not run (C5 is in the same class and is predicted to fail identically; **C18 and C15 are different samples and remain runnable**)." | archived the version as committed in `ed42f14` (archived, private) |
| 09-11 17:24 | C18 run: NOT CLEARED, t = 0.70 | private `LOG.md` |
| 09-11 17:25 | C18 declared VOID (fetcher truncated funding to 500 rows/symbol) | private `LOG.md`, `C18_void_truncated_funding.md` |
| 09-11 17:26–17:40 | funding re-fetched; `PREREG.md` C18 design line and `prereg_design.json` edited (`5b2801a`) | commit diff (archived) |
| 09-11 17:41 | **C18 CLEARED**, t = 3.73 | private `LOG.md` |
| 09-11 17:42 | **C15 run**, NOT CLEARED | private `LOG.md` |
| 09-11 17:43:37 | commit `b7cd128`; report retitled "complete"; text: "halted on the three-same-reason rule … — then, on instruction, C18 and C15 to complete the scoreable set. C5 was not run" | archived |

**Two independent departures from the registered halt rules.**

1. *The three-same-reason halt was overridden.* It fired after C11, was recorded as a halt with the report so titled, and was lifted the next day by operator instruction. The halted report itself said C18 and C15 were different samples and remained runnable, so at the time of the halt the operator did not regard the rule as barring them; the registered rule text, however, says "halt", not "halt this class". The override is documented privately and not in the public WRITEUP, which states the halt rules and reports C18 without mentioning that a halt had fired.

2. *The clear-halt was not applied.* The registered rule says a candidate clearing halts the phase for reporting. C18 cleared at 17:41 and C15 was run at 17:42. This is a separate departure: it does not depend on how the first is judged, because even under the operator's reading of rule 1 ("C15 remains runnable"), rule 2 should have stopped the phase before C15. C15's result (not cleared, t = 1.58) is therefore a test run outside the registered stopping rule. Neither departure is mentioned in the public repository; the public `LOG.md` is regenerated by `reproduce.sh` and carries neither the void entry nor the original timestamps.

Further facts of record: (i) the registered C18 design line was rewritten after its void run — statistic, placebo and refutation clauses unchanged, the numeric threshold recomputed on corrected data; (ii) `prereg.py` computes every "design" SE from the same data the test then uses, so "design versus achieved" is not a prior-versus-outcome comparison.

### Registration status

| claim | evidence | what it establishes |
|---|---|---|
| A 20-candidate list with scores, ranking and predictions existed before any test | `429601d` 2026-09-09 13:22:27 (`CANDIDATES.md`, 215 lines); first result commit 2026-09-10 10:40:40 | commit order in a local repository; author dates; no external anchor |
| Per-candidate criteria and the test code were recorded before any result was recorded | `bb9f1b9` 2026-09-10 10:40:23 (PREREG, design JSON, `common.py`, `run.py`, `prereg.py`); C14's result commit `ed9498a` 10:40:40 | commit order only. A 17-second gap between commits says nothing about when the C14 code ran. The candidate report files' mtimes in the private tree (09-10 10:40–10:43, 09-11 17:24–17:42; observation) are consistent with the LOG entries and with either sequence. |
| The ranking was amended before testing | `7145117` 2026-09-10 10:26:31 | commit order; the amendment text asserts "before any test" |
| "Committed to git before any test" (public WRITEUP) | true of commit order in the private repository; the public repository contains none of it (`prereg_design.json` in the public tree is generated by `reproduce.sh` and holds only the 8 designs that ran) | not demonstrable from the public repository |
| Predictions scored in "The calibration finding" | `PREREG.md` line 108 lists expected outcomes per candidate | recorded in the same commit as the criteria |
| btc-project pre-commitments | v2–v12: a hypothesis/criteria commit precedes the result commit (list in 0.2); v13: single commit | version-specific, as stated in 0.2 |

Not demonstrable: anything to an external-registry standard; execution order (as opposed to commit order) for any test; that the private v1 variant mining did not touch sealed data.

## 0.4 Inspection history — class (c)

Purpose: identify which data have been inspected *for the purposes these claims rely on*, so that they cannot be presented as a hold-out again. This inventory establishes what the repositories and their logs record. It does not establish what the analyst has seen elsewhere: market prices after every window below are public, and the analyst has had access to them.

### btc (P7)

| window | inspections recorded | source |
|---|---|---|
| training rows 2020-09 → 2025-08 (ex sealed_2022 ± 3d) | v1 variant mining; v2–v13 tests; public re-runs | `VERSIONS.md` |
| sealed_2022 (2022-01-01 → 2023-01-01) and sealed_recent (2025-09-01 → 2026-09-01) | 1. 2026-09-02T07:58:57Z: opened with the single-mask defect; Model B ICs read, Model A empty (disclosed). 2. 2026-09-02 ~09:15: re-scored after the fix — the "counted" look. 3. 2026-09-07 (v13): HAR and QLIKE scored on the same sealed outcomes, counter deliberately left at 1. 4. 2026-09-06, 09-07, 09-12 05:5x (public pipeline builds) and 2026-09-12 11:50 (verification rerun): both blocks re-scored for Model A, GARCH and HAR; the public code writes `looks = 1` as a literal. 5. Event-study ground truth: computed on all touches including sealed rows (v2 private; `event_study.py:213-218` public). | `sealed_opened.json`, `DECISIONS.md`, `VERSIONS.md`, `vol_model.py:176`, `har.py:110` |
| grid after 2026-09-01 | no rows exist (grid ends 2026-09-01 00:00; option fills end 2026-08-28) | parquet coverage |

**What this establishes:** the two designated sealed blocks have been inspected repeatedly and cannot supply fresh confirmation for any P7 claim. Every sealed-block statistic in the public repository is at minimum a third scoring of those outcomes.

### futures (P8)

| window | inspections recorded | source |
|---|---|---|
| training 2002-01 → 2024-08-02 | every stage, twice on 2026-09-09; public rebuilds 09-12 04:5x and 11:50 | commits, `progress.json` |
| sealed hold-out 2024-09-01 → 2026-09-09 | 1. 2026-09-09 11:43:25Z registration by an aborted run (nothing scored, per `DECISIONS.md`); 2. 2026-09-09 11:45:14Z scored: −1.18 (partial final bar); 3. 2026-09-12 04:53:23Z scored: −1.28 (settled close), public reproduction; 4. 2026-09-12 11:52 my rerun halted at s9 without scoring. Read upstream without a counter: `s0_stitch.py` offsets and `s1.py` schedule use full history; s6's combined placebo flip rates use full score histories. | private and public `holdout_looks.json`, `DECISIONS.md`, `progress.json` |
| candidates C14, C2, C9, C1, C11, C15 | 2002-01 → 2026-09-09 including the sealed window; run 2026-09-10 and 2026-09-12 (twice) | `common.py:26,44`, `prereg_design.json` |
| C18 | formation dates 2020-02-17 → 2026-08-31 (342 Mondays); outcomes through the week ending 2026-09-07; klines and funding on disk to 2026-09-09/10; run 2026-09-11 (void, then valid) and 2026-09-12 (twice) | `LOG.md`, cached parquets |
| C19 | training path only (`path_end` 2024-08-02) | `prereg_design.json` |

**What this establishes:** the designated historical hold-out (2024-09 → 2026-09-09) has been inspected and cannot supply fresh confirmation; the candidate tests have used every futures bar on disk through 2026-09-09 and every C18 outcome through 2026-09-07.

### Boundaries for any future protected window — class (c), with a stated limit

| series | last outcome used by any analysis in the repositories | earliest date a new window could begin |
|---|---|---|
| BTC 5-minute grid | 2026-09-01 00:00 (targets up to 4h before) | 2026-09-01 |
| Deribit option fills / structures | entries to 2026-08-28; the last 30-day structures settle inside September 2026 | after the last structure's expiry (≈ 2026-09-27) |
| futures daily bars | 2026-09-09 | 2026-09-10 |
| C18 | formation 2026-08-31, outcome week ending 2026-09-07 | formation dates from 2026-09-07 (outcomes from 2026-09-14) |

A window that is empty in the repository is unscored by these pipelines. It is not evidence that the analyst has not observed the market outcomes it will contain; those are public. Any future window can therefore be described as *unscored*, not as *unseen*, and that distinction must be stated wherever such a window is used.

## 0.5 Provenance per published number — class (a) where measured on preserved data, (c) where documentary

Legend: **E** established; **P** partially established; **U** source or sample provenance could not be established; the original figure is preserved as unverified and excluded from defended findings.

### P7 (btc-public)

| published figure(s) | source revision | acquisition schedule | sample membership | status |
|---|---|---|---|---|
| Sealed R² model vs GARCH (0.457/0.311, 0.554/0.165, 0.464/0.232, 0.540/−0.233); HAR gains +0.024/+0.026/+0.038/+0.051; QLIKE 3 of 4 | `reports/results/vol_model.json`, `har.json` at `69899dc`; byte-identical on the 2026-09-12 rerun from `data/grid` | raw parquets: mtime 2026-09-06 18:23 (observation; they were not produced by the public `fetch.py` in this tree); grid 2020-01-01 → 2026-09-01, 701,280 bars | sealed_2022: 87,552 rows = 304 days of 365; sealed_recent: 87,264 = 303 days; training 366,641 rows | **E** for the public run. **Differs from the registered private run** (v1: +0.141/+0.220, +0.391/+0.776; v13: QLIKE 2 of 4). GARCH α = 0.2000, β = 0.7800 lie on arch 7.2.0's starting grid; fit status unknown → GARCH figures **U** until 3.7 |
| Ground truth: 36 touches, 100 %, 5.3×, $1.45m vs $274k, 94 %, 2.4× | `event_study.json` `ground_truth`; same values in private v2 | Tardis first-of-month prints, `liquidations.parquet`, 148,572 rows 2020-01-01 → 2026-09-01 | all touches on print-covered days across the full grid **including both sealed blocks**, contrary to the "training window" label; mid-bucket mean $1.54m exceeds cluster $1.45m | **P**: sample established, label wrong |
| Framing 5: 53,088 prints, 61 days; 15m −0.94 [−3.54, 1.67] MDE 3.79; 30m −0.32 [−4.82, 4.00] MDE 6.54; 60m +3.81 [−1.48, 10.27] MDE 8.76; placebo −7.07 vs 1.20 | `event_study.json`; private v10: 66,387 prints / 63 training days, same 30m and 60m values | as above | training-masked prints with a prediction; 61 "days" = 47 first-of-month days plus next-day spill bars | **P**: numbers reproduce; three horizons registered, one quoted |
| Framing 1: matched difference +8.72 bps over 11 cells (no interval), placebo abs p95 9.94 (not cleared); absolute-move slope on map share +332 [197, 446], MDE 172, n = 129,875 on 1,452 days | `event_study.json`; private v2 registered this framing (its "ratio" and dose-response) | as above | training-masked | **P**; the sign of the absolute-move slope is opposite to the private v2 wording ("absolute movement slightly lower"); units of `cont_60m`/`share` to be confirmed from code before interpretation |
| Framing 2: slope −0.092 [−0.633, 0.418], MDE 0.753 (σ per unit log pressure), n = 4,036 on 70 days; notional-only control −0.055 [−0.39, 0.26] | `event_study.json`; private v3 | Tardis book snapshots, 70 days | training | **E** |
| Framing 3: raw slope −11.64 [−17.67, −6.44], MDE 8.00, n = 28,220 on 1,373 days; momentum-controlled β −2.84 (no interval) | `event_study.json`; private v3 sub-hypothesis (a) | as above | training | **E**; control added after the raw result (docstring) |
| Framing 4: weekend −1.37 bps (178 cells), Asia +1.16 (45 cells); no intervals | `event_study.json`; private v3 sub-hypothesis (b) | — | training | **E** as point values |
| Instrument: 8 structures, best 41.8; idealised 81.6; 67×; 309 years | `instrument.json`; private v8-prep: 77.7 | `option_fills.parquet`: 633,631 fills, 417 entry days 2020-01-01 → 2026-08-28, hours 00–03 UTC; 87 % Fridays but every weekday and 2020 present — not producible by the public `fetch.py` (Fridays from 2021-01-01) | straddles n = 201, 7d strips 242, 30d strips 53, calendars 102; 81.6 is the 2021-on subsample (190 trades); full sample 137.3 | **U** on acquisition; **P** on sample |
| Economics: 45.7–67.3 bps, 20.1 cost, MDE 73.7, +25.7, 521 trades / 10 years | `economics.json` from `har.json` sealed gains and `instrument.json`; private v13: 40–68, 20, 77, 671 / 13 years | derived | derived; cost excludes option bid-ask spread; dispersion carries √2 | **P**: derivation reproducible, inputs defective |
| "82,152 variants", "six bps against ten" | private v1 only | — | — | **U** (historical, private) |
| Five audit catches | private narrative | — | — | (c) documentary only |

### P8 (futures-public)

| published figure(s) | source revision | acquisition schedule | sample membership | status |
|---|---|---|---|---|
| Cost ratio 2.3; median round trip 2.69 bp = 4.1 % of a daily move; 0.85 for the daily rule | `s1_stats.json`; identical private and public | Yahoo `=F` daily bars: private fetch 2026-09-09 ~12:17 (`s0_fetch.log`), public re-fetch 2026-09-12 05:5x; `END = 2026-09-09` | 27 markets; spreads in ticks from `config.py`, impact 0.5 tick flat | **E** as a model output |
| Trend 0.24, 10.0 vs 3.24 bp, placebo p95 0.02; carry 0.08, MDE 0.61; value −0.44, −31.8 bp; correlations −0.07 / −0.47 | `s2/s3/s5_stats.json`; identical private and public | as above | training 2002-01 → 2024-08-02 | **E** |
| "timing +0.44 against a standing tilt of −0.22" attributed to trend | `s6_stats.json` (combined book: tilt −0.234, timing +0.446); trend's own (`s2_stats.json`): tilt +0.222, timing +0.130 | — | — | **E, contradicts the prose** |
| Combined 0.06, vol 16.6 %, maxDD −53 %, breadth 8.6, contributions; placebo p95 0.05 (public) / 0.08 (private) | `s6_stats.json` | 40 placebo draws | training | **E**; p95 of 40 draws is the second-largest draw |
| Hold-out −1.28 (−1.18 original), −21 %, components, SE 0.71 | public `s9_stats.json` (09-12); private RESULTS (09-09) | settled vs partial final bar | 2024-09-01 → 2026-09-09, 528 days | **E** |
| Splice verification 98.4–98.8 %, 91–96 % | `SPLICE_CHECK.md` from EIA series | — | CL, NG, HO, RB only | **E** for energy |
| Positive control 3.04 bp/day, t = 4.13, shuffle −0.24 | `C14.md`; SPY 1993 → 2026-09-09 | — | 6,210 days 2002 → 2026-09-09 | **E** |
| C18: alpha +1.02, SE 0.27, t 3.73, placebo 0.40, net +0.93; decomposition; 342 weeks; ~110 symbols; "29 names a leg" | `C18.md`, `C18_AUDIT.md`; Binance funding 822,464 rows / klines 261,315 rows, 142 symbols, 2019-09-08 → 2026-09-10 (private valid fetch 09-11 17:26; public 09-12 06:10) | universe = `status == TRADING` at fetch time with ≥ 3 y history; 121 of 142 list after 2020-02-17 | 342 formation Mondays; mean 22.2 names per leg, max 29 | **E** on the run; survivor-conditioned by construction; "29" is the maximum |
| C18 cost "20 bp round trip at 41 % turnover" = 0.083 %/wk | `run.py:221`: union-turnover share × 0.20 | — | recomputed from the cached book this stage: the book is 200 % gross (one leg = 1.0); mean traded notional Σ\|Δw\| = **1.888 per week in units of one leg's notional** (94 % of gross), from ≈ 20.8 entries, 20.7 exits and 2.5 flips per week across ≈ 44 names | **E**: the charged figure prices a one-leg round trip on the share of names replaced; it does not price the notional actually traded |
| "design SE 0.74 %/wk … achieved 0.27 … wrong by nearly threefold" | `CANDIDATES.md` line 159: "σ_w ≈ 5 %: 0.74 / **1.0 % per week**" — 0.74 is the **unadjusted MDE** (2.80 × SE) at 360 weeks, implying a prior SE of 0.264 %/wk; `PREREG.md` as committed recorded SE 0.033 (truncated data), after the re-fetch 0.272 | — | — | **E, contradicts the prose**: prior SE 0.26 and achieved SE 0.27 agree; the "threefold" is the z-multiplier 2.80 |
| "every published premium replicated in sign … at roughly its published size" | private `PHASE4_REPORT.md`: "at magnitudes consistent with the literature after decay"; no reference magnitudes recorded | — | — | **U** for "published size"; "every" contradicted by value (−0.44) and C2 (wrong sign) |
| Futures candidates C9 2.12, C1 2.48, C11 1.72, C15 1.58, C2 0.87, C19 −0.32 | `C*.md`, identical private and public | — | 2002 → 2026-09-09 (C19 training only) | **E**; C15 ran after the clear-halt (0.3) |
| Mandate: 53/500; 68/28/4 %; 25 % vs 40 %; 22.3 % | `s8_stats.json`, `s7_stats.json` | — | training path; overlapping starts; vol grid tops at 40 % | **E** as model outputs; accounting items 3.1/3.2 pending |
| "2.8 times its sample" | `PHASE4_REPORT.md`: (3.86/2.3)² | — | — | **E** as arithmetic; treats the observed slope as the true effect |

Gate: the record is complete. Unresolved provenance is recorded as such (P7 option-fill acquisition; P7 GARCH fit status; P7 private variant count; P8 "published size"; the units of framing 1's absolute-move slope).
