"""The as-of gate: the most important test here.

The grid is only allowed to hold a value at time `t` if that value was publicly
knowable at `t`. This does not trust the grid builder -- it rebuilds sampled values
straight from the raw sources by an independent path and compares.

Run standalone; the exit code is the gate result.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config


def load():
    grid = pd.read_parquet(config.GRID_DIR / "grid.parquet")
    grid["ts"] = pd.to_datetime(grid["ts"], utc=True)
    manifest = json.loads((config.GRID_DIR / "asof_manifest.json").read_text())
    return grid.set_index("ts").sort_index(), manifest


def close_enough(a, b, tol=1e-6):
    if pd.isna(a) and pd.isna(b):
        return True
    if pd.isna(a) or pd.isna(b):
        return False
    return abs(float(a) - float(b)) <= tol * max(abs(float(a)), abs(float(b)), 1.0)


def run(n=20, seed=config.RANDOM_SEED, verbose=True):
    grid, manifest = load()
    sources = sorted({m["source"] for m in manifest.values()})
    cache = {}
    for src in sources:
        p = config.RAW / f"{src}.parquet"
        if p.exists():
            d = pd.read_parquet(p)
            d["asof_time"] = pd.to_datetime(d["asof_time"], utc=True)
            cache[src] = d.sort_values("asof_time").reset_index(drop=True)

    rng = np.random.default_rng(seed)
    eligible = grid.index[grid.index >= grid.index.min() + pd.Timedelta(days=30)]
    stamps = pd.DatetimeIndex(sorted(rng.choice(eligible, size=min(n, len(eligible)),
                                                replace=False)))

    failures, checked = [], 0
    for col, meta in manifest.items():
        if col not in grid.columns or meta["source"] not in cache:
            continue
        raw, tol = cache[meta["source"]], meta.get("tolerance_min")
        for ts in stamps:
            sel = raw["asof_time"] <= ts
            if tol is not None:
                sel &= raw["asof_time"] >= ts - pd.Timedelta(minutes=tol)
            sub = raw.loc[sel, meta["column"]]
            want = sub.iloc[-1] if len(sub) and pd.notna(sub.iloc[-1]) else np.nan
            checked += 1
            if not close_enough(grid.at[ts, col], want):
                failures.append((col, str(ts), grid.at[ts, col], want))

    # Targets must be unknowable at their own timestamp: the last bars of the sample
    # have no future left, so a forward target there must be null.
    target_fail = []
    for col, bars in [("tgt_logrv_1h", config.H1), ("tgt_logrv_4h", config.H4)]:
        if col in grid.columns and grid[col].iloc[-bars:].notna().any():
            target_fail.append(col)

    passed = not failures and not target_fail
    if verbose:
        print(f"as-of: {checked} column-timestamp checks over {len(stamps)} "
              f"timestamps, {len(failures)} failures")
        print(f"forward-target direction: {len(target_fail)} failures")
        for f in failures[:5]:
            print(f"  {f}")
        print("PASS" if passed else "FAIL")
    return {"checks": checked, "failures": failures, "target_failures": target_fail,
            "passed": passed, "n_timestamps": len(stamps)}


if __name__ == "__main__":
    sys.exit(0 if run()["passed"] else 1)
