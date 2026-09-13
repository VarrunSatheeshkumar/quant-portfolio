"""s9: open the sealed hold-out exactly once; compile RESULTS.md.

Two years of daily returns give a Sharpe a standard error of about 0.7. The
hold-out therefore cannot confirm a band-level result; it can catch an artefact
or a gross failure. The pre-stated consistency criterion is that the hold-out
Sharpe lies within the training Sharpe ± 2 x SE(2 years) -- about ±1.4.
"""

import json
from datetime import date

import numpy as np
import pandas as pd

import backtest
import config
import progress
from lib import holdout
from stages import s4, s6, signal_eval

LOOKS = config.REPORTS / "holdout_looks.json"


def stats_json(stage):
    p = config.STAGES / f"{stage}_stats.json"
    return json.loads(p.read_text())


def main():
    counter = holdout.LookCounter(LOOKS)
    entry = counter.data.get("holdout", {})
    if counter.count("holdout") == 1 and entry.get("aborted") and not (config.STAGES / "s9_stats.json").exists():
        # the registration exists but the scoring run was killed before computing anything:
        # this run completes that same look and does not increment
        entry["history"].append({"note": f"scoring completed {date.today().isoformat()} by the final run", "at": pd.Timestamp.utcnow().isoformat()})
        entry["aborted"] = False
        counter.path.write_text(json.dumps(counter.data, indent=2))
    elif counter.count("holdout") > 0:
        # The tracked counter already records a scoring. A second scoring is not a hold-out, so
        # this run does not re-score: the tracked RESULTS.md and s9.md are retained as they are,
        # and the reproduction continues to the candidate tests.
        last = (entry.get("history") or [{}])[-1].get("at", "")[:10]
        line = (f"hold-out already scored (look count {counter.count('holdout')}, last {last}); not re-scored -- "
                f"a second scoring is not a hold-out; tracked RESULTS.md and s9.md retained")
        print(f"s9: {line}")
        return line
    else:
        counter.look("holdout", note=f"opened {date.today().isoformat()} after s0-s8 complete and every decision final")

    grid = signal_eval.load()
    scores = s6.load_scores()
    lo = config.SEALED_START
    hi = grid["w0"].index.max()
    b = s4.build(scores, grid, lo=lo, hi=hi)
    s = backtest.summary(b["gross"], b["cost"], config.CAPITAL)
    train = stats_json("s6")
    se2 = np.sqrt((1 + 0.5 * train["sharpe_net"] ** 2) / 2.0)      # SE of a 2-year annualised Sharpe
    consistent = abs(s["sharpe_net"] - train["sharpe_net"]) <= 2 * se2
    rolls = backtest.roll_days()
    stand = {}
    for k, v in scores.items():
        _, g, c = signal_eval.run_one(v, grid["w0"], rolls, lo=lo, hi=hi)
        stand[k] = backtest.sharpe((g.sum(axis=1) - c.sum(axis=1)) / config.CAPITAL)
    neff = b["neff"].dropna()
    lines = ["# s9 — sealed hold-out, opened once", "",
             f"Opened {date.today().isoformat()}; look count {counter.count('holdout')}. Period {lo} to {hi.date()} "
             f"({s['n_days']} days). Everything upstream was final before this ran.", "",
             f"* combined Sharpe after costs **{s['sharpe_net']:.2f}** (training {train['sharpe_net']:.2f}); "
             f"2-year SE ≈ {se2:.2f}; consistent with training: **{consistent}**",
             f"* annual return {s['ann_return']:.2%}, realised vol {s['ann_vol']:.2%} (target {config.VOL_TARGET:.0%}), "
             f"max drawdown {s['max_dd']:.1%}, breadth {neff.median():.1f}",
             f"* standalone on hold-out: " + ", ".join(f"{k} {v:.2f}" for k, v in stand.items()), ""]
    progress.write_report("s9", "\n".join(lines))
    b["net"].to_frame("net").to_parquet(config.STAGES / "s9_net.parquet")
    out = {k: v for k, v in s.items() if not isinstance(v, dict)}
    out.update(dict(consistent=bool(consistent), se2=float(se2), standalone=stand, breadth=float(neff.median()),
                    opened=date.today().isoformat(), lo=lo, hi=str(hi.date())))
    (config.STAGES / "s9_stats.json").write_text(json.dumps(out, indent=2, default=float))
    write_results(out, train)
    return (f"hold-out opened once ({date.today().isoformat()}): combined net Sharpe {s['sharpe_net']:.2f} vs training "
            f"{train['sharpe_net']:.2f}, consistent {consistent}; RESULTS.md written")


def write_results(ho, s6s):
    s1 = pd.read_parquet(config.STAGES / "s1_costs.parquet")
    s1_report = (config.STAGE_REPORTS / "s1.md").read_text()
    ratio_line = [l for l in s1_report.splitlines() if l.startswith("* **edge / cost")][0]
    sig = {k: stats_json(st) for k, st in zip(["trend", "carry", "value"], ["s2", "s3", "s5"])}
    s7 = pd.read_parquet(config.STAGES / "s7_by_vol.parquet")
    s8_report = (config.STAGE_REPORTS / "s8.md").read_text()
    s8_best = pd.read_parquet(config.STAGES / "s8_best.parquet")
    shares = pd.read_parquet(config.STAGES / "s4_sector_shares.parquet")
    corr_d = pd.DataFrame(s6s["corr_daily"]).round(3)
    corr_m = pd.DataFrame(s6s["corr_monthly"]).round(3)
    dist = s6s["dist"]
    base = s7.loc["15%"]
    n_att = int(s8_best["attainable"].sum())
    gap_lines = [l for l in s8_report.splitlines() if l.startswith("* vol target maximising") or l.startswith("* SPEC example mandate")]
    bind_lines = [l for l in s8_report.splitlines() if l.startswith("* overall")]

    def audit(st):
        return ("placebo " + ("cleared" if st["placebo_cleared"] else "NOT cleared") +
                "; stitching " + ("stable" if st["stitch_stable"] else "UNSTABLE") +
                "; band " + ("in" if st["in_band"] else "OUT (MDE %.2f)" % st["mde_sharpe"]) +
                "; shuffled %.2f" % st["shuffled_sharpe"])

    L = ["# RESULTS", "", f"Generated {date.today().isoformat()}. Training period {config.EVAL_START} to "
         f"{signal_eval.training_end().date()}; sealed hold-out {ho['lo']} to {ho['hi']}, opened once on {ho['opened']}. "
         "27 markets, six sectors, daily data, all free sources; see DECISIONS.md for every choice and s0's report for what "
         "the data is.", "",
         "## 1. Cost ratio (computed first, before any return was read)", "",
         ratio_line,
         f"* modelled round trip: universe median {s1.round_trip_bp.median():.2f} bp of notional, "
         f"{s1.cost_pct_of_daily_vol.median():.1f}% of a daily move; the 2-year note is the outlier at "
         f"{s1.loc['ZT', 'cost_pct_of_daily_vol']:.1f}%",
         "* the literal daily-rebalanced SPEC §5a rule failed this check (edge/cost 0.85); the pre-registered monthly-signal / "
         "weekly-size schedule passes (DECISIONS.md)", "",
         "## 2. Signals standalone (training period)", "",
         "| signal | Sharpe after costs | turnover ×/yr | gross bp per side traded | cost bp per side | avg abs score | coverage | audit |",
         "|---|---|---|---|---|---|---|---|"]
    for k, st in sig.items():
        L.append(f"| {k} | {st['sharpe_net']:.2f} | {st['turnover']:.1f} | {st['gross_bp_per_side_traded']:.1f} | "
                 f"{st['cost_bp_per_side_traded']:.2f} | {st['avg_abs_score']:.2f} | {st['coverage']:.0%} | {audit(st)} |")
    L += ["", "Carry covers 13 markets (FX, equity, US rates); commodity carry is unobservable on free data and is NaN, not zero. "
          "Standalone MDEs are 0.55–0.62 Sharpe-equivalent: no single signal can be distinguished from zero at 80% power over "
          "23 years, which is the annualised-ratio arithmetic from FAILURES.md; the standalone criteria are band and placebo.", "",
          "## 3. Pairwise correlation of the signals' returns", "", "Daily:", "", corr_d.to_markdown(), "", "Monthly:", "", corr_m.to_markdown(), "",
          "## 4. Portfolio construction", "",
          f"* realised vol {s6s['ann_vol']:.2%} against target {config.VOL_TARGET:.0%} (s4 gate: within ±20%)",
          f"* effective breadth median **{s6s['breadth']:.1f}** independent bets from 27 markets (band 8–15)",
          "* sector risk shares (mean / max): " + ", ".join(f"{c} {shares[c].mean():.0%}/{shares[c].max():.0%}" for c in shares.columns), "",
          "## 5. Combined programme (training period)", "",
          f"* Sharpe after costs **{s6s['sharpe_net']:.2f}** (gross {s6s['sharpe_gross']:.2f}); band 0.5–1.0: "
          f"{'in' if s6s['in_band'] else 'OUT'}; audit: placebo {'cleared' if s6s['placebo_cleared'] else 'NOT cleared'} "
          f"(p95 {s6s['placebo_p95']:.2f}), shuffled returns {s6s['shuffled_sharpe']:.2f}, stitching "
          f"{'stable' if s6s['stitch_stable'] else 'UNSTABLE'} (max dev {s6s['max_dev']:.2f})",
          f"* annual return {s6s['ann_return']:.2%}, max drawdown {s6s['max_dd']:.1%}, longest flat period "
          f"{dist['longest_flat_days']} trading days, {s6s['gross_bp_per_side_traded']:.1f} bp gross per side traded against "
          f"{s6s['cost_bp_per_side_traded']:.2f} bp cost",
          f"* distribution: worst day {dist['worst_day']:.2%}, best day {dist['best_day']:.2%}, skew {dist['skew']:.2f}, "
          f"excess kurtosis {dist['kurt']:.1f}, monthly hit rate {dist['month_hit']:.0%}, worst month {dist['worst_month']:.1%}",
          "* contribution by signal (combined minus without): " + ", ".join(f"{k} {v:+.2f}" for k, v in s6s["contrib"].items()), "",
          "## 6. Stitching sensitivity", "",
          "Yahoo `=F` series are unadjusted front-month splices; no contract chain exists on free data, so the SPEC §4 "
          "Panama-vs-ratio test is run on adjusted series rebuilt from roll-neutralised changes, and the roll treatment "
          "itself is varied (raw / switch day / ±1 / ±3 / roll-early-3). Combined programme:", ""]
    L += [f"* {k}: {v:.2f}" for k, v in s6s["sens"].items()]
    L += ["", f"* raw − neutralised = {s6s['raw_minus_w0']:+.2f} (a positive value above 0.15 would mark the raw result an artefact)", "",
          "## 7. Drawdown-mandate simulator (real s6 path, 8% target / 10% DD / 3% daily / 60 days)", "",
          f"* at 15% vol: pass **{base['pass_prob']:.1%}**, median {base['median_days_to_pass']:.0f} days to pass, breach by DD "
          f"{base['breach_dd']:.1%}, by daily loss {base['breach_daily']:.1%}, timeout **{base['timeout']:.1%}**", "",
          s7.round(3).to_markdown(), "",
          "## 8. Mandate feasibility sweep", "",
          f"* {n_att} of {len(s8_best)} mandates attainable (pass ≥ 50% at the best vol target)"] + bind_lines + gap_lines + ["",
          "## 9. Sealed hold-out (opened once)", "",
          f"* opened {ho['opened']}; combined Sharpe after costs **{ho['sharpe_net']:.2f}** on {ho['lo']}–{ho['hi']} "
          f"(training {s6s['sharpe_net']:.2f}; 2-year SE {ho['se2']:.2f}; consistent: {ho['consistent']})",
          f"* vol {ho['ann_vol']:.2%}, max drawdown {ho['max_dd']:.1%}, breadth {ho['breadth']:.1f}; standalone: " +
          ", ".join(f"{k} {v:.2f}" for k, v in ho["standalone"].items()), "",
          "## 10. Audit status", "",
          "| number | value | status |", "|---|---|---|",
          f"| cost ratio | {ratio_line.split('=')[1].split('—')[0].strip()} | computed before any return; schedule chosen on cost only |"]
    for k, st in sig.items():
        L.append(f"| {k} Sharpe | {st['sharpe_net']:.2f} | {audit(st)} |")
    L += [f"| combined Sharpe | {s6s['sharpe_net']:.2f} | placebo {'cleared' if s6s['placebo_cleared'] else 'NOT cleared'}; "
          f"shuffled {s6s['shuffled_sharpe']:.2f}; stitching {'stable' if s6s['stitch_stable'] else 'UNSTABLE'}; "
          f"band {'in' if s6s['in_band'] else 'OUT'} |",
          f"| breadth | {s6s['breadth']:.1f} | diversification ratio squared under the shrunk covariance |",
          f"| pass probability | {base['pass_prob']:.1%} | real path, overlapping starts, no interval |",
          f"| hold-out Sharpe | {ho['sharpe_net']:.2f} | one look; SE {ho['se2']:.2f} |", "",
          "## 11. Plain English", "", "_(written after the run; see below)_", ""]
    (config.REPORTS / "RESULTS.md").write_text("\n".join(L))


if __name__ == "__main__":
    print(main())
