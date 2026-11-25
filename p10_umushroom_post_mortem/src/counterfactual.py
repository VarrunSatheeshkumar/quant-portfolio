"""Component I: static books formed at the actual 7 Nov (crypto) and 9 Nov (equity) fill prices, no later trades,
valued at ASOF closes in GBP (Yahoo raw closes and GBPUSD). Weights read from P9's output files (../p9_umushroom_event_risk/out, read only)."""
import json

import pandas as pd

from config import ROOT, USD
import data
import ledger

P9 = ROOT.parent / "p9_umushroom_event_risk" / "out"   # sibling P9 folder in this repo
NAME = {"NVIDIA": "NVDA", "Applied Materials": "AMAT", "Walmart": "WMT", "Home Depot": "HD", "BAE Systems": "BA.L",
        "Rolls-Royce": "RR.L", "Bitcoin": "BTC-USD", "Ethereum": "ETH-USD"}
VAR95 = {"planned": 6432, "halfway": 5599, "equal_risk": 5013}   # P9 compare.json summary


def p9_weights():
    pa = pd.read_csv(P9 / "per_asset.csv")
    tr = json.loads((P9 / "compare.json").read_text())["trades"]
    planned = {NAME[r.asset]: r.weight_pct / 100 for r in pa.itertuples()}
    erc = {NAME[r.asset]: r.erc_weight_pct / 100 for r in pa.itertuples()}
    half = {NAME[t["asset"]]: t["halfway_pct"] / 100 for t in tr}
    var = {s["portfolio"]: s["var95_gbp"] for s in json.loads((P9 / "compare.json").read_text())["summary"]}
    return {"planned": planned, "halfway": half, "equal_risk": erc}, var


def first_fill_gbp():
    tx = ledger.load_tx()
    out = {}
    for a in NAME.values():
        r = tx[(tx.asset == a) & (tx.side == "buy")].iloc[0]
        out[a] = {"date": str(r.date.date()), "gbp_per_unit": -r.gbp_cash / r.units}
    return out


def value_asof(asof):
    raw = data.load(None, asof, kind="raw")
    fx = float(raw["GBPUSD=X"].dropna().iloc[-1])
    px = {a: float(raw[a].dropna().iloc[-1]) for a in NAME.values()}
    return {a: (p / fx if a in USD else p) for a, p in px.items()}, fx


def run(asof):
    W, var = p9_weights()
    fills = first_fill_gbp()
    gbp, fx = value_asof(asof)
    led = ledger.daily(asof)
    actual_nav = float(led["nav"].iloc[-1])
    res = {"asof": str(pd.Timestamp(asof).date()), "fx": fx, "actual_nav": round(actual_nav, 2),
           "actual_pnl": round(actual_nav - 100000, 2), "books": {}}
    for k, w in W.items():
        assert abs(sum(w.values()) - 0.80) < 1e-6, (k, sum(w.values()))
        pos = {a: 100000 * wi / fills[a]["gbp_per_unit"] * gbp[a] for a, wi in w.items()}
        nav = 100000 * (1 - sum(w.values())) + sum(pos.values())
        pnl = nav - 100000
        v = {"planned": var["Current"], "halfway": var["Halfway"], "equal_risk": var["Equal risk"]}[k]
        res["books"][k] = {"weights": w, "nav": round(nav, 2), "pnl": round(pnl, 2), "return_pct": round(pnl / 1000, 3),
                           "vs_actual_gbp": round(pnl - res["actual_pnl"], 2), "own_var95": v, "breaches_own_var95": bool(-pnl > v),
                           "pnl_by_asset": {a: round(p - 100000 * w[a], 2) for a, p in pos.items()}}
    return res


if __name__ == "__main__":
    import sys
    print(json.dumps(run(sys.argv[1] if len(sys.argv) > 1 else "2026-11-20"), indent=1))
