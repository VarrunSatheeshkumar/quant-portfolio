# C18 audit — before recording a result above its band

Long-short weekly return decomposed into the price leg and the funding leg (both %/week, month-block SE).

| component / period | mean | SE | t | weeks |
|---|---|---|---|---|
| total (all) | +1.036 | 0.283 | +3.67 | 341 |
| price leg (all) | +0.501 | 0.274 | +1.83 | 341 |
| funding leg (all) | +0.535 | 0.035 | +15.32 | 341 |
| total 2020-02 to 2021-12 | +2.249 | 0.827 | +2.72 | 98 |
| total 2022-01 to 2026-08 | +0.547 | 0.204 | +2.69 | 243 |
| price leg 2022+ | +0.081 | 0.204 | +0.40 | 243 |
| funding leg 2022+ | +0.466 | 0.034 | +13.72 | 243 |

* signal at entry: bottom-quintile funding -0.489 %/week, top-quintile +0.473 %/week (7-day sums)
* beta of the long-short on BTC: +0.027; alpha +1.015 vs raw mean +1.042 %/week
* names in a leg with no price a week later (dropped from the leg mean): 0 of 15192 leg-slots (0.00%)
* cost sensitivity at 41% weekly turnover: 20 bp round trip → 0.08; 50 bp → 0.20; 100 bp → 0.41 %/week against +1.04
* survivorship: the universe is perpetuals still trading in 2026-09 with ≥ 3 years of history; perpetuals delisted before then are absent. A high-funding name that died would have paid the short leg; a negative-funding name that died would have cost the long leg. The direction of the bias is not determinable from this data and is recorded as an open limitation.

## Verdict

* price leg works against the funding (price t <= -2): **not fired**
* lives in 2020-21 only (2022+ total t < 2): **not fired**
* depends on names vanishing mid-week (> 2% of leg-slots): **not fired**
* does not survive 50 bp round trip: **not fired**
* beta does the work (|beta| > 0.3): **not fired**

**AUDIT PASSED — recorded as cleared, with the survivorship limitation attached.**