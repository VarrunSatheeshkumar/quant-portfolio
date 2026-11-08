# P9 — UMushroom UK Investment Competition 2026: event-adjusted risk model

[Portfolio home](../README.md)

A two-person event-driven £100k paper portfolio (8 positions, 20% cash) timed to earnings and trading updates before the 22 Nov score lock; I built the risk model. The model measures where the portfolio's two-week risk sits. Every figure below is a model output, not a realised outcome: the competition's own scoring on 22 Nov is the only realised result, and a post-mortem will be added then.

**Protocol.** Model code, the 6 Nov data cutoff, the target weights and the call ledger were fixed before the evaluation window (9–20 Nov) and are not refitted afterwards. The portfolio is scored once, by the competition, on 22 Nov. This is a prospective demonstration of process; it does not establish risk calibration or trading skill.

## Modelled result (horizon 9–20 Nov, 10 trading days)

- **Two-week portfolio volatility: 3.9% (about £3,900).** 95% VaR about £6,400; 99% about £9,100 (normal approximation).
- **Concentration:** NVIDIA, Applied Materials, Bitcoin and Ethereum are 40% of capital but **80% of modelled risk**. AI and semiconductors alone are 25% of capital and 67% of risk.
- **Walmart is a low-risk diversifier:** 10% of capital, 2% of risk. Its correlations with NVIDIA (−0.18) and Applied Materials (−0.25) are negative, but its contribution to portfolio risk is still positive, so it diversifies rather than hedges.
- **Event risk** (the earnings days) is 36% of portfolio variance; the rest is ordinary day-to-day movement.
- **The earlier rule of thumb understated it:** weight × implied move (crypto two-week moves scaled from DVOL 38 and 60) put 71.5% of risk in the risk-on sleeve. The model, which adds day-to-day volatility and correlations, puts it at 80%; most of the gap is Walmart, whose report-day move is large but whose overall contribution is small. Without the crypto moves the rule of thumb gives 61.8% (`rule_of_thumb_risk_on_share_pct` in `out/results.json` uses the DVOL version).
- **Equal-risk alternative:** equal risk contribution would cut NVIDIA to 6.4% and Applied Materials to 5.0%, raise Walmart to 15%, and lower volatility to 3.1%. Not adopted: the ranked score rewards dispersion, so the tilt is deliberate.

| Holding | Weight | Ann. vol | 2-week s.d. | Share of risk | ERC weight | Deploy trigger (daily) |
|---|---|---|---|---|---|---|
| NVIDIA | 15% | 39% | 13.7% | 36.2% | 6.4% | −5.0% |
| Applied Materials | 10% | 69% | 19.0% | 30.7% | 5.0% | −8.7% |
| Walmart | 10% | 26% | 7.7% | 2.0% | 15.0% | −3.2% |
| Home Depot | 10% | 29% | 7.9% | 4.3% | 12.6% | −3.7% |
| BAE Systems | 10% | 32% | 7.3% | 4.2% | 13.7% | −4.0% |
| Rolls-Royce | 10% | 36% | 8.1% | 9.1% | 9.7% | −4.6% |
| Bitcoin | 10% | 37% | 7.3% | 8.4% | 9.9% | −4.6% |
| Ethereum | 5% | 50% | 9.9% | 5.2% | 7.7% | −6.3% |

Deploy trigger = a one-day fall of two daily standard deviations, the size of move that counts as a dip worth buying under the cash rule.

## Rebalance: halfway to equal risk (`compare.py`)

Holding the 4th of 52 place in the University of Bristol heat (top 10 qualify) favours protecting rank over adding variance, so the book moves halfway from the current weights towards equal risk, rounded to 0.5% and keeping cash at 20%.

| | Current | Halfway (adopted) | Equal risk |
|---|---|---|---|
| Two-week volatility | 3.91% | 3.40% | 3.05% |
| 95% two-week VaR | £6,432 | £5,599 | £5,013 |
| P(loss > £5,000) | 10.0% | 7.1% | 5.0% |
| AI + crypto share of risk | 80.4% | 67.8% | 50.0% |
| AI stocks' share of risk | 66.8% | 49.4% | 25.0% |
| AI sell-off stress* | −£3,613 | −£3,091 | −£2,580 |

*NVIDIA and Applied Materials fall by their implied moves; Bitcoin and Ethereum fall one two-week s.d.

Trades: NVIDIA 15% → 11%, Applied Materials 10% → 7.5%, Walmart 10% → 12.5%, Home Depot 10% → 11%, BAE 10% → 12%, Ethereum 5% → 6%; Rolls-Royce and Bitcoin unchanged. The cost is symmetric: about £500–800 less gain in a strong two weeks.

## Method

1. Daily closes 1 May – 6 Nov 2026, converted to sterling with GBP/USD; log returns on US trading days (UK bank holidays carry the previous close; crypto and FX are sampled on US trading days, so weekend moves fall into Monday).
2. Six past earnings-reaction days with verified dates are dropped so event moves are not counted twice; 125 days remain.
3. Diffusive covariance: Ledoit–Wolf shrinkage (intensity 0.09), scaled to 10 days.
4. Event risk: each report inside the window adds variance from its options-implied move m. The sources publish options-implied expected moves (conventionally the at-the-money straddle price as a share of the stock price), read here as the expected absolute move, so under a zero-mean normal the jump s.d. is m·√(π/2). If an input were instead a one-s.d. move this overstates that jump by 25%; the robustness table tests it.
5. Euler risk contributions, sleeve shares, and an equal-risk-contribution portfolio for comparison.

## Robustness

| Variant | 2-week vol | Risk-on share of risk |
|---|---|---|
| Base case | 3.91% | 80.4% |
| UK update moves 0% | 3.87% | 81.9% |
| UK update moves 5% | 3.97% | 77.8% |
| Sample covariance (no shrinkage) | 3.97% | 81.4% |
| Past event days kept in | 3.92% | 80.1% |
| Implied moves read as one s.d. (no √(π/2)) | 3.65% | 79.9% |

The headline holds across every variant.

### Implied-move inputs

| Holding | Input | Source | Observed | Definition |
|---|---|---|---|---|
| NVIDIA | ±9.0% | EarningsWatcher, Unusual Whales | 6 Nov 2026 | Published expected move into the 17 Nov report |
| Applied Materials | ±10.4% | EarningsWatcher | 6 Nov 2026 | Published expected move into the 12 Nov report |
| Walmart | ±4.6% | Benzinga | August 2026 (previous report) | Published expected move for the August report; stand-in until rechecked |
| Home Depot | ±4.2% | Benzinga | August 2026 (previous report) | Published expected move for the August report; stand-in until rechecked |
| BAE Systems, Rolls-Royce | ±3.0% | Assumption | — | No listed options; tested at 0% and 5% |

The option expiry and exact method behind each published move were not recorded, a gap in provenance. Each input is rechecked the day before its report; a changed input is logged as a new dated row, and the 6 Nov run is kept as the frozen baseline.

## Caveats

- Six months of data; correlations from one regime (including last week's AI sell-off).
- Jumps are treated as independent. NVIDIA's report will move Applied Materials too, so true concentration is, if anything, higher.
- Walmart and Home Depot implied moves are August levels; BAE and Rolls-Royce have no listed options, so ±3% is an assumption (tested at 0% and 5%).
- Implied moves include a few days of ordinary movement, a small double count.
- Applied Materials' past report days are not dropped (dates not verified), which slightly overstates its day-to-day volatility.
- Crypto closes at midnight UTC, equities at 21:00 UTC, which slightly understates crypto–equity correlation.
- Normal VaR understates tail risk around earnings.

## Call ledger

`ledger.csv` records each catalyst call (implied move, expected direction, rationale, exit rule, target weight). The file is dated 7 Nov 2026 19:50 UTC, before every report in the window; its status column records when each row was confirmed. The same calls are posted in the UMushroom portfolio Description, which the platform dates, before the first catalyst (US CPI, 10 Nov). After 22 Nov the ledger gains an `outcome` column and no other column is edited.

**Scoring rule (fixed 8 Nov 2026, before any catalyst).** Directional calls (the six equities): a hit if the close on the first full session after the report or update is above the close on the last session before it, in the stock's own currency; for after-close reports (Applied Materials, NVIDIA) that is the next day's close against the report day's close. If BAE publishes no update by 20 Nov, its call is recorded as void. Hit rate = hits ÷ scored calls. Alongside it: each realised report-day move against its implied move, and each holding's return in sterling from its fill to the 20 Nov close. Bitcoin and Ethereum carry no directional call; their realised two-week moves are compared with the model's two-week s.d.

`POSTMORTEM.md`, added after 22 Nov, will compare realised and implied moves per catalyst, report the hit rate, attribute returns by sleeve, and keep every wrong call.

## Data sources

NVIDIA, Walmart, Bitcoin, Ethereum and GBP/USD: Financial Modeling Prep. Applied Materials, Home Depot, BAE Systems and Rolls-Royce: Yahoo Finance adjusted closes. Implied moves: EarningsWatcher, Unusual Whales, Benzinga (August). The price file is not redistributed; [`data/README.md`](data/README.md) gives the symbols, sources, date range and file format needed to rebuild it.

Run: `pip install -r requirements.txt`, then `python -I model.py data/prices.txt out/` and `python -I compare.py data/prices.txt out/`
