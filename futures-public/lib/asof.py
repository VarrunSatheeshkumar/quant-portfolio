"""As-of grid construction.

The rule this enforces: a value may sit on the grid at time `t` only if it was
publicly knowable at `t`. Every source carries an `asof_time` -- the moment the value
became knowable, which is not the moment it describes -- and joins happen on that.

Two things here are not optional and are the reason this module exists:

  * every join has a **tolerance**. Without one, an as-of join does not produce a gap
    when a feed stops updating, it produces a flat line, and a flat line looks like
    data. That failure mode is silent and it will survive every downstream check.
  * every joined source gets a `time_since_update` column, so a model can tell a
    fresh value from a stale one and so staleness itself can be tested as a confound.
"""

import numpy as np
import pandas as pd


def make_grid(start, end, freq, tz="UTC"):
    """Empty grid indexed by decision time -- the instant a bar has closed."""
    idx = pd.date_range(pd.Timestamp(start, tz=tz), pd.Timestamp(end, tz=tz),
                        freq=freq, name="ts")
    return pd.DataFrame(index=idx)


def asof_join(grid, src, cols, tolerance, rename=None, name=None):
    """Backward as-of join of one source onto the grid, plus its staleness column.

    `src` must carry an `asof_time` column. Rows are matched to the most recent
    source observation at or before each grid timestamp, and only within `tolerance`.
    """
    if "asof_time" not in src.columns:
        raise ValueError("source must carry an asof_time column")
    name = name or (src.attrs.get("name") or "src")
    s = src.copy()
    s["asof_time"] = pd.to_datetime(s["asof_time"], utc=True)
    s = s[["asof_time"] + list(cols)].dropna(subset=["asof_time"]).sort_values("asof_time")
    s[f"_asof_{name}"] = s["asof_time"]

    out = pd.merge_asof(
        grid.reset_index().rename(columns={"index": "ts"}),
        s, left_on="ts", right_on="asof_time",
        direction="backward", allow_exact_matches=True,
        tolerance=pd.Timedelta(tolerance),
    ).set_index("ts").drop(columns=["asof_time"])

    if rename:
        out = out.rename(columns=rename)
    out[f"tsu_{name}"] = (out.index - out[f"_asof_{name}"]).dt.total_seconds() / 60.0
    return out.drop(columns=[f"_asof_{name}"])


def spike_decay(grid_index, event_times, half_life_bars):
    """Sparse events enter as a decaying spike, never forward-filled.

    Forward-filling an event holds a non-zero level flat for weeks, which is a
    different claim from "something happened and its effect faded".
    """
    s = pd.Series(0.0, index=grid_index)
    pos = grid_index.searchsorted(pd.DatetimeIndex(event_times), side="left")
    pos = pos[(pos >= 0) & (pos < len(grid_index))]
    s.iloc[pos] = 1.0
    decay = 0.5 ** (1.0 / half_life_bars)
    return s.ewm(alpha=1 - decay, adjust=False).mean() * (1 / (1 - decay))


def forward_target(series, bars, kind="sum"):
    """A target over (t, t+bars], strictly forward and never touching bar t.

    Written this way rather than with shift(-bars) on a rolling window because the
    off-by-one there is invisible and fatal.
    """
    rev = series[::-1]
    agg = getattr(rev.rolling(bars, min_periods=bars), kind)()
    return agg[::-1].shift(-1)


def trailing_z(series, window, min_periods=None, shift=1):
    """Trailing z-score. `shift=1` keeps the current row out of its own scaler.

    Use shift=1 for any statistic used to normalise the same row. Use shift=0 only
    when the current row is genuinely knowable at decision time and you want it in.
    """
    mp = min_periods or max(2, window // 4)
    m = series.rolling(window, min_periods=mp).mean().shift(shift)
    sd = series.rolling(window, min_periods=mp).std().shift(shift).replace(0, np.nan)
    return (series - m) / sd
