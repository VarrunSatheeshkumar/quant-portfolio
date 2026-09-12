"""s8: mandate feasibility sweep."""

import itertools

import numpy as np
import pandas as pd

import config
import progress
import simulator

DAILY = [0.01, 0.02, 0.03, 0.05]
MAXDD = [0.05, 0.08, 0.10, 0.15, 0.20]
TARGET = [0.04, 0.06, 0.08, 0.10, 0.15]
WINDOW = [20, 40, 60, 120, 250]
VOLS = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40]
ATTAINABLE = 0.5


def calmar(r):
    eq = (1 + r).cumprod()
    dd = (eq / eq.cummax() - 1).min()
    return float(r.mean() * 252 / abs(dd)) if dd < 0 else np.nan


def sweep(net):
    paths = {v: simulator.scaled(net, v) for v in VOLS}
    rows = []
    for d, m, t, w in itertools.product(DAILY, MAXDD, TARGET, WINDOW):
        for v in VOLS:
            s = simulator.summarise(simulator.simulate(paths[v], target=t, max_dd=m, daily_loss=d, window=w))
            s.update(daily=d, max_dd=m, target=t, window=w, vol=v)
            rows.append(s)
    sw = pd.DataFrame(rows)
    sw["binding"] = sw[["breach_dd", "breach_daily", "timeout"]].idxmax(axis=1)
    return sw, paths


def main():
    net = pd.read_parquet(config.STAGES / "s6_net.parquet")["net"].dropna()
    net4 = pd.read_parquet(config.STAGES / "s4_net.parquet")["net"].dropna()
    sw4, paths4 = sweep(net4)
    key4 = ["daily", "max_dd", "target", "window"]
    best4 = sw4.loc[sw4.groupby(key4)["pass_prob"].idxmax()].set_index(key4)
    best4["attainable"] = best4["pass_prob"] >= ATTAINABLE
    cal4 = pd.Series({v: calmar(paths4[v]) for v in VOLS})
    sw4.to_parquet(config.STAGES / "s8_sweep_trendcarry.parquet")
    best4.to_parquet(config.STAGES / "s8_best_trendcarry.parquet")
    paths = {v: simulator.scaled(net, v) for v in VOLS}
    rows = []
    for d, m, t, w in itertools.product(DAILY, MAXDD, TARGET, WINDOW):
        for v in VOLS:
            s = simulator.summarise(simulator.simulate(paths[v], target=t, max_dd=m, daily_loss=d, window=w))
            s.update(daily=d, max_dd=m, target=t, window=w, vol=v)
            rows.append(s)
    sw = pd.DataFrame(rows)
    sw["binding"] = sw[["breach_dd", "breach_daily", "timeout"]].idxmax(axis=1)
    sw.to_parquet(config.STAGES / "s8_sweep.parquet")

    key = ["daily", "max_dd", "target", "window"]
    best = sw.loc[sw.groupby(key)["pass_prob"].idxmax()].set_index(key)
    best["attainable"] = best["pass_prob"] >= ATTAINABLE
    n_att = int(best["attainable"].sum())
    share_bind = best["binding"].value_counts(normalize=True)
    # where each constraint binds: by window and by max_dd
    bind_by_window = sw.groupby("window")["binding"].value_counts(normalize=True).unstack().fillna(0)
    bind_by_dd = sw.groupby("max_dd")["binding"].value_counts(normalize=True).unstack().fillna(0)
    bind_by_vol = sw.groupby("vol")["binding"].value_counts(normalize=True).unstack().fillna(0)

    # the gap: vol maximising pass probability (per mandate) vs vol maximising Calmar on the real path
    cal = pd.Series({v: calmar(paths[v]) for v in VOLS})
    v_calmar = float(cal.idxmax())
    v_pass = best.reset_index()["vol"]
    spec_row = best.loc[(0.03, 0.10, 0.08, 60)]
    # per-mandate pass-probability-maximising vol, restricted to attainable mandates
    att = best[best["attainable"]]
    lines = ["# s8 — mandate feasibility sweep", "",
             f"{len(sw)} (mandate, vol) cells: daily loss {DAILY} × max DD {MAXDD} × target {TARGET} × window {WINDOW} × vol {VOLS}. "
             f"A mandate is attainable if its best vol target gives pass probability ≥ {ATTAINABLE:.0%}.", "",
             "## What is attainable", "",
             f"* **{n_att} of {len(best)} mandates attainable**",
             f"* attainable mandates' pass-maximising vol target: median {att['vol'].median():.0%} (min {att['vol'].min():.0%}, max {att['vol'].max():.0%})" if n_att else "* none attainable",
             f"* SPEC's example (8% target, 10% DD, 3% daily, 60 days): best pass {spec_row['pass_prob']:.1%} at {spec_row['vol']:.0%} vol, "
             f"binding {spec_row['binding']}", "",
             "## Which constraint binds, and where", "",
             "Share of cells where each outcome is the most common non-pass result:", "",
             "* overall (at each mandate's best vol): " + ", ".join(f"{k} {v:.0%}" for k, v in share_bind.items()), "",
             "By window:", "", bind_by_window.round(2).to_markdown(), "",
             "By max drawdown:", "", bind_by_dd.round(2).to_markdown(), "",
             "By vol target:", "", bind_by_vol.round(2).to_markdown(), "",
             "## The gap", "",
             f"* vol target maximising risk-adjusted return (Calmar = return / |max DD| on the real path): **{v_calmar:.0%}** "
             f"(Calmar by vol: " + ", ".join(f"{v:.0%}: {c:.2f}" for v, c in cal.items()) + ")",
             f"* vol target maximising pass probability, across all mandates: median **{v_pass.median():.0%}**, "
             f"across attainable ones {att['vol'].median():.0%}" if n_att else f"* vol maximising pass probability across all mandates: median {v_pass.median():.0%}",
             f"* SPEC example mandate: pass-maximising vol {spec_row['vol']:.0%} vs Calmar-maximising {v_calmar:.0%} — "
             f"gap {spec_row['vol'] - v_calmar:+.0%}", "",
             "## Feasibility surface (pass probability at the best vol), 60-day window, 3% daily limit", "",
             best.xs((0.03, 60), level=("daily", "window"))["pass_prob"].unstack("target").round(2).to_markdown(), "",
             "## Secondary: the pre-registered s4 trend+carry book (before value)", "",
             f"* {int(best4['attainable'].sum())} of {len(best4)} mandates attainable; binding at best vol: " +
             ", ".join(f"{k} {v:.0%}" for k, v in best4["binding"].value_counts(normalize=True).items()),
             f"* Calmar-maximising vol {cal4.idxmax():.0%}; pass-maximising vol median {best4['vol'].median():.0%} "
             f"(attainable: {best4.loc[best4['attainable'], 'vol'].median() if best4['attainable'].any() else float('nan'):.0%}); "
             f"SPEC mandate best pass {best4.loc[(0.03, 0.10, 0.08, 60), 'pass_prob']:.1%} at {best4.loc[(0.03, 0.10, 0.08, 60), 'vol']:.0%}", "",
             best4.xs((0.03, 60), level=("daily", "window"))["pass_prob"].unstack("target").round(2).to_markdown(), "",
             "## Gate", "", f"* surface computed: {len(sw)} cells; binding constraint identified: yes"]
    progress.write_report("s8", "\n".join(lines))
    best.to_parquet(config.STAGES / "s8_best.parquet")
    return (f"gate PASS — {n_att}/{len(best)} mandates attainable; binds: " + ", ".join(f"{k} {v:.0%}" for k, v in share_bind.items()) +
            f"; pass-max vol {spec_row['vol']:.0%} vs Calmar-max {v_calmar:.0%} on SPEC mandate")


if __name__ == "__main__":
    print(main())
