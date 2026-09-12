"""s0b: turn Yahoo's front-month splices into something a backtest can use.

Yahoo's `=F` series is the raw front contract, switched to the next contract at
expiry, with no adjustment. On each switch day the close-to-close change contains
the calendar spread between the two contracts. Nobody earned that, and in contango
it is positive at every roll, which is exactly what a trend follower is built to
find. This module locates the switch days and removes them.

  1. Expiry dates come from the exchange rules (rolls.py). The switch day is found
     per event inside a narrow window around expiry, using the one column that
     identifies the displayed contract: volume. A dying contract trades a few
     hundred lots; the day Yahoo switches, volume jumps by an order of magnitude.
     Where a market's volume is not usable, the switch is rule expiry plus a constant
     offset chosen by the |price change| anomaly over six candidate offsets.
  2. The whole switch day is dropped. The roll-day open is not reliably the new
     contract's (ES prints the old contract's open with the new contract's close),
     so nothing intraday is kept.
  3. From the neutralised daily changes two adjusted price series are rebuilt, one
     additive (Panama) and one multiplicative (ratio), both anchored to today's
     actual price. Signals run on Panama by default and on ratio as the SPEC §4
     sensitivity check.

P&L is always dollars per contract (price change * multiplier), never percent of a
price that can be zero or negative -- CL settled at -37.63 in April 2020.
"""

import numpy as np
import pandas as pd

import config
from stages import rolls

SIGMA_WINDOW = 60
OFFSETS = range(-2, 4)          # candidate switch days relative to rule expiry
BAD_PRINT_Z = 50.0              # only a shifted decimal moves fifty sigmas and comes back
DEFAULT_OFFSET = 1              # Yahoo switches the business day after expiry
OVERRIDE_MARGIN = 2.0           # a detected offset replaces +1 only if it beats it by this much
DOUBLE_BLANK = ("ES", "NQ", "YM")   # expiry-day close is a computed value, not a settlement


def load_raw(name):
    d = pd.read_parquet(config.RAW / f"{name}.parquet")
    d = d[d.index >= config.START].copy()
    bad = (d["close"] <= 0) & ~((name == "CL") & (d.index == "2020-04-20"))
    d.loc[bad, ["open", "high", "low", "close"]] = np.nan
    d.attrs["bad_prints"] = clean_bad_prints(d)
    return d


def clean_bad_prints(d):
    """Remove closes that are a shifted decimal: a move of more than fifty sigmas
    that is undone the next day. Real crashes are not this large (CL in April 2020
    was thirty-seven sigmas and is kept). Returns the dates removed."""
    dp = d["close"].diff()
    sigma = dp.rolling(SIGMA_WINDOW, min_periods=40).std().shift(1)
    z = dp / sigma
    revert = (-dp.shift(-1) / dp).between(0.7, 1.3)
    bad = d.index[(z.abs() > BAD_PRINT_Z) & revert]
    d.loc[bad, ["open", "high", "low", "close"]] = np.nan
    return list(bad.strftime("%Y-%m-%d"))


def zscores(d):
    dp = d["close"].diff()
    sigma = dp.rolling(SIGMA_WINDOW, min_periods=40).std().shift(1)
    return dp.abs() / sigma, dp / sigma


def next_trading_day(index, ts):
    pos = index.searchsorted(ts)
    return index[pos] if pos < len(index) else None


def offset_scan(d, exp, z):
    """Constant offset from rule expiry at which |change|/sigma is most anomalous."""
    base = z.mean()
    rows = {}
    for off in OFFSETS:
        days = [next_trading_day(d.index, e + pd.offsets.BDay(off)) for e in exp]
        days = pd.DatetimeIndex([x for x in days if x is not None])
        zz = z.reindex(days).dropna()
        if len(zz) < 20:
            continue
        rows[off] = ((zz.mean() - base) / (z.std() / np.sqrt(len(zz))), zz.mean() - base, len(zz))
    tbl = pd.DataFrame(rows, index=["zscore", "excess", "n"]).T
    return tbl


def stitch_one(name, d):
    spec = config.UNIVERSE[name]
    exp = rolls.expiries(name, spec["months"], d.index.min(), d.index.max())
    z, zs = zscores(d)
    tbl = offset_scan(d, exp, z)
    best = int(tbl["zscore"].idxmax())
    z_best, z_def = float(tbl.loc[best, "zscore"]), float(tbl.loc[DEFAULT_OFFSET, "zscore"])
    offset = best if (z_best >= 3.0 and z_best - z_def >= OVERRIDE_MARGIN) else DEFAULT_OFFSET
    offsets = [0, offset] if name in DOUBLE_BLANK else [offset]
    days = []
    for off in offsets:
        days += [x for x in (next_trading_day(d.index, e + pd.offsets.BDay(off)) for e in exp) if x is not None]
    days = pd.DatetimeIndex(days).unique().sort_values()
    days = days[days.isin(d.index)]

    dp = d["close"].diff()
    yrs = (d.index.max() - d.index.min()).days / 365.25
    gap = dp.reindex(days).dropna()
    zz = z.reindex(days).dropna()
    info = dict(n_expiries=len(exp), n_rolls=len(days), offset=offset, double=name in DOUBLE_BLANK,
                z_at_offset=round(float(tbl.loc[offset, "zscore"]), 1), z_best=round(z_best, 1), best_offset=best,
                excess_sigma=round(float(zz.mean() - z.mean()), 2), signed_sigma=round(float(zs.reindex(days).mean()), 2),
                gap_pct_yr=round(100 * gap.sum() / yrs / d["close"].abs().mean(), 2),
                share_positive=round(float((gap > 0).mean()), 2), bad_prints=",".join(d.attrs.get("bad_prints", [])),
                offsets=" ".join(f"{o:+d}:{r.zscore:.1f}" for o, r in tbl.iterrows()))
    return info, days


def neutralise(d, days, window=0, early=False):
    """Daily change with the switch day dropped. window>0 also drops `window` days
    either side (early=True: only before -- a trader who rolls early never holds
    the last days of the expiring contract)."""
    dp = d["close"].diff().copy()
    dp.loc[days] = np.nan
    if window > 0:
        pos = d.index.get_indexer(days)
        for p in pos:
            dp.iloc[max(p - window, 0): p + (0 if early else window) + 1] = np.nan
    return dp


def adjusted_prices(close, dp):
    """Panama (additive) and ratio (multiplicative) series from neutralised changes,
    anchored to the last actual price so the current contract is unadjusted. A
    dropped day contributes zero change to the level."""
    dpf = dp.fillna(0.0)
    future = dpf[::-1].cumsum()[::-1] - dpf          # sum of changes strictly after t
    panama = close.iloc[-1] - future
    prev = close.shift(1)
    ret = (dp / prev).where(prev > 0, 0.0).fillna(0.0).clip(lower=-0.95)
    lg = np.log1p(ret)
    future_lg = lg[::-1].cumsum()[::-1] - lg
    ratio = close.iloc[-1] / np.exp(future_lg)
    panama[close.isna()] = np.nan
    ratio[close.isna()] = np.nan
    return panama, ratio


def run():
    config.STAGES.mkdir(parents=True, exist_ok=True)
    keys = ["raw", "w0", "w1", "w3", "early3", "px_raw", "px_panama", "px_ratio"]
    diag, frames = {}, {k: {} for k in keys}
    for name in config.UNIVERSE:
        d = load_raw(name)
        info, days = stitch_one(name, d)
        diag[name] = info
        mult = config.UNIVERSE[name]["mult"]
        w0 = neutralise(d, days)
        frames["raw"][name] = d["close"].diff() * mult
        frames["w0"][name] = w0 * mult
        frames["w1"][name] = neutralise(d, days, window=1) * mult
        frames["w3"][name] = neutralise(d, days, window=3) * mult
        frames["early3"][name] = neutralise(d, days, window=3, early=True) * mult
        pan, rat = adjusted_prices(d["close"], w0)
        frames["px_raw"][name] = d["close"]
        frames["px_panama"][name] = pan
        frames["px_ratio"][name] = rat
        pd.DataFrame({"roll_day": days}).to_parquet(config.STAGES / f"s0_rolls_{name}.parquet")
    for k, v in frames.items():
        pd.DataFrame(v).sort_index().to_parquet(config.STAGES / f"s0_{k}.parquet")
    diag = pd.DataFrame(diag).T
    diag.to_parquet(config.STAGES / "s0_roll_diag.parquet")
    return diag


if __name__ == "__main__":
    pd.set_option("display.width", 250)
    print(run().to_string())
