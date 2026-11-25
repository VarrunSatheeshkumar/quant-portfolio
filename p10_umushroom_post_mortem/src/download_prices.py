"""Download daily closes (adjusted and raw) for all tickers from Yahoo via yfinance.
Writes data/raw/prices_<UTC ts>_{adj,raw}.csv and data/raw/prices_latest.txt (pointer)."""
import datetime as dt
import json
import sys
import warnings
warnings.filterwarnings("ignore")
import pandas as pd
import yfinance as yf
from config import RAW, ALL_TICKERS


def main(start="2000-01-01"):
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    RAW.mkdir(parents=True, exist_ok=True)
    adj = yf.download(ALL_TICKERS, start=start, auto_adjust=True, progress=False, threads=True)["Close"]
    raw = yf.download(ALL_TICKERS, start=start, auto_adjust=False, progress=False, threads=True)["Close"]
    adj.index = pd.to_datetime(adj.index).tz_localize(None).normalize()
    raw.index = pd.to_datetime(raw.index).tz_localize(None).normalize()
    from config import HOLDINGS
    o = yf.download(HOLDINGS + ["GBPUSD=X", "SYRE"], start="2026-10-01", auto_adjust=False, progress=False)
    o.index = pd.to_datetime(o.index).tz_localize(None).normalize()
    o[["Open", "High", "Low", "Close"]].to_csv(RAW / f"prices_{ts}_ohlc.csv")
    divs = {t: yf.Ticker(t).dividends.loc["2026-01-01":].to_dict() for t in HOLDINGS[:6]}
    (RAW / f"dividends_{ts}.json").write_text(json.dumps({t: {str(k.date()): v for k, v in d.items()} for t, d in divs.items()}, indent=1))
    fa, fr = RAW / f"prices_{ts}_adj.csv", RAW / f"prices_{ts}_raw.csv"
    adj.to_csv(fa); raw.to_csv(fr)
    (RAW / "prices_latest.txt").write_text(ts)
    last = {c: str(adj[c].dropna().index.max().date()) if adj[c].notna().any() else None for c in adj}
    meta = {"downloaded_utc": ts, "yfinance": yf.__version__, "last_date": last}
    (RAW / f"prices_{ts}_meta.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:])
