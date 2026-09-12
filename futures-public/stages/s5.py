"""s5: value, standalone; gate = its returns are negatively correlated with trend's."""

import pandas as pd

import backtest
import config
import progress
from stages import signal_eval


def value_score(px):
    w = config.VALUE_WINDOW
    ma = px.rolling(w, min_periods=int(0.8 * w)).mean()
    sd = px.rolling(w, min_periods=int(0.8 * w)).std()
    return -((px - ma) / sd).clip(-2, 2) / 2


def main():
    grid = signal_eval.load()
    score = value_score(grid["px_panama"])
    s, lines, pos, net, net_by_mkt = signal_eval.evaluate(score, grid, "s5 value")
    rolls = backtest.roll_days()
    _, g2, c2 = signal_eval.run_one(value_score(grid["px_ratio"]), grid["w0"], rolls)
    ratio_sharpe = backtest.sharpe((g2.sum(axis=1) - c2.sum(axis=1)) / config.CAPITAL)
    dev_ratio = abs(ratio_sharpe - s["sharpe_net"])
    s["stitch_stable"] = bool(s["stitch_stable"] and dev_ratio <= config.STITCH_TOLERANCE)

    trend_net = pd.read_parquet(config.STAGES / "s2_net.parquet")["net"]
    carry_net = pd.read_parquet(config.STAGES / "s3_net.parquet")["net"]
    corr_t, corr_c = float(net.corr(trend_net)), float(net.corr(carry_net))
    corr_tm = float(net.resample("ME").sum().corr(trend_net.resample("ME").sum()))
    lines += ["", f"* signal on ratio-adjusted prices: Sharpe {ratio_sharpe:.2f} (deviation {dev_ratio:.2f})",
              "", "## Correlation gate", "",
              f"* value vs trend, daily net returns: **{corr_t:+.3f}** (monthly {corr_tm:+.3f}) — "
              f"{'negative, as claimed' if corr_t < 0 else 'NOT negative — claim refuted'}",
              f"* value vs carry: {corr_c:+.3f}",
              "", "## Gate", "", f"* value-trend correlation negative: {corr_t < 0}",
              f"* placebo cleared: {s['placebo_cleared']}", f"* stitching stable: {s['stitch_stable']}", f"* in band: {s['in_band']}"]
    progress.write_report("s5", "\n".join(lines))
    score.to_parquet(config.STAGES / "s5_score.parquet")
    pos.to_parquet(config.STAGES / "s5_positions.parquet")
    net.to_frame("net").to_parquet(config.STAGES / "s5_net.parquet")
    net_by_mkt.to_parquet(config.STAGES / "s5_net_by_market.parquet")
    pd.Series({k: v for k, v in s.items() if not isinstance(v, dict)}).to_json(config.STAGES / "s5_stats.json")
    if corr_t >= 0:
        progress.halt("s5", f"value-trend correlation {corr_t:+.3f} is not negative")
    if not s["stitch_stable"]:
        progress.halt("s5", f"stitching unstable: {s['max_dev_from_w0']:.2f} / ratio {dev_ratio:.2f}")
    plc = "cleared" if s["placebo_cleared"] else "NOT cleared"
    flag = "" if s["in_band"] else f" (OUTSIDE BAND: MDE {s['mde_sharpe']:.2f})"
    return (f"gate PASS — value-trend corr {corr_t:+.2f}; value net Sharpe {s['sharpe_net']:.2f}{flag}, placebo {plc} "
            f"(p95 {s['placebo_p95']:.2f}), {s['gross_bp_per_side_traded']:.1f} bp/side vs {s['cost_bp_per_side_traded']:.2f} cost")


if __name__ == "__main__":
    print(main())
