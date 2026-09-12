"""Drawdown-mandate path simulator on real daily returns.

Start on a day, run the actual path forward, apply the mandate, record what
happened first: the profit target (pass), the max-drawdown limit or the daily-loss
limit (breach), or the end of the window (timeout). Every start day is used, so the
attempts span every regime in the sample and overlap heavily -- they are not
independent, and no confidence interval is claimed for the pass rate.
"""

import numpy as np
import pandas as pd


def simulate(r, target, max_dd, daily_loss, window):
    """r: daily net returns (fraction). Returns a DataFrame with one row per start."""
    x = np.asarray(r, float)
    x = np.nan_to_num(x, nan=0.0)
    n = len(x) - window
    if n <= 0:
        return pd.DataFrame()
    # rolling windows as a 2-D view: starts x days
    win = np.lib.stride_tricks.sliding_window_view(x, window)[:n]
    eq = np.cumprod(1 + win, axis=1)
    peak = np.maximum.accumulate(eq, axis=1)
    dd = eq / peak - 1
    hit_pass = eq >= 1 + target
    hit_dd = dd <= -max_dd
    hit_day = win <= -daily_loss
    first = lambda m: np.where(m.any(axis=1), m.argmax(axis=1), window)   # noqa: E731
    t_pass, t_dd, t_day = first(hit_pass), first(hit_dd), first(hit_day)
    t_breach = np.minimum(t_dd, t_day)
    outcome = np.where(t_pass < t_breach, "pass", np.where(t_breach < window, np.where(t_dd <= t_day, "breach_dd", "breach_daily"), "timeout"))
    # a pass and a breach on the same day: the daily limit is checked at the close, the target intraday-agnostic;
    # treat same-day as breach (conservative)
    same = (t_pass == t_breach) & (t_pass < window)
    outcome = np.where(same, np.where(t_dd <= t_day, "breach_dd", "breach_daily"), outcome)
    days = np.where(outcome == "pass", t_pass + 1, np.where(outcome == "timeout", window, t_breach + 1))
    return pd.DataFrame({"outcome": outcome, "days": days}, index=pd.Index(r.index[:n], name="start"))


def summarise(sim):
    if len(sim) == 0:
        return dict(n=0, pass_prob=np.nan, median_days_to_pass=np.nan, breach_dd=np.nan, breach_daily=np.nan, timeout=np.nan)
    share = sim["outcome"].value_counts(normalize=True)
    return dict(n=int(len(sim)), pass_prob=float(share.get("pass", 0.0)),
                median_days_to_pass=float(sim.loc[sim.outcome == "pass", "days"].median()) if (sim.outcome == "pass").any() else np.nan,
                breach_dd=float(share.get("breach_dd", 0.0)), breach_daily=float(share.get("breach_daily", 0.0)),
                timeout=float(share.get("timeout", 0.0)))


def scaled(r, vol_target, ann=252):
    """Linear rescaling of the return path to a vol target."""
    return r * (vol_target / (r.std() * np.sqrt(ann)))
