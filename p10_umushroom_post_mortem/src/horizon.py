"""Component G: signal by horizon. History strictly <= 6 Nov 2026.
G2 identity: dln P = dln EPS_ttm + dln(P/E); s_E(h) = Cov(dlnP, dlnEPS)/Var(dlnP); s_PE = 1 - s_E.
Caveats printed with every number: trailing EPS is backward-looking; a fall in the multiple can be rational news about
future earnings; four hindsight-chosen tickers. s_E at 1q is near zero partly by construction (TTM EPS moves only on report days)."""
import math

import numpy as np
import pandas as pd

from config import CUTOFF, FACTOR_MAP, USD
import data
import event_study
import fundamentals

US = ["NVDA", "WMT", "AMAT", "HD"]
HS = (1, 4, 12, 20)
FLOOR = 0.20
CAVEAT = ("Trailing EPS is backward-looking; a fall in the multiple can be rational news about future earnings; "
          "four hindsight-chosen tickers; the 1-quarter figure is near zero partly by construction.")
SPLITS = {"NVDA": ["2021-07-20", "2024-06-10"], "WMT": ["2024-02-26"]}


def eps_series(t, snap=None):
    """Reported EPS rows up to 3 days before the cutoff. Returns (rows, counts): same-day duplicates are ambiguous and
    both rows are dropped; rows after the cutoff are dropped; each counted separately."""
    snap = snap or fundamentals.snapshots()[-1]
    df = pd.read_csv(snap / f"{t}_get_earnings_dates.csv")
    df["ts"] = pd.to_datetime(df["Earnings Date"], utc=True).dt.tz_convert("America/New_York")
    df = df.dropna(subset=["Reported EPS"])
    df["date"] = df.ts.dt.tz_localize(None).dt.normalize()
    n0 = len(df)
    df = df.drop_duplicates(subset=["date"], keep=False)          # same-day duplicates are ambiguous: drop both
    n_dup = n0 - len(df)
    df = df.sort_values("ts")
    n1 = len(df)
    df = df[df.date <= CUTOFF - pd.Timedelta(days=3)]
    df = df.assign(q=df.date.dt.year * 4 + (df.date.dt.month - 1) // 3)   # calendar quarter of the report = fiscal-quarter sequence
    assert df.q.is_monotonic_increasing and df.q.is_unique, t
    out = df[["ts", "date", "q", "Reported EPS"]].rename(columns={"Reported EPS": "eps"}).reset_index(drop=True)
    return out, {"same_day_duplicates": int(n_dup), "after_cutoff": int(n1 - len(df))}


def quarterly_panel(t, snap=None):
    """One row per report with trailing-twelve-month EPS = sum of four CONSECUTIVE fiscal quarters (the report and the
    three before it, with no missing quarter in between). Reports whose trailing year has a gap are left out."""
    ev, counts = eps_series(t, snap)
    px = data.load_pre(None, CUTOFF, kind="raw", tickers=[t])[t].dropna()   # split-adjusted, not dividend-adjusted
    tdays = px.index
    rows, gaps = [], 0
    for k in range(3, len(ev)):
        if ev.q[k] - ev.q[k - 3] != 3:                              # a missing quarter inside the trailing year
            gaps += 1
            continue
        d0 = event_study.reaction_day(ev.ts[k], tdays)
        if d0 is None:
            continue
        i = tdays.get_loc(d0) + 1                                   # close two sessions after the release
        if i >= len(tdays):
            continue
        ttm = float(ev.eps[k - 3:k + 1].sum())
        rows.append({"date": ev.date[k], "q": int(ev.q[k]), "price": float(px.iloc[i]),
                     "price_date": tdays[i], "ttm": ttm})
    p = pd.DataFrame(rows)
    counts["ttm_with_missing_quarter"] = gaps
    return p, counts


def changes(p, h, floor=None):
    """Log changes between reports exactly h fiscal quarters apart (matched on the quarter index, not on row offsets,
    so a missing report never stretches a pair)."""
    floor = FLOOR if floor is None else floor
    s = p.set_index("q")
    q0 = s.index[np.isin(s.index + h, s.index)]
    a, b = s.loc[q0], s.loc[q0 + h]
    x = np.log(b.price.values) - np.log(a.price.values)
    ok = (b.ttm.values >= floor) & (a.ttm.values >= floor) & (b.ttm.values > 0) & (a.ttm.values > 0)
    y = np.full(len(x), np.nan)
    y[ok] = np.log(b.ttm.values[ok]) - np.log(a.ttm.values[ok])
    q = np.asarray(q0)
    keep = ~np.isnan(y)
    return x[keep], y[keep], q[keep], int((~keep).sum())


def s_e(x, y):
    vx = np.var(x, ddof=1)
    return float(np.cov(x, y, ddof=1)[0, 1] / vx), float(np.cov(x, x - y, ddof=1)[0, 1] / vx)


def _within(X, Y, T):
    """Deviations from each company's own means (T = company code), computed on the rows given."""
    k = np.bincount(T, minlength=len(US)).astype(float)
    k[k == 0] = 1.0
    mx = np.bincount(T, weights=X, minlength=len(US)) / k
    my = np.bincount(T, weights=Y, minlength=len(US)) / k
    return X - mx[T], Y - my[T]


def g2(n_draws=20000, seed=20261122, panels=None, floor=None, recentre="draw"):
    """recentre="draw" (used for every published figure): company means recomputed in each bootstrap draw.
    recentre="fixed" reproduces the estimator before the third audit (means fixed at their full-sample values), kept
    only so test T18 can record its false-claim rate beside the current one."""
    panels = panels or {t: quarterly_panel(t)[0] for t in US}
    est = {"per_ticker": {}, "pooled": {}, "dropped_floor": {}, "n": {}}
    data_h = {}
    for h in HS:
        X, Y, Q, T = [], [], [], []
        for t in US:
            x, y, q, nd = changes(panels[t], h, floor)
            se, spe = s_e(x, y)
            est["per_ticker"].setdefault(t, {})[h] = {"s_E": round(se, 3), "s_PE": round(spe, 3), "n": len(x)}
            est["dropped_floor"].setdefault(t, {})[h] = nd
            X.append(x); Y.append(y); Q.append(q); T += [US.index(t)] * len(x)
        X, Y, Q, T = np.concatenate(X), np.concatenate(Y), np.concatenate(Q), np.array(T)
        se, spe = s_e(*_within(X, Y, T))                                # pooled on within-company deviations
        est["pooled"][h] = {"s_E": round(se, 3), "s_PE": round(spe, 3), "n": len(X)}
        data_h[h] = (X, Y, Q, T)
    # circular block bootstrap over calendar quarters, block = h, same blocks across tickers; within-company means are
    # recomputed in every draw (fixed full-sample means made the intervals too narrow, third audit)
    rng = np.random.default_rng(seed)
    qmin = min(d[2].min() for d in data_h.values()); qmax = max(d[2].max() for d in data_h.values())
    allq = np.arange(qmin, qmax + 1)
    nq = len(allq)
    boots = {h: np.empty(n_draws) for h in HS}
    diff = np.empty(n_draws)
    assert recentre in ("draw", "fixed")
    fixed = {h: tuple(np.array([data_h[h][j][data_h[h][3] == c].mean() for c in range(len(US))]) for j in (0, 1)) for h in HS}
    # rows of each horizon sorted by quarter, so a draw of quarters maps to row indices without a Python loop
    order = {h: np.argsort(data_h[h][2], kind="stable") for h in HS}
    cnt = {h: np.bincount(data_h[h][2] - qmin, minlength=nq) for h in HS}
    first = {h: np.concatenate([[0], np.cumsum(cnt[h])[:-1]]) for h in HS}

    def draw_quarters(block):
        nb = math.ceil(nq / block)
        starts = rng.integers(0, nq, nb)
        return ((starts[:, None] + np.arange(block)[None, :]) % nq).ravel()[:nq]

    def slope(h, qs):
        """Pooled slope on the resampled rows, with each company's means recomputed on the draw (as the point
        estimate demeans within company on the sample it uses)."""
        n = cnt[h][qs]
        ii = order[h][np.repeat(first[h][qs] - np.cumsum(n) + n, n) + np.arange(n.sum())]
        X, Y, T = data_h[h][0][ii], data_h[h][1][ii], data_h[h][3][ii]
        if recentre == "fixed":
            return s_e(X - fixed[h][0][T], Y - fixed[h][1][T])[0]
        return s_e(*_within(X, Y, T))[0]

    for b in range(n_draws):
        for h in HS:
            boots[h][b] = slope(h, draw_quarters(h))
        # the 20q - 1q difference: one draw of calendar-quarter blocks (block 20) applied to both horizons (paired)
        qs = draw_quarters(max(HS))
        diff[b] = slope(20, qs) - slope(1, qs)
    est["pooled_ci95"] = {h: [round(float(np.quantile(boots[h], q)), 3) for q in (0.025, 0.975)] for h in HS}
    est["pooled_diff_20_1"] = {"point": round(est["pooled"][20]["s_E"] - est["pooled"][1]["s_E"], 3),
                               "ci95": [round(float(np.quantile(diff, q)), 3) for q in (0.025, 0.975)],
                               "ci99": [round(float(np.quantile(diff, q)), 3) for q in (0.005, 0.995)],
                               "bootstrap": "paired: the same calendar-quarter blocks (length 20) for both horizons"}
    rises = {t: est["per_ticker"][t][20]["s_E"] > est["per_ticker"][t][1]["s_E"] for t in US}
    est["rises_per_ticker"] = rises
    # Claim bar on the 99% interval: in T18's synthetic null (random-walk multiple, no true difference) the paired 95%
    # interval excludes zero in about 17% of panels, not 5%, even with company means recomputed in each draw (block
    # bootstrap with ~100 quarters and 20-quarter overlaps), so the 95% bar would claim a rise too often (out/t18.json).
    # All G2 intervals are too narrow by the same cause.
    est["claim_bar_met"] = bool(est["pooled_diff_20_1"]["ci99"][0] > 0 and sum(rises.values()) >= 3)
    est["interval_note"] = ("Block-bootstrap intervals are too narrow here: in a synthetic null with ~100 quarters they "
                            "exclude a true zero difference far more often than nominal (test T18); read them as descriptive.")
    est["exceptions"] = [t for t, r in rises.items() if not r]
    est["caveat"] = CAVEAT
    est["n_draws"], est["seed"] = n_draws, seed
    return est


def split_check():
    out = {}
    for t, ds in SPLITS.items():
        p, _ = quarterly_panel(t)
        for d in ds:
            d = pd.Timestamp(d)
            before = p[p.date < d].tail(1); after = p[p.date > d].head(1)
            out[f"{t} {d.date()}"] = round(float(after.ttm.iloc[0] / before.ttm.iloc[0]), 3)
    return out


def report_calendar(t, snap=None):
    """Reaction days of every release dated on or before the 6 Nov cutoff in the estimates file, whether or not Yahoo
    filled in its EPS (Walmart's 20 Aug 2026 report has none), mapped on the stock's full pre-cutoff trading calendar
    so that no release before a window's first session is pulled onto that session."""
    snap = snap or fundamentals.snapshots()[-1]
    df = pd.read_csv(snap / f"{t}_get_earnings_dates.csv")
    ts = pd.to_datetime(df["Earnings Date"], utc=True).dt.tz_convert("America/New_York")
    ts = ts[ts.dt.tz_localize(None).dt.normalize() <= CUTOFF]
    tdays = data.load_pre(None, CUTOFF, kind="adj", tickers=[t])[t].dropna().index
    days = {event_study.reaction_day(x, tdays) for x in ts}
    return sorted(x for x in days if x is not None)


def g1(start="2021-11-01"):
    """10-day R^2 on market + sector (non-overlapping 10-session blocks on the equity's own trading sessions, history
    to 6 Nov) and the share of daily variance on earnings reaction days (5 years to 6 Nov). Report days come from
    report_calendar: every dated release, with or without reported EPS, mapped on the full trading history and only
    then intersected with the five-year window."""
    out = {}
    for t in US + ["BA.L", "RR.L"]:
        mkt, sec = FACTOR_MAP[t]
        full = data.load_pre(start, CUTOFF, kind="adj", tickers=[t, mkt, sec])
        sessions = full[t].dropna().index                          # the equity's own trading days only
        px = full.ffill().reindex(sessions)
        if t not in USD:
            px[sec] = px[sec].shift(1)                             # US-listed sector ETF: previous session's close
        px = px.dropna()
        b = px.iloc[::10]
        r = np.log(b).diff().dropna()
        X = np.column_stack([np.ones(len(r)), r[mkt], r[sec]])
        coef, *_ = np.linalg.lstsq(X, r[t].values, rcond=None)
        res = r[t].values - X @ coef
        row = {"r2_10d_mkt_sector": round(1 - res.var() / r[t].values.var(), 3), "n_blocks": len(r),
               "calendar": "own trading sessions"}
        if t in US:
            d = np.log(px[t]).diff().dropna()
            mask = d.index.isin(report_calendar(t))
            row["share_var_on_report_days"] = round(float((d[mask] ** 2).sum() / (d ** 2).sum()), 3)
            row["report_days"] = int(mask.sum()); row["share_of_days"] = round(float(mask.mean()), 3)
        out[t] = row
    return out


def lo_mackinlay(r, q):
    """Variance ratio and heteroskedasticity-robust z* (Lo-MacKinlay 1988) on log returns r."""
    r = np.asarray(r); T = len(r); mu = r.mean()
    s1 = ((r - mu) ** 2).sum() / (T - 1)
    rq = np.convolve(r, np.ones(q), "valid")
    m = q * (T - q + 1) * (1 - q / T)
    sq = ((rq - q * mu) ** 2).sum() / m
    vr = sq / s1
    e2 = (r - mu) ** 2
    theta = 0.0
    for j in range(1, q):
        delta = (e2[j:] * e2[:-j]).sum() / (e2.sum() ** 2)
        theta += (2 * (q - j) / q) ** 2 * delta * T
    theta /= T
    z = (vr - 1) / math.sqrt(theta) if theta > 0 else float("nan")
    return round(float(vr), 3), round(float(z), 2)


def g3(start="2010-01-01", book=None):
    out = {}
    if book is not None:
        r = np.log1p(book.values)
        out["BOOK_13Nov"] = {q: dict(zip(("VR", "z_robust"), lo_mackinlay(r, q))) for q in (5, 10, 21, 63)}
        out["BOOK_13Nov"]["reading_10d"] = ("significantly below 1" if out["BOOK_13Nov"][10]["z_robust"] < -1.96
                                            else "no evidence that two-week moves reverse")
    for t in US + ["BA.L", "RR.L", "BTC-USD"]:
        s = data.load_pre(start, CUTOFF, kind="adj", tickers=[t])[t].dropna()
        r = np.log(s).diff().dropna().values
        out[t] = {q: dict(zip(("VR", "z_robust"), lo_mackinlay(r, q))) for q in (5, 10, 21, 63)}
        vr10, z10 = out[t][10]["VR"], out[t][10]["z_robust"]
        out[t]["reading_10d"] = ("significantly below 1" if z10 < -1.96 else "no evidence that two-week moves reverse")
    return out


def leak_snapshot():
    p = {t: quarterly_panel(t)[0] for t in US}
    return json_dump({t: v.to_dict(orient="list") for t, v in p.items()}) + json_dump(g3("2024-01-01"))


def json_dump(o):
    import json
    return json.dumps(o, default=str)
