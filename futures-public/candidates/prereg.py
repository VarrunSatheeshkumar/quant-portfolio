"""Pre-registration: measure each design's dispersion without reading its signal.

Prints, per tested candidate, the sample size, the block-bootstrap standard error
of the pre-registered statistic, the threshold it must clear at N = 20, and the
MDE. Means are computed inside the bootstrap and never printed or stored.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C          # noqa: E402
import simulator            # noqa: E402

out = {}
d = C.load()
cost = C.cost_sigma()


def rec(key, n, se, unit, **extra):
    out[key] = dict(n=int(n), se=se, clear=C.Z_CLEAR * se, mde20=C.Z_MDE * se, mde_unadj=C.Z_MDE_UNADJ * se, unit=unit, **extra)
    print(f"{key:4s} n={n:6d}  {C.mde_line(se, unit)}" + (f"  | {extra}" if extra else ""))


# C14 control: SPY overnight, bp/day
s = C.c14_series()
se = C.block_se(s.overnight.values * 1e4, s.index)
rec("C14", len(s), se, "bp/day", cost_bp=0.86, first=str(s.index.min().date()), last=str(s.index.max().date()))

# C19: paired difference in outcome shares at 15% vol, base mandate; SE from month blocks of start dates
net, capped, mult = C.c19_paths()
BASE = dict(target=0.08, max_dd=0.10, daily_loss=0.03, window=60)
a = simulator.simulate(simulator.scaled(net, 0.15), **BASE)
b = simulator.simulate(simulator.scaled(capped, 0.15), **BASE)
diff_daily = ((b.outcome == "breach_daily").astype(float) - (a.outcome == "breach_daily").astype(float))
diff_pass = ((b.outcome == "pass").astype(float) - (a.outcome == "pass").astype(float))
se_d = C.block_se(diff_daily.values * 100, diff_daily.index)
se_p = C.block_se(diff_pass.values * 100, diff_pass.index)
rec("C19", len(a), se_d, "pp (breach_daily share)", se_pass_pp=se_p, mean_multiplier=float(mult.mean()),
    share_days_capped=float((mult < 1).mean()), path_end=str(net.index.max().date()))

# C2: expiring-contract pressure, sigma units over 3 bars
ev = C.c2_events(d)
se = C.block_se(ev.y.values, ev.date)
rec("C2", len(ev), se, "sigma (3-bar sum)", per_market=ev.groupby("market").size().to_dict(),
    cost_sigma_3x_spread={m: round(3 * float(cost[m]), 3) for m in C.PHYSICAL})

# panel candidates: slope of next-month sigma-unit return on the cross-sectionally standardised signal
y = C.next_month_return(d["rs"][C.COMMODITIES])
for key, sig in [("C9", C.c9_signal(d)), ("C1", C.c1_signal(d))]:
    x = sig.reindex(y.index)
    num, den = C.panel_slope(y, x)
    se = C.slope_se(num, den)
    both = (y.notna() & x.notna())
    ls, turn = C.tercile_ls(y, x)
    rec(key, int(both.sum().sum()), se, "sigma_m per 1 sd of signal", months=int((both.sum(axis=1) >= 8).sum()),
        ls_se_sigma_m=C.block_se(ls.values, ls.index), tercile_turnover=float(turn.mean()),
        median_rt_cost_sigma=float(cost[C.COMMODITIES].median()))

# C11: treasury auction round trip, sigma units
ev = C.c11_events(d)
se = C.block_se(ev.y.values, ev.date)
rec("C11", len(ev), se, "sigma (post - pre, 4 bars)", per_market=ev.groupby("market").size().to_dict(),
    cost_two_round_trips={m: round(2 * float(cost[m]), 3) for m in ["ZN", "ZB"]})

# C15: EIA report drift, sigma units over 2 bars
ev = C.c15_events(d)
se = C.block_se(ev.y.values, ev.date)
rec("C15", len(ev), se, "sigma (signed 2-bar sum)", per_market=ev.groupby("market").size().to_dict(),
    cost_one_round_trip={m: round(float(cost[m]), 3) for m in ["CL", "HO", "RB"]})

# C18: crypto funding carry, weekly long-short alpha on BTC, % per week
try:
    w = C.c18_weekly()
    _, df = C.alpha_on_btc(w.ls * 100, w.btc * 100)
    se = C.alpha_se(df)
    rec("C18", len(df), se, "% per week (alpha on BTC)", first=str(w.index.min().date()), last=str(w.index.max().date()),
        mean_symbols=float(w.n.mean()), turnover=float(w.turnover.mean()), cost_pct_week=float(w.turnover.mean() * 0.20))
except FileNotFoundError:
    print("C18 pending: Binance data not yet cached")

REP = C.config.REPORTS / "candidates"
REP.mkdir(parents=True, exist_ok=True)
json.dump(out, open(REP / "prereg_design.json", "w"), indent=1, default=str)
