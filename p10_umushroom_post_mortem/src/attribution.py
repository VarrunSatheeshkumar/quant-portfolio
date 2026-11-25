"""Component B: exact GBP return attribution of the period P&L.

Per USD equity, holding P&L on day t (u = units held at t-1, P local close, X = GBP per USD):
  u*P_{t-1}*X_{t-1}*r_t  (local)  +  u*P_{t-1}*(X_t-X_{t-1})  (FX)  +  u*(P_t-P_{t-1})*(X_t-X_{t-1})  (cross)
Local return r_t = b_m*m_t + b_s*s_perp_t + AR_t, with pre-cutoff betas and s_perp = s - g*m.
AR on event reaction days -> event buckets; elsewhere -> residual. Crypto: own bucket. ETH: closed line.
Trade-day fill-to-close P&L -> execution bucket.
"""
import json

import numpy as np
import pandas as pd

from config import CUTOFF, FACTOR_MAP, PEER_MAP, ROOT, USD
import data
import ledger

EQUITIES = ["NVDA", "WMT", "AMAT", "HD", "BA.L", "RR.L"]
LAG = {"ITA": 1}   # US-listed sector ETF for UK names: use previous US session


def _series_on_calendar(px, cal):
    return px.reindex(px.index.union(cal)).ffill().reindex(cal)


def factor_returns(asset, cal, sector_mode="etf"):
    """Returns DataFrame indexed by the asset's own trading days in cal: r, m, s (simple)."""
    mkt, sec = FACTOR_MAP[asset]
    allpx = data.load(None, cal[-1], kind="adj")
    own = allpx[asset].dropna()
    own = own[(own.index >= cal[0]) & (own.index <= cal[-1])]
    dcal = pd.date_range(cal[0] - pd.Timedelta(days=10), cal[-1], freq="D")
    M = _series_on_calendar(allpx[mkt].dropna(), dcal)
    if sector_mode == "etf" or asset not in PEER_MAP:   # UK names have no peer basket: ETF rule
        S = allpx[sec].dropna()
        if sec in USD and asset not in USD:
            S = data.to_gbp(allpx[[sec]].dropna())[sec]
        S = _series_on_calendar(S, dcal)
        lag = LAG.get(sec, 0) if asset not in USD else 0
        if lag:
            S = S.shift(lag)
    else:  # ex-self equal-weight peer basket (daily rebalanced), cumulated into an index
        peers = PEER_MAP[asset]
        pr = allpx[peers].dropna(how="all")
        ret = pr.pct_change().mean(axis=1).fillna(0.0)
        S = _series_on_calendar((1 + ret).cumprod(), dcal)
    days = own.index
    df = pd.DataFrame({"P": own})
    df["M"] = M.reindex(days).values
    df["S"] = S.reindex(days).values
    out = (df / df.shift(1) - 1).iloc[1:]
    out.columns = ["r", "m", "s"]
    return out.dropna()


def estimate_betas(asset, est_start, est_end=CUTOFF, sector_mode="etf"):
    est_end = pd.Timestamp(est_end)
    assert est_end <= CUTOFF
    cal = pd.date_range(est_start, est_end, freq="D")
    f = factor_returns(asset, cal, sector_mode)
    assert f.index.max() <= CUTOFF
    out = fit_betas(f.r.values, f.m.values, f.s.values, uk_rule=asset not in USD)
    out.update({"n": len(f), "first": str(f.index.min().date()), "last": str(f.index.max().date())})
    return out


def fit_betas(r, m, s, uk_rule=False):
    """OLS: s = c + g*m; r = a + b_m*m + b_s*(s - c - g*m). UK rule: drop sector if R2 gain < 2 pts."""
    X = np.column_stack([np.ones(len(m)), m])
    c, g = np.linalg.lstsq(X, s, rcond=None)[0]
    s_perp = s - c - g * m
    X2 = np.column_stack([np.ones(len(m)), m, s_perp])
    coef = np.linalg.lstsq(X2, r, rcond=None)[0]
    resid = r - X2 @ coef
    r2_full = 1 - resid.var() / r.var()
    coef1 = np.linalg.lstsq(X, r, rcond=None)[0]
    res1 = r - X @ coef1
    r2_mkt = 1 - res1.var() / r.var()
    dropped = False
    if uk_rule and (r2_full - r2_mkt) < 0.02:
        dropped = True
        coef, resid = np.array([coef1[0], coef1[1], 0.0]), res1
    return {"sector_dropped": dropped, "r2_gain_sector": r2_full - r2_mkt, "alpha": coef[0], "b_m": coef[1],
            "b_s": coef[2], "g": g, "c": c, "resid_sd": resid.std(ddof=3), "r2": r2_full, "r2_mkt_only": r2_mkt}


def split_day(u, P0, P1, X0, X1, b, m, s, alpha_in=False):
    """Exact split of one asset-day holding P&L (GBP). Returns dict of components incl. 'ar'."""
    base = u * P0 * X0
    r = P1 / P0 - 1
    s_perp = s - b["g"] * m - (b["c"] if alpha_in else 0.0)
    out = {"fx": u * P0 * (X1 - X0), "cross": u * (P1 - P0) * (X1 - X0),
           "market": base * b["b_m"] * m, "sector": base * b["b_s"] * s_perp,
           "alpha": base * b["alpha"] if alpha_in else 0.0}
    out["ar"] = base * r - out["market"] - out["sector"] - out["alpha"]
    return out


def est_start_for(window, end=CUTOFF):
    if window == "p9":
        return pd.Timestamp("2026-05-01")
    spy = data.load_pre(None, end, tickers=["SPY"]).dropna()
    return spy.index[-(window + 1)]


def reaction_days(window="0", unsched_file="events_unscheduled.csv"):
    ev = pd.read_csv(ROOT / "data" / "input" / "events.csv", parse_dates=["reaction_day"])
    unsched_f = ROOT / "data" / "input" / unsched_file
    uns = pd.read_csv(unsched_f, parse_dates=["reaction_day"]) if unsched_f.exists() else ev.iloc[0:0]
    out = {}
    raw = data.load(kind="adj")
    for kind, tab in (("scheduled", ev), ("unscheduled", uns)):
        for _, e in tab.iterrows():
            tdays = raw[e.asset].dropna().index
            i = tdays.get_indexer([e.reaction_day])[0]
            if i < 0:
                continue
            offs = {"0": [0], "0,+1": [0, 1], "-1,+1": [-1, 0, 1]}[window]
            for o in offs:
                if 0 <= i + o < len(tdays):
                    out[(e.asset, tdays[i + o])] = kind
    return out


def attribute(asof, beta_window="p9", event_window="0", alpha_in=False, sector_mode="etf", led=None,
              unsched_file="events_unscheduled.csv"):
    led = ledger.daily(asof) if led is None else led
    cal = led["nav"].index
    units_prev, local, fx = led["prev_units"], led["local"], led["fx"]
    X = 1.0 / fx
    ev = reaction_days(event_window, unsched_file)
    rows = []
    betas = {}
    est_start = est_start_for(beta_window)
    for a in EQUITIES:
        b = estimate_betas(a, est_start, sector_mode=sector_mode)
        betas[a] = b
        f = factor_returns(a, pd.date_range(cal[0], cal[-1], freq="D"), sector_mode)
        for t in cal[1:]:
            u = units_prev.loc[t, a]
            if u == 0:
                continue
            tp = t - pd.Timedelta(days=1)
            P0, P1 = local.loc[tp, a], local.loc[t, a]
            X0, X1 = (X.loc[tp], X.loc[t]) if a in USD else (1.0, 1.0)
            base = u * P0 * X0
            r = P1 / P0 - 1
            rec = {"date": t, "asset": a, "fx": u * P0 * (X1 - X0), "cross": u * (P1 - P0) * (X1 - X0),
                   "market": 0.0, "sector": 0.0, "alpha": 0.0, "event_sched": 0.0, "event_unsched": 0.0,
                   "residual": 0.0, "local": base * r}
            if t in f.index and abs(r) > 0:
                fr = f.loc[t]
                sp = split_day(u, P0, P1, X0, X1, b, fr.m, fr.s, alpha_in)
                rec.update({k: sp[k] for k in ("market", "sector", "alpha")})
                ar = sp["ar"]
                s_perp = fr.s - b["g"] * fr.m - (b["c"] if alpha_in else 0.0)
                kind = ev.get((a, t))
                rec["ar_pct"] = 100 * ar / base
                rec["ar_z"] = rec["ar_pct"] / 100 / b["resid_sd"]
                rec["r_pct"] = 100 * r
                if kind == "scheduled":
                    rec["event_sched"] = ar
                elif kind == "unscheduled":
                    rec["event_unsched"] = ar
                else:
                    rec["residual"] = ar
            elif abs(r) > 0:   # trading-day mismatch: keep exact by putting local move in residual
                rec["residual"] = base * r
            rows.append(rec)
    eq = pd.DataFrame(rows)
    # crypto
    crypto = {}
    for a in ["BTC-USD", "ETH-USD"]:
        crypto[a] = float(led["hold_pnl"][a].sum())
    exec_pnl = led["exec_pnl"]
    eth_total = crypto["ETH-USD"] + float(exec_pnl["ETH-USD"].sum())
    syre = float(led["hold_pnl"]["SYRE"].sum() + exec_pnl["SYRE"].sum()) if "SYRE" in exec_pnl else 0.0
    execution = float(exec_pnl.drop(columns=[c for c in ("ETH-USD", "SYRE") if c in exec_pnl]).sum().sum())
    total = float(led["nav"].iloc[-1] - 100000.0)
    buckets = {
        "market": eq.market.sum(), "sector": eq.sector.sum(), "fx": eq.fx.sum(), "fx_local_cross": eq.cross.sum(),
        "alpha": eq.alpha.sum(), "event_scheduled_AR": eq.event_sched.sum(), "event_unscheduled_AR": eq.event_unsched.sum(),
        "residual_AR": eq.residual.sum(), "crypto_BTC": crypto["BTC-USD"], "execution_fill_to_close": execution,
        "ETH_closed_realised": eth_total, "satellite_SYRE": syre,
    }
    buckets = {k: round(float(v), 2) for k, v in buckets.items()}
    gap = round(total - sum(buckets.values()), 4)
    # Scope of the "fx" bucket: the four US equities only. Bitcoin, Ethereum and Spyre are also dollar-quoted; their
    # currency effect sits inside their own buckets. The same daily FX and cross terms, computed for them here, give
    # the currency effect across every dollar-quoted holding (memo only; not a bucket, so the sum is unchanged).
    fx_other = {}
    for a in ("BTC-USD", "ETH-USD", "SYRE"):
        v = 0.0
        for t in cal[1:]:
            u = units_prev.loc[t, a]
            if u == 0:
                continue
            tp = t - pd.Timedelta(days=1)
            P0, P1, X0, X1 = local.loc[tp, a], local.loc[t, a], X.loc[tp], X.loc[t]
            v += u * P0 * (X1 - X0) + u * (P1 - P0) * (X1 - X0)
        fx_other[a] = round(float(v), 2)
    core = round(float(eq[eq.asset.isin([a for a in EQUITIES if a in USD])][["fx", "cross"]].sum().sum()), 2)
    fx_scope = {"core_us_equities_gbp": core, "inside_other_buckets_gbp": fx_other,
                "all_dollar_holdings_gbp": round(core + sum(fx_other.values()), 2)}
    per_asset = eq.groupby("asset")[["market", "sector", "fx", "cross", "alpha", "event_sched", "event_unsched", "residual"]].sum().round(2)
    per_asset["execution"] = exec_pnl.drop(columns=[c for c in ("ETH-USD", "SYRE") if c in exec_pnl]).sum().round(2).reindex(per_asset.index)
    per_asset["total"] = per_asset.sum(axis=1).round(2)
    return {"asof": str(pd.Timestamp(asof).date()), "total_pnl": round(total, 2), "buckets": buckets, "sum_gap": gap,
            "betas": betas, "per_asset": per_asset, "daily": eq, "crypto_hold": crypto, "fx_scope": fx_scope,
            "exec_by_asset": exec_pnl.sum().round(2).to_dict()}


def flag_unscheduled(res, z=2.5):
    d = res["daily"]
    if "ar_z" not in d:
        return d.iloc[0:0]
    sched = reaction_days("0")
    f = d[(d.ar_z.abs() > z) & ~d.apply(lambda r: (r.asset, r.date) in sched, axis=1)]
    return f[["date", "asset", "r_pct", "ar_pct", "ar_z"]]


if __name__ == "__main__":
    import sys
    asof = sys.argv[1] if len(sys.argv) > 1 else "2026-11-18"
    r = attribute(asof)
    print(json.dumps(r["buckets"], indent=1), "total", r["total_pnl"], "gap", r["sum_gap"])
    print(r["per_asset"].to_string())
    print(pd.DataFrame(r["betas"]).T[["b_m", "b_s", "g", "alpha", "resid_sd", "r2", "r2_mkt_only", "n"]].round(4).to_string())
    print(flag_unscheduled(r).round(2).to_string())
    print(r["daily"][["date", "asset", "r_pct", "ar_pct", "ar_z"]].dropna().round(2).to_string())
