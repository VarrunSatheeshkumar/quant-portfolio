"""HAR-RV: the benchmark that actually matters.

GARCH is the textbook baseline; HAR-RV (Corsi 2009) is the one the realised-volatility
literature actually uses, and it usually wins, because it feeds on realised variance
directly instead of inferring it from squared returns one step at a time. Beating
GARCH and losing to HAR would mean the map features add nothing a heterogeneous
autoregression of past realised variance does not already carry.

Specification is the standard one: forward log realised volatility regressed on
trailing log realised volatility over a day, a week and a month, fitted by ordinary
least squares. Same walk-forward schedule as Model A -- monthly refit on a trailing
twelve months, with the same purge -- so the two are scored on identical rows.

**On look counts.** This module does not open the sealed blocks again. Model A's
sealed-block predictions are read from the artifact the counted look already
produced, and HAR is fitted on training rows only. The sealed-block outcomes used to
score HAR are the same values that single look already revealed, and HAR is a fixed,
pre-specified benchmark with nothing tuned against them, so no selection is being
conditioned on sealed data. It is still a second statistic computed on those
outcomes, and a reader who counts strictly should know that is what happened.
"""

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config
from src import audit
from src.vol_model import build_panel, fit_predict, qlike, r2, slices

warnings.filterwarnings("ignore")

# Day, week, month in 5-minute bars -- Corsi's components, unchanged.
HAR_WINDOWS = {"d": 288, "w": 2016, "m": 8640}
# The same cascade shifted down one scale. Corsi built HAR for daily forecasts; at a
# one-hour horizon a day is already the long component, and a benchmark whose
# shortest input is 288 bars stale is being handicapped rather than tested. Both are
# reported, and the intraday one is the harder benchmark.
HAR_INTRADAY = {"h": 12, "d": 288, "w": 2016}
SPECS = {"har_dwm": HAR_WINDOWS, "har_intraday": HAR_INTRADAY}


def har_features(df, windows, tag):
    """Trailing log realised volatility over each component window.

    The rolling sum ends at bar t inclusive: `ret2` at t is the squared return
    realised over the bar ending at t, so it is known at t. The target starts at
    t+1. No window touches its own target.
    """
    out = pd.DataFrame(index=df.index)
    for k, n in windows.items():
        s = df["ret2"].rolling(n, min_periods=n // 2).sum()
        out[f"{tag}_log_rv_{k}"] = np.log(np.sqrt(s).replace(0, np.nan))
    return out


def walk_forward(df, cols, y, train_ok):
    """Model A's schedule and normalisation, a different feature set."""
    X = np.nan_to_num(df[cols].to_numpy(float), nan=0.0, posinf=0.0, neginf=0.0)
    have = df[cols].notna().all(axis=1).to_numpy()
    oos = pd.Series(np.nan, index=df.index)
    for tr, te in slices(df.index, train_ok & np.isfinite(y) & have, have):
        # alpha is a rounding-error ridge: this is OLS, with the training-window
        # normalisation Model A uses so the two are treated identically.
        oos.iloc[np.nonzero(te)[0]] = fit_predict(X, y, tr, te, alpha=1e-6)
    return oos.to_numpy()


def main():
    df = build_panel()
    cols = {}
    for tag, windows in SPECS.items():
        f = har_features(df, windows, tag)
        df = df.join(f)
        cols[tag] = list(f.columns)
    train_ok = audit.training_mask(df.index)

    # Model A comes from the artifact, not from a refit: these are the predictions
    # the counted look already scored.
    ma = pd.read_parquet(config.INTERIM / "model_a.parquet")
    ma["ts"] = pd.to_datetime(ma["ts"], utc=True)
    ma = ma.set_index("ts").reindex(df.index)

    scores = {}
    for name in config.HORIZONS:
        y = df[f"tgt_logrv_{name}"].to_numpy(float)
        preds = {tag: walk_forward(df, cols[tag], y, train_ok) for tag in SPECS}
        mdl = np.log(ma[f"sigma_hat_{name}"].to_numpy(float))
        gch = np.log(ma[f"garch_{name}"].to_numpy(float))

        row = {}
        for label, mask in [
                ("train", train_ok),
                ("sealed_2022", audit.in_block(df.index, config.SEALED_2022)),
                ("sealed_recent", audit.in_block(df.index, config.SEALED_RECENT))]:
            # Scored on rows where every forecast exists, so the comparison is like
            # for like rather than each model picking its own sample.
            ev = mask & np.isfinite(y) & np.isfinite(mdl) & np.isfinite(gch)
            for h in preds.values():
                ev = ev & np.isfinite(h)
            if ev.sum() < 500:
                continue
            cell = {
                "n": int(ev.sum()),
                "looks": 0 if label == "train" else 1,
                "r2_model": r2(y[ev], mdl[ev]),
                "r2_garch": r2(y[ev], gch[ev]),
                "qlike_model": qlike(np.exp(2 * y[ev]), np.exp(2 * mdl[ev])),
                "qlike_garch": qlike(np.exp(2 * y[ev]), np.exp(2 * gch[ev])),
            }
            for tag, h in preds.items():
                cell[f"r2_{tag}"] = r2(y[ev], h[ev])
                cell[f"gain_over_{tag}"] = r2(y[ev], mdl[ev]) - r2(y[ev], h[ev])
                cell[f"qlike_{tag}"] = qlike(np.exp(2 * y[ev]), np.exp(2 * h[ev]))
            row[label] = cell
        scores[name] = row

    beats = {tag: {h: all(v[f"gain_over_{tag}"] > 0 for v in row.values())
                   for h, row in scores.items()} for tag in SPECS}
    qbeats = {tag: {h: all(v["qlike_model"] < v[f"qlike_{tag}"] for v in row.values())
                    for h, row in scores.items()} for tag in SPECS}
    # The binding benchmark is whichever HAR does better on each cell.
    worst_gain = min(min(v[f"gain_over_{tag}"] for v in row.values())
                     for tag in SPECS for row in scores.values())
    # QLIKE disagrees with R2 here, and it disagrees in some cells and not others, so
    # the honest summary is a count of cells rather than a verdict.
    sealed_cells = [v for row in scores.values() for lab, v in row.items()
                    if lab != "train"]
    qlike_losses = {tag: sum(1 for v in sealed_cells
                             if v["qlike_model"] > v[f"qlike_{tag}"])
                    for tag in SPECS}
    payload = {"scores": scores,
               "model_beats_har_everywhere_r2": beats,
               "model_beats_har_everywhere_qlike": qbeats,
               "smallest_gain_over_any_har": float(worst_gain),
               "n_sealed_cells": len(sealed_cells),
               "sealed_cells_lost_on_qlike": qlike_losses,
               "windows_bars": {t: w for t, w in SPECS.items()},
               "note": "Sealed-block outcomes are the ones the single counted look "
                       "already revealed; HAR was fitted on training rows only and "
                       "no look counter is incremented."}

    config.RESULTS.mkdir(parents=True, exist_ok=True)
    json.dump(payload, open(config.RESULTS / "har.json", "w"), indent=2, default=float)

    for h, row in scores.items():
        for label, v in row.items():
            print(f"  {h} {label:14s} model {v['r2_model']:.4f} | HAR d/w/m "
                  f"{v['r2_har_dwm']:.4f} ({v['gain_over_har_dwm']:+.4f}) | "
                  f"HAR intraday {v['r2_har_intraday']:.4f} "
                  f"({v['gain_over_har_intraday']:+.4f}) | GARCH "
                  f"{v['r2_garch']:.4f}  (looks={v['looks']})")
    print(f"  beats every HAR on R2: {beats}")
    print(f"  beats every HAR on QLIKE: {qbeats}")
    print(f"  smallest gain over any HAR anywhere: {worst_gain:+.4f}")
    print(f"  sealed cells lost on QLIKE (of {len(sealed_cells)}): {qlike_losses}")


if __name__ == "__main__":
    main()
