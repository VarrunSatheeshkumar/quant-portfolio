"""s2: trend, standalone, end to end."""

import numpy as np
import pandas as pd

import backtest
import config
import progress
from stages import signal_eval


def trend_score(px):
    # holidays are NaN rows on the business-day grid; a full window would never exist
    return sum(np.sign(px - px.rolling(k, min_periods=int(0.8 * k)).mean()) for k in config.TREND_LOOKBACKS) / len(config.TREND_LOOKBACKS)


def main():
    grid = signal_eval.load()
    score = trend_score(grid["px_panama"])
    s, lines, pos, net, net_by_mkt = signal_eval.evaluate(score, grid, "s2 trend")
    # the SPEC §4 alternative adjustment: same rule on the ratio-adjusted series
    score_ratio = trend_score(grid["px_ratio"])
    rolls = backtest.roll_days()
    _, g2, c2 = signal_eval.run_one(score_ratio, grid["w0"], rolls)
    ratio_sharpe = backtest.sharpe((g2.sum(axis=1) - c2.sum(axis=1)) / config.CAPITAL)
    dev_ratio = abs(ratio_sharpe - s["sharpe_net"])
    s["ratio_series_sharpe"] = ratio_sharpe
    s["stitch_stable"] = bool(s["stitch_stable"] and dev_ratio <= config.STITCH_TOLERANCE)
    lines.insert(lines.index("## By sector (net Sharpe)") - 1,
                 f"* signal on ratio-adjusted prices: Sharpe {ratio_sharpe:.2f} (deviation {dev_ratio:.2f})")

    score.to_parquet(config.STAGES / "s2_score.parquet")
    pos.to_parquet(config.STAGES / "s2_positions.parquet")
    net.to_frame("net").to_parquet(config.STAGES / "s2_net.parquet")
    net_by_mkt.to_parquet(config.STAGES / "s2_net_by_market.parquet")
    pd.Series({k: v for k, v in s.items() if not isinstance(v, dict)}).to_json(config.STAGES / "s2_stats.json")

    audit = s["placebo_cleared"] and s["stitch_stable"] and abs(s["shuffled_sharpe"]) < 0.3
    lines += ["", "## Gate", "",
              f"* placebo cleared: {s['placebo_cleared']}", f"* stitching stable: {s['stitch_stable']}",
              f"* in band: {s['in_band']}" + ("" if s["in_band"] else f" — audit {'resolved' if audit else 'NOT resolved'}"),
              f"* shuffled-return Sharpe near zero: {abs(s['shuffled_sharpe']) < 0.3}"]
    progress.write_report("s2", "\n".join(lines))
    if not s["placebo_cleared"]:
        progress.halt("s2", f"trend did not clear placebo: {s['sharpe_net']:.2f} vs p95 {s['placebo_p95']:.2f}")
    if not s["stitch_stable"]:
        progress.halt("s2", f"stitching unstable: max deviation {s['max_dev_from_w0']:.2f}, ratio dev {dev_ratio:.2f}")
    if not s["in_band"] and not audit:
        progress.halt("s2", f"Sharpe {s['sharpe_net']:.2f} outside band and audit unresolved")
    flag = "" if s["in_band"] else " (OUTSIDE BAND, audit resolved)"
    return (f"gate PASS — trend net Sharpe {s['sharpe_net']:.2f}{flag}, placebo p95 {s['placebo_p95']:.2f}, "
            f"{s['gross_bp_per_side_traded']:.1f} bp/side vs {s['cost_bp_per_side_traded']:.2f} cost, splice artefact {s['raw_minus_w0']:+.2f}")


if __name__ == "__main__":
    print(main())
