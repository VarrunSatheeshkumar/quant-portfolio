"""Plan 2 additions to C/B: VaR flags, NVDA 20 Nov decomposition, breach diagnosis, deploy-trigger audit, Sharpe."""
import math

import numpy as np
import pandas as pd

from config import ROOT, USD
import attribution
import data
import ledger

P9 = ROOT.parent / "p9_umushroom_event_risk" / "out"   # sibling P9 folder in this repo
P9_NAME = {"NVIDIA": "NVDA", "Applied Materials": "AMAT", "Walmart": "WMT", "Home Depot": "HD", "BAE Systems": "BA.L",
           "Rolls-Royce": "RR.L", "Bitcoin": "BTC-USD", "Ethereum": "ETH-USD"}
P9_VAR95, P9_VAR99, P9_SD, P9_AI_STRESS = 6432, 9094, 3.91, -3613


def var_flags(pnl):
    loss = -pnl
    return {"loss_gbp": round(loss, 2), "var95": P9_VAR95, "var99": P9_VAR99,
            "var95_breached": bool(loss > P9_VAR95), "var99_breached": bool(loss > P9_VAR99),
            "excess_over_var95": round(loss - P9_VAR95, 2), "headroom_to_var99": round(P9_VAR99 - loss, 2),
            "ai_selloff_stress_gbp": P9_AI_STRESS, "loss_vs_ai_stress_x": round(loss / -P9_AI_STRESS, 2)}


def nvda_day(day="2026-11-20"):
    day = pd.Timestamp(day)
    adj = data.load(None, day, kind="adj")
    out = {}
    for mode in ("etf", "peers"):
        b = attribution.estimate_betas("NVDA", pd.Timestamp("2026-05-01"), sector_mode=mode)
        f = attribution.factor_returns("NVDA", pd.date_range(day - pd.Timedelta(days=7), day, freq="D"), mode).loc[day]
        sp = f.s - b["g"] * f.m
        pred = b["b_m"] * f.m + b["b_s"] * sp
        out[mode] = {"r_pct": round(100 * f.r, 2), "m_pct": round(100 * f.m, 2), "s_pct": round(100 * f.s, 2),
                     "b_m": round(b["b_m"], 3), "b_s": round(b["b_s"], 3), "g": round(b["g"], 3),
                     "predicted_pct": round(100 * pred, 2), "abnormal_pct": round(100 * (f.r - pred), 2),
                     "abnormal_z": round((f.r - pred) / b["resid_sd"], 2),
                     "spy_only_abnormal_pct": round(100 * (f.r - b["b_m"] * f.m), 2),
                     "spy_only_predicted_pct": round(100 * b["b_m"] * f.m, 2)}
    peers = ["AMD", "AVGO", "TSM", "MU", "LRCX", "KLAC", "ASML"]
    raw = data.load(None, day, kind="raw")
    pm = {p: round(100 * (raw[p].dropna().iloc[-1] / raw[p].dropna().iloc[-2] - 1), 2) for p in peers}
    for t in ("SPY", "QQQ", "SMH", "AMAT"):
        pm[t] = round(100 * (raw[t].dropna().iloc[-1] / raw[t].dropna().iloc[-2] - 1), 2)
    return {"raw_pct": out["etf"]["r_pct"], "spy_only": {"predicted_pct": out["etf"]["spy_only_predicted_pct"], "abnormal_pct": out["etf"]["spy_only_abnormal_pct"]},
            "spy_smh": out["etf"], "spy_peers": out["peers"], "moves_20nov_pct": pm,
            "caveat": "On 20 Nov the sector is not independent of NVDA: the report was about NVDA and peers fell with it. The model cannot say which way causation ran."}


def breach_diagnosis(start="2026-11-06", end="2026-11-20"):
    pa = pd.read_csv(P9 / "per_asset.csv")
    raw = data.load(None, end, kind="raw")
    fx = raw["GBPUSD=X"].dropna()
    rows = {}
    for r in pa.itertuples():
        a = P9_NAME[r.asset]
        s = raw[a].dropna()
        g = (s / fx.reindex(s.index).ffill()) if a in USD else s
        g0, g1 = float(g.loc[:start].iloc[-1]), float(g.loc[:end].iloc[-1])
        lr = math.log(g1 / g0)
        rows[a] = {"gbp_log_ret_pct": round(100 * lr, 2), "p9_two_week_sd_pct": r.two_week_sd_pct,
                   "z": round(100 * lr / r.two_week_sd_pct, 2)}
    rows["_beyond_minus2"] = [a for a, v in rows.items() if not a.startswith("_") and v["z"] < -2]
    return rows


def deploy_audit(start="2026-11-09", end="2026-11-20"):
    pa = pd.read_csv(P9 / "per_asset.csv")
    trig = {P9_NAME[r.asset]: r.deploy_trigger_daily_pct for r in pa.itertuples()}
    raw = data.load(None, end, kind="raw")
    fx = raw["GBPUSD=X"].dropna()
    hits = []
    for a, t in trig.items():
        s = raw[a].dropna()
        loc = 100 * s.pct_change()
        g = (s / fx.reindex(s.index).ffill()) if a in USD else s
        gb = 100 * g.pct_change()
        for d in loc.loc[start:end].index:
            if a == "ETH-USD" and d > pd.Timestamp("2026-11-13"):
                continue  # ETH closed 13 Nov
            if loc.loc[d] <= t or gb.loc[d] <= t:
                hits.append({"date": str(d.date()), "asset": a, "local_pct": round(float(loc.loc[d]), 2),
                             "gbp_pct": round(float(gb.loc[d]), 2), "trigger_pct": t,
                             "hit_local": bool(loc.loc[d] <= t), "hit_gbp": bool(gb.loc[d] <= t)})
    return {"triggers_from_p9_file": trig, "hits": hits}


def own_sharpe(asof):
    nav = ledger.daily(asof)["nav"]
    us = data.load(None, asof, kind="raw")["NVDA"].dropna().index
    s = nav.reindex(us[(us >= "2026-11-06") & (us <= asof)]).pct_change().dropna()
    sr_d = float(s.mean() / s.std(ddof=1))
    T = len(s)
    # Point estimate deliberately not reported: over ~10 sessions its standard error swamps it.
    return {"T_sessions": T, "se_annualised": round(math.sqrt((1 + sr_d ** 2 / 2) / T) * math.sqrt(252), 2),
            "note": "realised Sharpe not reported: the standard error over this many sessions makes it meaningless"}
