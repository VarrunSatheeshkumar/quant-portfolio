"""Component H: drawdown context. How often did a 10-session fall this size happen, and was what followed different
from any other date? History strictly <= 6 Nov 2026 (load_pre). Selection caveat applies to every book/single-name number."""
import numpy as np
import pandas as pd

from config import CUTOFF, USD
import data

BOOK13 = ["NVDA", "WMT", "AMAT", "HD", "BA.L", "RR.L", "BTC-USD"]
CAVEAT = "Hindsight-selected names (and a book built from them): forward returns reflect past winners."


def book_returns(weights, start="2014-09-01", end=CUTOFF, loader=None):
    loader = loader or data.load_pre
    px = loader(start, end, kind="adj", tickers=list(weights) + ["GBPUSD=X"])
    cal = px["NVDA"].dropna().index if "NVDA" in weights else px.dropna(how="all").index
    cal = cal[cal >= px[list(weights)].dropna().index.min()]
    fx = px["GBPUSD=X"].reindex(cal).ffill()
    g = pd.DataFrame({a: (px[a].reindex(cal).ffill() / fx if a in USD else px[a].reindex(cal).ffill()) for a in weights})
    r = g.pct_change().dropna()
    w = pd.Series(weights)
    return (r[w.index] * w).sum(axis=1)   # daily rebalanced; cash weight earns 0


def us_sessions(start, end, loader):
    """US equity sessions (NVIDIA's trading days), the calendar the book and the US names use."""
    return loader(start, end, kind="adj", tickers=["NVDA"])["NVDA"].dropna().index


def local_returns(ticker, start="2000-01-01", end=CUTOFF, us_calendar=False):
    """Daily returns in the asset's own currency. us_calendar=True samples a 7-day asset (Bitcoin) on US sessions,
    so its ten-row windows are ten US sessions, as for the book and the equities."""
    s = data.load_pre(start, end, kind="adj", tickers=[ticker])[ticker].dropna()
    if us_calendar:
        cal = us_sessions(start, end, data.load_pre)
        s = s.reindex(s.index.union(cal)).ffill().reindex(cal[cal >= s.index.min()])
    return s.pct_change().dropna()


def episodes(roll, thr, spacing=21):
    idx = np.where(roll.values <= thr)[0]
    out, last = [], -10 ** 9
    for i in idx:
        if i - last > spacing:
            out.append(i)
            last = i
        elif i - last <= spacing:
            pass
    # spacing rule: after a counted first crossing, none counted for `spacing` sessions
    return out


def _episodes_strict(roll, thr, spacing):
    hits = roll.values <= thr
    out, blocked_until = [], -1
    for i, h in enumerate(hits):
        if h and i > blocked_until:
            out.append(i)
            blocked_until = i + spacing
    return out


def forward(cum, i, h):
    """Return from position i (end of the 10-day window) over the next h sessions, or None if beyond the data."""
    if i + h >= len(cum):
        return None
    return float(cum[i + h] / cum[i] - 1)


def analyse(r, thr, h_fwd=(126, 252), spacing=21, n_draws=20000, seed=20261122, win=10):
    cum = np.concatenate([[1.0], np.cumprod(1 + r.values)])     # cum[k] = value after k returns
    roll = pd.Series(cum[win:] / cum[:-win] - 1, index=r.index[win - 1:])   # 10-day return ending at day j
    pos = np.arange(win, len(cum))                                # position in cum for each roll entry
    eps = _episodes_strict(roll, thr, spacing)
    res = {"threshold_pct": round(100 * thr, 2), "n_windows": int(len(roll)), "k_windows_at_or_below": int((roll <= thr).sum()),
           "share_windows_pct": round(100 * float((roll <= thr).mean()), 2), "n_episodes": len(eps),
           "episodes_by_spacing": {s: len(_episodes_strict(roll, thr, s)) for s in (10, 21, 42)},
           "first": str(r.index[0].date()), "last": str(r.index[-1].date()), "episodes": [], "forward": {}}
    for e in eps:
        row = {"date": str(roll.index[e].date()), "fall_10d_pct": round(100 * float(roll.iloc[e]), 2)}
        for h in h_fwd:
            f = forward(cum, pos[e], h)
            row[f"fwd{h}_pct"] = None if f is None else round(100 * f, 2)
        res["episodes"].append(row)
    rng = np.random.default_rng(seed)
    for h in h_fwd:
        eligible = np.where(pos + h < len(cum))[0]
        obs = [forward(cum, pos[e], h) for e in eps if pos[e] + h < len(cum)]
        dropped = len(eps) - len(obs)
        allf = cum[pos[eligible] + h] / cum[pos[eligible]] - 1
        out = {"n_used": len(obs), "n_dropped_window_past_cutoff": dropped,
               "unconditional_mean_pct": round(100 * float(allf.mean()), 2),
               "unconditional_share_pos_pct": round(100 * float((allf > 0).mean()), 1)}
        if obs:
            mo, so = float(np.mean(obs)), float(np.mean(np.array(obs) > 0))
            means, shares = random_dates(allf, len(obs), spacing, n_draws, rng)
            out.update({"obs_mean_pct": round(100 * mo, 2), "obs_share_pos_pct": round(100 * so, 1),
                        "pctile_mean": round(100 * float((means < mo).mean() + 0.5 * (means == mo).mean()), 1),
                        "pctile_share": round(100 * float((shares < so).mean() + 0.5 * (shares == so).mean()), 1),
                        "rand_mean_2.5_97.5_pct": [round(100 * float(np.quantile(means, q)), 2) for q in (0.025, 0.975)],
                        "rand_share_2.5_97.5_pct": [round(100 * float(np.quantile(shares, q)), 1) for q in (0.025, 0.975)]})
            pm, ps = out["pctile_mean"], out["pctile_share"]
            out["verdict"] = ("not distinguishable from any other date" if 2.5 <= pm <= 97.5 and 2.5 <= ps <= 97.5
                              else "different from a random date")
        res["forward"][h] = out
    res["caveat"] = CAVEAT
    return res


def random_dates(allf, n, spacing, n_draws, rng):
    """Draw n eligible dates with pairwise gaps > spacing sessions (the same rule as _episodes_strict), n_draws times.
    'Stars and bars': n distinct sorted positions in range(span), span = N - (n-1)*spacing, then add i*spacing to the
    i-th; consecutive gaps are then >= spacing + 1 and every arrangement with such gaps is equally likely."""
    N = len(allf)
    means, shares = np.empty(n_draws), np.empty(n_draws)
    span = N - (n - 1) * spacing
    assert span >= n, "not enough history for spacing"
    for k in range(n_draws):
        base = np.sort(rng.choice(span, size=n, replace=False))
        idx = base + np.arange(n) * spacing
        f = allf[idx]
        means[k], shares[k] = f.mean(), (f > 0).mean()
    return means, shares


def realised_10d(weights=None, ticker=None, start="2026-11-06", end="2026-11-20", us_calendar=False):
    if ticker:
        s = data.load(start, end, kind="adj", tickers=[ticker])[ticker].dropna()
        if us_calendar:
            cal = us_sessions(start, end, data.load)
            s = s.reindex(s.index.union(cal)).ffill().reindex(cal)
        return float(s.iloc[-1] / s.iloc[0] - 1), int(len(s) - 1)
    r = book_returns(weights, start=start, end=end, loader=data.load)
    r = r[r.index > pd.Timestamp(start)]
    return float(np.prod(1 + r.values) - 1), int(len(r))
