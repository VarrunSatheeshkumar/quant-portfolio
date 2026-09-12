"""Designs shared by the pre-registration and the candidate tests.

Every candidate's statistic is built here, once, so the number tested is the
number that was pre-registered. Nothing in this module prints a mean: the
pre-registration script reads only dispersions from these designs.

Units: a market's daily return is its neutralised dollar change per contract
(data/grid/w0, roll days blank) divided by its trailing 60-day dollar volatility
known at the previous close -- "sigma units". Costs are in the same units:
round-trip cost as a share of a one-sigma move, from the s1 model.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import backtest                  # noqa: E402
import config                    # noqa: E402
from lib import power            # noqa: E402
from stages import rolls         # noqa: E402

START = "2002-01-01"             # 60-day vol and 252-day lookbacks exist for every market
Z_CLEAR = 3.02                   # two-sided alpha 0.05/20 = 0.0025 -> a directional claim clears at t >= 3.02
Z_MDE = 3.86                     # z_{0.99875} + z_{0.80}: MDE at 80% power under the N=20 correction
Z_MDE_UNADJ = 2.80
COMMODITIES = ["CL", "NG", "HO", "RB", "GC", "SI", "HG", "ZC", "ZS", "ZW", "KC", "SB", "CT"]
PHYSICAL = ["CL", "NG", "HO", "RB", "ZC", "ZS", "ZW", "KC", "SB", "CT"]    # metals excluded: Yahoo shows any-month nearest
CAND = ROOT / "data" / "raw" / "cand"
STAGES = ROOT / "data" / "stages"


# ----------------------------------------------------------------------------- data
def load():
    w0 = pd.read_parquet(config.GRID / "w0.parquet")
    raw = pd.read_parquet(config.GRID / "raw.parquet")
    px = pd.read_parquet(config.GRID / "px_raw.parquet")
    cols = [c for c in w0.columns if c in config.UNIVERSE]
    w0, raw, px = w0[cols], raw[cols], px[cols]
    dvol = backtest.dollar_vol(w0)
    rs = (w0 / dvol).loc[START:]
    return dict(w0=w0, raw=raw, px=px, dvol=dvol, rs=rs)


def cost_sigma():
    """Round-trip cost per market as a share of a one-sigma daily move."""
    s1 = pd.read_parquet(STAGES / "s1_costs.parquet")
    return (s1["round_trip_bp"] / s1["daily_vol_bp"]).astype(float)


def block_se(values, dates, n=2000, seed=config.SEED):
    """Standard error of a mean with whole months resampled."""
    v = np.asarray(values, float)
    ok = np.isfinite(v)
    blocks = pd.DatetimeIndex(dates)[ok].to_period("M").astype(str)
    return float(power.block_bootstrap(v[ok], blocks, n=n, seed=seed).std())


def mde_line(se, unit):
    return (f"SE {se:.4g} {unit}; clears at |stat| >= {Z_CLEAR * se:.4g} {unit} in the predicted direction "
            f"(t >= {Z_CLEAR}); MDE {Z_MDE_UNADJ * se:.4g} unadjusted / **{Z_MDE * se:.4g} at N = 20** {unit}")


# ----------------------------------------------------------------------------- event windows
def window_sum(r, end_date, k, side):
    """Sum of k consecutive bars of r. side='ending': the k bars ending at end_date
    inclusive (end_date must be a bar). side='after': the k bars strictly after
    end_date. NaN if a bar is missing or blank (a roll day inside the window)."""
    idx = r.index
    pos = idx.searchsorted(end_date)
    if pos >= len(idx):
        return np.nan
    if side == "ending":
        if idx[pos] != end_date or pos - k + 1 < 0:
            return np.nan
        seg = r.iloc[pos - k + 1: pos + 1]
    else:
        if idx[pos] == end_date:
            pos += 1
        if pos + k > len(idx):
            return np.nan
        seg = r.iloc[pos: pos + k]
    return float(seg.sum()) if seg.notna().all() and len(seg) == k else np.nan


def random_windows(r, n, k, avoid, rng, gap=5):
    """n random k-bar windows per market, away from `avoid` dates, for placebos."""
    idx = r.index
    bad = np.zeros(len(idx), bool)
    for d in avoid:
        p = idx.searchsorted(d)
        bad[max(p - gap - k, 0): p + gap + 1] = True
    cand = np.nonzero(~bad)[0]
    cand = cand[cand >= k]
    pick = rng.choice(cand, n, replace=True)
    out = []
    for p in pick:
        seg = r.iloc[p - k + 1: p + 1]
        out.append(float(seg.sum()) if seg.notna().all() else np.nan)
    return np.array(out)


# ----------------------------------------------------------------------------- C2 expiring-contract pressure
def c2_events(d, k=3, clip=5.0):
    """One row per exchange-rule expiry of a physically delivered market: the sum of
    the last k bars' sigma-unit returns (winsorised at +-clip per day), minus the
    market's mean k-bar sum on non-event days (a nuisance control, not an input)."""
    rs = d["rs"].clip(-clip, clip)
    rows = []
    for m in PHYSICAL:
        r = d["rs"][m].clip(-clip, clip).loc[START:]
        exp = rolls.expiries(m, config.UNIVERSE[m]["months"], r.index.min(), r.index.max())
        base = r.rolling(k).sum()
        mask = np.ones(len(r), bool)
        for e in exp:
            p = r.index.searchsorted(e)
            mask[max(p - k - 5, 0): p + 6] = False
        base_mean = float(base[mask].mean())
        for e in exp:
            v = window_sum(r, e, k, "ending")
            if np.isfinite(v):
                rows.append(dict(market=m, date=e, raw=v, y=v - base_mean, base=base_mean))
    return pd.DataFrame(rows)


def c2_placebo(d, ev, n=400, k=3, clip=5.0, seed=config.SEED):
    rng = np.random.default_rng(seed)
    out = []
    per = ev.groupby("market").size()
    for _ in range(n):
        vals = []
        for m, cnt in per.items():
            r = d["rs"][m].clip(-clip, clip).loc[START:]
            e = ev.loc[ev.market == m]
            v = random_windows(r, int(cnt), k, pd.DatetimeIndex(e.date), rng) - float(e.base.iloc[0])
            vals.append(v)
        out.append(float(np.nanmean(np.concatenate(vals))))
    return np.array(out)


# ----------------------------------------------------------------------------- monthly commodity panel (C1, C5, C9)
def month_ends(index):
    key = index.to_period("M")
    last = pd.Series(index, index=index).groupby(key).transform("last")
    return pd.DatetimeIndex(sorted(set(last)))


def next_month_return(rs, min_bars=15):
    """Sigma-unit return over the month after each month-end, per market."""
    me = month_ends(rs.index)
    out = {}
    for i, t in enumerate(me[:-1]):
        seg = rs.loc[t:me[i + 1]].iloc[1:]
        out[t] = seg.sum().where(seg.notna().sum() >= min_bars)
    return pd.DataFrame(out).T


def panel_slope(y, x):
    """Slope of y on x with month fixed effects; x is z-scored across markets within
    each month first, so the slope is sigma-units of next-month return per one
    cross-sectional standard deviation of the signal."""
    z = x.sub(x.mean(axis=1), axis=0).div(x.std(axis=1), axis=0)
    both = y.notna() & z.notna()
    y, z = y.where(both), z.where(both)
    yd = y.sub(y.mean(axis=1), axis=0)
    zd = z.sub(z.mean(axis=1), axis=0)
    num = (yd * zd).sum(axis=1)
    den = (zd ** 2).sum(axis=1)
    return num, den                     # per-month pieces; slope = num.sum()/den.sum()


def slope_from_pieces(num, den):
    return float(num.sum() / den.sum())


def slope_se(num, den, n=2000, seed=config.SEED):
    """Month-block bootstrap of the ratio of sums."""
    rng = np.random.default_rng(seed)
    num, den = num.values, den.values
    ok = np.isfinite(num) & (den > 0)
    num, den = num[ok], den[ok]
    out = np.empty(n)
    for i in range(n):
        ii = rng.integers(0, len(num), len(num))
        out[i] = num[ii].sum() / den[ii].sum()
    return float(out.std())


def panel_placebo(y, x, n=400, seed=config.SEED):
    """Signal shuffled across markets within each month: same values, random assignment."""
    rng = np.random.default_rng(seed)
    out = np.empty(n)
    vals = x.values.copy()
    for i in range(n):
        sh = vals.copy()
        for r in range(sh.shape[0]):
            ok = np.isfinite(sh[r])
            sh[r, ok] = rng.permutation(sh[r, ok])
        num, den = panel_slope(y, pd.DataFrame(sh, index=x.index, columns=x.columns))
        out[i] = slope_from_pieces(num, den)
    return out


def tercile_ls(y, x):
    """Monthly long-short of top minus bottom tercile of x, and its membership turnover."""
    z = x.sub(x.mean(axis=1), axis=0).div(x.std(axis=1), axis=0)
    both = y.notna() & z.notna()
    z = z.where(both)
    rk = z.rank(axis=1, pct=True)
    long = (rk > 2 / 3).astype(float).where(both)
    short = (rk <= 1 / 3).astype(float).where(both)
    ls = (y * long).sum(axis=1) / long.sum(axis=1).replace(0, np.nan) - (y * short).sum(axis=1) / short.sum(axis=1).replace(0, np.nan)
    pos = long.fillna(0) - short.fillna(0)
    turn = pos.diff().abs().sum(axis=1) / 2 / pos.abs().sum(axis=1).replace(0, np.nan)
    return ls, turn


def c9_signal(d, window=252, min_bars=200):
    """Trailing 12-month skewness of daily dollar changes (scale-free), at month-ends."""
    w0 = d["w0"][COMMODITIES]
    sk = w0.rolling(window, min_periods=min_bars).skew()
    me = month_ends(d["rs"].index)
    return -sk.reindex(me)                       # sign so that the predicted slope is positive


def c1_signal(d, lookback_days=365, min_rolls=3, clip=0.25):
    """Trailing-year sum of roll-day gaps as a share of price, at month-ends, negated:
    backwardation (new front below old) gives a positive signal."""
    raw, px = d["raw"], d["px"]
    me = month_ends(d["rs"].index)
    out = {}
    for m in COMMODITIES:
        days = pd.DatetimeIndex(pd.read_parquet(STAGES / f"s0_rolls_{m}.parquet")["roll_day"])
        days = days[days.isin(raw.index)]
        gap = (raw[m] / config.UNIVERSE[m]["mult"] / px[m].shift(1).abs()).reindex(days).clip(-clip, clip)
        s = {}
        for t in me:
            g = gap[(gap.index > t - pd.Timedelta(days=lookback_days)) & (gap.index <= t)]
            s[t] = -float(g.sum()) if g.notna().sum() >= min_rolls else np.nan
        out[m] = pd.Series(s)
    return pd.DataFrame(out)


# ----------------------------------------------------------------------------- C11 treasury auction cycle
def c11_events(d):
    t = pd.read_parquet(CAND / "treasury_auctions.parquet")
    t = t[(t.auctionDate >= START) & (t.auctionDate <= config.END)].dropna(subset=["auctionDate"])
    term = t.securityTerm.astype(str)
    fam = np.where(term.str.startswith(("10-Year", "9-Year")), "ZN", np.where(term.str.startswith(("30-Year", "29-Year")), "ZB", ""))
    t = t.assign(market=fam)[lambda x: x.market != ""]
    rows = []
    for m in ["ZN", "ZB"]:
        r = d["rs"][m]
        me = month_ends(r.index)
        for a in sorted(set(t.loc[t.market == m, "auctionDate"].dt.normalize())):
            p = r.index.searchsorted(a)
            if p >= len(r) or r.index[p] != a or p < 3:
                continue
            # skip auctions within two trading days of a month end (the C12 confound)
            near_me = any(abs(p - r.index.searchsorted(x)) <= 2 for x in me[(me >= a - pd.Timedelta(days=7)) & (me <= a + pd.Timedelta(days=7))])
            if near_me:
                continue
            pre = window_sum(r, r.index[p - 1], 2, "ending")          # bars A-2, A-1
            post = window_sum(r, r.index[p - 1], 2, "after")           # bars A, A+1
            if np.isfinite(pre) and np.isfinite(post):
                rows.append(dict(market=m, date=a, pre=pre, post=post, y=post - pre))
    return pd.DataFrame(rows)


def c11_placebo(d, ev, n=400, seed=config.SEED):
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        vals = []
        for m in ["ZN", "ZB"]:
            r = d["rs"][m]
            e = ev[ev.market == m]
            idx = r.index
            cand = np.arange(3, len(idx) - 3)
            pick = rng.choice(cand, len(e), replace=True)
            for p in pick:
                pre = window_sum(r, idx[p - 1], 2, "ending")
                post = window_sum(r, idx[p - 1], 2, "after")
                if np.isfinite(pre) and np.isfinite(post):
                    vals.append(post - pre)
        out.append(float(np.mean(vals)))
    return np.array(out)


# ----------------------------------------------------------------------------- C15 EIA report drift
def c15_events(d, markets=("CL", "HO", "RB"), k=2):
    """Release day = Wednesday, or Thursday when Monday/Tuesday/Wednesday of that week is
    not a trading day. y = sign(release-day return) x next k bars."""
    rows = []
    for m in markets:
        r = d["rs"][m]
        idx = r.index
        weeks = pd.Series(idx, index=idx).groupby(idx.to_period("W")).agg(list)
        for _, days in weeks.items():
            wd = {x.weekday(): x for x in days}
            rel = wd.get(2) if all(w in wd for w in (0, 1, 2)) else wd.get(3)
            if rel is None or not np.isfinite(r[rel]) or r[rel] == 0:
                continue
            nxt = window_sum(r, rel, k, "after")
            if np.isfinite(nxt):
                rows.append(dict(market=m, date=rel, r0=r[rel], y=np.sign(r[rel]) * nxt))
    return pd.DataFrame(rows)


def c15_pseudo(d, weekday, markets=("CL", "HO", "RB"), k=2):
    """The same statistic with another weekday as the pseudo-release day."""
    rows = []
    for m in markets:
        r = d["rs"][m]
        for t in r.index[r.index.weekday == weekday]:
            if not np.isfinite(r[t]) or r[t] == 0:
                continue
            nxt = window_sum(r, t, k, "after")
            if np.isfinite(nxt):
                rows.append(dict(market=m, date=t, y=np.sign(r[t]) * nxt))
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- C14 overnight control
def c14_series():
    s = pd.read_parquet(CAND / "spy.parquet").loc[START:]
    on = (s["open"] + s["dividends"]) / s["close"].shift(1) - 1
    intra = s["close"] / s["open"] - 1
    return pd.DataFrame(dict(overnight=on, intraday=intra)).dropna()


# ----------------------------------------------------------------------------- C19 VIX cap
def c19_paths(window_days=1260):
    net = pd.read_parquet(STAGES / "s6_net.parquet")["net"].dropna()
    vix = pd.read_parquet(CAND / "vix.parquet")["close"]
    med = vix.rolling(window_days, min_periods=750).median()
    mult = (med / vix).clip(upper=1.0).shift(1).reindex(net.index).ffill()
    capped = net * mult
    return net, capped, mult


# ----------------------------------------------------------------------------- C18 crypto funding carry
def c18_weekly(min_symbols=20, quintile=0.2):
    f = pd.read_parquet(CAND / "binance_funding.parquet")
    k = pd.read_parquet(CAND / "binance_klines_1d.parquet")
    px = k.pivot(index="open_time", columns="symbol", values="close").sort_index()
    fr = f.pivot_table(index=f["fundingTime"].dt.normalize(), columns="symbol", values="fundingRate", aggfunc="sum").sort_index()
    fr = fr.reindex(px.index).fillna(0.0).where(px.notna())
    mondays = px.index[px.index.weekday == 0]
    rows = []
    for i, t in enumerate(mondays[:-1]):
        t1 = mondays[i + 1]
        sig = fr.loc[t - pd.Timedelta(days=7): t - pd.Timedelta(days=1)].sum().where(px.loc[t].notna())     # last 7 days, as-of
        sig = sig.dropna()
        if len(sig) < min_symbols:
            continue
        ret = px.loc[t1] / px.loc[t] - 1
        fund = fr.loc[t + pd.Timedelta(days=1): t1].sum()          # funding accrued while held
        tot_long = ret - fund                                    # longs pay positive funding
        tot_short = -ret + fund
        n = int(np.ceil(len(sig) * quintile))
        lo = sig.nsmallest(n).index
        hi = sig.nlargest(n).index
        r_long = tot_long.reindex(lo).mean()
        r_short = tot_short.reindex(hi).mean()
        btc = ret.get("BTCUSDT", np.nan)
        rows.append(dict(date=t, n=len(sig), long=list(lo), short=list(hi), ls=r_long + r_short, btc=btc))
    w = pd.DataFrame(rows).set_index("date")
    prev = None
    turn = []
    for _, row in w.iterrows():
        cur = set(row["long"]) | set(row["short"])
        turn.append(np.nan if prev is None else 1 - len(cur & prev) / max(len(cur), 1))
        prev = cur
    w["turnover"] = turn
    return w


def alpha_on_btc(ls, btc):
    """Intercept and its month-block bootstrap SE of ls on btc."""
    df = pd.DataFrame(dict(y=ls, x=btc)).dropna()
    X = np.column_stack([np.ones(len(df)), df.x.values])
    b = np.linalg.lstsq(X, df.y.values, rcond=None)[0]
    return float(b[0]), df


def alpha_se(df, n=2000, seed=config.SEED):
    rng = np.random.default_rng(seed)
    months = df.index.to_period("M")
    uniq = months.unique()
    pos = {m: np.nonzero(months == m)[0] for m in uniq}
    out = np.empty(n)
    for i in range(n):
        ii = np.concatenate([pos[m] for m in rng.choice(uniq, len(uniq), replace=True)])
        X = np.column_stack([np.ones(len(ii)), df.x.values[ii]])
        out[i] = np.linalg.lstsq(X, df.y.values[ii], rcond=None)[0][0]
    return float(out.std())
