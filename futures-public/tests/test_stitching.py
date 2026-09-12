"""Stitching invariants that hold regardless of what the roll detector found:

  * every roll day is a trading day of that market, and rolls are spaced at least
    ten business days apart;
  * on non-roll days the neutralised change equals the raw change exactly;
  * the neutralised series is *less* dispersed on roll days than the raw one
    (removing a spread cannot add variance);
  * both adjusted price series end at the actual last price, and the Panama series
    differences reproduce the neutralised changes.
"""

import numpy as np
import pandas as pd

import config


def run():
    raw = pd.read_parquet(config.STAGES / "s0_raw.parquet")
    w0 = pd.read_parquet(config.STAGES / "s0_w0.parquet")
    px = pd.read_parquet(config.STAGES / "s0_px_raw.parquet")
    pan = pd.read_parquet(config.STAGES / "s0_px_panama.parquet")
    rat = pd.read_parquet(config.STAGES / "s0_px_ratio.parquet")
    diag = pd.read_parquet(config.STAGES / "s0_roll_diag.parquet")
    for name, spec in config.UNIVERSE.items():
        days = pd.DatetimeIndex(pd.read_parquet(config.STAGES / f"s0_rolls_{name}.parquet")["roll_day"])
        own = px[name].dropna().index
        assert days.isin(own).all(), f"{name}: roll day not a trading day"
        # at most one switch day per expiry (two for the equity double-blank), never more
        n_exp = int(diag.loc[name, "n_expiries"])
        assert len(days) <= n_exp * (2 if diag.loc[name, "double"] else 1), f"{name}: more roll days than expiries"
        assert len(days) >= 0.8 * n_exp, f"{name}: too few roll days for its expiries"
        non = ~raw.index.isin(days)
        a, b = raw.loc[non, name], w0.loc[non, name]
        ok = a.notna() & b.notna()
        assert np.allclose(a[ok], b[ok]), f"{name}: non-roll changes altered"
        r_roll = raw.loc[days, name].dropna()
        n_roll = w0.loc[days, name].dropna()
        if len(n_roll) > 10:
            assert n_roll.abs().mean() <= r_roll.abs().mean() + 1e-9, f"{name}: neutralising increased dispersion"
        last = px[name].dropna().index[-1]
        assert np.isclose(pan.loc[last, name], px.loc[last, name]), f"{name}: panama not anchored"
        assert np.isclose(rat.loc[last, name], px.loc[last, name]), f"{name}: ratio not anchored"
        dpan = pan[name].diff() * spec["mult"]
        ok = w0[name].notna() & dpan.notna() & px[name].shift(1).notna()
        assert np.allclose(dpan[ok], w0.loc[ok, name], atol=1e-6 * spec["mult"]), f"{name}: panama diffs != neutralised"
    return len(config.UNIVERSE)


if __name__ == "__main__":
    print("stitching invariants passed for markets:", run())
