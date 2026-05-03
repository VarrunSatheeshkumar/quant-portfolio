# JustWalk: Quantitative Analytics Model

JustWalk is a clean energy startup I founded. We secured £50,000 from Vodafone and installed piezoelectric floor tiles at their London Paddington office. This model was built to answer three questions that kept coming up in conversations with the Vodafone team and potential investors.

## The three questions

**1. How much energy does it actually generate?**

The energy model starts from physics rather than assumptions. A person stepping on a tile does roughly 2.5 joules of work on the tile (conservative mid-range from the literature; actual range is 1–7J depending on tile design and body weight). After rectifier and voltage regulator losses, about 22% of that becomes usable electricity.

```
Energy (Wh) = persons × 2 steps × 2.5J × 0.22 × n_tiles / 3600
```

At the Vodafone office site with 50 tiles: ~6.6 kWh per year, worth about £2. That number is not a modelling error — piezoelectric energy density is genuinely low.

**2. Is the investment financially viable?**

Short answer: not on energy revenue alone. The NPV at 8% WACC over 10 years is approximately -£43,000 for the office installation. This is because £2/year in electricity revenue against £500/year maintenance means the cash flows are always negative.

The transit hub scenario shows where the economics do work. At a high-traffic site (modelled at ~5 million persons/year) with 200 tiles and a realistic SaaS analytics revenue of £45,000/year: NPV ≈ £125,000, IRR ≈ 23.5%, probability of positive NPV across Monte Carlo scenarios ≈ 93%.

The honest conclusion: **the data analytics product is the business, not the energy.** The tiles are a data collection mechanism that also happens to generate power.

**3. Are there days where the data looks wrong?**

Z-score anomaly detection on a 28-day rolling window. Flags days where footfall deviates by more than 2.5 standard deviations from the recent norm. Under normality this should produce about 4–5 false positives per year in 365 days of daily data. The 28-day window (rather than a fixed threshold) means the detector adapts when the underlying footfall level changes.

## Financial model detail

NPV = -CapEx + Σ CF_t/(1+r)^t where CF_t includes 1%/year tile degradation.

IRR is found using Newton-Raphson on NPV(r) = 0. The derivative (dNPV/dr) is the duration of the cash flow stream. When cash flows are always negative (office case), no real IRR exists — the code returns None rather than a nonsensical number.

Monte Carlo simulation samples each uncertain parameter (joules per step, efficiency, electricity rate, degradation) from a Normal distribution and computes 5,000 NPV scenarios. This gives a distribution rather than a point estimate — more honest for decision-making.

## Running

```bash
pip install numpy pandas scipy matplotlib
python justwalk.py
```

Plots saved to `./plots/`: hourly footfall patterns, ROI analysis with NPV sensitivity, anomaly detection time series.
