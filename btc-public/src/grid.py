"""The as-of grid: a five-minute panel where nothing appears before it was knowable.

Two rules do most of the work here.

A value may sit at time *t* only if it was publicly knowable at *t*. Every source
carries an `asof_time` -- the moment it became knowable, which is not the moment it
describes -- and joins happen on that, never on event time.

Every join has a **tolerance**. Without one, an as-of join does not produce a gap when
a feed stops updating, it produces a flat line, and a flat line looks like data. That
is not hypothetical: the exchange publishes its monthly archive several weeks after
month end, and an unbounded join carried a stale July price across the whole of
August before the tolerance was added.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config

MANIFEST = {}


def _join(grid, name, cols, tolerance, rename=None, event_col=None):
    """Backward as-of join of one source, plus its staleness column."""
    p = config.RAW / f"{name}.parquet"
    if not p.exists():
        print(f"  [warn] {name} missing, skipping")
        return grid
    src = pd.read_parquet(p)
    src["asof_time"] = pd.to_datetime(src["asof_time"], utc=True)
    src = src[["asof_time"] + list(cols)].dropna(subset=["asof_time"])
    src = src.sort_values("asof_time")
    src[f"_asof_{name}"] = src["asof_time"]

    out = pd.merge_asof(
        grid.reset_index().rename(columns={"index": "ts"}), src,
        left_on="ts", right_on="asof_time", direction="backward",
        allow_exact_matches=True, tolerance=pd.Timedelta(tolerance),
    ).set_index("ts").drop(columns=["asof_time"])

    ren = rename or {}
    out = out.rename(columns=ren)
    out[f"tsu_{name}"] = (out.index - out[f"_asof_{name}"]).dt.total_seconds() / 60.0
    for c in cols:
        MANIFEST[ren.get(c, c)] = {"source": name, "column": c,
                                   "event_column": event_col,
                                   "tolerance_min": pd.Timedelta(tolerance).total_seconds() / 60}
    return out.drop(columns=[f"_asof_{name}"])


def build():
    start = pd.Timestamp(config.GRID_START, tz="UTC") + pd.Timedelta(config.GRID_FREQ)
    end = pd.Timestamp(config.GRID_END, tz="UTC")
    g = pd.DataFrame(index=pd.date_range(start, end, freq=config.GRID_FREQ, name="ts"))

    m15, h1, h6 = "15min", "1h", "6h"
    one_bar = config.GRID_FREQ

    g = _join(g, "futures_klines_5m",
              ["open", "high", "low", "close", "volume", "quote_volume", "trades",
               "taker_buy_base"], m15, event_col="open_time")
    g = _join(g, "premium_5m", ["premium_index"], m15, event_col="open_time")
    # Funding settles every 8h and a settled rate is legitimately the live value
    # until the next settlement, so its tolerance is the settlement interval plus slack.
    g = _join(g, "funding", ["funding_rate"], "9h", event_col="funding_time")
    g = _join(g, "metrics_5m",
              ["sum_open_interest", "sum_open_interest_value",
               "sum_taker_long_short_vol_ratio"], h1,
              rename={"sum_open_interest": "oi", "sum_open_interest_value": "oi_value",
                      "sum_taker_long_short_vol_ratio": "taker_ls"},
              event_col="create_time")
    g = _join(g, "dvol_1h", ["dvol"], h6, event_col="bar_start")
    # Tick-derived columns exist only on the free tier's sample days. A one-bar
    # tolerance stops the join forward-filling a 2020 sample day across all of 2020.
    g = _join(g, "liq_5m", ["liq_long", "liq_short", "liq_count"], one_bar,
              event_col="ts")
    g = _join(g, "book_5m", ["spread", "depth"], one_bar, event_col="ts")

    g = derive(g)
    g = add_targets(g)
    return g[g["close"].notna()]


def derive(g):
    px = g["close"]
    g["ret_5m"] = np.log(px).diff()
    g["ret2"] = g["ret_5m"] ** 2
    g["vwap_bar"] = g["quote_volume"] / g["volume"].replace(0, np.nan)

    # Windows end at the current bar, which is knowable at ts by construction of the
    # grid -- the bar has closed. That is not the same as using the current *target*.
    for name, bars in [("1h", config.H1), ("4h", config.H4), ("24h", 288)]:
        g[f"rv_{name}"] = np.sqrt(g["ret2"].rolling(bars, min_periods=max(2, bars // 4)).sum())
        g[f"ret_{name}"] = np.log(px).diff(bars)

    g["oi_notional"] = g["oi"] * px
    g["oi_vol_ratio"] = g["oi_notional"] / g["quote_volume"].rolling(288, min_periods=72).sum()
    for w, nm in [(config.H1, "1h"), (config.H4, "4h")]:
        g[f"liq_long_{nm}"] = g["liq_long"].rolling(w, min_periods=w // 4).sum()
        g[f"liq_short_{nm}"] = g["liq_short"].rolling(w, min_periods=w // 4).sum()

    g["hour"] = g.index.hour
    g["dow"] = g.index.dayofweek
    g["us_hours"] = ((g.index.hour >= 13) & (g.index.hour < 21)).astype(int)
    g["weekend"] = (g.index.dayofweek >= 5).astype(int)
    g["asia"] = (g.index.hour < 8).astype(int)
    return g


def _forward(series, bars, kind="sum"):
    """A target over (t, t+bars], strictly forward, never touching bar t.

    Written by reversing rather than with a shifted rolling window because the
    off-by-one there is invisible and fatal.
    """
    rev = series[::-1]
    return getattr(rev.rolling(bars, min_periods=bars), kind)()[::-1].shift(-1)


def add_targets(g):
    for name, bars in config.HORIZONS.items():
        fwd = _forward(g["ret2"], bars, "sum")
        g[f"tgt_logrv_{name}"] = np.log(np.sqrt(fwd).replace(0, np.nan))
    b = config.H4
    hi = _forward(g["high"], b, "max")
    lo = _forward(g["low"], b, "min")
    g["tgt_mfe_4h"] = hi / g["close"] - 1.0
    g["tgt_mae_4h"] = lo / g["close"] - 1.0
    return g


def main():
    config.GRID_DIR.mkdir(parents=True, exist_ok=True)
    g = build()
    g.reset_index().to_parquet(config.GRID_DIR / "grid.parquet", index=False)
    (config.GRID_DIR / "asof_manifest.json").write_text(json.dumps(MANIFEST, indent=2))
    stale = {c: float(g[c].max()) for c in g.columns if c.startswith("tsu_")}
    print(f"grid: {len(g):,} rows x {g.shape[1]} cols, "
          f"{g.index.min()} -> {g.index.max()}")
    print(f"  worst staleness by source, minutes: "
          f"{ {k.replace('tsu_', ''): round(v) for k, v in stale.items()} }")


if __name__ == "__main__":
    main()
