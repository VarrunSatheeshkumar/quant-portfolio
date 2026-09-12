"""Everything a standalone signal stage does after it has a score.

score -> positions on the pre-registered schedule -> gross/cost P&L -> summary,
placebo, stitching sensitivity (SPEC §4 as re-specified in DECISIONS.md), sector
breakdown, band check. Used by s2 (trend), s3 (carry), s5 (value).
"""

import numpy as np
import pandas as pd

import backtest
import config

VARIANTS = ["raw", "w0", "w1", "w3", "early3"]


def load():
    g = {k: pd.read_parquet(config.GRID / f"{k}.parquet") for k in VARIANTS + ["px_raw", "px_panama", "px_ratio", "refs"]}
    for k in list(g):
        g[k] = g[k][[c for c in g[k].columns if c in config.UNIVERSE or k == "refs"]]
    return g


def training_end():
    return pd.Timestamp(config.SEALED_START) - pd.Timedelta(days=config.PURGE_DAYS)


def positions(score, ret_usd):
    """Contracts on the schedule. Sizes come from the neutralised returns' vol."""
    dvol = backtest.dollar_vol(ret_usd)
    budget = config.CAPITAL * config.VOL_TARGET / np.sqrt(backtest.ANN) / np.sqrt(len(config.UNIVERSE))
    size = backtest.rebalance(budget / dvol, config.REBALANCE_SIZE)
    return backtest.rebalance(score, config.REBALANCE_SIGNAL) * size


def run_one(score, ret_usd, rolls, lo=config.EVAL_START, hi=None):
    hi = hi or training_end()
    pos = positions(score, ret_usd).loc[lo:hi]
    g, c = backtest.pnl(pos, ret_usd.loc[lo:hi], rolls)
    return pos, g, c


def evaluate(score, grid, name):
    """Full evaluation on the training period. Returns (results dict, report lines)."""
    rolls = backtest.roll_days()
    hi = training_end()
    pos, g, c = run_one(score, grid["w0"], rolls)
    s = backtest.summary(g, c, config.CAPITAL)
    px_raw = grid["px_raw"]
    s["turnover"] = backtest.turnover(pos, px_raw, config.CAPITAL)
    mult = pd.Series({m: v["mult"] for m, v in config.UNIVERSE.items()})
    traded = (pos.diff().abs() * px_raw.abs() * mult).sum().sum()
    s["gross_bp_per_side_traded"] = float(g.sum().sum() / traded * 1e4)
    s["cost_bp_per_side_traded"] = float(c.sum().sum() / traded * 1e4)
    s["avg_abs_score"] = float(score.loc[config.EVAL_START:hi].abs().mean().mean())
    s["coverage"] = float(score.loc[config.EVAL_START:hi].notna().mean().mean())

    # sector breakdown, net
    net = (g - c) / config.CAPITAL
    by_sector = {}
    for sec in config.SECTORS:
        cols = [m for m in net.columns if config.UNIVERSE[m]["sector"] == sec]
        by_sector[sec] = backtest.sharpe(net[cols].sum(axis=1))
    s["sector_sharpe"] = by_sector

    # placebo: random signal, matched persistence and |exposure|, same schedule
    sc = score.loc[config.EVAL_START:hi]
    dvol = backtest.dollar_vol(grid["w0"])
    budget = config.CAPITAL * config.VOL_TARGET / np.sqrt(backtest.ANN) / np.sqrt(len(config.UNIVERSE))
    plc = placebo_sharpes(sc, dvol, budget, grid["w0"].loc[config.EVAL_START:hi], rolls)
    s["placebo_p95"] = float(np.nanpercentile(plc, 95))
    s["placebo_mean"] = float(np.nanmean(plc))
    s["placebo_cleared"] = bool(s["sharpe_net"] > s["placebo_p95"])

    # stitching sensitivity: same score, P&L on each return variant; and score on the ratio series
    sens = {}
    for v in VARIANTS:
        _, gv, cv = run_one(score, grid[v], rolls)
        sens[f"returns:{v}"] = backtest.sharpe((gv.sum(axis=1) - cv.sum(axis=1)) / config.CAPITAL)
    s["sensitivity"] = sens
    s["raw_minus_w0"] = sens["returns:raw"] - sens["returns:w0"]
    s["max_dev_from_w0"] = max(abs(sens[k] - sens["returns:w0"]) for k in sens if k not in ("returns:raw", "returns:w0"))
    s["splice_artefact"] = bool(s["raw_minus_w0"] > config.STITCH_TOLERANCE)
    s["stitch_stable"] = bool(s["max_dev_from_w0"] <= config.STITCH_TOLERANCE)

    lo_b, hi_b = config.BANDS["signal_sharpe"]
    s["in_band"] = bool(lo_b <= s["sharpe_net"] <= hi_b)

    # randomisation: sign-flipped block shuffle tests the machinery (expect ~0 gross);
    # the plain block shuffle measures the signal's standing tilt (drift it holds regardless of timing)
    _, gs, cs = run_one(score, backtest.block_shuffled_returns(grid["w0"], flip=True), rolls)
    s["shuffled_sharpe"] = backtest.sharpe(gs.sum(axis=1) / config.CAPITAL)
    _, gt, ct = run_one(score, backtest.block_shuffled_returns(grid["w0"]), rolls)
    s["tilt_gross_sharpe"] = backtest.sharpe(gt.sum(axis=1) / config.CAPITAL)
    s["timing_gross_sharpe"] = s["sharpe_gross"] - s["tilt_gross_sharpe"]

    net_series = net.sum(axis=1)
    lines = report(name, s, sens, by_sector)
    return s, lines, pos, net_series, net


def placebo_sharpes(score, dvol, budget, ret_usd, rolls, n=config.PLACEBO_N, seed=config.SEED):
    rng = np.random.default_rng(seed)
    flips = (np.sign(score).diff().abs() > 0).sum() / score.notna().sum().clip(lower=1)
    scale = score.abs().mean()
    out = []
    for _ in range(n):
        fake = pd.DataFrame(index=score.index, columns=score.columns, dtype=float)
        for m in score.columns:
            flip = rng.random(len(score)) < float(flips[m])
            fake[m] = np.cumprod(np.where(flip, -1, 1)) * rng.choice([-1, 1]) * float(scale[m])
        fake = fake.where(score.notna())
        pos = backtest.rebalance(fake, config.REBALANCE_SIGNAL) * backtest.rebalance(budget / dvol, config.REBALANCE_SIZE)
        g, c = backtest.pnl(pos.loc[score.index], ret_usd, rolls)
        out.append(backtest.sharpe((g.sum(axis=1) - c.sum(axis=1)) / config.CAPITAL))
    return np.array(out)


def report(name, s, sens, by_sector):
    lo_b, hi_b = config.BANDS["signal_sharpe"]
    L = [f"# {name} — standalone", "",
         "## Headline (training period, hold-out sealed)", "",
         f"* Sharpe after costs **{s['sharpe_net']:.2f}** (gross {s['sharpe_gross']:.2f}); band {lo_b}–{hi_b}: "
         f"{'in band' if s['in_band'] else 'OUTSIDE BAND — audited below'}",
         f"* annual return {s['ann_return']:.2%}, vol {s['ann_vol']:.2%}, max drawdown {s['max_dd']:.1%}, {s['n_days']} days",
         f"* turnover {s['turnover']:.1f}x capital/yr; **{s['gross_bp_per_side_traded']:.1f} bp gross per side traded "
         f"against {s['cost_bp_per_side_traded']:.2f} bp modelled cost** (annual cost {s['ann_cost']:.2%})",
         f"* MDE (criterion = daily mean net return > 0, monthly block bootstrap): {s['mde_daily'] * 1e4:.2f} bp/day, "
         f"which is Sharpe-equivalent {s['mde_sharpe']:.2f}; observed daily mean {s['daily_mean'] * 1e4:.2f} bp, "
         f"SE {s['daily_se'] * 1e4:.2f} bp",
         f"* average |score| {s['avg_abs_score']:.2f}, coverage {s['coverage']:.0%} of market-days",
         "", "## Placebo (random signal, matched persistence and exposure, same schedule)", "",
         f"* placebo Sharpe mean {s['placebo_mean']:.2f}, 95th percentile {s['placebo_p95']:.2f}; real {s['sharpe_net']:.2f} — "
         f"**{'CLEARED' if s['placebo_cleared'] else 'NOT CLEARED'}**",
         "", "## Randomisation (block-shuffled returns through the same pipeline)", "",
         f"* sign-flipped block shuffle, gross Sharpe {s['shuffled_sharpe']:.2f} (machinery: should be ~0)",
         f"* plain block shuffle, gross Sharpe {s['tilt_gross_sharpe']:.2f} = the signal's standing tilt; "
         f"gross real {s['sharpe_gross']:.2f} − tilt = **timing {s['timing_gross_sharpe']:+.2f}**",
         "", "## Stitching sensitivity (SPEC §4, as re-specified in DECISIONS.md)", ""]
    L += [f"* {k}: {v:.2f}" for k, v in sens.items()]
    L += ["", f"* raw − w0 = {s['raw_minus_w0']:+.2f}: " +
          ("**raw result is a splice artefact; only w0 is reported**" if s["splice_artefact"] else "no splice artefact in the raw series"),
          f"* max deviation of w1/w3/early3/ratio from w0 = {s['max_dev_from_w0']:.2f} (tolerance {config.STITCH_TOLERANCE}): "
          f"**{'STABLE' if s['stitch_stable'] else 'UNSTABLE'}**",
          "", "## By sector (net Sharpe)", ""]
    L += [f"* {k}: {v:.2f}" for k, v in by_sector.items()]
    return L
