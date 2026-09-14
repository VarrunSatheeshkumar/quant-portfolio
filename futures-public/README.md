# Futures signals: trend, carry and value

Part two of three. Part one: [BTC forced flow](../btc-public/) · Part three: equities (in progress) · [Portfolio home](../README.md)

**Start here**

- Read the [strategy table](WRITEUP.md#the-three-signals) for the futures programme. For the separate crypto funding candidate, check [one C18 week](WRITEUP.md#worked-example-constructing-one-c18-week) from funding ranks to its return and cost proxy.
- [Stage reports](reports/stage_reports/) contain the futures outputs; [C18.md](reports/candidates/C18.md) and [C18_AUDIT.md](reports/candidates/C18_AUDIT.md) retain historical generated wording. Use the write-up for the current cost and halt-rule qualifications.
- The [claim ledger](../audit/CLAIM_LEDGER.md) records sources and permitted interpretations; the [audit guide](../audit/README.md) explains its scope and private-source limitations. Coverage is not an exhaustive certification.
- Tracked reports need no data. `./reproduce.sh` rebuilds missing stage outputs and runs the candidate chain while retaining the already scored hold-out; see [Running it](#running-it) for the prerequisites and output status.

## Measurements

The measurements are in [the write-up](WRITEUP.md).

- **Signals:** trend net Sharpe 0.24, carry 0.08 (design MDE in Sharpe units 0.61), value −0.44, combined 0.06; no Sharpe interval has been computed for any of them.
- **Hold-out:** net Sharpe −1.28; the block was scored 2026-09-09 (−1.18 on a partial final bar) and 2026-09-12 (−1.28 on the settled close).
- **Candidate screen:** none of the three non-control candidates predicted to clear the registered threshold did so. Of the four predicted to have the right sign without clearing, three matched that prediction. The fourth, C18 (crypto funding-rate carry), cleared with gross alpha +1.015 %/wk, month-block SE 0.27, t 3.73; net alpha with costs entered into the weekly series has not been computed.

Read the [halt-rule record](WRITEUP.md#the-halt-rule-record) and [registration status](WRITEUP.md#registration-status) alongside the candidate results.

## Research structure

- **[Futures programme](WRITEUP.md#the-three-signals):** trend, carry and value, specified in advance on daily futures data from free sources across 13–27 markets, with a modelled cost, a portfolio layer and a sealed two-year hold-out.
- **[Candidate screen](WRITEUP.md#the-candidate-screen):** candidate claims recorded in a private local repository in commits preceding the result commits (not verifiable from this repository; commit order, not execution order). The [crypto funding candidate C18](WRITEUP.md#c18-crypto-funding-rate-carry) has its own results and worked example.
- **[Mandate simulator](WRITEUP.md#the-mandate-simulator):** the drawdown-mandate simulator.

## Running it

```
pip install -r requirements.txt
./reproduce.sh
```

`reproduce.sh` runs `python build.py` (stages s0–s9), then the candidate fetch, the splice check, the pre-registration dispersions, the eight candidate tests and the C18 audit. Data sources are keyless: Yahoo Finance, TreasuryDirect, Binance, EIA. `config.END` fixes the last bar at 2026-09-09. `data/` is not tracked; `reports/` is tracked.

The build checks the saved outputs required by each stage. A missing output reruns that stage and invalidates downstream completion records; a fresh clone runs s0–s8. The already scored hold-out is retained only when both tracked reports (`reports/RESULTS.md` and `reports/stage_reports/s9.md`) are present and nonempty; its status is recorded as retained, not newly scored. Missing retained reports stop the run. The splice check also stops on missing or empty inputs without issuing a research verdict.

Training stage reports and candidate reports are regenerated; the retained `RESULTS.md` remains a historical summary and is not rewritten to describe newly generated training outputs. The public candidate `LOG.md` records the reproduction's executions and lacks the private void entry and original timestamps. A reproduction does not re-establish the original registration or stopping-rule sequence.

The [saved reproduction record](../audit/REPRODUCTION.md) preserves the previous session's run, which logged exit 0. Its generated stage and candidate reports matched the saved versions, apart from the execution log; the hold-out reports were retained. The final missing-input and checkpoint guards were checked separately with local fixtures, without repeating the downloads or rescoring the hold-out.

Selected literal phrases in this README and `WRITEUP.md` are checked for presence against the tracked reports by `python -m tests.test_documents`, without validating their interpretation. `python -m tests.test_asof` and `python -m tests.test_stitching` run the as-of and stitching checks.

<details>
<summary>Module reference</summary>

## What each module does

| module | role |
|---|---|
| `config.py` | constants: universe and contract specs, cost inputs, signal parameters, bands, dates |
| `build.py`, `progress.py` | orchestrator and stage bookkeeping; a failed gate halts the run |
| `stages/s0_fetch.py`, `rolls.py`, `s0_stitch.py`, `s0_grid.py`, `s0.py` | daily bars with an `asof_time` per row; exchange-rule expiries; roll-switch offsets selected on the full price history including the sealed period; the as-of grid; the as-of and stitching tests |
| `stages/s1.py` | the cost model and the projected edge/cost ratio under an assumed gross Sharpe of 0.4; the return panel is read to compute dollar volatility; cost normalisation uses the final 250 observations |
| `stages/s2.py`, `s3.py`, `s5.py`, `signal_eval.py` | trend, carry and value, each evaluated standalone with a placebo, a block permutation and the stitching sensitivity |
| `backtest.py` | the P&L engine; costs on trades and rolls; monthly block bootstrap of the daily mean return, reported in Sharpe units as a mean-return MDE |
| `portfolio.py`, `stages/s4.py` | sector scaling (sectors above a 35 % standalone-risk share are scaled down once by cap/share), Ledoit–Wolf shrinkage, vol targeting, diversification ratio squared |
| `stages/s6.py` | the three-signal programme, its correlation matrix, leave-one-signal-out Sharpe differences, a 40-draw placebo |
| `simulator.py`, `stages/s7.py`, `s8.py` | the drawdown-mandate simulator on the training path and the 500-mandate sweep |
| `stages/s9.py` | retains and validates the historical reports when the counter already records a look; only an unscored hold-out enters the scoring path; the consistency check uses a training-based calculation |
| `lib/holdout.py` | the look counter used by s9 |
| `candidates/common.py`, `prereg.py`, `run.py`, `fetch.py`, `splice_check.py`, `audit_c18.py` | the candidate designs, the design dispersions (computed from the same data the tests then use), the eight tests, the candidate data, the splice check for the four energy contracts, and the post-hoc C18 audit |

</details>

The saved run used Python 3.9.6. The configured fetch paths use public endpoints without an API-key argument; compatibility across other Python versions has not been established here.
