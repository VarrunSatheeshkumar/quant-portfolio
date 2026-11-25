"""Component E: strategic restatement. Weekly (Friday) GBP log returns, Ledoit-Wolf, annualised x52.
Expected returns are ASSUMPTIONS (reverse optimisation); the horizon table is hypothetical."""
import math

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.covariance import LedoitWolf

from config import USD
import data
import p9_replica as p9

TICK = {"NVDA": "NVDA", "AMAT": "AMAT", "WMT": "WMT", "HD": "HD", "BAE": "BA.L", "RR": "RR.L", "BTC": "BTC-USD", "SYRE": "SYRE"}
SLEEVES = {"AI/semis": ["NVDA", "AMAT"], "US consumer": ["WMT", "HD"], "UK industrials": ["BAE", "RR"],
           "Crypto": ["BTC"], "Satellite": ["SYRE"]}
CAP = 0.15
ASSUMPTIONS = {"sharpe_grid": [0.2, 0.3, 0.4], "risk_free": 0.0, "cash_return": 0.0, "var_z": 1.645,
               "weekly_day": "Friday close (W-FRI last obs)", "annualise": 52, "cap": CAP, "leverage": "none",
               "cap_rule": "weights above 15% clipped; excess spread pro rata over uncapped names (cash unchanged)",
               "expected_returns": "reverse-optimised pi = lambda * Sigma * w_held, lambda = S / sigma_p: ASSUMPTION",
               "horizon_table": "P(loss over T) = Phi(-S * sqrt(T)): HYPOTHETICAL"}


def weekly(end, weeks, assets):
    end = pd.Timestamp(end)
    loader = data.load_pre if end <= data.CUTOFF else data.load
    px = loader(end - pd.Timedelta(weeks=weeks + 3), end, kind="adj", tickers=[TICK[a] for a in assets] + ["GBPUSD=X"])
    px = px.ffill()
    fx = px["GBPUSD=X"]
    g = pd.DataFrame({a: (px[TICK[a]] / fx if TICK[a] in USD else px[TICK[a]]) for a in assets})
    w = g.resample("W-FRI").last()
    w = w[w.index <= end + pd.Timedelta(days=6)]
    r = np.log(w).diff().dropna().iloc[-weeks:]
    assert len(r) == weeks, (len(r), weeks)
    return r


def cov_lw(r):
    lw = LedoitWolf().fit(r.values)
    return pd.DataFrame(lw.covariance_ * 52, index=r.columns, columns=r.columns), float(lw.shrinkage_)


def euler_shares(w, cov):
    w = np.asarray(w)
    sig = math.sqrt(w @ cov @ w)
    rc = w * (cov @ w) / sig
    return sig, rc / sig


def cap_weights(w, total, cap=CAP):
    w = np.asarray(w, float).copy()
    for _ in range(100):
        over = w > cap + 1e-12
        if not over.any():
            break
        excess = (w[over] - cap).sum()
        w[over] = cap
        free = w < cap - 1e-12
        w[free] += excess * w[free] / w[free].sum()
    assert abs(w.sum() - total) < 1e-9
    return w


def erc(cov, total):
    return p9.equal_risk_weights(np.asarray(cov), total)


def sleeve_rp(cov, assets, total):
    cov = pd.DataFrame(cov, index=assets, columns=assets)
    sleeves = {k: [a for a in v if a in assets] for k, v in SLEEVES.items()}
    sleeves = {k: v for k, v in sleeves.items() if v}
    inner = {}
    for k, v in sleeves.items():
        inner[k] = pd.Series(erc(cov.loc[v, v].values, 1.0), index=v) if len(v) > 1 else pd.Series([1.0], index=v)
    V = pd.DataFrame(0.0, index=assets, columns=list(sleeves))
    for k, s in inner.items():
        V.loc[s.index, k] = s.values
    C = V.T.values @ cov.values @ V.values
    tot = erc(C, total)
    return V.values @ tot


def describe(w, cov, assets, nav, rets=None):
    sig, sh = euler_shares(w, cov.values)
    shares = dict(zip(assets, (100 * sh).round(2)))
    out = {"weights_pct": dict(zip(assets, (100 * np.asarray(w)).round(2))), "invested_pct": round(100 * float(np.sum(w)), 2),
           "ann_vol_pct": round(100 * sig, 2), "var95_1y_normal_gbp": round(ASSUMPTIONS["var_z"] * sig * nav),
           "risk_share_pct": shares,
           "ai_crypto_risk_share_pct": round(sum(shares[a] for a in ("NVDA", "AMAT", "BTC") if a in shares), 1),
           "sleeve_risk_share_pct": {k: round(sum(shares.get(a, 0) for a in v), 1) for k, v in SLEEVES.items()}}
    if rets is not None:
        pr = (rets[assets].values @ np.asarray(w))   # weekly log approx, fixed weights
        roll = pd.Series(pr).rolling(52).sum().dropna()
        out["rolling52_p5_pct"] = round(100 * (math.exp(roll.quantile(0.05)) - 1), 2) if len(roll) else None
        out["rolling52_n"] = int(len(roll))
    return out


def run(held_w, cash, nav, end, weeks, assets):
    r = weekly(end, weeks, assets)
    cov, shrink = cov_lw(r)
    total = 1 - cash
    hw = np.array([held_w.get(a, 0.0) for a in assets])
    hw = hw / hw.sum() * total
    e = cap_weights(erc(cov.values, total), total)
    s = cap_weights(sleeve_rp(cov.values, assets, total), total)
    res = {"end": str(pd.Timestamp(end).date()), "weeks": weeks, "assets": assets, "shrinkage": round(shrink, 4),
           "first_week": str(r.index[0].date()), "last_week": str(r.index[-1].date()),
           "ann_vol_by_asset_pct": dict(zip(assets, (100 * np.sqrt(np.diag(cov.values))).round(1))),
           "min_eig": float(np.linalg.eigvalsh(cov.values).min()),
           "held": describe(hw, cov, assets, nav, r), "erc_capped": describe(e, cov, assets, nav, r),
           "sleeve_rp_capped": describe(s, cov, assets, nav, r)}
    sig_h = res["held"]["ann_vol_pct"] / 100
    res["implied_returns_ASSUMPTION"] = {}
    for S in ASSUMPTIONS["sharpe_grid"]:
        lam = S / sig_h
        pi = lam * cov.values @ hw
        res["implied_returns_ASSUMPTION"][str(S)] = dict(zip(assets, (100 * pi).round(2)))
    res["_w"] = {"held": hw.tolist(), "erc": e.tolist(), "sleeve": s.tolist()}
    return res, cov


def horizon_table():
    T = {"2 weeks": 2 / 52, "1 year": 1, "3 years": 3, "5 years": 5}
    return {str(S): {k: round(100 * float(stats.norm.cdf(-S * math.sqrt(t))), 1) for k, t in T.items()}
            for S in ASSUMPTIONS["sharpe_grid"]}
