"""Component D3: historical base rate for the four US names (EPS beats only; guidance history is not
sourceable mechanically). Betas from sessions [-260, -11] strictly before each reaction day.
AR = r - b_m*SPY - b_s*s_perp (no alpha). CAR(+1,+20), CAR(+1,+60), day 0 excluded.

A pre-window reference: the price panel stops at the 6 Nov 2026 cutoff (load_pre), so an event is kept only if its
whole forward window (day +60) ends on or before 6 Nov. Inference clusters by calendar quarter of the reaction day:
the t-test uses quarter-clustered errors and the bootstrap intervals resample whole quarters.

Classification: beat / miss / tie by the sign of Yahoo's reported Surprise(%), which is computed from unrounded EPS.
Comparing the cent-rounded EPS columns turns small genuine beats and misses into ties (65 published "ties" had a positive
reported surprise), so the rounded comparison is used only when Surprise(%) is missing. Rows with a surprise but no
rounded EPS are kept; rows with neither have no known sign and are left out (counted). Two rows for the same ticker and
reaction day are one report: kept once if they agree, left out (counted) if their signs conflict, because the file
gives no fiscal period to say which row is right (Walmart 13 Aug 2002: -3.64% and +2.34%; NVIDIA 9 Nov 2006)."""
import json
import math

import numpy as np
import pandas as pd
from scipy import stats

from config import CUTOFF, FACTOR_MAP, SEED
import data
import fundamentals

US = ["NVDA", "WMT", "AMAT", "HD"]


def classify(est, act, surprise):
    """(sign, source): sign +1 beat, -1 miss, 0 tie, None unknown. Reported Surprise(%) first; the rounded EPS
    comparison only when the surprise is missing."""
    if pd.notna(surprise):
        return int(np.sign(surprise)), "surprise"
    if pd.notna(est) and pd.notna(act):
        return int(np.sign(act - est)), "eps"
    return None, "none"


def load_events(snap=None, counts=None):
    """All listed reports for the four US names with a known beat/miss/tie sign. counts (optional dict) receives
    'listed_events' (every row dated before the snapshot was taken) and 'unknown_sign' (no surprise and no EPS pair)."""
    snap = snap or fundamentals.snapshots()[-1]
    counts = {} if counts is None else counts
    taken = pd.Timestamp(json.loads((snap / "manifest.json").read_text())["downloaded_utc"].replace("Z", ""), tz="UTC")
    rows, listed, unknown = [], 0, 0
    for t in US:
        df = pd.read_csv(snap / f"{t}_get_earnings_dates.csv")
        df["ts"] = pd.to_datetime(df["Earnings Date"], utc=True).dt.tz_convert("America/New_York")
        df = df[df.ts <= taken]                                    # reports dated after the snapshot are still to come
        for _, r in df.iterrows():
            listed += 1
            sign, src = classify(r["EPS Estimate"], r["Reported EPS"], r["Surprise(%)"])
            if sign is None:
                unknown += 1
                continue
            rows.append({"ticker": t, "ts": r.ts, "est": r["EPS Estimate"], "act": r["Reported EPS"],
                         "surprise_reported": r["Surprise(%)"], "sign": sign, "sign_source": src})
    counts["listed_events"], counts["unknown_sign"] = listed, unknown
    ev = pd.DataFrame(rows)
    ev["beat"] = ev.sign > 0
    ev["miss"] = ev.sign < 0
    return ev, snap.name


def reaction_day(ts, tdays):
    d = pd.Timestamp(ts.date())
    minutes = ts.hour * 60 + ts.minute
    after_close = minutes >= 16 * 60
    idx = tdays.searchsorted(d)                 # first trading day >= d
    if idx >= len(tdays):
        return None
    if after_close and tdays[idx] == d:
        idx += 1
    return tdays[idx] if idx < len(tdays) else None


def returns_panel(ticker):
    mkt, sec = FACTOR_MAP[ticker]
    px = data.load_pre(None, CUTOFF, kind="adj", tickers=[ticker, mkt, sec]).dropna()
    return px.pct_change().dropna()


def event_rows(ev, est=(-260, -11), min_obs=150, offset_label=0, dropped=None):
    """dropped (optional dict) collects counts of events left out: 'after_cutoff' (forward window would end after the
    6 Nov cutoff, or the reaction day is after it) and 'short_history' (fewer than the estimation sessions needed)."""
    out = []
    dropped = {} if dropped is None else dropped
    dropped.setdefault("after_cutoff", 0); dropped.setdefault("short_history", 0)
    for t in US:
        r = returns_panel(t)
        tdays = r.index
        mkt, sec = FACTOR_MAP[t]
        for _, e in ev[ev.ticker == t].iterrows():
            d0 = reaction_day(e.ts, tdays)
            if d0 is None:
                dropped["after_cutoff"] += 1
                continue
            i0 = tdays.get_loc(d0) + offset_label
            lo, hi = i0 + est[0], i0 + est[1]
            if i0 + 60 >= len(tdays):
                dropped["after_cutoff"] += 1
                continue
            if lo < 0:
                dropped["short_history"] += 1
                continue
            w = r.iloc[lo:hi + 1]
            if len(w) < min_obs:
                dropped["short_history"] += 1
                continue
            assert tdays.get_loc(w.index.max()) <= i0 - 11   # T5: estimation ends >= 11 sessions before day 0
            X = np.column_stack([np.ones(len(w)), w[mkt]])
            c, g = np.linalg.lstsq(X, w[sec].values, rcond=None)[0]
            sp = w[sec].values - c - g * w[mkt].values
            X2 = np.column_stack([np.ones(len(w)), w[mkt], sp])
            coef = np.linalg.lstsq(X2, w[t].values, rcond=None)[0]
            sd = (w[t].values - X2 @ coef).std(ddof=3)
            post = r.iloc[i0 - 1:i0 + 61]
            sp_post = post[sec] - g * post[mkt]
            ar = post[t] - coef[1] * post[mkt] - coef[2] * sp_post
            ar = ar.values   # index 0 = day -1, 1 = day 0, 2.. = +1..
            out.append({"ticker": t, "ts": e.ts, "day0": tdays[i0], "est_last": w.index.max(), "last_outcome_day": tdays[i0 + 60],
                        "beat": e.beat, "miss": e.miss, "sign": e.sign, "sign_source": e.sign_source, "eps_est": e.est, "eps_act": e.act,
                        "surprise_pct": e.surprise_reported,
                        "ar_m1": ar[0], "ar0": ar[1], "ar_p1": ar[2], "car1_20": ar[2:22].sum(),
                        "car1_60": ar[2:62].sum(), "resid_sd": sd, "est_gap_sessions": i0 - tdays.get_loc(w.index.max()), "quarter": tdays[i0].to_period("Q")})
    return pd.DataFrame(out)


def cluster_t(x, clusters):
    x = np.asarray(x, float)
    m = x.mean()
    u = pd.Series(x - m).groupby(np.asarray(clusters)).sum().values
    G, n = len(u), len(x)
    var = (u ** 2).sum() / n ** 2 * G / max(G - 1, 1)
    se = math.sqrt(var)
    t = m / se if se > 0 else np.nan
    p = 2 * stats.t.sf(abs(t), df=G - 1)
    return t, p, se, G


def boot_ci(x, clusters, n=10000, seed=SEED):
    """95% interval for the mean, resampling whole clusters (calendar quarters) with replacement."""
    rng = np.random.default_rng(seed)
    x = np.asarray(x, float)
    codes, _ = pd.factorize(np.asarray(clusters))
    G = codes.max() + 1
    s = np.bincount(codes, weights=x, minlength=G)
    c = np.bincount(codes, minlength=G).astype(float)
    draw = rng.integers(0, G, size=(n, G))
    means = s[draw].sum(axis=1) / c[draw].sum(axis=1)
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def summarise(x, q, seed=SEED):
    x = np.asarray(x, float)
    t, p, se, G = cluster_t(x, q)
    lo, hi = boot_ci(x, q, seed=seed)
    return {"n": int(len(x)), "clusters": G, "mean_pct": round(100 * x.mean(), 2), "median_pct": round(100 * float(np.median(x)), 2),
            "share_pos_pct": round(100 * float((x > 0).mean()), 1), "boot95_pct": [round(100 * lo, 2), round(100 * hi, 2)],
            "boot": "quarter-cluster", "t_cluster_q": round(t, 2), "p_two_sided": round(p, 3)}


def run(seed=SEED):
    counts = {}
    ev, snap = load_events(counts=counts)
    dropped = {}
    df = event_rows(ev, dropped=dropped)
    df, dup = dedupe(df)
    assert (df.last_outcome_day <= CUTOFF).all()
    beats = df[df.beat]
    bf, br = beats[beats.ar0 < 0], beats[beats.ar0 >= 0]
    res = {"snapshot": snap, "n_events": len(df), "n_beats": len(beats), "first": str(df.day0.min().date()),
           "last": str(df.day0.max().date()), "last_outcome_day": str(df.last_outcome_day.max().date()),
           "history_cap": str(CUTOFF.date()),
           "classification": "sign of reported Surprise(%); rounded EPS comparison only where the surprise is missing",
           "n_by_sign_source": df.sign_source.value_counts().to_dict(),
           "n_misses": int(df.miss.sum()), "n_ties": int((df.sign == 0).sum()),
           "removed": {"listed_events": int(counts["listed_events"]), "unknown_sign": int(counts["unknown_sign"]),
                       "duplicate_rows_same_sign": dup["same_sign"],
                       "conflicting_duplicates_rows": dup["conflict_rows"], "conflicting_duplicates_reports": dup["conflict_reports"],
                       "conflicting_duplicates": dup["conflict_list"],
                       "forward_window_after_cutoff": int(dropped["after_cutoff"]),
                       "short_estimation_history": int(dropped["short_history"])},
           "per_ticker_n": df.ticker.value_counts().to_dict(),
           "P_AR0_neg_given_beat_pct": round(100 * float((beats.ar0 < 0).mean()), 1),
           "P_AR0_neg_given_beat_by_ticker": {k: round(100 * float((g.ar0 < 0).mean()), 1) for k, g in beats.groupby("ticker")},
           "P_AR0_neg_all_pct": round(100 * float((df.ar0 < 0).mean()), 1)}
    for name, g in (("beat_and_fell", bf), ("beat_and_rose", br), ("all", df)):
        res[name] = {h: summarise(g[h], g.quarter, seed) for h in ("car1_20", "car1_60")}
    # fell minus rose: resample whole quarters of the beats sample, so both groups move together (paired by quarter)
    diff = {}
    codes, _ = pd.factorize(beats.quarter.astype(str))
    G = codes.max() + 1
    fell = (beats.ar0 < 0).values
    for h in ("car1_20", "car1_60"):
        d = bf[h].mean() - br[h].mean()
        x = beats[h].values
        sf = np.bincount(codes, weights=x * fell, minlength=G); nf = np.bincount(codes, weights=fell.astype(float), minlength=G)
        sr = np.bincount(codes, weights=x * ~fell, minlength=G); nr = np.bincount(codes, weights=(~fell).astype(float), minlength=G)
        rng = np.random.default_rng(seed)
        draw = rng.integers(0, G, size=(5000, G))
        bs = sf[draw].sum(1) / nf[draw].sum(1) - sr[draw].sum(1) / nr[draw].sum(1)
        diff[h] = {"diff_pct": round(100 * d, 2), "boot95_pct": [round(100 * np.quantile(bs, .025), 2), round(100 * np.quantile(bs, .975), 2)],
                   "boot": "quarter-cluster"}
    res["fell_minus_rose"] = diff
    return res, df


def dedupe(df):
    """One row per report (ticker, reaction day). Rows that agree in sign are kept once; reports whose rows have
    different signs are left out, since the file gives no fiscal period to choose between them."""
    keep, same, crows, clist = [], 0, 0, []
    for (t, d0), g in df.groupby(["ticker", "day0"], sort=False):
        if g.sign.nunique() > 1:
            crows += len(g)
            clist.append(f"{t} {d0.date()}: " + ", ".join(f"{x:+.2f}%" for x in g.surprise_pct))
            continue
        same += len(g) - 1
        keep.append(g.index[0])
    out = df.loc[sorted(keep)].reset_index(drop=True)
    return out, {"same_sign": same, "conflict_rows": crows, "conflict_reports": len(clist), "conflict_list": clist}


def alignment(df):
    """T9: variance of AR on labelled reaction day vs day before / after, per ticker."""
    out = {}
    for t, g in df.groupby("ticker"):
        v = {"day-1": float((g.ar_m1 ** 2).mean()), "day0": float((g.ar0 ** 2).mean()), "day+1": float((g.ar_p1 ** 2).mean())}
        out[t] = {k: round(1e4 * x, 2) for k, x in v.items()}
        out[t]["day0_highest"] = v["day0"] > max(v["day-1"], v["day+1"])
    return out


if __name__ == "__main__":
    r, df = run()
    print(json.dumps(r, indent=1, default=str))
    print(json.dumps(alignment(df), indent=1))
    print("max(est_last - day0) sessions check:", (df.est_last < df.day0).all())
