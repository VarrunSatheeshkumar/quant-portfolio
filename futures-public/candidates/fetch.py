"""Fetch and cache the external series the candidates need. Nothing here reads a
return. Each source is cached under data/raw/cand/ so an interrupted run resumes.

  TreasuryDirect: every auctioned Note and Bond with its auction date.
  Binance USDT-M perpetuals: funding history and daily klines per symbol.
  yfinance: SPY (with dividends), ^VIX.
"""

import json
import sys
import time
import warnings

import pandas as pd
import requests
import yfinance as yf

sys.path.insert(0, ".")
import config    # noqa: E402

warnings.filterwarnings("ignore")
H = {"User-Agent": "Mozilla/5.0"}
OUT = config.RAW / "cand"
OUT.mkdir(parents=True, exist_ok=True)


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def treasury():
    p = OUT / "treasury_auctions.parquet"
    if p.exists():
        return
    frames = []
    for typ in ["Note", "Bond"]:
        url = f"https://www.treasurydirect.gov/TA_WS/securities/search?type={typ}&format=json"
        r = requests.get(url, headers=H, timeout=180)
        r.raise_for_status()
        d = pd.DataFrame(r.json())
        log("treasury", typ, d.shape)
        frames.append(d)
    d = pd.concat(frames, ignore_index=True)
    keep = [c for c in ["cusip", "securityType", "securityTerm", "auctionDate", "issueDate", "maturityDate", "reopening",
                        "offeringAmount", "term", "type"] if c in d.columns]
    d = d[keep]
    d["auctionDate"] = pd.to_datetime(d["auctionDate"], errors="coerce")
    d.to_parquet(p)
    log("treasury done", d.shape)


def binance():
    """Per-symbol cache so a timeout resumes instead of restarting. Only perpetuals
    listed at least three years ago are worth a weekly cross-section."""
    p = OUT / "binance_funding.parquet"
    if p.exists():
        return
    cache = OUT / "binance"
    cache.mkdir(exist_ok=True)
    info = requests.get("https://fapi.binance.com/fapi/v1/exchangeInfo", headers=H, timeout=60).json()
    syms = sorted(s["symbol"] for s in info["symbols"]
                  if s.get("contractType") == "PERPETUAL" and s.get("quoteAsset") == "USDT" and s.get("status") == "TRADING"
                  and int(s.get("onboardDate", 0)) <= int(pd.Timestamp("2023-09-01").timestamp() * 1000))
    log("binance symbols with >=3y history", len(syms))

    def paged(url, params, key_last, page):
        rows, start = [], 0
        while True:
            for attempt in range(5):
                try:
                    r = requests.get(url, params=dict(params, startTime=start, limit=page), headers=H, timeout=60)
                    break
                except Exception as e:      # noqa: BLE001
                    log("retry", params.get("symbol"), repr(e)[:60]); time.sleep(10 * (attempt + 1))
            else:
                raise RuntimeError("gave up " + params.get("symbol"))
            if r.status_code == 429:
                log("429, sleeping 60"); time.sleep(60); continue
            r.raise_for_status()
            got = r.json()
            if not got:
                break
            rows += got
            nxt = key_last(got[-1]) + 1
            # Binance caps the funding endpoint at 500 rows regardless of `limit`, so
            # "fewer than a page" is not the end of the data; only an empty page or a
            # cursor that stops advancing is.
            if nxt <= start or len(got) < 100:
                break
            start = nxt
            time.sleep(0.25)
        return rows

    def funding_windows(sym, first_ms, days=200):
        """The funding endpoint returns the most recent rows when startTime is 0 and
        never more than 500 per call, so history is walked in explicit windows."""
        rows, start, now, step = [], first_ms, int(pd.Timestamp(config.END).timestamp() * 1000) + 86400000, days * 86400000
        while start < now:
            for attempt in range(5):
                try:
                    r = requests.get("https://fapi.binance.com/fapi/v1/fundingRate",
                                     params=dict(symbol=sym, startTime=start, endTime=min(start + step, now), limit=1000),
                                     headers=H, timeout=60)
                    break
                except Exception as e:      # noqa: BLE001
                    log("retry", sym, repr(e)[:60]); time.sleep(10 * (attempt + 1))
            else:
                raise RuntimeError("gave up " + sym)
            if r.status_code == 429:
                log("429, sleeping 60"); time.sleep(60); continue
            r.raise_for_status()
            rows += r.json()
            start += step + 1
            time.sleep(0.25)
        return rows

    for i, sym in enumerate(syms):
        fp = cache / f"{sym}.parquet"
        ff = cache / f"{sym}_funding.parquet"
        if fp.exists() and ff.exists():
            continue
        kl = paged("https://fapi.binance.com/fapi/v1/klines", dict(symbol=sym, interval="1d"), lambda x: x[6], 1500) if not fp.exists() else None
        first_ms = int(pd.read_parquet(fp).open_time.min().timestamp() * 1000) if fp.exists() else int(kl[0][0])
        fund = funding_windows(sym, first_ms)
        f = pd.DataFrame(fund)
        if len(f):
            f["fundingTime"] = pd.to_datetime(f["fundingTime"], unit="ms")
            f["fundingRate"] = pd.to_numeric(f["fundingRate"], errors="coerce")
        f.to_parquet(ff)
        if kl is not None:
            k = pd.DataFrame([[sym] + row[:8] for row in kl], columns=["symbol", "open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume"])
            k["open_time"] = pd.to_datetime(k["open_time"], unit="ms")
            for c in ["open", "high", "low", "close", "volume", "quote_volume"]:
                k[c] = pd.to_numeric(k[c], errors="coerce")
            k.to_parquet(fp)
        if i % 20 == 0:
            log("binance", i, sym, "funding rows", len(f))
        time.sleep(0.2)
    fs = [pd.read_parquet(x) for x in cache.glob("*_funding.parquet")]
    ks = [pd.read_parquet(x) for x in cache.glob("*.parquet") if not x.name.endswith("_funding.parquet")]
    ff = pd.concat([x for x in fs if len(x)], ignore_index=True)
    ff[ff.fundingTime <= pd.Timestamp(config.END) + pd.Timedelta(days=1)].to_parquet(p)
    kk = pd.concat(ks, ignore_index=True)
    kk[kk.open_time <= config.END].to_parquet(OUT / "binance_klines_1d.parquet")
    log("binance done")


def yahoo():
    for tk, name in [("SPY", "spy"), ("^VIX", "vix")]:
        p = OUT / f"{name}.parquet"
        if p.exists():
            continue
        d = yf.Ticker(tk).history(period="max", auto_adjust=False, actions=True)
        d.index = pd.DatetimeIndex(d.index).tz_localize(None).normalize()
        d = d[d.index <= config.END]
        d.columns = [c.lower().replace(" ", "_") for c in d.columns]
        d.to_parquet(p)
        log(name, d.shape, d.index.min().date(), d.index.max().date())


if __name__ == "__main__":
    for fn in [yahoo, treasury, binance]:
        try:
            fn()
        except Exception as e:     # noqa: BLE001
            log("FAILED", fn.__name__, repr(e)[:200])
    log("all done")
