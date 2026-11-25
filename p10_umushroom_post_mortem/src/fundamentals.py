"""Component D2: forward EPS revisions vs price, from the raw yfinance eps_trend snapshot.
dln(P) = dln(EPS_fwd) + dln(P/E_fwd) over the same lookback window."""
import json
import math
import pathlib

import pandas as pd

from config import RAW
import data

TICKERS = ["NVDA", "WMT", "AMAT", "HD", "BA.L", "RR.L"]


def snapshots():
    return sorted(p for p in RAW.glob("estimates_*") if (p / "manifest.json").exists())


def decompose(snap=None):
    snap = snap or snapshots()[-1]
    ts = pd.Timestamp(json.loads((snap / "manifest.json").read_text())["downloaded_utc"].replace("Z", ""))
    raw = data.load(kind="raw")
    rows = []
    for t in TICKERS:
        f = snap / f"{t.replace('.', '_')}_get_eps_trend.csv"
        if not f.exists():
            rows.append({"ticker": t, "status": "NO DATA"})
            continue
        tr = pd.read_csv(f, index_col=0)
        px = raw[t].dropna()
        px = px[px.index < ts.normalize() + pd.Timedelta(days=1)]
        last_d, last_p = px.index[-1], float(px.iloc[-1])
        for period in ("0y", "+1y"):
            if period not in tr.index or pd.isna(tr.loc[period, "current"]):
                continue
            for lb, days in (("7daysAgo", 7), ("30daysAgo", 30), ("90daysAgo", 90)):
                e0, e1 = float(tr.loc[period, lb]), float(tr.loc[period, "current"])
                d0 = ts.normalize() - pd.Timedelta(days=days)
                p0s = px[px.index <= d0]
                p0, p0d = float(p0s.iloc[-1]), p0s.index[-1]
                dlp, dle = math.log(last_p / p0), math.log(e1 / e0)
                rows.append({"ticker": t, "period": period, "lookback": lb, "eps_then": e0, "eps_now": e1,
                             "eps_chg_pct": round(100 * (e1 / e0 - 1), 2), "price_from": str(p0d.date()),
                             "price_to": str(last_d.date()), "price_chg_pct": round(100 * (last_p / p0 - 1), 2),
                             "dlnP": round(dlp, 4), "dlnEPS": round(dle, 4), "dlnPE": round(dlp - dle, 4)})
    return pd.DataFrame(rows), str(snap.name)


def revisions(snap=None):
    snap = snap or snapshots()[-1]
    out = {}
    for t in TICKERS:
        f = snap / f"{t.replace('.', '_')}_get_eps_revisions.csv"
        if f.exists():
            out[t] = pd.read_csv(f, index_col=0).to_dict(orient="index")
    return out


if __name__ == "__main__":
    df, s = decompose()
    print(s)
    print(df[df.lookback != "90daysAgo"].to_string())
