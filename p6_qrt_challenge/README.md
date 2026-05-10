# QRT × ENS Data Challenge 2026 — Asset Allocation Forecasting

**Rank: 339 / 1,106 · Accuracy: 0.5177 · Beat official LightGBM baseline (0.5079)**

---

## What this is

This is my entry for the [QRT × ENS Data Challenge 2026](https://challengedata.ens.fr/). The task was to predict whether a given asset allocation's daily return is positive or negative — basically, should you go long or short? Binary classification, evaluated on accuracy.

I did this alongside first-year coursework. Nothing here was part of any module or supervised project. I just found the problem interesting and wanted to see how far I could get.

---

## The data

Each row represents one allocation on one day. You get:
- 20 days of past returns (RET_1 to RET_20)
- 20 days of signed volume (a liquidity proxy)
- Median daily turnover
- A group label and an allocation ID

No prices. No names. No timestamps in order. The date labels are deliberately shuffled, so you can't exploit any temporal structure directly. That caught me off guard at first.

Train set: ~527,000 rows. Test set: ~31,870 rows.

---

## What I tried

**Feature engineering** was most of the work. From the 20-day return and volume windows I computed rolling means and standard deviations at multiple lookback windows, Sharpe-like ratios, skewness, kurtosis, autocorrelation, return-volume correlation, trend slopes, and drawdown stats. I also built cross-sectional features: how does this allocation rank relative to others on the same day?

**Models**: LightGBM and CatBoost, both with magnitude-weighted samples — rows where the absolute return is larger are weighted more heavily at training time, since those are the ones where getting the sign right actually matters. Binary classification objective worked better than regression in cross-validation, which makes sense since the task only scores the sign.

**Domain adaptation**: there's a measurable distribution shift between training and test rows. I used CORAL (aligning covariance matrices between train and test feature spaces per fold) and adversarial sample reweighting (a classifier that distinguishes train from test, whose outputs become per-sample training weights). These reduced the gap between cross-validation score and leaderboard score.

**Sequence model**: a small two-layer transformer on the 20-day return and volume sequences. Gave a modest independent signal that blended well with the tabular models.

**Cross-validation**: GroupKFold by time period across 5 folds. This is critical — random row splits leak information because cross-sectional features are computed across all rows on the same day.

**Final blend**: weighted average across five component models, with weights optimised on adversarially-reweighted out-of-fold predictions.

---

## A note on what I built

Some of the techniques here — particularly the domain adaptation (CORAL, adversarial reweighting) and the sequence transformer — were genuinely beyond my level when I started. I researched and implemented them to understand what was possible, reading the relevant papers and working through the maths from scratch, not because I already had command of the theory. I'd say I understand them now, but they weren't techniques I came in knowing.

---

## The thing that surprised me

About halfway through I noticed something: allocations that consistently underperform relative to their peers across many training days keep underperforming. Same in the other direction.

That's a momentum signal at the allocation level. Once I saw it I realised the problem is really about predicting *relative* performance, not absolute returns. The allocations that are structurally worth shorting versus going long are partially identifiable from their cross-sectional history. This maps directly to statistical arbitrage — and I came to it from first principles rather than reading it somewhere. I added features that capture this explicitly and they helped.

---

## Result

- **0.5177 accuracy** on the held-out test set
- **Rank 339 out of 1,106 participants**
- The official QRT LightGBM baseline scores 0.5079 — I beat it by roughly 1 percentage point
- The signal-to-noise ratio here is genuinely tiny. Going from 0.50 to 0.52 is meaningful. Going further is very hard.

---

## Why the code isn't here

The challenge is still running. I'm not sharing the full implementation until it closes. Happy to discuss the approach.

---

## What I'd try with more time

- Better probability calibration before thresholding
- Learned allocation embeddings — treating each allocation ID as an entity with a learnable vector derived from its training history
- Stronger domain adaptation — the train/test feature distribution gap is the main ceiling and I only partially addressed it
- More principled ensembling — the blend weights were tuned on a noisy estimator

The problem is hard enough that I'm genuinely uncertain any of these would move the rank dramatically. The ceiling feels structural.

---

*Independent project. First year, studying maths and economics at the University of Nottingham.*
