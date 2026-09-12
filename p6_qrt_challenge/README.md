# QRT × ENS Data Challenge 2026 — Asset Allocation Forecasting

**Rank: 178 / 1,106 · Accuracy: 0.5212 · Beat official LightGBM baseline (0.5079) by ~1.3 percentage points**

---

## What this is

My entry for the [QRT × ENS Data Challenge 2026](https://challengedata.ens.fr/). Binary classification: predict whether each asset allocation's daily return will be positive or negative. Evaluated on accuracy.

Independent project, done alongside first-year coursework. Not part of any module.

---

## The data

Each row is one allocation on one day: 20 days of past returns, 20 days of signed volume, median daily turnover, a group label, and an allocation ID. No prices, no names, no ordered timestamps — the date labels are shuffled, so you can't use temporal structure directly.

Train: ~527,000 rows. Test: ~31,870 rows.

---

## My method

The submission is an **equal-weight average of 10 independently-trained models**, thresholded at 0.5.

- **Tree models** (LightGBM and CatBoost, multiple variants — binary, Random Forest mode, two-stage magnitude-then-sign, residual targets) for the bulk of the signal.
- **Set Transformer** (a neural net that does attention across all allocations within the same day) — this was the breakthrough component. The data signal is dominantly cross-sectional, so a model that natively handles "the set of allocations on this day" extracts signal per-row models miss.
- **Pseudo-labelling**: the test set's most-confident predictions from an earlier model are added back as extra training data, weighted at 0.3×. This is the trick that unlocked most of the gain.
- **Domain adaptation** (CORAL + adversarial reweighting) to reduce the train-vs-test distribution gap.
- **GroupKFold by time** across 5 folds — random row splits leak because cross-sectional features touch all allocations on the same day.

Hyperparameters were pre-committed in writing before training; blend formula was locked equal-weight; submission rule was "only submit if the new blend's out-of-fold score improves by ≥ 1 basis point."

---

## What I tried before settling on this

A lot. Briefly: deeper boosting, quantile/Tweedie regression, lambdarank, random forests, multi-task NN, CNN on the return sequence, bigger/wider Set Transformers, different pseudo-label teachers, fold-partition bagging, trailing target features. Across 19 audited candidates, **18 were rejected** by the locked rules (they passed individual gates but diluted the blend or failed standalone). The one that cleared the +1 bp threshold — a bigger Set Transformer trained with the strongest pseudo-teacher — moved the LB from 0.5207 to 0.5212.

---

## The thing that surprised me

Allocations that consistently underperform their peers across many training days keep underperforming. Same in the other direction. That's a momentum signal at the allocation level, and it maps directly to statistical arbitrage — predicting *relative* performance, not absolute returns. I came to it from first principles rather than reading it, and adding features that capture it explicitly helped.

---

## A note on what I built

Some techniques — particularly the Set Transformer with pseudo-labels, CORAL/adversarial domain adaptation, and the disciplined pseudo-label chain — were genuinely beyond my level when I started. I researched and implemented them from the relevant papers, working through the maths from scratch.

---

## Result

- **0.5212 accuracy**, **rank 178 / 1,106**
- Official LightGBM baseline: 0.5079 — beat it by ~1.3 percentage points
- The signal-to-noise ratio here is tiny. Going from 0.50 to 0.52 is meaningful; going further is very hard.

---

## Why the code isn't here

The challenge is still running. Happy to discuss the approach.

---

*Independent project. First year, studying maths and economics at the University of Nottingham.*
