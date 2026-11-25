"""Observed-decline stress (Description, Risk management: "future stress testing now uses the observed decline").

P9's AI sell-off stress (-3,613 GBP) assumed NVDA and AMAT fall by their implied report-day move and crypto by one
two-week s.d. The realised loss was 2.4x that. This module replaces the assumed shocks with the ones that happened:
each asset's GBP return from the 6 Nov close (last close before trading) to the 20 Nov close (cut-off).

Two scenarios, applied to three books (weights as % of NAV; cash earns 0):
  full        every holding takes its observed 6-20 Nov GBP return
  ai_crypto   only NVDA, AMAT and BTC take theirs, the rest 0 (like-for-like with P9's AI sell-off stress)
Books: held on 20 Nov, after the proposed NVIDIA trim (K.book_after), and at full risk budget (E.w_star).
Writes out/stress_observed.json. Reads saved prices only (no download)."""
import json

import data
from config import OUT, USD, CUTOFF, PERIOD_END

TICK = {"NVDA": "NVDA", "AMAT": "AMAT", "WMT": "WMT", "HD": "HD", "BAE": "BA.L", "RR": "RR.L", "BTC": "BTC-USD",
        "SYRE": "SYRE"}
AI_CRYPTO = ("NVDA", "AMAT", "BTC")
P9_AI_STRESS = -3613


def observed_gbp_returns(start=CUTOFF, end=PERIOD_END):
    px = data.load(None, end, kind="raw", tickers=list(TICK.values()) + ["GBPUSD=X"]).ffill()
    a, b = px.loc[:start].iloc[-1], px.loc[:end].iloc[-1]
    out = {}
    for k, t in TICK.items():
        r = b[t] / a[t]
        if t in USD:
            r *= a["GBPUSD=X"] / b["GBPUSD=X"]
        out[k] = float(r - 1)
    return out


def book_loss(weights_pct, shocks, nav):
    pnl = {k: nav * w / 100 * shocks.get(k, 0.0) for k, w in weights_pct.items()}
    return round(sum(pnl.values()), 2), {k: round(v, 2) for k, v in pnl.items()}


def on_positions(shocks, asof=PERIOD_END):
    """The full observed-decline shock applied to the rebuilt sterling positions at the asof close (no rounding)."""
    import ledger
    v = ledger.daily(str(asof.date()))["value"].iloc[-1]
    return round(float(sum(v[t] * shocks[k] for k, t in TICK.items())), 2)


def run():
    R2 = json.loads((OUT / "results2.json").read_text())
    nav = R2["platform"]["nav"]
    shocks = observed_gbp_returns()
    scen = {"full": shocks, "ai_crypto": {k: v for k, v in shocks.items() if k in AI_CRYPTO}}
    books = {"held_20nov": R2["E"]["held_weights_pct_yahoo_20nov"],
             "after_nvda_trim": R2["K"]["book_after"]["weights_pct"],
             "full_budget": R2["E"]["w_star_pct"]}
    res = {"window": [str(CUTOFF.date()), str(PERIOD_END.date())], "nav_gbp": nav,
           "shocks_gbp_pct": {k: round(100 * v, 2) for k, v in shocks.items()},
           "shocks_gbp_exact": shocks,
           "p9_ai_stress_gbp": P9_AI_STRESS, "p9_var95_gbp_ref": 6432, "p9_var99_gbp_ref": 9094,
           "note": "P9 references (stress and VaR) were set on P9's original £100k book; same-book VaR is in latest_25nov.json and the P10 README",
           "basis": ("Book losses are scaled to the platform NAV (nav_gbp) using weights rounded to 0.01% of NAV, from "
                     "Yahoo 20 Nov closes; held_20nov_full_on_rebuilt_positions_gbp applies the same shocks to the "
                     "rebuilt positions themselves"),
           "held_20nov_full_on_rebuilt_positions_gbp": on_positions(shocks),
           "books": {}}
    # Validation: the 13 Nov book (H) under the full scenario should match H's realised 6-20 Nov book return within 1 pt (buy-and-hold here, daily-rebalanced in H).
    m = {v: k for k, v in TICK.items()}
    w13 = {m[t]: 100 * x for t, x in R2["H"]["book_weights_13nov"].items()}
    res["check_13nov_book"] = {"stress_pct": round(sum(w * shocks[k] for k, w in w13.items()), 2),
                               "H_realised_pct": R2["H"]["book_realised_6_20nov_pct"]}
    for b, w in books.items():
        res["books"][b] = {"invested_pct": round(sum(w.values()), 2)}
        for s, sh in scen.items():
            loss, per = book_loss(w, sh, nav)
            res["books"][b][s] = {"pnl_gbp": loss, "pnl_pct_nav": round(100 * loss / nav, 2),
                                  "x_p9_ai_stress": round(loss / P9_AI_STRESS, 2),
                                  "beyond_p9_var95_ref": bool(-loss > 6432), "beyond_p9_var99_ref": bool(-loss > 9094),
                                  "per_asset_gbp": per}
    (OUT / "stress_observed.json").write_text(json.dumps(res, indent=1, allow_nan=False))
    return res


if __name__ == "__main__":
    r = run()
    print("shocks %:", r["shocks_gbp_pct"])
    for b, v in r["books"].items():
        print(f"{b:16s} full {v['full']['pnl_gbp']:>10,.0f} ({v['full']['pnl_pct_nav']}%)   "
              f"AI+crypto {v['ai_crypto']['pnl_gbp']:>10,.0f} ({v['ai_crypto']['x_p9_ai_stress']}x P9)")
