"""Public data acquisition. Everything here is free and needs no credentials.

Sources, and why each is here:

  Binance archive   5-minute perpetual klines, premium index, funding, and the
                    5-minute metrics file that carries open interest -- the map is
                    built from the change in open interest, so it cannot start before
                    that file does (2020-09).
  Tardis free tier  the first calendar day of each month: tick liquidation prints,
                    which are the ground truth the leverage mix is calibrated against,
                    and top-25 book snapshots.
  Deribit           DVOL, and the public history API's option fills, used for the
                    instrument-cost calculation.

Nothing is cached in the repository. `data/` is gitignored and rebuilt by running.
"""

import gzip
import io
import json
import sys
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config

VISION = "https://data.binance.vision/data"
TARDIS = "https://datasets.tardis.dev/v1/binance-futures"
UA = {"User-Agent": "Mozilla/5.0"}
KLINE_COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time",
              "quote_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore"]


def _get(url, tries=4, timeout=90):
    """GET with backoff. A 404 is an answer -- missing months at the edges are normal."""
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                        timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            last = e
            time.sleep(600.0 if e.code == 429 else 2.0 * (i + 1))
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2.0 * (i + 1))
    print(f"  [warn] {url[:70]}: {last}")
    return None


def _zip_csv(url, names=None, header=None):
    b = _get(url)
    if b is None:
        return None
    try:
        with zipfile.ZipFile(io.BytesIO(b)) as z:
            with z.open(z.namelist()[0]) as f:
                return pd.read_csv(f, names=names, header=header)
    except zipfile.BadZipFile:
        return None


def _pool(fn, items, workers=10):
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return [r for r in ex.map(fn, items) if r is not None and len(r)]


def _epoch(values):
    """Binance switched parts of the archive from millisecond to microsecond epochs
    mid-2025, and `np.where` will not save you -- it evaluates both branches, so the
    microsecond values overflow before the selection happens."""
    v = pd.to_numeric(values, errors="coerce")
    out = pd.Series(pd.NaT, index=v.index, dtype="datetime64[ns, UTC]")
    us = v > 1e14
    if us.any():
        out[us] = pd.to_datetime(v[us], unit="us", utc=True)
    if (~us).any():
        out[~us] = pd.to_datetime(v[~us], unit="ms", utc=True)
    return out


def _months(start=config.GRID_START, end=config.GRID_END):
    return [d.strftime("%Y-%m") for d in pd.date_range(start, end, freq="MS")]


def _days(start, end):
    return [d.strftime("%Y-%m-%d") for d in pd.date_range(start, end, freq="D")]


def _save(df, name):
    config.RAW.mkdir(parents=True, exist_ok=True)
    df.to_parquet(config.RAW / f"{name}.parquet", index=False)
    print(f"  {name}: {len(df):,} rows")


def _have(name):
    return (config.RAW / f"{name}.parquet").exists()


def _read_klines(parts, numeric):
    """Binance began writing a header row partway through the archive."""
    out = []
    for d in parts:
        if str(d.iloc[0, 0]).lower().startswith("open_time"):
            d = d.iloc[1:]
        out.append(d)
    d = pd.concat(out, ignore_index=True)
    d["open_time"] = _epoch(d["open_time"])
    d["close_time"] = _epoch(d["close_time"])
    for c in numeric:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    return d.drop(columns=["ignore"]).sort_values("open_time").drop_duplicates("open_time")


def _kline_series(kind, path, name, numeric, rename=None, keep=None):
    """Monthly archive plus a daily tail, because the monthly file for the current
    month is published several weeks late -- and an as-of join over that gap produces
    a flat line rather than a gap, which looks like data."""
    if _have(name):
        return
    monthly = [f"{VISION}/{path}/{config.SYMBOL}-{kind}-{m}.zip" for m in _months()]
    parts = _pool(lambda u: _zip_csv(u, KLINE_COLS, None), monthly)
    d = _read_klines(parts, numeric)
    tail_from = (d["open_time"].max() + pd.Timedelta(minutes=5)).floor("D")
    if tail_from < pd.Timestamp(config.GRID_END, tz="UTC"):
        daily_path = path.replace("monthly", "daily")
        urls = [f"{VISION}/{daily_path}/{config.SYMBOL}-{kind}-{day}.zip"
                for day in _days(tail_from, config.GRID_END)]
        extra = _pool(lambda u: _zip_csv(u, KLINE_COLS, None), urls)
        if extra:
            d = pd.concat([d, _read_klines(extra, numeric)], ignore_index=True)
            d = d.sort_values("open_time").drop_duplicates("open_time")
    if keep:
        d = d[keep]
    if rename:
        d = d.rename(columns=rename)
    # A bar is knowable the instant it closes, and not before.
    d["asof_time"] = d["close_time"] + pd.Timedelta(milliseconds=1)
    _save(d, name)


def futures_klines():
    _kline_series("5m", f"futures/um/monthly/klines/{config.SYMBOL}/5m",
                  "futures_klines_5m",
                  ["open", "high", "low", "close", "volume", "quote_volume", "trades",
                   "taker_buy_base", "taker_buy_quote"])


def premium_index():
    _kline_series("5m", f"futures/um/monthly/premiumIndexKlines/{config.SYMBOL}/5m",
                  "premium_5m", ["close"],
                  rename={"close": "premium_index"},
                  keep=["open_time", "close_time", "close"])


def funding():
    """Settled funding. It is not knowable before it settles, so asof is settlement."""
    if _have("funding"):
        return
    cols = ["calc_time", "funding_interval_hours", "last_funding_rate"]
    urls = [f"{VISION}/futures/um/monthly/fundingRate/{config.SYMBOL}/"
            f"{config.SYMBOL}-fundingRate-{m}.zip" for m in _months()]
    parts = _pool(lambda u: _zip_csv(u, cols, None), urls)
    d = pd.concat([p.iloc[1:] if str(p.iloc[0, 0]).lower().startswith("calc") else p
                   for p in parts], ignore_index=True)
    d["funding_time"] = _epoch(d["calc_time"])
    d["funding_rate"] = pd.to_numeric(d["last_funding_rate"], errors="coerce")
    d = d[["funding_time", "funding_rate"]].dropna().sort_values("funding_time")
    d = d.drop_duplicates("funding_time")
    d["asof_time"] = d["funding_time"]
    _save(d, "funding")


def metrics():
    """5-minute open interest. Daily zips, 2020-09 onward, and nothing earlier exists.

    asof is pushed one period past the sample instant: these are snapshots served by
    a REST endpoint with unstated latency, and being a bar early is a leak while being
    a bar late is not.
    """
    if _have("metrics_5m"):
        return
    days = _days(config.METRICS_START,
                 pd.Timestamp(config.GRID_END) - pd.Timedelta(days=1))
    urls = [f"{VISION}/futures/um/daily/metrics/{config.SYMBOL}/"
            f"{config.SYMBOL}-metrics-{day}.zip" for day in days]
    parts = _pool(lambda u: _zip_csv(u, None, 0), urls, workers=16)
    d = pd.concat(parts, ignore_index=True)
    d["create_time"] = pd.to_datetime(d["create_time"], utc=True)
    num = ["sum_open_interest", "sum_open_interest_value",
           "sum_taker_long_short_vol_ratio"]
    for c in num:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d[["create_time"] + num].sort_values("create_time").drop_duplicates("create_time")
    d["asof_time"] = d["create_time"] + pd.Timedelta(minutes=5)
    _save(d, "metrics_5m")


def dvol():
    """Deribit's implied-volatility index. Launched 2021-03; earlier calls are empty."""
    if _have("dvol_1h"):
        return
    step = pd.Timedelta(days=25)
    starts = pd.date_range(pd.Timestamp("2021-01-01", tz="UTC"),
                           pd.Timestamp(config.GRID_END, tz="UTC"), freq=step)

    def one(s):
        u = ("https://www.deribit.com/api/v2/public/get_volatility_index_data"
             f"?currency=BTC&start_timestamp={int(s.timestamp()*1000)}"
             f"&end_timestamp={int((s+step).timestamp()*1000)}&resolution=3600")
        b = _get(u, tries=3)
        time.sleep(0.1)
        rows = (json.loads(b) if b else {}).get("result", {}).get("data") or []
        return pd.DataFrame(rows, columns=["t", "o", "h", "l", "dvol"]) if rows else None

    parts = _pool(one, list(starts), workers=6)
    d = pd.concat(parts, ignore_index=True)
    d["bar_start"] = pd.to_datetime(d["t"], unit="ms", utc=True)
    d = d[["bar_start", "dvol"]].sort_values("bar_start").drop_duplicates("bar_start")
    d["asof_time"] = d["bar_start"] + pd.Timedelta(hours=1)
    _save(d, "dvol_1h")


def _tardis_months():
    return [(d.year, d.month) for d in
            pd.date_range(config.GRID_START, config.GRID_END, freq="MS")]


def liquidations():
    """Every forced-order print on the free tier's first-of-month sample days.

    This is the ground truth the leverage mix is fitted against. Binance's side field
    is the side of the *liquidating order*: a long being closed out sends a SELL.
    """
    if _have("liquidations"):
        return
    def one(ym):
        b = _get(f"{TARDIS}/liquidations/{ym[0]}/{ym[1]:02d}/01/{config.SYMBOL}.csv.gz")
        if b is None:
            return None
        d = pd.read_csv(io.BytesIO(gzip.decompress(b)))
        d["ts"] = pd.to_datetime(d["timestamp"], unit="us", utc=True)
        d["price"] = pd.to_numeric(d["price"], errors="coerce")
        d["amount"] = pd.to_numeric(d["amount"], errors="coerce")
        d = d.dropna(subset=["price", "amount"])
        d["notional"] = d["price"] * d["amount"]
        d["is_long_liq"] = (d["side"].astype(str).str.lower() == "sell").astype(int)
        return d[["ts", "price", "amount", "notional", "is_long_liq"]]

    parts = _pool(one, _tardis_months(), workers=8)
    d = pd.concat(parts, ignore_index=True).sort_values("ts")
    d["asof_time"] = d["ts"]          # a public stream: knowable as it prints
    _save(d, "liquidations")

    bar = d.set_index("ts").resample("5min", label="right", closed="right").agg(
        liq_long=("notional", lambda x: 0.0), liq_count=("notional", "size")).reset_index()
    # Resample only inside the sample days: a plain resample would manufacture
    # hundreds of thousands of zero-liquidation bars across days Tardis never covers.
    g = d.set_index("ts")
    bar = pd.DataFrame({
        "ts": g.resample("5min", label="right", closed="right").size().index,
        "liq_long": g["notional"].where(g["is_long_liq"] == 1, 0.0)
        .resample("5min", label="right", closed="right").sum().values,
        "liq_short": g["notional"].where(g["is_long_liq"] == 0, 0.0)
        .resample("5min", label="right", closed="right").sum().values,
        "liq_count": g.resample("5min", label="right", closed="right").size().values,
    })
    have = set(d["ts"].dt.floor("D").unique())
    keep = (bar["ts"] - pd.Timedelta(microseconds=1)).dt.floor("D").isin(have)
    bar = bar[keep].reset_index(drop=True)
    bar["asof_time"] = bar["ts"]
    _save(bar, "liq_5m")


def book_snapshots():
    """Top-25 book depth, reduced to 5-minute aggregates by streaming.

    One of these files is ~700 MB decompressed and there are eighty of them. Parsing
    them into frames pins several gigabytes; this streams off the socket, takes every
    twentieth snapshot, and keeps nothing larger than one row in memory.
    """
    if _have("book_5m"):
        return
    from collections import defaultdict
    lv, stride = 25, 20

    def one(ym):
        y, m = ym
        url = f"{TARDIS}/book_snapshot_25/{y}/{m:02d}/01/{config.SYMBOL}.csv.gz"
        acc = defaultdict(lambda: np.zeros(4))
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(url, headers=UA), timeout=300) as resp:
                with gzip.GzipFile(fileobj=resp) as gz:
                    head = gz.readline().decode().strip().split(",")
                    ix = {c: i for i, c in enumerate(head)}
                    ap = [ix[f"asks[{i}].price"] for i in range(lv)]
                    aq = [ix[f"asks[{i}].amount"] for i in range(lv)]
                    bp = [ix[f"bids[{i}].price"] for i in range(lv)]
                    bq = [ix[f"bids[{i}].amount"] for i in range(lv)]
                    ts_i = ix["timestamp"]
                    for k, raw in enumerate(gz):
                        if k % stride:
                            continue
                        f = raw.decode().split(",")
                        try:
                            a0, b0 = float(f[ap[0]]), float(f[bp[0]])
                            if a0 <= 0 or b0 <= 0:
                                continue
                            depth = sum(float(f[bp[i]] or 0) * float(f[bq[i]] or 0)
                                        + float(f[ap[i]] or 0) * float(f[aq[i]] or 0)
                                        for i in range(lv))
                            bar = (int(f[ts_i]) // 300_000_000 + 1) * 300_000_000
                        except (ValueError, IndexError):
                            continue
                        v = acc[bar]
                        v[0] += 1
                        v[1] += (a0 - b0) / ((a0 + b0) / 2.0)
                        v[2] += depth
        except Exception as e:  # noqa: BLE001
            print(f"  [warn] book {y}-{m:02d}: {e}")
            return None
        if not acc:
            return None
        d = pd.DataFrame([{"ts": b, "spread": v[1] / v[0], "depth": v[2] / v[0]}
                          for b, v in acc.items()])
        d["ts"] = pd.to_datetime(d["ts"], unit="us", utc=True)
        return d.sort_values("ts")

    parts = _pool(one, _tardis_months(), workers=3)
    if not parts:
        return
    d = pd.concat(parts, ignore_index=True).sort_values("ts").drop_duplicates("ts")
    d["asof_time"] = d["ts"]
    _save(d, "book_5m")


def deribit_option_fills(entry_days):
    """Historical option fills for the instrument-cost calculation.

    These are fills with a direction, not quotes: a taker buy print bounds the ask, a
    taker sell print bounds the bid, and their gap is the spread actually paid.
    """
    if _have("option_fills"):
        return
    api = ("https://history.deribit.com/api/v2/public/"
           "get_last_trades_by_currency_and_time")
    months = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
              "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}

    def parse_instrument(name):
        try:
            _, dt_s, strike, kind = name.split("-")
            return (pd.Timestamp(year=2000 + int(dt_s[-2:]), month=months[dt_s[-5:-2]],
                                 day=int(dt_s[:-5]), hour=8, tz="UTC"),
                    float(strike), kind == "C")
        except Exception:  # noqa: BLE001
            return (pd.NaT, np.nan, None)

    def one(day):
        t0 = pd.Timestamp(day, tz="UTC")
        cur, end = int(t0.timestamp() * 1000), int((t0 + pd.Timedelta(hours=4)).timestamp() * 1000)
        rows, calls = [], 0
        while cur < end and calls < 40:
            b = _get(f"{api}?currency=BTC&kind=option&start_timestamp={cur}"
                     f"&end_timestamp={end}&count=1000&sorting=asc", tries=3)
            calls += 1
            if b is None:
                break
            res = (json.loads(b) or {}).get("result", {})
            tr = res.get("trades") or []
            if not tr:
                break
            rows += tr
            nxt = tr[-1]["timestamp"] + 1
            if nxt <= cur or not res.get("has_more"):
                break
            cur = nxt
        if not rows:
            return None
        d = pd.DataFrame(rows)
        d["ts"] = pd.to_datetime(d["timestamp"], unit="ms", utc=True)
        parsed = d["instrument_name"].map(parse_instrument)
        d["expiry"] = [p[0] for p in parsed]
        d["strike"] = [p[1] for p in parsed]
        d["is_call"] = [p[2] for p in parsed]
        d["entry_day"] = day
        return d.dropna(subset=["expiry", "strike"])[
            ["entry_day", "ts", "instrument_name", "direction", "price", "iv",
             "amount", "index_price", "expiry", "strike", "is_call"]]

    parts = _pool(one, entry_days, workers=4)
    if not parts:
        return
    _save(pd.concat(parts, ignore_index=True).sort_values("ts"), "option_fills")


def main():
    config.RAW.mkdir(parents=True, exist_ok=True)
    entry_days = [d.strftime("%Y-%m-%d") for d in
                  pd.date_range("2021-01-01", config.GRID_END, freq="W-FRI")]
    for fn, args in [(futures_klines, ()), (premium_index, ()), (funding, ()),
                     (metrics, ()), (dvol, ()), (liquidations, ()),
                     (book_snapshots, ()), (deribit_option_fills, (entry_days,))]:
        print(f"[fetch] {fn.__name__}", flush=True)
        fn(*args)
    print("fetch complete")


if __name__ == "__main__":
    main()
