"""Component C: horizon and statistical power. No invented alpha; IR grid is hypothetical."""
import math

import numpy as np
import pandas as pd
from scipy import stats

from config import SEED
import data
import ledger
import p9_replica as p9

MAP = {v: k for k, v in p9.TICK.items()}


def held_weights(date):
    d = ledger.daily(date)
    v = d["value"].loc[pd.Timestamp(date)]
    nav = d["nav"].loc[pd.Timestamp(date)]
    return {MAP[a]: float(v[a] / nav) for a in v.index if a in MAP}, float(d["cash"].loc[pd.Timestamp(date)] / nav)


def z_scores(realised_pct, sigmas):
    return {k: {"sigma_pct": round(s, 3), "z": round(realised_pct / s, 3),
                "p_one_sided": round(float(stats.norm.cdf(realised_pct / s)), 3)} for k, s in sigmas.items()}


def portfolio_daily_gbp(weights, years=2, end="2026-11-06"):
    """Fixed-weight daily GBP simple returns (US trading days, crypto/UK ffilled), pre-cutoff only."""
    end = pd.Timestamp(end)
    start = end - pd.DateOffset(years=years) - pd.Timedelta(days=10)
    px = data.load_pre(start, end, kind="adj", tickers=list(p9.TICK.values()) + ["GBPUSD=X"])
    cal = px["NVDA"].dropna().index
    fx = px["GBPUSD=X"].reindex(cal).ffill()
    g = {}
    for a, t in p9.TICK.items():
        s = px[t].reindex(cal).ffill()
        g[a] = s / fx if t in data.USD else s
    r = pd.DataFrame(g).pct_change().dropna()
    r = r[r.index > end - pd.DateOffset(years=years)]
    w = pd.Series(weights)
    return (r[w.index] * w).sum(axis=1)   # daily rebalanced to fixed weights; cash earns 0


def placebo(port, realised_pct, horizons=(8, 9, 10)):
    out = {}
    for h in horizons:
        roll = (1 + port).rolling(h).apply(np.prod, raw=True).dropna() - 1
        out[h] = {"n_windows": int(len(roll)), "share_at_or_below_pct": round(100 * float((roll * 100 <= realised_pct).mean()), 1),
                  "sd_pct": round(100 * float(roll.std()), 2), "p5_pct": round(100 * float(roll.quantile(0.05)), 2)}
    return out


def block_bootstrap(port, h=10, block=5, n=10000, seed=SEED, realised_pct=None):
    rng = np.random.default_rng(seed)
    x = port.values
    T = len(x)
    nb = math.ceil(h / block)
    starts = rng.integers(0, T, size=(n, nb))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]) % T
    paths = x[idx].reshape(n, -1)[:, :h]
    ret = np.prod(1 + paths, axis=1) - 1
    res = {"sd_pct": round(100 * float(ret.std()), 3), "p2_5_pct": round(100 * float(np.quantile(ret, 0.025)), 3),
           "p97_5_pct": round(100 * float(np.quantile(ret, 0.975)), 3)}
    if realised_pct is not None:
        res["share_at_or_below_pct"] = round(100 * float((ret * 100 <= realised_pct).mean()), 2)
    return res


def closed_form(T=10, irs=(0.0, 0.25, 0.5, 1.0)):
    rows = []
    for ir in irs:
        rows.append({"IR_hypothetical": ir, "expected_t_after_T": round(ir * math.sqrt(T / 252), 3),
                     "P_loss_over_T_pct": round(100 * float(stats.norm.cdf(-ir * math.sqrt(T / 252))), 1),
                     "years_for_t2": (round((2 / ir) ** 2, 1) if ir > 0 else None)})
    return rows


def mde(sigma_pct, alpha=0.05, power=0.8):
    k = stats.norm.ppf(1 - alpha) + stats.norm.ppf(power)
    return {"multiplier": round(float(k), 3), "mde_pct": round(float(k * sigma_pct), 2)}


def binom_table():
    return {"P(<=1 of 5|0.5)": round(float(stats.binom.cdf(1, 5, 0.5)), 4),
            "P(<=1 of 6|0.5)": round(float(stats.binom.cdf(1, 6, 0.5)), 4),
            "P(<=2 of 6|0.5)": round(float(stats.binom.cdf(2, 6, 0.5)), 4),
            "two_sided_1of5": round(float(stats.binomtest(1, 5, 0.5).pvalue), 4),
            "two_sided_1of6": round(float(stats.binomtest(1, 6, 0.5).pvalue), 4),
            "two_sided_2of6": round(float(stats.binomtest(2, 6, 0.5).pvalue), 4)}


def call_moves(asof):
    """Report-day move (first close after vs last close before, local ccy) vs implied move."""
    calls = [("RR.L", "2026-11-12", 3.0, "assumed"), ("BA.L", "2026-11-12", 3.0, "assumed"),
             ("AMAT", "2026-11-13", 10.4, "options 6 Nov"), ("HD", "2026-11-17", 4.2, "options Aug level"),
             ("NVDA", "2026-11-18", 9.0, "options 6 Nov"), ("WMT", "2026-11-19", 4.6, "options Aug level")]
    raw = data.load(kind="raw")
    rows = []
    for a, day, im, src in calls:
        s = raw[a].dropna()
        day = pd.Timestamp(day)
        if day not in s.index or day > pd.Timestamp(asof):
            rows.append({"asset": a, "reaction_day": str(day.date()), "status": "PENDING (close not yet available)",
                         "prev_close": round(float(s[s.index < day].iloc[-1]), 2) if (s.index < day).any() else None,
                         "implied_move_pct": im, "implied_src": src})
            continue
        prev, cur = float(s[s.index < day].iloc[-1]), float(s.loc[day])
        mv = 100 * (cur / prev - 1)
        rows.append({"asset": a, "reaction_day": str(day.date()), "prev_close": round(prev, 3), "close": round(cur, 3),
                     "move_pct": round(mv, 2), "call": "Up", "hit": mv > 0, "implied_move_pct": im, "implied_src": src,
                     "abs_move_lt_implied": abs(mv) < im})
    return rows
