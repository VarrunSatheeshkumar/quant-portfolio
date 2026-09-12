"""s0c: the as-of grid.

One row per business day. A market's own bar dated D is knowable at D's close and
sits on row D. Every reference series (spot FX, cash index, yield) sits on row D
with the value dated D-1 (config.REF_LAG_DAYS) -- see DECISIONS.md. The grid
carries, for each column, the asof_time of the row it was taken from, so the
as-of test can check the rule on random timestamps rather than trust it.
"""

import numpy as np
import pandas as pd

import config


def business_days(end):
    return pd.bdate_range(config.START, end, name="date")


def build():
    px = pd.read_parquet(config.STAGES / "s0_px_raw.parquet")
    idx = business_days(px.index.max())
    refs, ref_asof = {}, {}
    for name in config.REFERENCES:
        r = pd.read_parquet(config.RAW / f"{name}.parquet")["close"]
        r = r[r > 0].dropna()
        r = r[~r.index.duplicated(keep="last")].sort_index()
        # the value knowable on grid day D is the last one dated <= D - lag
        shifted = r.copy()
        shifted.index = shifted.index + pd.offsets.BDay(config.REF_LAG_DAYS)
        aligned = shifted.reindex(idx, method="ffill", tolerance=pd.Timedelta(days=10))
        refs[name] = aligned
        src_dates = pd.Series(r.index, index=r.index + pd.offsets.BDay(config.REF_LAG_DAYS))
        ref_asof[name] = src_dates.reindex(idx, method="ffill", tolerance=pd.Timedelta(days=10))
    refs = pd.DataFrame(refs)
    ref_asof = pd.DataFrame(ref_asof)
    # ZT has no 2-year yield on Yahoo: linear interpolation in maturity between 13w and 5y
    refs["ZT2Y"] = refs["IRX"] + (refs["FVX"] - refs["IRX"]) * (2.0 - 0.25) / (5.0 - 0.25)
    ref_asof["ZT2Y"] = ref_asof[["IRX", "FVX"]].max(axis=1)
    config.GRID.mkdir(parents=True, exist_ok=True)
    refs.to_parquet(config.GRID / "refs.parquet")
    ref_asof.to_parquet(config.GRID / "refs_asof.parquet")
    for k in ["raw", "w0", "w1", "w3", "early3", "px_raw", "px_panama", "px_ratio"]:
        f = pd.read_parquet(config.STAGES / f"s0_{k}.parquet").reindex(idx)
        f.to_parquet(config.GRID / f"{k}.parquet")
    return refs


if __name__ == "__main__":
    print(build().tail().to_string())
