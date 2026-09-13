# BTC forced-flow: liquidation map, price response, volatility forecast

Part one of three. Part two: futures trend, carry and value (`../futures-public`) · Part three: equities (in progress)

**Start here**

- Begin with the [measurements and dispositions](WRITEUP.md#what-the-measurements-are), then follow [one cluster touch](WRITEUP.md#one-touch-from-map-state-to-measurement) through the calculation.
- Read [event_study.json](reports/results/event_study.json) for locator/price-response outputs, [har.json](reports/results/har.json) for the forecast comparison, and [instrument.json](reports/results/instrument.json) / [economics.json](reports/results/economics.json) for option measurements and conditional formula outputs.
- Those JSONs are tracked and readable on a fresh clone. Default `python run.py` attempts to fetch/build missing `data/`, runs the as-of and document checks, and skips the tracked result JSONs; it does not regenerate those estimates by default.
- Recomputing with `--only` or `--force-from` needs the upstream data; the archived option-fill file is not reproducible by the fetch code as written. See [Running it](#running-it).

The claim ledger records the 2026-09-12 audit and the presentation provenance added on 2026-09-13. The write-up reports the retained measurements, their limitations and the withdrawn wording.

## What the repository contains

A liquidation map built from public open interest, price and funding on a five-minute grid; five framings of "does price respond to the map?", each with a hypothesis recorded privately before its result commit (the public statistics for framing 1 are not the registered statistic); a 24-feature ridge volatility model compared against GARCH(1,1) and two HAR-RV specifications; and eight costed option structures.

The measurements, with their intervals and what could not be established, are in `WRITEUP.md`. In summary of the locator: in the touch bar and the next three five-minute bars, on print-covered days, a liquidation print somewhere in the market occurred for 100 % of cluster touches (n 36), 99.9 % of mid touches (n 908) and 92.4 % of empty touches (n 5,164). Of the price response: continuation after unpredicted prints, print unit, day-block bootstrap: at 30 min −0.3 [−4.8, 4.0]; at 15 min −0.9 [−3.5, 1.7]; at 60 min +3.8 [−1.5, 10.3] bps. Of the volatility comparison: point R² differences over the hour/day/week HAR of +0.024/+0.026/+0.038/+0.051 on 87,552 and 87,264 evaluated rows per block (304 and 303 complete-day equivalents out of 365); no uncertainty was computed; on QLIKE the intraday HAR beats Model A in three of the four sealed cells.

## Running it

```bash
pip install -r requirements.txt
python run.py
```

The fetch code uses public keyless endpoints; the option-fill file in the archive was not produced by that code as written. Default `run.py` runs skip stages whose artefacts exist; `--only` and `--force-from` recompute them. `data/` is gitignored; `reports/results/` is tracked. 52 selected literal phrases in this README and `WRITEUP.md` are checked for presence against `reports/results/` by `tests/test_documents.py`, without validating their interpretation.

## What each module does

| Module | What it does |
| --- | --- |
| `config.py` | Constants: date ranges, horizons, sealed-block bounds, the leverage ladder, bucket width, the 3.5-day map half-life, the 10 bps band. |
| `src/fetch.py` | Fetches klines, open interest, funding, premium index, DVOL, liquidation prints, book snapshots and Deribit option fills from public endpoints. |
| `src/grid.py` | Builds the five-minute grid with as-of joins, tolerances and staleness columns. |
| `src/liquidation_map.py` | Infers leveraged cohorts from open-interest changes, walks them down a leverage ladder to forced-exit prices, and accumulates a histogram with a 3.5-day half-life. The leverage mix is calibrated once on training print days (log-scale correlation 0.30) and applied to all periods, including the 2022 sealed block. |
| `src/vol_model.py` | The ridge model, refitted monthly on a trailing year; its GARCH and map-feature inputs are fitted once on all training rows (2020-09 to 2025-08) and supplied to every month, including the 2022 sealed block. |
| `src/har.py` | HAR-RV in two specifications (day/week/month; hour/day/week), fitted on training rows and scored on the sealed outcomes; three trailing realised-volatility features, the shortest a trailing one-day average ending at the current bar. |
| `src/event_study.py` | The locator statistics and the five framings. |
| `src/instrument.py` | Eight option structures priced from amount-weighted buy-flagged and sell-flagged fills over the four-hour entry window, with missing sides imputed from the other leg's half-spread. |
| `src/economics.py` | Multiplies √ΔR² by √(2/π) and each structure's stored dispersion; its assumptions are listed in `reports/results/economics.json` and in `WRITEUP.md`. |
| `src/audit.py` | Masks, purge, block bootstrap, label placebo, block permutation, MDE calculator. |
| `tests/test_asof.py` | At 20 sampled timestamps, checks that grid values match the raw files under the raw files' own as-of timestamps and tolerances, and that forward targets are null at the series tail. |
| `tests/test_documents.py` | Checks selected literal phrases in this README and `WRITEUP.md` against `reports/results/`. |

## Sealed blocks

The repository has no look counter; the "looks" values in `reports/results/` are literals written by the code. The sealed blocks have been scored repeatedly: 2026-09-02 (twice), 2026-09-06, 2026-09-07 and 2026-09-12 (twice). The window after 2026-09-01 contains no data and has not been scored. The locator statistics were computed on all 73 OI-covered print days, of which 26 fall inside the sealed blocks including their ±3-day purge.

## Scope

This repository re-implements four analyses of a private project; its figures differ from the private figures. For v2 through v12 of that project, a commit recording the hypothesis precedes the commit recording the result (author-dated, local, unpushed); for v13, hypothesis, code and result were committed together.
