"""Component A: daily GBP NAV from the transaction ledger, reconciliations, implied fill FX."""
import json

import numpy as np
import pandas as pd

from config import ROOT, USD
import data

TX_FILE = ROOT / "data" / "input" / "transactions.csv"
# Platform readings, keyed by the valuation date they show (not the time they were read).
#   2026-11-19  intraday reading on 19 Nov (UK evening, before the US close); the Spyre buy was still pending
#   2026-11-20  the Stage 1 cut-off value (20 Nov close), read from the platform on 21 Nov ~21:50 UTC
PLATFORM_SNAPSHOTS = {
    "2026-11-19": {"file": "platform_snapshot.json", "observed": "2026-11-19 UK evening, intraday (before the US close)",
                   "timing": "mixed-time reconstruction: the reading was taken before the US close. Platform quotes are "
                             "used where the reading gives them; the other prices (Home Depot, Rolls-Royce) and GBPUSD are "
                             "Yahoo's 19 Nov closes, and Home Depot's close and the GBPUSD close came after the reading. "
                             "No intraday quotes at the reading time are on file, so the comparison with the platform NAV "
                             "is approximate"},
    "2026-11-20": {"file": "platform_snapshot_20261122.json", "observed": "2026-11-21 ~21:50 UTC (shows the 20 Nov close)",
                   "timing": "same-time: the reading shows the 20 Nov close, read after every market in the book had "
                             "closed; platform quotes for every holding, GBPUSD from Yahoo's 20 Nov close"},
}
ASSETS = ["NVDA", "WMT", "AMAT", "HD", "BA.L", "RR.L", "BTC-USD", "ETH-USD", "SYRE"]


def platform_snapshot(valuation_date):
    """The platform reading whose valuation date equals valuation_date. KeyError if there is none: a run for another
    date must not borrow a reading made for a different day."""
    key = str(pd.Timestamp(valuation_date).date())
    meta = PLATFORM_SNAPSHOTS[key]
    snap = json.loads((ROOT / "data" / "input" / meta["file"]).read_text())
    return snap, {"valuation_date": key, "observed": meta["observed"], "timing": meta["timing"], "file": meta["file"]}


def load_tx():
    tx = pd.read_csv(TX_FILE, parse_dates=["date"])
    tx["signed_units"] = np.where(tx.side == "sell", -tx.units, np.where(tx.side == "buy", tx.units, 0.0))
    return tx


def accounting(tx=None):
    tx = load_tx() if tx is None else tx
    cash = round(tx.gbp_cash.sum(), 2)
    units = tx[tx.asset != "CASH"].groupby("asset").signed_units.sum().round(6).to_dict()
    open_assets = [a for a, u in units.items() if abs(u) > 1e-9]
    open_cost = round(-tx[tx.asset.isin(open_assets)].gbp_cash.sum(), 2)
    eth_realised = round(tx[tx.asset == "ETH-USD"].gbp_cash.sum(), 2)
    # running balances, both as exact sums and as the platform printed them
    running = tx.groupby("date").gbp_cash.sum().cumsum().round(2).to_dict()
    return {"cash": cash, "units": units, "open_cost": open_cost, "eth_realised": eth_realised,
            "running_cash": {str(k.date()): v for k, v in running.items()}}


def implied_fx(tx=None):
    tx = load_tx() if tx is None else tx
    t = tx[(tx.ccy == "USD")].copy()
    t["usd_value"] = t.units * t.local_price
    t["implied_gbpusd"] = (t.usd_value / t.gbp_cash.abs()).round(5)
    px = data.load(kind="raw", tickers=["GBPUSD=X"])["GBPUSD=X"].dropna()
    t["yahoo_gbpusd_close"] = t.date.map(lambda d: round(float(px.loc[:d].iloc[-1]), 5))
    t["spread_vs_close_pct"] = (100 * (t.yahoo_gbpusd_close / t.implied_gbpusd - 1)).round(3)
    return t[["date", "asset", "side", "units", "local_price", "gbp_cash", "implied_gbpusd",
              "yahoo_gbpusd_close", "spread_vs_close_pct"]]


def fill_vs_range(tx=None):
    """Was each fill inside the day's Yahoo regular-session range (raw OHLC file)?"""
    tx = load_tx() if tx is None else tx
    ohlc = pd.read_csv(data.RAW / f"prices_{data._ts()}_ohlc.csv", header=[0, 1], index_col=0, parse_dates=True)
    ohlc.index = pd.to_datetime(ohlc.index).normalize()
    rows = []
    for _, r in tx[tx.asset != "CASH"].iterrows():
        k = 100.0 if r.asset in ("BA.L", "RR.L") else 1.0
        g = lambda f: round(float(ohlc[(f, r.asset)].loc[r.date]) / k, 2)
        prev = ohlc[("Close", r.asset)].loc[:r.date - pd.Timedelta(days=1)].dropna()
        lo, hi = g("Low"), g("High")
        rows.append({"date": str(r.date.date()), "asset": r.asset, "fill": r.local_price, "low": lo, "high": hi,
                     "close": g("Close"), "prev_close": round(float(prev.iloc[-1]) / k, 2),
                     "inside_range": bool(lo <= r.local_price <= hi)})
    return pd.DataFrame(rows)


def gbp_prices(start, end, kind="raw"):
    """Daily calendar (incl. weekends) GBP prices for held assets, forward-filled closes."""
    px = data.load(None, end, kind=kind, tickers=ASSETS + ["GBPUSD=X"])
    cal = pd.date_range(start, end, freq="D")
    px = px.reindex(px.index.union(cal)).ffill().reindex(cal)
    fx = px["GBPUSD=X"]
    local = px[ASSETS]
    gbp = local.copy()
    for a in ASSETS:
        if a in USD:
            gbp[a] = local[a] / fx
    return local, fx, gbp


def daily(asof, start="2026-11-06", kind="raw"):
    """Daily NAV and per-position P&L. Trades are effective on their date; P&L on a trade day
    splits into holding P&L on prior units and execution P&L = traded units x (close - fill).
    Trades dated before `start` set the opening units and cash; only trades inside [start, asof] are booked as fills.
    Opening positions are marked from the close before `start`, so the first day's holding P&L is the same as in a
    run that starts earlier."""
    tx = load_tx()
    start = pd.Timestamp(start)
    local0, fx0, gbp0 = gbp_prices(start - pd.Timedelta(days=1), asof, kind)    # one extra day: the preceding close
    local, fx, gbp = local0.iloc[1:], fx0.iloc[1:], gbp0.iloc[1:]
    cal = gbp.index
    trades = tx[tx.asset != "CASH"]
    before = trades[trades.date < cal[0]]
    opening = before.groupby("asset").signed_units.sum().reindex(ASSETS).fillna(0.0)
    units = pd.DataFrame(np.tile(opening.values, (len(cal), 1)), index=cal, columns=ASSETS)
    cashflow = pd.Series(0.0, index=cal)
    fill_cost = pd.DataFrame(0.0, index=cal, columns=ASSETS)   # GBP paid (+) / received (-)
    for _, r in trades[(trades.date >= cal[0]) & (trades.date <= cal[-1])].iterrows():
        d = r.date
        units.loc[d:, r.asset] += r.signed_units
        cashflow.loc[d] += r.gbp_cash
        fill_cost.loc[d, r.asset] += -r.gbp_cash
    cash = 100000.0 + before.gbp_cash.sum() + cashflow.cumsum()
    value = units * gbp
    nav = value.sum(axis=1) + cash
    prev_units = units.shift(1)
    prev_units.iloc[0] = opening.values
    du = units - prev_units
    hold = prev_units * gbp0.diff().iloc[1:].fillna(0.0)
    execution = du * gbp - fill_cost
    out = {"local": local, "fx": fx, "gbp": gbp, "units": units, "cash": cash, "value": value,
           "nav": nav, "hold_pnl": hold, "exec_pnl": execution, "prev_units": prev_units}
    return out


def platform_reconciliation(valuation_date):
    """Ledger against one dated platform reading. Every lookup is bounded to the valuation date: platform-quoted
    prices where the reading gives them, otherwise the last Yahoo close on or before that date; GBPUSD likewise.
    Trades listed as pending in the reading are left out (not yet executed when it was read)."""
    snap, meta = platform_snapshot(valuation_date)
    d = pd.Timestamp(meta["valuation_date"])
    tx = load_tx()
    tx = tx[tx.date <= d]
    pending = set(snap.get("pending", {}))
    tx = tx[~(tx.asset.isin(pending) & (tx.date == d))]
    acc = accounting(tx)
    raw = data.load(None, d, kind="raw")
    assert raw.index.max() <= d
    last = {a: (float(raw[a].dropna().iloc[-1]), str(raw[a].dropna().index[-1].date())) for a in ASSETS + ["GBPUSD=X"]}
    fxv, fxd = last["GBPUSD=X"]
    q = snap["quoted_prices"]
    rows, total = [], acc["cash"]
    for a, u in acc["units"].items():
        if abs(u) < 1e-9:
            continue
        price, src = (q[a], "platform") if a in q else (last[a][0], f"yahoo {last[a][1]}")
        g = price / fxv if a in USD else price
        rows.append({"asset": a, "units": u, "price": price, "src": src, "gbp": round(u * g, 2)})
        total += u * g
    units_check = {a: {"ledger": acc["units"].get(a, 0.0), "platform": u, "match": abs(acc["units"].get(a, 0.0) - u) < 1e-6}
                   for a, u in snap.get("quoted_units", {}).items()}
    return {**meta, "nav_at_platform_prices": round(total, 2), "platform_nav": snap["nav_gbp"],
            "diff_vs_platform": round(total - snap["nav_gbp"], 2),
            "platform_return_pct": round(100 * (snap["nav_gbp"] / 100000 - 1), 4),
            "cash_ledger": acc["cash"], "cash_platform": snap["cash_gbp"], "cash_diff": round(acc["cash"] - snap["cash_gbp"], 2),
            "pending_excluded": sorted(pending), "units_check": units_check, "fx": fxv, "fx_date": fxd, "rows": rows}


def main(asof):
    acc = accounting()
    d = daily(asof)
    nav = d["nav"]
    res = {"accounting": acc, "nav_yahoo_asof": round(float(nav.iloc[-1]), 2), "asof": str(pd.Timestamp(asof).date()),
           "return_pct_vs_100k": round(100 * (nav.iloc[-1] / 100000 - 1), 4),
           "platform": (platform_reconciliation(asof) if str(pd.Timestamp(asof).date()) in PLATFORM_SNAPSHOTS else None),
           "platform_reconciliation_2026-11-19_intraday": platform_reconciliation("2026-11-19")}
    res["unrealised_check"] = round(res["nav_yahoo_asof"] - acc["cash"] - acc["open_cost"], 2)
    from config import OUT; OUT.mkdir(exist_ok=True); nav.round(2).to_csv(OUT / "nav_daily.csv")
    return res, d


if __name__ == "__main__":
    import sys
    r, _ = main(sys.argv[1] if len(sys.argv) > 1 else "2026-11-18")
    print(json.dumps(r, indent=1, default=str))
    print(implied_fx().to_string())
    print(fill_vs_range().to_string())
