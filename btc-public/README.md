# BTC forced-flow: liquidation maps, volatility forecasting, and what you can trade

Part one of three. Part two: futures trend, carry and value (`../futures-public`) · Part three: equities (in progress)

The question this project set out to answer: **leveraged perpetual-futures positions
are forced to exit at prices you can compute in advance — can you locate that flow,
and is it worth anything?**

The map locates the flow. Reconstructed liquidation levels sit where real forced
selling actually happens: on the days with tick-level liquidation prints, mapped
price levels carried 5.3x the liquidation notional of unmapped ones, and every
cluster touch coincided with real forced selling. But price does not respond to those
levels in any way a trader can capture — five pre-registered framings, the last of
them adequately powered, all returned effects smaller than a round trip. The same
flow reconstruction *does* forecast volatility, in both sealed hold-out blocks at
both horizons: comfortably against a GARCH(1,1) baseline, by a few points of R²
against a horizon-matched HAR-RV, and losing to that HAR on QLIKE in three of the
four sealed cells. That is the one result here that survived, and it is worth less
than the cheapest instrument that could express it.

Read [`WRITEUP.md`](WRITEUP.md) for the story end to end, or
[`reports/SUMMARY.md`](reports/SUMMARY.md) for the findings and the numbers alone.

## Running it

```bash
pip install -r requirements.txt
python run.py
```

The pipeline fetches its own data from public endpoints into `data/` (gitignored,
several GB, a few hours on a cold start) and writes results to `reports/results/`.
Stages skip themselves if their output already exists, so an interrupted run
resumes. `--force-from <stage>` re-runs from a stage onward, `--only <stage>` runs
one. Any stage that cannot verify its own output halts the run rather than passing
bad data downstream.

No credentials are needed. Every source used here is public and keyless, and
nothing in the code reads an environment variable or a key file.

## What each module does

| Module | What it does |
| --- | --- |
| `config.py` | Every constant: date ranges, horizons, hold-out block bounds, the leverage ladder, bucket width, cost band. Nothing is hard-coded elsewhere. |
| `src/fetch.py` | Pulls klines, open interest, funding, premium index, DVOL, liquidation prints, book snapshots and Deribit option fills from public endpoints. |
| `src/grid.py` | Builds the 5-minute as-of grid. Every value enters at the time it was publicly knowable, every join carries a staleness tolerance, and every joined column gets a `tsu_` companion recording how old it is — so a dead feed shows up as null, not as a flat line. |
| `src/liquidation_map.py` | Turns ΔOI × sign(Δprice) into leveraged cohorts, walks them down a leverage ladder to their forced-exit prices, and bins the result into a decaying histogram of expected forced flow per price bucket. The leverage weights are calibrated against real liquidation prints on the log1p scale. |
| `src/vol_model.py` | Model A. Ridge on map-derived and market features, walk-forward monthly on a trailing year, scored against an analytic multi-step GARCH(1,1) forecast at 1h and 4h. |
| `src/har.py` | The benchmark that matters. HAR-RV in two specifications — Corsi's day/week/month cascade, and the same cascade shifted to hour/day/week for these horizons — fitted on Model A's schedule and scored on the same rows. Reads Model A's stored predictions rather than refitting, so no hold-out counter moves. |
| `src/event_study.py` | The map's ground truth (do touches coincide with real prints?) and the five pre-registered framings of "does price move through a cluster?", each with its placebo and its MDE. |
| `src/instrument.py` | Prices eight option structures plus an idealised variance swap against the volatility forecast, to find the cheapest instrument that could express it. |
| `src/economics.py` | Turns the forecast's improvement over HAR into expected basis points per trade and puts it beside each structure's measured cost, so the ceiling reads economically and not only as a power calculation. Every assumption it makes favours the trade. |
| `src/audit.py` | The machinery the claims rest on: sealed-block masks, purge/embargo, block bootstrap, label-shuffle placebos, the randomisation test, and the MDE calculator. |
| `tests/test_asof.py` | Rebuilds sampled grid values independently from the raw sources and checks forward-target direction. Runs as a pipeline stage, not a side quest. |
| `tests/test_documents.py` | Checks every number quoted in this README, in `WRITEUP.md` and in `SUMMARY.md` against `reports/results/`, so the prose cannot drift from the run. Figures it cannot reproduce — those belonging to components the public cut does not contain — are named rather than skipped. |

## Hold-out discipline

Two sealed blocks and a live forward window are held out of everything. Each
sealed-block number in `SUMMARY.md` carries the number of times that block was
looked at to produce it. The live forward window was never opened.

## Scope

This repository is a consolidation of a larger private project. It reproduces four
results and nothing else. The variant mining, the direction model, the calendar and
term-structure tests, the daily model and the news pipeline are not here — they are
described in `SUMMARY.md` only where they bear on what survived.
