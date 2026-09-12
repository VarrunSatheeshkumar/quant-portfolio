"""Run one pre-registered candidate test. `python candidates/run.py C2`.

Each test computes exactly the statistic in common.py / PREREG.md, its
month-block SE, the corrected t, the placebo, and the cost comparison, writes
reports/candidates/<key>.md, and appends one line to reports/candidates/LOG.md.
The halting rules are applied by the operator between runs, not here.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C          # noqa: E402
import config               # noqa: E402
import simulator            # noqa: E402
from lib import validate    # noqa: E402

REP = config.REPORTS / "candidates"
D = json.load(open(REP / "prereg_design.json"))


def verdict(t, predicted_sign, placebo_ok, extra_ok=True):
    sign_ok = np.sign(t) == predicted_sign
    cleared = bool(sign_ok and abs(t) >= C.Z_CLEAR and placebo_ok and extra_ok)
    unadj = bool(sign_ok and abs(t) >= 1.96)
    return cleared, unadj


def finish(key, lines, status, oneline):
    (REP / f"{key}.md").write_text("\n".join(lines))
    with open(REP / "LOG.md", "a") as f:
        f.write(f"* {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')} **{key}** — {status}: {oneline}\n")
    print(f"{key} {status}: {oneline}")


def c14():
    s = C.c14_series()
    on = s.overnight * 1e4
    se = C.block_se(on.values, on.index)
    m = float(on.mean()); t = m / se
    # machinery: sign-flipped monthly block shuffle
    blocks = on.index.to_period("M").astype(str)
    rng = np.random.default_rng(config.SEED)
    uniq = pd.Index(blocks).unique()
    flips = pd.Series(rng.choice([-1.0, 1.0], len(uniq)), index=uniq).reindex(blocks).values
    sh = pd.Series(validate.block_shuffle(on.values, blocks) * flips, index=on.index)
    t_sh = float(sh.mean() / C.block_se(sh.values, sh.index))
    late = on.loc["2020-01-01":]
    intra = float(s.intraday.mean() * 1e4)
    cleared, unadj = verdict(t, +1, True, abs(t_sh) < C.Z_CLEAR)
    tradeable = m - 0.86 > 0
    L = ["# C14 — positive control: SPY overnight return", "",
         f"* mean overnight **{m:.2f} bp/day**, SE {se:.2f}, **t = {t:.2f}** (clears at 3.02); N = {len(on)}",
         f"* intraday mean {intra:.2f} bp/day (descriptive); 2020–2026 overnight mean {late.mean():.2f} bp/day (n = {len(late)})",
         f"* machinery: sign-flipped monthly-block shuffle t = {t_sh:.2f} (must be inside ±3.02)",
         f"* net of the ES round trip (0.86 bp): {m - 0.86:.2f} bp/day → {'tradeable' if tradeable else 'not tradeable'}",
         "", f"**{'CLEARED' if cleared else 'NOT CLEARED'}** at N = 20" + ("" if cleared else " — HALT: the pipeline did not detect a known effect")]
    finish("C14", L, "CLEARED" if cleared else "NOT CLEARED", f"overnight {m:.2f} bp/day, t = {t:.2f}, shuffle t = {t_sh:.2f}")


def c19():
    net, capped, mult = C.c19_paths()
    BASE = dict(target=0.08, max_dd=0.10, daily_loss=0.03, window=60)
    a = simulator.simulate(simulator.scaled(net, 0.15), **BASE)
    b = simulator.simulate(simulator.scaled(capped, 0.15), **BASE)
    sa, sb = simulator.summarise(a), simulator.summarise(b)
    dd = ((b.outcome == "breach_daily").astype(float) - (a.outcome == "breach_daily").astype(float)) * 100
    dp = ((b.outcome == "pass").astype(float) - (a.outcome == "pass").astype(float)) * 100
    se_d, se_p = C.block_se(dd.values, dd.index), C.block_se(dp.values, dp.index)
    d_daily, d_pass = float(dd.mean()), float(dp.mean())
    t = d_daily / se_d
    pass_ok = d_pass >= -C.Z_MDE * se_p
    # placebo: VIX block-shuffled by month
    vix = pd.read_parquet(C.CAND / "vix.parquet")["close"]
    blocks = vix.index.to_period("M").astype(str)
    plc = []
    for i in range(200):
        v = pd.Series(validate.block_shuffle(vix.values, blocks, seed=config.SEED + i), index=vix.index)
        med = v.rolling(1260, min_periods=750).median()
        m_ = (med / v).clip(upper=1.0).shift(1).reindex(net.index).ffill()
        bb = simulator.simulate(simulator.scaled(net * m_, 0.15), **BASE)
        plc.append(float(((bb.outcome == "breach_daily").astype(float) - (a.outcome == "breach_daily").astype(float)).mean() * 100))
    plc = np.array(plc)
    placebo_ok = d_daily < np.percentile(plc, 5)
    cleared, unadj = verdict(t, -1, placebo_ok, pass_ok)
    # descriptive: vol grid
    rows = {}
    for v in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40]:
        ra = simulator.summarise(simulator.simulate(simulator.scaled(net, v), **BASE))
        rb = simulator.summarise(simulator.simulate(simulator.scaled(capped, v), **BASE))
        rows[f"{v:.0%}"] = dict(pass_uncapped=ra["pass_prob"], pass_capped=rb["pass_prob"], daily_uncapped=ra["breach_daily"], daily_capped=rb["breach_daily"],
                                timeout_uncapped=ra["timeout"], timeout_capped=rb["timeout"])
    grid = pd.DataFrame(rows).T
    sharpe_a = float(net.mean() / net.std() * np.sqrt(252)); sharpe_b = float(capped.mean() / capped.std() * np.sqrt(252))
    L = ["# C19 — VIX-regime exposure cap against the daily-loss breach", "",
         f"* base mandate at 15% vol, {len(a)} paired starts: uncapped pass {sa['pass_prob']:.1%}, breach_daily {sa['breach_daily']:.1%}, breach_dd {sa['breach_dd']:.1%}, timeout {sa['timeout']:.1%}",
         f"* capped: pass {sb['pass_prob']:.1%}, breach_daily {sb['breach_daily']:.1%}, breach_dd {sb['breach_dd']:.1%}, timeout {sb['timeout']:.1%}",
         f"* **Δbreach_daily = {d_daily:+.2f} pp**, SE {se_d:.2f}, **t = {t:.2f}** (clears at −3.02); Δpass = {d_pass:+.2f} pp, SE {se_p:.2f} (non-inferiority bound −{C.Z_MDE*se_p:.2f}: {'ok' if pass_ok else 'FAILED'})",
         f"* placebo (200 month-shuffled VIX paths): Δbreach_daily 5th pct {np.percentile(plc, 5):+.2f}, median {np.median(plc):+.2f} pp → {'cleared' if placebo_ok else 'NOT cleared'}",
         f"* Sharpe of the path: uncapped {sharpe_a:.2f}, capped {sharpe_b:.2f} (descriptive; cap binds {float((mult < 1).mean()):.0%} of days, mean multiplier {float(mult.mean()):.2f})",
         "", "## Across the vol grid (descriptive)", "", grid.round(3).to_markdown(), "",
         f"**{'CLEARED' if cleared else 'NOT CLEARED'}** at N = 20" + ("" if cleared else f" ({'unadjusted 5% only' if unadj else 'no'})")]
    finish("C19", L, "CLEARED" if cleared else "NOT CLEARED", f"Δbreach_daily {d_daily:+.2f} pp (t {t:.2f}), Δpass {d_pass:+.2f} pp, placebo p5 {np.percentile(plc,5):+.2f}")


def c2():
    d = C.load()
    ev = C.c2_events(d)
    se = C.block_se(ev.y.values, ev.date)
    m = float(ev.y.mean()); t = m / se
    plc = C.c2_placebo(d, ev)
    placebo_ok = m < np.percentile(plc, 5)
    cleared, unadj = verdict(t, -1, placebo_ok)
    cost = C.cost_sigma()
    w_cost = float(np.mean([3 * cost[x] for x in ev.market]))
    raw_ev = C.c2_events(d, clip=1e9)
    per = ev.groupby("market").y.agg(["mean", "size"]).round(3)
    L = ["# C2 — expiring-contract pressure", "",
         f"* mean demeaned 3-bar return **{m:+.3f}σ**, SE {se:.3f}, **t = {t:.2f}** (clears at −3.02); N = {len(ev)}",
         f"* placebo (400 random-window draws): 5th pct {np.percentile(plc, 5):+.3f}, median {np.median(plc):+.3f} → {'cleared' if placebo_ok else 'NOT cleared'}",
         f"* event-weighted cost (3× spread round trip) {w_cost:.3f}σ → {'|effect| exceeds cost' if abs(m) > w_cost and m < 0 else 'not tradeable'}",
         f"* un-winsorised mean {raw_ev.y.mean():+.3f}σ (descriptive)", "", "## Per market", "", per.to_markdown(), "",
         f"**{'CLEARED' if cleared else 'NOT CLEARED'}** at N = 20" + ("" if cleared else f" ({'unadjusted 5% only' if unadj else 'no'})")]
    finish("C2", L, "CLEARED" if cleared else "NOT CLEARED", f"mean {m:+.3f}σ, t = {t:.2f}, placebo p5 {np.percentile(plc,5):+.3f}")


def panel(key, sigfn, extra_reg=True):
    d = C.load()
    y = C.next_month_return(d["rs"][C.COMMODITIES])
    x = sigfn(d).reindex(y.index)
    num, den = C.panel_slope(y, x)
    b = C.slope_from_pieces(num, den); se = C.slope_se(num, den); t = b / se
    plc = C.panel_placebo(y, x)
    placebo_ok = b > np.percentile(plc, 95)
    cleared, unadj = verdict(t, +1, placebo_ok)
    ls, turn = C.tercile_ls(y, x)
    cost = C.cost_sigma()[C.COMMODITIES].median()
    cost_m = 2 * float(turn.mean()) * cost + 2 * cost
    # descriptive: slope controlling for trailing 12-month return
    mom = d["rs"][C.COMMODITIES].rolling(252, min_periods=200).sum().reindex(y.index)
    zm = mom.sub(mom.mean(axis=1), axis=0).div(mom.std(axis=1), axis=0)
    zx = x.sub(x.mean(axis=1), axis=0).div(x.std(axis=1), axis=0)
    rows = pd.concat([y.stack().rename("y"), zx.stack().rename("x"), zm.stack().rename("m")], axis=1).dropna()
    rows[["y", "x", "m"]] = rows[["y", "x", "m"]] - rows.groupby(level=0)[["y", "x", "m"]].transform("mean")
    X = rows[["x", "m"]].values
    beta = np.linalg.lstsq(X, rows.y.values, rcond=None)[0]
    corr_xm = float(rows.x.corr(rows.m))
    L = [f"# {key} — panel test", "",
         f"* slope **{b:+.3f}** daily-sigma-sum per sd of signal (= {b/np.sqrt(21):+.3f} σ_m), SE {se:.3f}, **t = {t:.2f}** (clears at 3.02); N = {D[key]['n']} market-months",
         f"* placebo (400 within-month permutations): 95th pct {np.percentile(plc, 95):+.3f}, median {np.median(plc):+.3f} → {'cleared' if placebo_ok else 'NOT cleared'}",
         f"* tercile long-short mean {ls.mean():+.3f}σ/month (SE {C.block_se(ls.values, ls.index):.3f}); turnover {turn.mean():.0%}/month; cost ≈ {cost_m:.3f}σ/month → net {ls.mean() - cost_m:+.3f}",
         f"* with trailing 12-month return as a second regressor: slope on signal {beta[0]:+.3f}, on momentum {beta[1]:+.3f}; corr(signal, momentum) {corr_xm:+.2f} (descriptive)",
         "", f"**{'CLEARED' if cleared else 'NOT CLEARED'}** at N = 20" + ("" if cleared else f" ({'unadjusted 5% only' if unadj else 'no'})")]
    return L, dict(b=b, t=t, se=se, plc95=float(np.percentile(plc, 95)), ls=float(ls.mean()), cleared=cleared, unadj=unadj, y=y, x=x)


def c9():
    L, r = panel("C9", C.c9_signal)
    finish("C9", L, "CLEARED" if r["cleared"] else "NOT CLEARED", f"slope {r['b']:+.3f}, t = {r['t']:.2f}, placebo p95 {r['plc95']:+.3f}, L/S {r['ls']:+.3f}σ/mo")


def c1():
    L, r = panel("C1", C.c1_signal)
    finish("C1", L, "CLEARED" if r["cleared"] else "NOT CLEARED", f"slope {r['b']:+.3f}, t = {r['t']:.2f}, placebo p95 {r['plc95']:+.3f}, L/S {r['ls']:+.3f}σ/mo")


def c11():
    d = C.load()
    ev = C.c11_events(d)
    se = C.block_se(ev.y.values, ev.date)
    m = float(ev.y.mean()); t = m / se
    plc = C.c11_placebo(d, ev)
    placebo_ok = m > np.percentile(plc, 95)
    cleared, unadj = verdict(t, +1, placebo_ok)
    cost = C.cost_sigma()
    w_cost = float(np.mean([2 * cost[x] for x in ev.market]))
    per = ev.groupby("market")[["pre", "post", "y"]].mean().round(3)
    L = ["# C11 — Treasury auction cycle", "",
         f"* mean (post − pre) **{m:+.3f}σ**, SE {se:.3f}, **t = {t:.2f}** (clears at 3.02); N = {len(ev)}",
         f"* pre mean {ev.pre.mean():+.3f}σ, post mean {ev.post.mean():+.3f}σ (descriptive)",
         f"* placebo (400 random-day draws): 95th pct {np.percentile(plc, 95):+.3f}, median {np.median(plc):+.3f} → {'cleared' if placebo_ok else 'NOT cleared'}",
         f"* cost of the two round trips {w_cost:.3f}σ → {'effect exceeds cost' if m > w_cost else 'not tradeable'}", "", "## Per market", "", per.to_markdown(), "",
         f"**{'CLEARED' if cleared else 'NOT CLEARED'}** at N = 20" + ("" if cleared else f" ({'unadjusted 5% only' if unadj else 'no'})")]
    finish("C11", L, "CLEARED" if cleared else "NOT CLEARED", f"mean {m:+.3f}σ, t = {t:.2f}, pre {ev.pre.mean():+.3f}, post {ev.post.mean():+.3f}")


def c18():
    w = C.c18_weekly()
    a, df = C.alpha_on_btc(w.ls * 100, w.btc * 100)
    se = C.alpha_se(df); t = a / se
    # placebo: permute the funding signal across symbols within each week -> rebuild the book
    rng = np.random.default_rng(config.SEED)
    f = pd.read_parquet(C.CAND / "binance_funding.parquet")
    k = pd.read_parquet(C.CAND / "binance_klines_1d.parquet")
    px = k.pivot(index="open_time", columns="symbol", values="close").sort_index()
    fr = f.pivot_table(index=f["fundingTime"].dt.normalize(), columns="symbol", values="fundingRate", aggfunc="sum").reindex(px.index).fillna(0.0).where(px.notna())
    plc = []
    for _ in range(400):
        vals = []
        for tdate, row in w.iterrows():
            syms = list(set(row["long"]) | set(row["short"]))
            allsym = list(fr.loc[tdate].dropna().index) if tdate in fr.index else syms
            pick = rng.choice(allsym, size=len(row["long"]) + len(row["short"]), replace=False)
            lo, hi = pick[:len(row["long"])], pick[len(row["long"]):]
            t1 = w.index[w.index.get_loc(tdate) + 1] if w.index.get_loc(tdate) + 1 < len(w) else None
            if t1 is None:
                continue
            ret = px.loc[t1] / px.loc[tdate] - 1
            fund = fr.loc[tdate + pd.Timedelta(days=1): t1].sum()
            vals.append(float((ret - fund).reindex(lo).mean() + (-ret + fund).reindex(hi).mean()))
        s = pd.Series(vals, index=w.index[:len(vals)]) * 100
        plc.append(C.alpha_on_btc(s, w.btc.reindex(s.index) * 100)[0])
    plc = np.array(plc)
    placebo_ok = a > np.percentile(plc, 95)
    cleared, unadj = verdict(t, +1, placebo_ok)
    cost = float(w.turnover.mean() * 0.20)
    L = ["# C18 — crypto funding-rate carry", "",
         f"* alpha on BTC **{a:+.3f} %/week**, SE {se:.3f}, **t = {t:.2f}** (clears at 3.02); N = {len(df)} weeks; raw long-short mean {w.ls.mean()*100:+.3f} %/week",
         f"* placebo (400 within-week symbol permutations): 95th pct {np.percentile(plc, 95):+.3f}, median {np.median(plc):+.3f} → {'cleared' if placebo_ok else 'NOT cleared'}",
         f"* turnover {w.turnover.mean():.0%}/week → cost ≈ {cost:.3f} %/week at 20 bp round trip; net alpha {a - cost:+.3f}",
         f"* by year (descriptive): " + ", ".join(f"{y}: {v*100:+.2f}" for y, v in w.ls.groupby(w.index.year).mean().items()),
         "", f"**{'CLEARED' if cleared else 'NOT CLEARED'}** at N = 20" + ("" if cleared else f" ({'unadjusted 5% only' if unadj else 'no'})")]
    finish("C18", L, "CLEARED" if cleared else "NOT CLEARED", f"alpha {a:+.3f} %/wk, t = {t:.2f}, placebo p95 {np.percentile(plc,95):+.3f}")


def c15():
    d = C.load()
    ev = C.c15_events(d)
    se = C.block_se(ev.y.values, ev.date)
    m = float(ev.y.mean()); t = m / se
    pseudo = {wd: float(C.c15_pseudo(d, i).y.mean()) for wd, i in [("Mon", 0), ("Tue", 1), ("Thu", 3), ("Fri", 4)]}
    placebo_ok = m > max(pseudo.values())
    cleared, unadj = verdict(t, +1, placebo_ok)
    cost = C.cost_sigma()
    w_cost = float(np.mean([cost[x] for x in ev.market]))
    L = ["# C15 — EIA weekly petroleum report drift", "",
         f"* mean signed 2-bar continuation after the release **{m:+.3f}σ**, SE {se:.3f}, **t = {t:.2f}** (clears at 3.02); N = {len(ev)}",
         f"* pseudo-release days: " + ", ".join(f"{k} {v:+.3f}" for k, v in pseudo.items()) + f" → Wednesday {'exceeds all' if placebo_ok else 'does NOT exceed all'}",
         f"* cost of one round trip {w_cost:.3f}σ → {'effect exceeds cost' if m > w_cost else 'not tradeable'}",
         f"* per market: " + ", ".join(f"{k} {v:+.3f}" for k, v in ev.groupby('market').y.mean().items()),
         "", f"**{'CLEARED' if cleared else 'NOT CLEARED'}** at N = 20" + ("" if cleared else f" ({'unadjusted 5% only' if unadj else 'no'})")]
    finish("C15", L, "CLEARED" if cleared else "NOT CLEARED", f"mean {m:+.3f}σ, t = {t:.2f}, pseudo max {max(pseudo.values()):+.3f}")


if __name__ == "__main__":
    {"C14": c14, "C19": c19, "C2": c2, "C9": c9, "C1": c1, "C11": c11, "C18": c18, "C15": c15}[sys.argv[1]]()
