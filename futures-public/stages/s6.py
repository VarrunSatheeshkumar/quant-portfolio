"""s6: the three-signal programme through the portfolio layer; randomisation,
placebo, stitching sensitivity, correlation matrix, return distribution.

There is nothing to fit: the signals are rules, the weights are equal, the
covariance is trailing. Walk-forward therefore has no training window to purge;
the whole non-sealed period is out of sample by construction, and the sealed
hold-out is the only true test of that claim (s9).
"""

import json

import numpy as np
import pandas as pd

import backtest
import config
import progress
from stages import s4, signal_eval

SIGNALS = ["trend", "carry", "value"]
PLACEBO_N = 40


def load_scores():
    return {"trend": pd.read_parquet(config.STAGES / "s2_score.parquet"),
            "carry": pd.read_parquet(config.STAGES / "s3_score.parquet"),
            "value": pd.read_parquet(config.STAGES / "s5_score.parquet")}


def random_like(score, rng):
    flips = (np.sign(score).diff().abs() > 0).sum() / score.notna().sum().clip(lower=1)
    scale = score.abs().mean()
    fake = pd.DataFrame(index=score.index, columns=score.columns, dtype=float)
    for m in score.columns:
        flip = rng.random(len(score)) < float(flips[m])
        fake[m] = np.cumprod(np.where(flip, -1, 1)) * rng.choice([-1, 1]) * float(scale[m])
    return fake.where(score.notna())


def longest_flat(net):
    eq = (1 + net.fillna(0)).cumprod()
    peak = eq.cummax()
    under = eq < peak
    runs, cur = [], 0
    for u in under:
        cur = cur + 1 if u else 0
        runs.append(cur)
    return int(max(runs))


def main():
    grid = signal_eval.load()
    scores = load_scores()
    b = s4.build(scores, grid)
    s = backtest.summary(b["gross"], b["cost"], config.CAPITAL)
    s["turnover"] = backtest.turnover(b["pos"], grid["px_raw"], config.CAPITAL)
    net = b["net"]
    mult = pd.Series({m: v["mult"] for m, v in config.UNIVERSE.items()})
    traded = (b["pos"].diff().abs() * grid["px_raw"].abs() * mult).sum().sum()
    s["gross_bp_per_side_traded"] = float(b["gross"].sum().sum() / traded * 1e4)
    s["cost_bp_per_side_traded"] = float(b["cost"].sum().sum() / traded * 1e4)

    # correlation matrix of the standalone books, daily and monthly
    stand = pd.DataFrame({k: pd.read_parquet(config.STAGES / f"{st}_net.parquet")["net"]
                          for k, st in zip(SIGNALS, ["s2", "s3", "s5"])})
    corr_d, corr_m = stand.corr(), stand.resample("ME").sum().corr()

    # contribution of each signal: combined minus the book without it (diagnostic)
    contrib = {}
    for k in SIGNALS:
        bb = s4.build({j: v for j, v in scores.items() if j != k}, grid)
        contrib[k] = s["sharpe_net"] - backtest.sharpe(bb["net"])

    # randomisation: block-shuffled returns through the identical pipeline
    shuf = dict(grid)
    shuf["w0"] = backtest.block_shuffled_returns(grid["w0"], flip=True)
    bs = s4.build(scores, shuf)
    shuffled_gross = backtest.sharpe(bs["gross"].sum(axis=1) / config.CAPITAL)
    shuffled_sharpe = backtest.sharpe(bs["net"])      # net carries the cost drag of random positions
    tilt = dict(grid)
    tilt["w0"] = backtest.block_shuffled_returns(grid["w0"])
    tilt_gross = backtest.sharpe(s4.build(scores, tilt)["gross"].sum(axis=1) / config.CAPITAL)
    timing_gross = s["sharpe_gross"] - tilt_gross

    # placebo: all three scores random, matched persistence and exposure
    rng = np.random.default_rng(config.SEED)
    plc = []
    for _ in range(PLACEBO_N):
        fake = {k: random_like(v, rng) for k, v in scores.items()}
        plc.append(backtest.sharpe(s4.build(fake, grid)["net"]))
    plc = np.array(plc)
    p95 = float(np.nanpercentile(plc, 95))
    cleared = s["sharpe_net"] > p95

    # stitching sensitivity on the combined programme
    sens = {}
    for v in signal_eval.VARIANTS:
        gv = dict(grid)
        gv["w0"] = grid[v]
        sens[f"returns:{v}"] = backtest.sharpe(s4.build(scores, gv)["net"])
    from stages.s2 import trend_score
    from stages.s5 import value_score
    ratio_scores = dict(scores, trend=trend_score(grid["px_ratio"]), value=value_score(grid["px_ratio"]))
    sens["prices:ratio"] = backtest.sharpe(s4.build(ratio_scores, grid)["net"])
    raw_minus = sens["returns:raw"] - sens["returns:w0"]
    max_dev = max(abs(v - sens["returns:w0"]) for k, v in sens.items() if k not in ("returns:raw", "returns:w0"))
    stable = max_dev <= config.STITCH_TOLERANCE

    lo_b, hi_b = config.BANDS["combined_sharpe"]
    in_band = lo_b <= s["sharpe_net"] <= hi_b
    machinery_ok = stable and abs(shuffled_gross) < 0.3 and shuffled_sharpe < 0.3
    audit_ok = machinery_ok
    neff = b["neff"].dropna()
    m_ret = net.resample("ME").sum()
    dist = dict(worst_day=float(net.min()), best_day=float(net.max()), skew=float(net.skew()), kurt=float(net.kurt()),
                p01=float(net.quantile(.01)), p99=float(net.quantile(.99)), month_hit=float((m_ret > 0).mean()),
                worst_month=float(m_ret.min()), best_month=float(m_ret.max()), longest_flat_days=longest_flat(net))

    lines = ["# s6 — three-signal programme", "",
             "## Headline (training period, hold-out sealed)", "",
             f"* Sharpe after costs **{s['sharpe_net']:.2f}** (gross {s['sharpe_gross']:.2f}); band {lo_b}–{hi_b}: "
             f"{'in band' if in_band else 'OUTSIDE BAND — audit ' + ('resolved' if audit_ok else 'NOT resolved')}",
             f"* annual return {s['ann_return']:.2%}, realised vol {s['ann_vol']:.2%} (target {config.VOL_TARGET:.0%}), "
             f"max drawdown {s['max_dd']:.1%}, longest flat period {dist['longest_flat_days']} trading days",
             f"* turnover {s['turnover']:.1f}x; **{s['gross_bp_per_side_traded']:.1f} bp gross per side traded against "
             f"{s['cost_bp_per_side_traded']:.2f} bp cost**; annual cost {s['ann_cost']:.2%}",
             f"* MDE (daily mean, monthly block bootstrap): {s['mde_daily'] * 1e4:.2f} bp/day = Sharpe-equivalent {s['mde_sharpe']:.2f}; "
             f"observed {s['daily_mean'] * 1e4:.2f} bp/day, SE {s['daily_se'] * 1e4:.2f}",
             f"* effective breadth median {neff.median():.1f}; portfolio scale factor λ median {b['lam'].median():.2f} "
             "(above 1 means the signals cancel and the vol layer levers the residual)", "",
             "## Pairwise correlation of the standalone books (daily net returns)", "", corr_d.round(3).to_markdown(), "",
             "Monthly:", "", corr_m.round(3).to_markdown(), "",
             "## Contribution by signal (combined Sharpe minus the book without it)", ""]
    lines += [f"* {k}: {v:+.2f}" for k, v in contrib.items()]
    lines += ["", "## Randomisation and placebo", "",
              f"* sign-flipped block shuffle through the full pipeline: gross Sharpe {shuffled_gross:.2f} (machinery: should be ~0), "
              f"net {shuffled_sharpe:.2f} (carries the cost of random positions; must not be positive)",
              f"* plain block shuffle: gross {tilt_gross:.2f} = standing tilt of the book; real gross {s['sharpe_gross']:.2f} − tilt = "
              f"**timing {timing_gross:+.2f}**",
              f"* placebo (three random scores, matched persistence and exposure, {PLACEBO_N} draws): mean {np.nanmean(plc):.2f}, "
              f"95th pct {p95:.2f}; real {s['sharpe_net']:.2f} — **{'CLEARED' if cleared else 'NOT CLEARED'}**",
              "", "## Stitching sensitivity (combined)", ""]
    lines += [f"* {k}: {v:.2f}" for k, v in sens.items()]
    lines += ["", f"* raw − w0 = {raw_minus:+.2f}" + (" — **raw is a splice artefact**" if raw_minus > config.STITCH_TOLERANCE else ""),
              f"* max deviation from w0 = {max_dev:.2f} (tolerance {config.STITCH_TOLERANCE}): **{'STABLE' if stable else 'UNSTABLE'}**",
              "", "## Return distribution (daily net)", ""]
    lines += [f"* {k}: {v:.4f}" if isinstance(v, float) else f"* {k}: {v}" for k, v in dist.items()]
    lines += ["", "## Walk-forward", "",
              "No parameter is fitted: signals are fixed rules, weights are equal, covariance is trailing. The "
              "training period is out of sample by construction; the sealed two years (s9) are the test of that.",
              "", "## Gate", "", f"* in band: {in_band}" + ("" if in_band else f" — machinery verified: {machinery_ok}; recorded as a result"),
              f"* randomisation: gross ~0 and net not positive: {abs(shuffled_gross) < 0.3 and shuffled_sharpe < 0.3}",
              f"* placebo cleared: {cleared}", f"* stitching stable: {stable}"]
    progress.write_report("s6", "\n".join(lines))
    b["pos"].to_parquet(config.STAGES / "s6_positions.parquet")
    net.to_frame("net").to_parquet(config.STAGES / "s6_net.parquet")
    neff.to_frame("neff").to_parquet(config.STAGES / "s6_neff.parquet")
    out = {k: v for k, v in s.items() if not isinstance(v, dict)}
    out.update(dict(shuffled_sharpe=shuffled_sharpe, shuffled_gross=shuffled_gross, tilt_gross=tilt_gross, timing_gross=timing_gross,
                    lam_median=float(b["lam"].median()), placebo_p95=p95, placebo_mean=float(np.nanmean(plc)), placebo_cleared=bool(cleared),
                    raw_minus_w0=raw_minus, max_dev=max_dev, stitch_stable=bool(stable), in_band=bool(in_band),
                    breadth=float(neff.median()), contrib=contrib, sens=sens, dist=dist,
                    corr_daily=corr_d.to_dict(), corr_monthly=corr_m.to_dict()))
    (config.STAGES / "s6_stats.json").write_text(json.dumps(out, indent=2, default=float))
    if abs(shuffled_gross) >= 0.3 or shuffled_sharpe >= 0.3:
        progress.halt("s6", f"randomisation produced gross {shuffled_gross:.2f} / net {shuffled_sharpe:.2f} on shuffled returns: bug")
    if not stable:
        progress.halt("s6", f"stitching unstable on combined: {max_dev:.2f}")
    if not in_band and not audit_ok:
        progress.halt("s6", f"combined Sharpe {s['sharpe_net']:.2f} outside band, machinery checks failed")
    flag = "" if in_band else " (OUTSIDE BAND, machinery verified: result recorded)"
    plc = "cleared" if cleared else "NOT cleared"
    return (f"gate PASS — combined net Sharpe {s['sharpe_net']:.2f}{flag}, vol {s['ann_vol']:.1%}, maxDD {s['max_dd']:.0%}, "
            f"breadth {neff.median():.1f}, shuffled gross {shuffled_gross:.2f}, placebo {plc} (p95 {p95:.2f})")


if __name__ == "__main__":
    print(main())
