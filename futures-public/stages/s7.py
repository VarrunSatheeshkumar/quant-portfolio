"""s7: the drawdown-mandate simulator on the real s6 path."""

import json

import numpy as np
import pandas as pd

import config
import progress
import simulator

BASE = dict(target=0.08, max_dd=0.10, daily_loss=0.03, window=60)
VOLS = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40]
SPEC_PRIOR = "SPEC §9 synthetic prior: Sharpe 0.8 at 15% vol, 8% target before 10% loss inside 60 days: ~23% pass; ~86% timeouts at lower vol."


def run_book(net):
    rows = {}
    for v in VOLS:
        rows[f"{v:.0%}"] = simulator.summarise(simulator.simulate(simulator.scaled(net, v), **BASE))
    return pd.DataFrame(rows).T


def main():
    net = pd.read_parquet(config.STAGES / "s6_net.parquet")["net"].dropna()
    net4 = pd.read_parquet(config.STAGES / "s4_net.parquet")["net"].dropna()
    tbl4 = run_book(net4)
    tbl4.to_parquet(config.STAGES / "s7_by_vol_trendcarry.parquet")
    realised = float(net.std() * np.sqrt(252))
    rows = {}
    for v in VOLS:
        r = simulator.scaled(net, v)
        sim = simulator.simulate(r, **BASE)
        rows[f"{v:.0%}"] = simulator.summarise(sim)
        if abs(v - 0.15) < 1e-9:
            sim.to_parquet(config.STAGES / "s7_base_outcomes.parquet")
    tbl = pd.DataFrame(rows).T
    base = tbl.loc["15%"]
    at_real = simulator.summarise(simulator.simulate(net, **BASE))
    ok = int(tbl["n"].min()) > 1000 and np.allclose(tbl[["pass_prob", "breach_dd", "breach_daily", "timeout"]].sum(axis=1), 1.0)
    # what binds at each vol: the most common non-pass outcome
    binds = tbl[["breach_dd", "breach_daily", "timeout"]].idxmax(axis=1)
    lines = ["# s7 — drawdown-mandate simulator (real s6 daily net returns, training period)", "",
             f"Base mandate: target +{BASE['target']:.0%}, max drawdown {BASE['max_dd']:.0%}, daily loss {BASE['daily_loss']:.0%}, "
             f"window {BASE['window']} trading days. Every day with {BASE['window']} days ahead is a start ({int(tbl['n'].min())} attempts). "
             "Attempts overlap and are not independent; no interval is claimed.", "",
             f"## At the {config.VOL_TARGET:.0%} target (path rescaled from realised {realised:.1%})", "",
             f"* pass probability **{base['pass_prob']:.1%}**, median days to pass {base['median_days_to_pass']:.0f}",
             f"* breach by drawdown {base['breach_dd']:.1%}, by daily loss {base['breach_daily']:.1%}, timeout **{base['timeout']:.1%}**",
             f"* on the unscaled path (realised {realised:.1%}): pass {at_real['pass_prob']:.1%}, timeout {at_real['timeout']:.1%}", "",
             "## Across vol targets (same mandate)", "", tbl.round(3).to_markdown(), "",
             "Binding (most common non-pass) outcome by vol target: " + ", ".join(f"{k}: {v}" for k, v in binds.items()), "",
             f"## Against the prior", "", f"* {SPEC_PRIOR}",
             f"* here the programme's Sharpe is {json.loads((config.STAGES / 's6_stats.json').read_text())['sharpe_net']:.2f}, not 0.8, so the "
             "pass rate should sit below 23% at 15% vol; the timeout share at low vol is the check on the simulator's machinery.", "",
             "## Secondary: the pre-registered s4 trend+carry book (before value), same mandate", "",
             tbl4.round(3).to_markdown(), "",
             "## Gate", "", f"* runs on real backtest returns: yes (s6_net.parquet); outcomes partition every attempt: {ok}"]
    progress.write_report("s7", "\n".join(lines))
    tbl.to_parquet(config.STAGES / "s7_by_vol.parquet")
    if not ok:
        progress.halt("s7", "outcome shares do not sum to one or too few attempts")
    return (f"gate PASS — base mandate at 15% vol: pass {base['pass_prob']:.1%}, timeout {base['timeout']:.1%}, "
            f"breach dd {base['breach_dd']:.1%} / daily {base['breach_daily']:.1%}, median {base['median_days_to_pass']:.0f} days")


if __name__ == "__main__":
    print(main())
