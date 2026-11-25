"""The only route to prices. Estimators must call load_pre(); it asserts no date > CUTOFF.

Raw downloads are treated as untrusted data (CSV parsed with pandas only).
Rows dated on the download day are dropped for markets that had not closed at download time
(US equities/ETFs before 21:10 UTC, crypto before 00:00 UTC next day, FX before 22:00 UTC,
UK before 16:40 UTC), so an intraday print is never treated as a close.
"""
import datetime as dt

import numpy as np
import pandas as pd

from config import RAW, CUTOFF, PENCE, USD

_CACHE = {}
_NOISE = {"on": False, "seed": None}   # used by leakage test T4


def _ts():
    return (RAW / "prices_latest.txt").read_text().strip()


def download_time():
    return dt.datetime.strptime(_ts(), "%Y%m%dT%H%M%SZ")


def _provisional_mask(df):
    t = download_time()
    day = pd.Timestamp(t.date())
    if day not in df.index:
        return df
    df = df.copy()
    hm = t.hour * 60 + t.minute
    for c in df.columns:
        if c in ("BTC-USD", "ETH-USD"):
            closed = False                    # daily bar closes 00:00 UTC next day
        elif c == "GBPUSD=X":
            closed = hm >= 22 * 60
        elif c.endswith(".L") or c == "^FTSE":
            closed = hm >= 16 * 60 + 40
        else:
            closed = hm >= 21 * 60 + 10
        if not closed:
            df.loc[day, c] = np.nan
    return df


def _read(kind):
    key = (kind, _ts())
    if key not in _CACHE:
        df = pd.read_csv(RAW / f"prices_{_ts()}_{kind}.csv", index_col=0, parse_dates=True)
        df.index = pd.to_datetime(df.index).normalize()
        df = _provisional_mask(df)
        for c in df.columns:                  # pence -> pounds
            if c in PENCE:
                df[c] = df[c] / 100.0
        _CACHE[key] = df
    df = _CACHE[key].copy()
    if _NOISE["on"]:
        rng = np.random.default_rng(_NOISE["seed"])
        post = df.index > CUTOFF
        df.loc[post] = df.loc[post] * rng.uniform(0.5, 1.5, size=df.loc[post].shape)
    return df


def load(start=None, end=None, kind="adj", tickers=None):
    """Full access (for realised-period accounting only)."""
    df = _read(kind)
    if tickers is not None:
        df = df[list(tickers)]
    return df.loc[start:end]


def load_pre(start=None, end=CUTOFF, kind="adj", tickers=None):
    """Estimation access: hard cutoff."""
    end = pd.Timestamp(end)
    assert end <= CUTOFF, f"estimation end {end.date()} > cutoff {CUTOFF.date()}"
    df = load(start, end, kind, tickers)
    assert df.index.max() <= CUTOFF
    return df


def load_before(event_date, start=None, kind="adj", tickers=None, gap_sessions=10):
    """For the historical event study: data strictly before event - gap sessions. Not subject to
    the competition cutoff (historical events), but never touches the event window."""
    df = load(start, None, kind, tickers)
    idx = df.index[df.index < pd.Timestamp(event_date)]
    last = idx[-gap_sessions - 1] if len(idx) > gap_sessions else idx[0]
    out = df.loc[:last]
    assert out.index.max() < pd.Timestamp(event_date)
    return out


def to_gbp(df):
    """Convert USD columns to GBP using GBPUSD=X (USD per GBP), forward-filled onto df's index."""
    fx = load(kind="adj", tickers=["GBPUSD=X"])["GBPUSD=X"]
    fx = fx.reindex(df.index.union(fx.index)).ffill().reindex(df.index)
    out = df.copy()
    for c in out.columns:
        if c in USD:
            out[c] = out[c] / fx
    return out
