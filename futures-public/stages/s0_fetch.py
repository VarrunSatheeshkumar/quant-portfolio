"""s0a: fetch every series from yfinance into data/raw/<name>.parquet.

Each row carries `asof_time`: the close of the session it describes, which is the
moment it became publicly knowable. Yahoo's daily bar is stamped with the session
date, so asof_time = that date. Re-runs skip anything fetched today.
"""

import time
import warnings
from datetime import date

import pandas as pd
import yfinance as yf

import config

warnings.filterwarnings("ignore")


def fetch_one(name, ticker):
    out = config.RAW / f"{name}.parquet"
    if out.exists() and date.fromtimestamp(out.stat().st_mtime) == date.today():
        return pd.read_parquet(out)
    d = yf.Ticker(ticker).history(period="max", auto_adjust=False)
    if d is None or len(d) == 0:
        raise RuntimeError(f"{name} ({ticker}): empty from yfinance")
    d = d[["Open", "High", "Low", "Close", "Volume"]].copy()
    d.columns = [c.lower() for c in d.columns]
    d.index = pd.DatetimeIndex(d.index.tz_localize(None).normalize(), name="date")
    d = d[~d.index.duplicated(keep="last")].sort_index()
    d = d[d.index <= config.END]
    d["asof_time"] = d.index
    d.to_parquet(out)
    time.sleep(0.5)          # yfinance rate budget; the previous project learnt this
    return d


def run():
    config.RAW.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, spec in list(config.UNIVERSE.items()) + list(config.REFERENCES.items()):
        d = fetch_one(name, spec["yf"])
        mult = spec.get("mult")
        last = float(d["close"].dropna().iloc[-1])
        rows.append(dict(name=name, ticker=spec["yf"], rows=len(d), start=d.index.min().date(),
                         end=d.index.max().date(), null_close=float(d["close"].isna().mean()),
                         last=last, notional=(last * mult if mult else None)))
    return pd.DataFrame(rows).set_index("name")


if __name__ == "__main__":
    print(run().to_string())
