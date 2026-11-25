"""Mark-to-market update for the pre-final pitch (26 Nov 2026, 18:00 UK).

The book is unchanged since the 20 Nov cut-off (no trades). This revalues it at the 25 Nov close, the last common US/UK
equity close before the pitch: US markets are closed on 26 Nov for Thanksgiving, while UK shares close at 16:30 on 26 Nov
and Bitcoin and GBP/USD keep trading before 18:00 (data/input/prices_25nov_snapshot.json: US shares at the official
21:00 UK close, UK shares at the 16:30 official close, Bitcoin and GBP/USD at 21:00 UK). It does not change any 20 Nov
result.

Risk numbers use the same 156-week covariance as component E (data to 20 Nov), so only the weights move.
Writes out/latest_25nov.json."""
import json

import pandas as pd

import data
import ledger
import strategic as E
import stress
from config import OUT, ROOT, USD, PENCE

SNAP = ROOT / "data" / "input" / "prices_25nov_snapshot.json"
M = {"NVDA": "NVDA", "AMAT": "AMAT", "WMT": "WMT", "HD": "HD", "BA.L": "BAE", "RR.L": "RR", "BTC-USD": "BTC",
     "SYRE": "SYRE"}


def gbp(t, px, fx, pence=False):
    """Sterling value of one unit. The snapshot quotes UK shares in pence (Yahoo); data.load already gives pounds."""
    p = px / 100 if (pence and t in PENCE) else px
    return p / fx if t in USD else p


def run():
    book = json.loads((OUT / "book_frozen_20261120.json").read_text())
    R2 = json.loads((OUT / "results2.json").read_text())
    snap = json.loads(SNAP.read_text())
    fx = snap["GBPUSD=X"]["price"]
    units = {t: u for t, u in book["units"].items() if u > 0}
    cash = book["cash_gbp"]

    # 20 Nov closes (same loader as the rest of P10) for the change since the cut-off
    px20 = data.load(None, "2026-11-20", kind="raw", tickers=list(units) + ["GBPUSD=X"]).ffill().iloc[-1]
    # average sterling cost per unit from the ledger (buys only)
    tx = ledger.load_tx()
    buys = tx[(tx.side == "buy") & tx.asset.isin(list(units))]
    cost = {t: float(-buys[buys.asset == t].gbp_cash.sum()) for t in units}
    ucost = {t: float(buys[buys.asset == t].units.sum()) for t in units}
    lcost = {t: float((buys[buys.asset == t].units * buys[buys.asset == t].local_price).sum() / ucost[t]) for t in units}

    rows, val = {}, {}
    for t, u in units.items():
        p = snap[t]["price"]
        v = u * gbp(t, p, fx, pence=True)
        v20 = u * gbp(t, float(px20[t]), float(px20["GBPUSD=X"]))
        val[t] = v
        local_now = p / 100 if t in PENCE else p
        rows[M[t]] = {"price_local": round(local_now, 4), "price_time_utc": snap[t]["time_utc"], "units": u,
                      "value_gbp": round(v, 2),
                      "change_since_20nov_gbp": round(float(v - v20), 2),
                      "local_return_vs_avg_fill_pct": round(100 * (local_now / lcost[t] - 1), 2),
                      "gbp_return_vs_cost_pct": round(100 * (v / cost[t] - 1), 2)}
    nav = sum(val.values()) + cash
    for t in units:
        rows[M[t]]["weight_pct"] = round(100 * val[t] / nav, 2)

    # risk at the new weights, component E's covariance (156 weeks to 20 Nov)
    assets = list(E.TICK)
    hw = {M[t]: val[t] / nav for t in units}
    _, cov = E.run(hw, cash / nav, nav, "2026-11-20", 156, assets)
    import numpy as np
    w = np.array([hw.get(a, 0.0) for a in assets])
    risk = E.describe(w, cov, assets, nav)
    sig_exact, _ = E.euler_shares(w, cov.values)
    two_week_sd = sig_exact * (2 / 52) ** 0.5

    S = json.loads((OUT / "stress_observed.json").read_text())
    shocks = S["shocks_gbp_exact"]
    wpct = {M[t]: 100 * val[t] / nav for t in units}
    full, _ = stress.book_loss(wpct, shocks, nav)
    aic, _ = stress.book_loss(wpct, {k: v for k, v in shocks.items() if k in stress.AI_CRYPTO}, nav)

    usd = sum(val[t] for t in units if t in USD)
    res = {"label": "Mark to market at the 25 Nov close, the last common US/UK equity close before the 26 Nov 18:00 pitch (US closed 26 Nov for Thanksgiving; UK shares, Bitcoin and FX can still move on 26 Nov); book unchanged since the 20 Nov cut-off",
           "snapshot_taken_utc": snap["_taken_utc"], "gbpusd": fx,
           "nav_gbp": round(nav, 2), "return_vs_100k_pct": round(100 * (nav / 100000 - 1), 2),
           "change_since_20nov_platform_gbp": round(nav - R2["platform"]["nav"], 2),
           "change_since_20nov_yahoo_gbp": round(nav - R2["platform"]["yahoo_nav"], 2),
           "cash_gbp": cash, "cash_pct": round(100 * cash / nav, 2), "usd_share_pct": round(100 * usd / nav, 1),
           "holdings": rows,
           "risk": {"ann_vol_pct": risk["ann_vol_pct"], "two_week_sd_pct": round(100 * two_week_sd, 2),
                    "two_week_var95_gbp": round(1.645 * two_week_sd * nav), "var95_1y_normal_gbp": risk["var95_1y_normal_gbp"],
                    "risk_share_pct": risk["risk_share_pct"], "ai_crypto_risk_share_pct": risk["ai_crypto_risk_share_pct"],
                    "sleeve_risk_share_pct": risk["sleeve_risk_share_pct"], "cov": "component E, 156 weeks to 20 Nov"},
           "observed_decline_stress": {"full_gbp": full, "ai_crypto_only_gbp": aic,
                                       "x_p9_ai_stress_ai_crypto": round(aic / stress.P9_AI_STRESS, 2)},
           "w_star_pct": R2["E"]["w_star_pct"]}
    (OUT / "latest_25nov.json").write_text(json.dumps(res, indent=1, allow_nan=False))
    return res


if __name__ == "__main__":
    r = run()
    print(json.dumps({k: v for k, v in r.items() if k != "holdings"}, indent=1))
    for k, v in r["holdings"].items():
        print(k, v)
