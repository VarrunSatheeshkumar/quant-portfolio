"""T10: replicate the P9 2-week risk model with Yahoo data to the 6 Nov cutoff.
Logic copied from ../p9_umushroom_event_risk/model.py (P9 left untouched)."""
import math

import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf

import data

HORIZON_DAYS = 10
TICK = {"NVDA": "NVDA", "AMAT": "AMAT", "WMT": "WMT", "HD": "HD", "BAE": "BA.L", "RR": "RR.L",
        "BTC": "BTC-USD", "ETH": "ETH-USD"}
ASSETS = list(TICK)
P9_WEIGHTS = {"NVDA": 0.15, "AMAT": 0.10, "WMT": 0.10, "HD": 0.10, "BAE": 0.10, "RR": 0.10, "BTC": 0.10, "ETH": 0.05}
IMPLIED_MOVE = {"NVDA": 9.0, "AMAT": 10.4, "WMT": 4.6, "HD": 4.2, "BAE": 3.0, "RR": 3.0, "BTC": None, "ETH": None}
PAST_EVENT_DAYS = ["2026-05-19", "2026-05-21", "2026-07-30", "2026-08-18", "2026-08-20", "2026-08-27"]
RISK_ON = ["NVDA", "AMAT", "BTC", "ETH"]


def euler(w, cov):
    sigma = math.sqrt(w @ cov @ w)
    return sigma, w * (cov @ w) / sigma


def equal_risk_weights(cov, total, iters=5000):
    w = np.full(len(cov), total / len(cov))
    for _ in range(iters):
        mrc = cov @ w
        w = w * (1 / (w * mrc)) ** 0.5
        w = w / w.sum() * total
    return w


def gbp_returns(start="2026-05-01", end="2026-11-06"):
    px = data.load_pre(start, end, kind="adj", tickers=list(TICK.values()) + ["GBPUSD=X"])
    cal = px["NVDA"].dropna().index
    fx = px["GBPUSD=X"].reindex(cal).ffill()
    out = {}
    for a, t in TICK.items():
        s = px[t].reindex(cal).ffill()
        out[a] = s / fx if t in data.USD else s
    prices = pd.DataFrame(out).dropna()
    assert prices.index.max() <= data.CUTOFF
    return np.log(prices).diff().dropna()


def model(weights=None, use_sample=False, start="2026-05-01"):
    w = np.array([(weights or P9_WEIGHTS)[a] for a in ASSETS])
    rets_all = gbp_returns(start)
    drop = [pd.Timestamp(d) for d in PAST_EVENT_DAYS if pd.Timestamp(d) in rets_all.index]
    rets = rets_all.drop(index=drop)
    lw = LedoitWolf().fit(rets.values)
    base = np.cov(rets.values, rowvar=False) if use_sample else lw.covariance_
    cov_d = base * HORIZON_DAYS
    jump = np.array([(IMPLIED_MOVE[a] or 0) / 100 * math.sqrt(math.pi / 2) for a in ASSETS])
    cov_t = cov_d + np.diag(jump ** 2)
    sig, rc = euler(w, cov_t)
    share = rc / sig
    erc = equal_risk_weights(cov_t, w.sum())
    return {"two_week_sd_pct": 100 * sig, "var95_gbp": 100000 * 1.645 * sig,
            "risk_on_share_pct": 100 * sum(share[ASSETS.index(a)] for a in RISK_ON),
            "shrinkage": float(lw.shrinkage_), "n_days": len(rets), "first": str(rets.index[0].date()),
            "last": str(rets.index[-1].date()), "cov_daily": lw.covariance_, "erc_sd_pct": 100 * euler(erc, cov_t)[0],
            "share": dict(zip(ASSETS, (100 * share).round(1)))}


if __name__ == "__main__":
    m = model()
    print({k: v for k, v in m.items() if k != "cov_daily"})
