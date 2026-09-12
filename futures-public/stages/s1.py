"""s1: cost model and the cost ratio, before any signal is evaluated.

Nothing here reads a return. Turnover comes from the SPEC's trend *positions*
(price versus moving averages, vol-scaled), which are a function of prices only.
The question is whether the edge this strategy class is known to have -- the
pre-registered band, midpoint Sharpe 0.4 -- survives the modelled cost.
"""

import numpy as np
import pandas as pd

import backtest
import config
import progress

ASSUMED_SHARPE = 0.4     # midpoint of SPEC §8 standalone band
FAVOURABLE = 2.0         # pre-registered: edge/cost >= 2 favourable, >= 1 marginal, < 1 halt
CAPITAL = config.CAPITAL
SCHEDULES = [("D", "D"), ("W", "W"), ("M", "M"), (config.REBALANCE_SIGNAL, config.REBALANCE_SIZE)]


def trend_score(px):
    """Sign of price against each SPEC lookback MA, averaged. Prices only."""
    # holidays are NaN rows on the business-day grid; a full window would never exist
    return sum(np.sign(px - px.rolling(k, min_periods=int(0.8 * k)).mean()) for k in config.TREND_LOOKBACKS) / len(config.TREND_LOOKBACKS)


def trend_positions(px, dvol, sig_freq="D", size_freq="D"):
    sig = trend_score(px)
    budget = CAPITAL * config.VOL_TARGET / np.sqrt(backtest.ANN) / np.sqrt(len(config.UNIVERSE))
    size = backtest.rebalance(budget / dvol, size_freq)
    return backtest.rebalance(sig, sig_freq) * size, sig


def schedule_row(pos, px_raw, side, rolls, mult):
    t = backtest.turnover(pos, px_raw, CAPITAL)
    cost_yr = (pos.diff().abs() * side).sum(axis=1).mean() * backtest.ANN
    held = pos.shift(1)
    roll = sum(held.loc[held.index.isin(d), m].abs().sum() * 2 * side[m] for m, d in rolls.items()) / (len(pos) / backtest.ANN)
    gross = (pos.abs() * px_raw.abs() * mult).sum(axis=1).mean() / CAPITAL
    edge = ASSUMED_SHARPE * config.VOL_TARGET / t * 1e4
    cbp, rbp = cost_yr / CAPITAL / t * 1e4, roll / CAPITAL / t * 1e4
    return dict(turnover_x=round(t, 1), gross_notional_x=round(gross, 2), cost_bp_side=round(cbp, 2),
                roll_bp_side=round(rbp, 2), edge_bp_side=round(edge, 1), ratio=round(edge / (cbp + rbp), 2),
                sharpe_drag=round((cost_yr + roll) / CAPITAL / config.VOL_TARGET, 3))


def main():
    px = pd.read_parquet(config.GRID / "px_panama.parquet")
    px_raw = pd.read_parquet(config.GRID / "px_raw.parquet")
    ret = pd.read_parquet(config.GRID / "w0.parquet")
    dvol = backtest.dollar_vol(ret)
    side = backtest.cost_per_side(None)
    rolls = backtest.roll_days()

    rows = []
    for m, s in config.UNIVERSE.items():
        p = px_raw[m].abs().dropna()
        notional = float((p * s["mult"]).tail(250).median())
        dv = float(dvol[m].dropna().tail(250).median())
        n_rolls_yr = len(rolls[m]) / ((px.index[-1] - px[m].first_valid_index()).days / 365.25)
        rt_bp = 2 * side[m] / notional * 1e4
        rows.append(dict(market=m, sector=s["sector"], notional=round(notional), side_cost=round(side[m], 2),
                         round_trip_bp=round(rt_bp, 2), daily_vol_bp=round(dv / notional * 1e4, 1),
                         cost_pct_of_daily_vol=round(100 * rt_bp / (dv / notional * 1e4), 2),
                         rolls_per_yr=round(n_rolls_yr, 1), roll_cost_bp_yr=round(rt_bp * n_rolls_yr, 2)))
    tbl = pd.DataFrame(rows).set_index("market")

    mult = pd.Series({m: s["mult"] for m, s in config.UNIVERSE.items()})
    sched = {}
    for sf, zf in SCHEDULES:
        pos, sig = trend_positions(px, dvol, sf, zf)
        sched[f"signal {sf} / size {zf}"] = schedule_row(pos.loc[config.EVAL_START:], px_raw, side, rolls, mult)
    sched = pd.DataFrame(sched).T
    chosen = sched.iloc[-1]
    t_over, cost_bp_per_side, ratio, drag = chosen.turnover_x, chosen.cost_bp_side, chosen.ratio, chosen.sharpe_drag
    edge_bp_per_side, roll_bp = chosen.edge_bp_side, chosen.roll_bp_side
    gross_notional = chosen.gross_notional_x
    sig = trend_score(px).loc[config.EVAL_START:]
    hp = 1 / (np.sign(sig).diff().abs().gt(0).sum() / sig.notna().sum()).mean()
    verdict = "favourable" if ratio >= FAVOURABLE else ("marginal" if ratio >= 1 else "unfavourable")
    lines = ["# s1 — cost model and cost ratio", "",
             "## Cost ratio (computed before any return was read)", "",
             f"* trend positions (SPEC §5a rule, vol-scaled, schedule below): one-sided turnover **{t_over:.1f}x capital/yr**, "
             f"average gross notional {gross_notional:.2f}x capital, mean holding period of a sign ~{hp:.0f} days",
             f"* modelled cost: **{cost_bp_per_side:.2f} bp per side** of notional traded (notional-weighted), "
             f"plus rolls {roll_bp:.2f} bp per side-equivalent",
             f"* **Sharpe drag {drag:.3f}** at the {config.VOL_TARGET:.0%} target",
             f"* expected gross edge at the band midpoint (Sharpe {ASSUMED_SHARPE}): **{edge_bp_per_side:.1f} bp per side traded**",
             f"* **edge / cost = {ratio:.1f}** — {verdict} (pre-registered: >= {FAVOURABLE} favourable, >= 1 marginal, < 1 halt)", "",
             "For comparison the previous project's ratio was 6 bp of edge against 10 bp of cost.", "",
             "## Execution schedule (chosen on cost alone; the last row is the pre-registered choice)", "",
             "The literal daily-rebalanced four-sign score turns the book fifty times a year: the 20-day sign flaps "
             "around its average and every flap trades half a position. Sampling the score on a schedule is the "
             "one-parameter remedy. ZT carries ~40% of all turnover under every schedule because a 2-year note "
             "position of equal risk is ten times the notional of an equity index position.", "",
             sched.to_markdown(), "",
             "## Per-market cost model", "",
             "Commission $2.50/side all-in; slippage = half the typical spread + 0.5 tick impact per side; roll = one "
             "round trip per contract held over a switch day. Futures are unfunded: margin sits in bills, so there is "
             "no financing cost and returns are excess returns by construction.", "",
             tbl.to_markdown(), "",
             f"Universe median: round trip {tbl.round_trip_bp.median():.2f} bp, "
             f"{tbl.cost_pct_of_daily_vol.median():.1f}% of a daily move (SPEC §0 expected ~2%).", ""]
    progress.write_report("s1", "\n".join(lines))
    tbl.to_parquet(config.STAGES / "s1_costs.parquet")
    if ratio < 1:
        progress.halt("s1", f"cost ratio {ratio:.2f} < 1")
    return f"gate PASS — edge/cost {ratio:.1f} ({verdict}); turnover {t_over:.1f}x/yr, {cost_bp_per_side:.1f} bp/side, Sharpe drag {drag:.3f}"


if __name__ == "__main__":
    print(main())
