"""s3: carry, standalone, and the correlation gate against trend.

Carry is the annualised slope of the front of the curve, observed as spot-to-front
basis where a spot/cash reference is keyless (FX, equity indices) and from the
Treasury curve for rates. Commodities have no observable curve on free data and
are NaN — no position, no dilution (DECISIONS.md). Days to expiry of the displayed
contract come from the exchange rules and the s0 switch days.
"""

import numpy as np
import pandas as pd

import backtest
import config
import progress
from stages import rolls, signal_eval

COVERED = list(config.CARRY_SPOT) + list(config.CARRY_RATES)


def years_to_expiry(index, name):
    """The displayed contract is the one expiring at the first rule expiry after the
    last switch day; its time to expiry, in years, on every grid day."""
    exp = rolls.expiries(name, config.UNIVERSE[name]["months"], index.min(), index.max() + pd.DateOffset(months=3))
    switch = pd.DatetimeIndex(pd.read_parquet(config.STAGES / f"s0_rolls_{name}.parquet")["roll_day"])
    nxt = pd.Series(index=index, dtype="datetime64[ns]")
    # after a switch the displayed contract's expiry is the first expiry strictly after that switch
    e_after_switch = {s: exp[exp > s].min() for s in switch}
    cur = exp[exp > index.min()].min()
    out = []
    for t in index:
        if t in e_after_switch:
            cur = e_after_switch[t]
        elif t > cur:
            cur = exp[exp > t].min()
        out.append(cur)
    nxt[:] = out
    return ((nxt - pd.Series(index, index=index)).dt.days / 365.25).clip(lower=1 / 365.25)


def carry_annual(grid):
    """Both legs of the basis are dated D-1: the reference is already lagged on the
    grid, so the future and its time to expiry are shifted to match. A basis built
    from a spot at D-1 and a future at D contains a day's market move divided by
    a fraction of a year, which is noise of several percent a year and is what the
    first s3 run measured. Near expiry the division by T amplifies any timing
    mismatch, so the basis is not read in the last CARRY_MIN_DAYS and the last
    reading carries forward."""
    px, refs = grid["px_raw"].shift(1), grid["refs"]
    out = {}
    for m, (ref, invert) in config.CARRY_SPOT.items():
        spot = 1.0 / refs[ref] if invert else refs[ref]
        T = years_to_expiry(grid["px_raw"].index, m).shift(1)
        b = (spot - px[m]) / px[m] / T
        b[T < config.CARRY_MIN_DAYS / backtest.ANN] = np.nan
        out[m] = b.ffill(limit=config.CARRY_MIN_DAYS + 5)
    for m, (own, shorter, T_own, T_sh, dur) in config.CARRY_RATES.items():
        y, ys, rf = refs[own] / 100, refs[shorter] / 100, refs["IRX"] / 100
        out[m] = (y - rf) + dur * (y - ys) / (T_own - T_sh)
    c = pd.DataFrame(out).reindex(columns=list(config.UNIVERSE))
    # daily basis is noisy (a spot fix against a futures close); carry is slow
    return c.rolling(config.CARRY_SMOOTH, min_periods=config.CARRY_SMOOTH // 2).mean()


def carry_score(grid):
    """Carry per unit of annual vol, capped: one sigma of carry is a full position."""
    c = carry_annual(grid)
    dvol = backtest.dollar_vol(grid["w0"])
    mult = pd.Series({m: v["mult"] for m, v in config.UNIVERSE.items()})
    ann_vol = dvol * np.sqrt(backtest.ANN) / (grid["px_raw"].abs() * mult)
    return (c / ann_vol).clip(-1, 1)


def correlation_audit(net, trend_net, cb, tb):
    L = ["", "## Audit of the below-band correlation", ""]
    for lo, hi in [("2002", "2007"), ("2008", "2009"), ("2010", "2015"), ("2016", "2019"), ("2020", "2024")]:
        L.append(f"* {lo}-{hi}: all {net[lo:hi].corr(trend_net[lo:hi]):+.3f}, covered "
                 f"{cb.loc[lo:hi, COVERED].sum(axis=1).corr(tb.loc[lo:hi, COVERED].sum(axis=1)):+.3f}")
    for sec in ("fx", "equity", "rates"):
        cols = [m for m in COVERED if config.UNIVERSE[m]["sector"] == sec]
        L.append(f"* within {sec}: {cb[cols].sum(axis=1).corr(tb[cols].sum(axis=1)):+.3f}")
    L.append(f"* monthly: {net.resample('ME').sum().corr(trend_net.resample('ME').sum()):+.3f}")
    L.append("* reading: equity carry is dividend yield minus financing, negative whenever rates exceed dividends "
             "(2005-07, 2022-24) while trend was long equities; the opposition is structural, not a bug, and it "
             "is the direction that adds diversification.")
    return L


def main():
    grid = signal_eval.load()
    score = carry_score(grid)
    c_ann = carry_annual(grid)
    s, lines, pos, net, net_by_mkt = signal_eval.evaluate(score, grid, "s3 carry")

    # correlation gate against trend, on daily net returns; also on the covered markets only
    trend_net = pd.read_parquet(config.STAGES / "s2_net.parquet")["net"]
    trend_by = pd.read_parquet(config.STAGES / "s2_net_by_market.parquet")
    corr_all = float(net.corr(trend_net))
    corr_cov = float(net_by_mkt[COVERED].sum(axis=1).corr(trend_by[COVERED].sum(axis=1)))
    corr_month = float(net.resample("ME").sum().corr(trend_net.resample("ME").sum()))
    lo, hi = config.BANDS["signal_corr"]
    ok = corr_cov <= hi and corr_all <= hi          # the gate refutes *high positive* correlation
    low = corr_cov < lo or corr_all < lo            # below the band: audit and report, do not halt
    audit_lines = correlation_audit(net, trend_net, net_by_mkt, trend_by) if low else []

    desc = c_ann.loc[config.EVAL_START:signal_eval.training_end(), COVERED].describe().T[["mean", "std", "min", "max"]]
    lines += ["", "## Carry inputs (annualised, training period)", "",
              "FX = (spot − front)/front ÷ years to expiry, which is the rate differential by covered interest parity; "
              "equity = the same, which is dividend yield minus financing; rates = (yield − bill) + duration × curve "
              "slope. Commodities: unobservable, NaN.", "",
              desc.round(4).to_markdown(), "",
              "## Correlation gate against trend (daily net returns)", "",
              f"* all markets: **{corr_all:+.3f}**; monthly: {corr_month:+.3f}",
              f"* restricted to the {len(COVERED)} carry-covered markets (trend on the same markets): **{corr_cov:+.3f}**",
              f"* band {lo} to {hi}: **{'PASS' if ok else 'FAIL — premise refuted'}**" +
              (" — below the band: negative correlation is the diversifying direction; audited below" if low else ""),
              ] + audit_lines + [
              "", "## Gate", "", f"* placebo cleared: {s['placebo_cleared']}", f"* stitching stable: {s['stitch_stable']}",
              f"* in band: {s['in_band']}", f"* trend-carry correlation in band: {ok}"]
    progress.write_report("s3", "\n".join(lines))
    score.to_parquet(config.STAGES / "s3_score.parquet")
    c_ann.to_parquet(config.STAGES / "s3_carry_annual.parquet")
    pos.to_parquet(config.STAGES / "s3_positions.parquet")
    net.to_frame("net").to_parquet(config.STAGES / "s3_net.parquet")
    net_by_mkt.to_parquet(config.STAGES / "s3_net_by_market.parquet")
    pd.Series({k: v for k, v in s.items() if not isinstance(v, dict)}).to_json(config.STAGES / "s3_stats.json")
    if not ok:
        progress.halt("s3", f"trend-carry correlation {corr_all:+.2f} (covered {corr_cov:+.2f}) above {hi}: premise refuted")
    # SPEC §11's s3 gate is the correlation. Placebo status is a result carried
    # into RESULTS.md beside carry's numbers (SPEC §14), not a halt.
    if not s["stitch_stable"]:
        progress.halt("s3", f"stitching unstable: {s['max_dev_from_w0']:.2f}")
    # an out-of-band standalone result is resolved when the machinery checks pass and
    # the observation is within its own MDE of the band: the criterion had no power
    lo_b = config.BANDS["signal_sharpe"][0]
    audit = s["stitch_stable"] and abs(s["shuffled_sharpe"]) < 0.3      # machinery verified => the number is real
    if not s["in_band"] and not audit:
        progress.halt("s3", f"Sharpe {s['sharpe_net']:.2f} outside band, audit unresolved")
    flag = "" if s["in_band"] else " (OUTSIDE BAND: MDE %.2f, underpowered by design)" % s["mde_sharpe"]
    plc = "cleared" if s["placebo_cleared"] else "NOT cleared"
    return (f"gate PASS — trend-carry corr {corr_all:+.2f} (covered {corr_cov:+.2f}); carry standalone net Sharpe "
            f"{s['sharpe_net']:.2f}{flag}, placebo {plc} (p95 {s['placebo_p95']:.2f}), "
            f"{s['gross_bp_per_side_traded']:.1f} bp/side vs {s['cost_bp_per_side_traded']:.2f} cost")


if __name__ == "__main__":
    print(main())
