"""As-of test: on 20 random grid timestamps per series, the value on the grid must
come from a source row whose asof_time is not after the grid date (own bars) or
not after the grid date minus the reference lag (references)."""

import numpy as np
import pandas as pd

import config


def run():
    rng = np.random.default_rng(config.SEED)
    px = pd.read_parquet(config.GRID / "px_raw.parquet")
    refs = pd.read_parquet(config.GRID / "refs.parquet")
    ref_asof = pd.read_parquet(config.GRID / "refs_asof.parquet")
    checked = 0
    for name in config.UNIVERSE:
        raw = pd.read_parquet(config.RAW / f"{name}.parquet")
        col = px[name].dropna()
        for d in rng.choice(col.index, 20, replace=False):
            d = pd.Timestamp(d)
            src = raw.loc[d]
            assert pd.Timestamp(src["asof_time"]) <= d, f"{name} {d}: asof after grid date"
            assert np.isclose(src["close"], col.loc[d]), f"{name} {d}: grid value not the source close"
            checked += 1
    for name in config.REFERENCES:
        col = refs[name].dropna()
        for d in rng.choice(col.index, 20, replace=False):
            d = pd.Timestamp(d)
            src_date = pd.Timestamp(ref_asof.loc[d, name])
            assert src_date <= d - pd.offsets.BDay(config.REF_LAG_DAYS), f"{name} {d}: reference not lagged"
            raw = pd.read_parquet(config.RAW / f"{name}.parquet")["close"]
            assert np.isclose(raw.loc[src_date], col.loc[d]), f"{name} {d}: reference value mismatch"
            checked += 1
    return checked


if __name__ == "__main__":
    print("asof checks passed:", run())
