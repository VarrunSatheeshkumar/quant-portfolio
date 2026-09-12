"""s4: position-level and portfolio-level vol targeting, sector caps, breadth.

Applied to the equal-weight trend + carry book (value arrives in s5; the layer is
a function and s6 reuses it). Gate: realised vol tracks the target.
"""

import numpy as np
import pandas as pd

import backtest
import config
import portfolio
import progress
from stages import signal_eval

TOL = 0.20      # realised vol within 20% of target, full period and median rolling year


def build(scores, grid, lo=config.EVAL_START, hi=None):
    hi = hi or signal_eval.training_end()
    score = portfolio.combine_scores(scores)
    ret = grid["w0"]
    dvol = backtest.dollar_vol(ret)
    base = signal_eval.positions(score, ret)
    capped = portfolio.sector_cap(base, dvol)
    scaled, lam, ivol, neff, delta = portfolio.target_portfolio(capped, ret, dvol)
    scaled = scaled.loc[lo:hi]
    g, c = backtest.pnl(scaled, ret.loc[lo:hi], backtest.roll_days())
    net = (g.sum(axis=1) - c.sum(axis=1)) / config.CAPITAL
    return dict(score=score, base=base, capped=capped, pos=scaled, lam=lam.loc[lo:hi], ivol=ivol.loc[lo:hi],
                neff=neff.loc[lo:hi], delta=delta.loc[lo:hi], gross=g, cost=c, net=net, dvol=dvol)


def sector_risk_shares(pos, dvol):
    risk = pos.abs() * dvol
    tot = risk.sum(axis=1)
    return pd.DataFrame({sec: risk[[m for m in pos.columns if config.UNIVERSE[m]["sector"] == sec]].sum(axis=1) / tot
                         for sec in config.SECTORS})


def main():
    grid = signal_eval.load()
    scores = {"trend": pd.read_parquet(config.STAGES / "s2_score.parquet"),
              "carry": pd.read_parquet(config.STAGES / "s3_score.parquet")}
    b = build(scores, grid)
    s = backtest.summary(b["gross"], b["cost"], config.CAPITAL)
    s["turnover"] = backtest.turnover(b["pos"], grid["px_raw"], config.CAPITAL)
    realised = s["ann_vol"]
    roll_vol = b["net"].rolling(250).std() * np.sqrt(backtest.ANN)
    med_roll = float(roll_vol.median())
    ok_full = abs(realised / config.VOL_TARGET - 1) <= TOL
    ok_roll = abs(med_roll / config.VOL_TARGET - 1) <= TOL
    within = float(((roll_vol / config.VOL_TARGET).between(1 - 2 * TOL, 1 + 2 * TOL)).mean())

    # the same book without the portfolio layer, for the comparison that justifies it
    g0, c0 = backtest.pnl(b["capped"].loc[b["pos"].index], grid["w0"].loc[b["pos"].index], backtest.roll_days())
    net0 = (g0.sum(axis=1) - c0.sum(axis=1)) / config.CAPITAL
    r0 = net0.rolling(250).std() * np.sqrt(backtest.ANN)

    shares = sector_risk_shares(b["pos"], b["dvol"]).loc[b["pos"].index]
    neff = b["neff"].dropna()
    lo_b, hi_b = config.BANDS["effective_breadth"]
    lines = ["# s4 — sizing and portfolio construction (trend + carry book)", "",
             "## Gate: realised vol against target", "",
             f"* target {config.VOL_TARGET:.0%}; realised full-period **{realised:.2%}** ({'PASS' if ok_full else 'FAIL'}, tolerance ±{TOL:.0%})",
             f"* rolling one-year realised vol: median {med_roll:.2%} ({'PASS' if ok_roll else 'FAIL'}); "
             f"within ±{2 * TOL:.0%} of target {within:.0%} of the time; min {roll_vol.min():.2%}, max {roll_vol.max():.2%}",
             f"* without the portfolio layer (per-position sizing and sector caps only): full-period {net0.std() * np.sqrt(252):.2%}, "
             f"rolling-year min {r0.min():.2%}, max {r0.max():.2%} — the range the portfolio layer removes", "",
             "## Book", "",
             f"* Sharpe after costs **{s['sharpe_net']:.2f}** (gross {s['sharpe_gross']:.2f}); "
             f"without portfolio layer {backtest.sharpe(net0):.2f}",
             f"* annual return {s['ann_return']:.2%}, max drawdown {s['max_dd']:.1%}, turnover {s['turnover']:.1f}x, "
             f"annual cost {s['ann_cost']:.2%}",
             f"* scale factor lambda: median {b['lam'].median():.2f}, 5th–95th pct {b['lam'].quantile(.05):.2f}–{b['lam'].quantile(.95):.2f}",
             f"* shrinkage intensity toward constant correlation: median {b['delta'].median():.2f}", "",
             "## Effective breadth (diversification ratio squared, weekly)", "",
             f"* median **{neff.median():.1f}** independent bets from {len(config.UNIVERSE)} markets; "
             f"5th–95th pct {neff.quantile(.05):.1f}–{neff.quantile(.95):.1f}; band {lo_b}–{hi_b}: "
             f"{'in band' if lo_b <= neff.median() <= hi_b else 'OUTSIDE BAND'}",
             f"* minimum {neff.min():.1f} on {neff.idxmin().date()} — correlations at their highest", "",
             "## Sector risk shares (standalone-risk basis, cap " + f"{config.SECTOR_CAP:.0%})", "",
             shares.describe().T[["mean", "min", "max"]].round(3).to_markdown(), ""]
    progress.write_report("s4", "\n".join(lines))
    b["pos"].to_parquet(config.STAGES / "s4_positions.parquet")
    b["net"].to_frame("net").to_parquet(config.STAGES / "s4_net.parquet")
    pd.DataFrame({"lam": b["lam"], "roll_vol": roll_vol}).to_parquet(config.STAGES / "s4_scale.parquet")
    neff.to_frame("neff").to_parquet(config.STAGES / "s4_neff.parquet")
    shares.to_parquet(config.STAGES / "s4_sector_shares.parquet")
    if not (ok_full and ok_roll):
        progress.halt("s4", f"realised vol {realised:.2%} / median rolling {med_roll:.2%} vs target {config.VOL_TARGET:.0%}")
    if not (lo_b <= neff.median() <= hi_b):
        progress.mark("s4", "running", note="breadth outside band; audit in report")
    return (f"gate PASS — realised vol {realised:.1%} vs target {config.VOL_TARGET:.0%} (rolling-year median {med_roll:.1%}); "
            f"effective breadth {neff.median():.1f}; trend+carry net Sharpe {s['sharpe_net']:.2f}")


if __name__ == "__main__":
    print(main())
