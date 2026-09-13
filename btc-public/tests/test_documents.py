"""Selected literal phrases in README.md and WRITEUP.md, checked against reports/results/.

Each check rebuilds a phrase from the stored artefacts and asserts it appears in the
document. Whitespace is collapsed before matching. This validates the presence of
the phrase, not its interpretation. Figures that come from `data/` (not tracked) are
checked only when the data is present; figures from the private project are named
as not checkable here.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config

MINUS = "−"


def num(x, dp):
    return f"{x:.{dp}f}".replace("-", MINUS)


def signed(x, dp):
    s = f"{x:+.{dp}f}"
    return s.replace("-", MINUS)


def flat(text):
    return re.sub(r"\s+", " ", text.replace("**", "").replace("`", ""))


def main():
    R = config.RESULTS
    vol = json.load(open(R / "vol_model.json"))
    har = json.load(open(R / "har.json"))
    ev = json.load(open(R / "event_study.json"))
    ins = json.load(open(R / "instrument.json"))
    eco = json.load(open(R / "economics.json"))

    gt = ev["ground_truth"]
    lev = ev["framings"]["5_anticipation"]["level_after_unpredicted"]
    pl5 = ev["framings"]["5_anticipation"]["placebo"]
    f1 = ev["framings"]["1_acceleration"]
    f2 = ev["framings"]["2_pressure"]["slope"]
    f3 = ev["framings"]["3_age"]
    f4 = ev["framings"]["4_regime"]
    vs = vol["scores"]
    hs = har["scores"]

    def cell(h, b, k):
        return vs[h][b][k]

    checks = []

    def add(doc, phrase):
        if doc == "both":
            checks.extend([("readme", phrase), ("writeup", phrase)])
        else:
            checks.append((doc, phrase))

    # ---- locator
    for kind, label in (("cluster", "cluster touches"), ("mid", "mid touches"), ("empty", "empty touches")):
        pct = gt[kind]["pct_with_liquidation"] * 100
        pct_s = f"{pct:.0f}" if kind == "cluster" else f"{pct:.1f}"
        add("both", f"{pct_s} % of {label} (n {int(gt[kind]['n']):,})")
    add("writeup", f"cluster ${gt['cluster']['mean_liq_notional'] / 1e6:.2f}m (n {int(gt['cluster']['n'])}), "
                   f"mid ${gt['mid']['mean_liq_notional'] / 1e6:.2f}m (n {int(gt['mid']['n'])}), "
                   f"empty ${gt['empty']['mean_liq_notional'] / 1e6:.2f}m (n {int(gt['empty']['n']):,})")
    add("writeup", f"{gt['empty_zero_mass_share'] * 100:.0f} % of empty touches are zero-mass buckets")
    add("writeup", f"cluster/empty = {gt['notional_multiple_cluster_over_empty']:.1f}")
    add("writeup", f"cluster/non-zero-mass empty = {gt['notional_multiple_excluding_emptied']:.1f}")

    # ---- price after prints, three horizons
    l30 = lev["30m"]
    add("writeup", f"{l30['n']:,} prints on {l30['n_days']} day-blocks")
    add("writeup", f"MDE {l30['mde_bps']:.1f} bps")
    for h in ("30m", "15m", "60m"):
        v = lev[h]
        estimate = signed(v['level_bps'], 1) if v['level_bps'] > 0 else num(v['level_bps'], 1)
        interval = f"[{num(v['ci_lo'], 1)}, {num(v['ci_hi'], 1)}]"
        add("readme", f"at {h.replace('m', ' min')} {estimate} {interval}")
        add("writeup", f"| {h.replace('m', ' min')} | {estimate} | {interval} |")
    add("writeup", f"interval [{num(l30['ci_lo'], 1)}, {num(l30['ci_hi'], 1)}] lies inside ±{config.BAND_BPS:.0f} bps")
    add("writeup", f"matched difference is {num(pl5['real'], 1)} bps")
    add("writeup", f"{pl5['n_placebo']} draws) the 95th percentile of absolute deviations from the placebo mean is "
                   f"{pl5['placebo_abs_p95']:.1f} bps")

    # ---- framings 1-4
    add("writeup", f"({signed(f1['matched_diff_bps'], 1)} bps over {f1['n_cells']} cells)")
    s1 = f1["abs_move_slope"]
    add("writeup", f"interval [{s1['ci_lo']:.0f}, {s1['ci_hi']:.0f}] and MDE {s1['mde']:.0f}")
    add("writeup", f"slope {signed(s1['slope'], 0)} [{s1['ci_lo']:.0f}, {s1['ci_hi']:.0f}]")
    add("writeup", f"slope {num(f2['slope'], 2)} [{num(f2['ci_lo'], 2)}, {num(f2['ci_hi'], 2)}], MDE {f2['mde']:.2f} bps per unit log-pressure, "
                   f"n {f2['n']:,} on {f2['n_days']} book days")
    r3 = f3["raw_slope"]
    add("writeup", f"raw slope {num(r3['slope'], 1)} [{num(r3['ci_lo'], 1)}, {num(r3['ci_hi'], 1)}] bps per unit log-age, "
                   f"MDE {r3['mde']:.1f}, n {r3['n']:,} on {r3['n_days']:,} days")
    add("writeup", f"momentum-controlled slope is {num(f3['controlled_for_momentum']['beta_log_age'], 1)} with no interval")
    add("writeup", f"weekend {num(f4['weekend']['matched_diff_bps'], 1)} bps over {f4['weekend']['n_cells']} cells; "
                   f"Asia {signed(f4['asia']['matched_diff_bps'], 1)} bps over {f4['asia']['n_cells']} cells")

    # ---- volatility
    add("writeup", f"R² in the sealed blocks: {num(cell('1h', 'sealed_2022', 'r2_model'), 3)} against "
                   f"{num(cell('1h', 'sealed_2022', 'r2_garch'), 3)} and {num(cell('1h', 'sealed_recent', 'r2_model'), 3)} against "
                   f"{num(cell('1h', 'sealed_recent', 'r2_garch'), 3)} at one hour, {num(cell('4h', 'sealed_2022', 'r2_model'), 3)} against "
                   f"{num(cell('4h', 'sealed_2022', 'r2_garch'), 3)} and {num(cell('4h', 'sealed_recent', 'r2_model'), 3)} against "
                   f"{num(cell('4h', 'sealed_recent', 'r2_garch'), 3)} at four hours")
    garch_better = sum(1 for h in ("1h", "4h") for b in ("sealed_2022", "sealed_recent")
                       if cell(h, b, "qlike_garch") < cell(h, b, "qlike_model"))
    words = {1: "one", 2: "two", 3: "three", 4: "four"}
    add("writeup", f"on QLIKE GARCH is better in {words[garch_better]} of four sealed cells")
    dwm = [hs[h][b]["gain_over_har_dwm"] for h in ("1h", "4h") for b in ("sealed_2022", "sealed_recent")]
    add("writeup", f"loses by {min(dwm):.2f} to {max(dwm):.2f} R²")
    gains = [hs[h][b]["gain_over_har_intraday"] for h in ("1h", "4h") for b in ("sealed_2022", "sealed_recent")]
    add("both", "R² differences over the hour/day/week HAR of " + "/".join(signed(g, 3) for g in gains))
    n22, nrec = vs["1h"]["sealed_2022"]["n"], vs["1h"]["sealed_recent"]["n"]
    add("both", f"{n22:,} and {nrec:,} evaluated rows per block ({n22 // 288} and {nrec // 288} complete-day equivalents out of 365)")
    lost = har["sealed_cells_lost_on_qlike"]["har_intraday"]
    add("both", f"intraday HAR beats Model A in {words[lost]} of the {words[har['n_sealed_cells']]} sealed cells")
    from src import vol_model  # noqa: E402
    add("both", f"{len(vol_model.FEATURES)}-feature ridge")
    add("both", f"{config.MAP_HALF_LIFE_BARS / 288:.1f}-day half-life")

    # ---- option structures and the economics formula outputs
    ideal = ins["best_idealised_mde_bps"]
    full = ins["best_idealised_mde_full_sample_bps"]
    floor_name = ins["best_idealised_structure"]
    nq = ins["idealised_2021_on"][floor_name]["n_train_trades"]
    yrs = ins["idealised_2021_on"][floor_name]["years_of_sample"]
    add("writeup", f"({nq} weekly strips) the stored idealised MDE is {ideal:.1f} bps ({full:.1f} on the full sample)")
    add("writeup", f"({ideal:.1f}/{ins['band_bps']:.0f})² = {ins['sample_multiple_needed']:.0f}")
    add("writeup", f"{ins['sample_multiple_needed']:.0f} × {yrs:.1f} years = {ins['years_needed']:.0f}")
    add("writeup", f"Eight structures were costed; the smallest stored MDE is {ins['best_structure_mde_bps']:.1f} bps")
    assert ins["n_structures_costed"] == 8
    add("writeup", f"Cost of {eco['best_cost_bps']:.1f} bps for the daily-hedged straddle comprises fees and hedge fees")
    add("writeup", f"stored MDE for the daily-hedged straddle is {eco['best_mde_bps']:.1f} bps; the stored edge range is "
                   f"{eco['best_edge_bps_low']:.1f}–{eco['best_edge_bps_high']:.1f} bps")
    words[10] = "ten"
    add("writeup", f"{eco['independent_trades_needed']:.0f} independent trades, about "
                   f"{words[int(round(eco['years_needed_weekly']))]} years of weekly ones")

    # ---- sealed-block rows and the test's own count (self-referential by design)
    docs = {"readme": flat((config.ROOT / "README.md").read_text()),
            "writeup": flat((config.ROOT / "WRITEUP.md").read_text())}
    add("both", f"{len(checks) + 4} selected literal phrases")  # +4: these two checks and the two data/ sentence checks below
    add("both", "up to five further data-derived phrases are checked when their source files are available")

    # ---- figures from data/ (not tracked): checked only when the data is present
    data_checks = []
    mix_path = config.INTERIM / "leverage_mix.json"
    if mix_path.exists():
        mix = json.load(open(mix_path))
        corr = next(v for k, v in mix.items() if "corr" in k)
        for doc in ("readme", "writeup"):
            data_checks.append((doc, f"log-scale correlation {corr:.2f}"))
    liq = config.RAW / "liquidations.parquet"
    if liq.exists():
        import pandas as pd
        t = pd.to_datetime(pd.read_parquet(liq)["ts"], utc=True)
        d = pd.DatetimeIndex(sorted(t.dt.normalize().unique()))
        first = d[d.day == 1]
        oi = first >= pd.Timestamp("2020-09-01", tz="UTC")
        lo22, hi22 = pd.Timestamp(config.SEALED_2022[0], tz="UTC"), pd.Timestamp(config.SEALED_2022[1], tz="UTC")
        lor, hir = pd.Timestamp(config.SEALED_RECENT[0], tz="UTC"), pd.Timestamp(config.SEALED_RECENT[1], tz="UTC")
        gap = pd.Timedelta(days=config.PURGE_DAYS)
        sealed = ((first >= lo22 - gap) & (first < hi22 + gap)) | ((first >= lor - gap) & (first < hir + gap))
        n_oi, n_sealed = int(oi.sum()), int((sealed & oi).sum())
        n_train = int(((~sealed) & oi & (first < pd.Timestamp(config.LIVE_FORWARD_START, tz="UTC"))).sum())
        for doc in ("readme", "writeup"):
            data_checks.append((doc, f"all {n_oi} OI-covered print days, of which {n_sealed} fall inside the sealed blocks"))
        data_checks.append(("writeup", f"({n_train} first-of-month training days)"))

    fails = []
    for doc, phrase in checks + data_checks:
        if phrase not in docs[doc]:
            fails.append(f"  {doc}: {phrase!r}")

    unverifiable = ["82,152", "six-basis-point", "six basis points"]
    noted = [u for u in unverifiable if flat(u) in docs["writeup"]]

    if fails:
        print(f"FAIL: {len(fails)} document phrases do not match reports/results/")
        print("\n".join(fails))
        sys.exit(1)
    print(f"documents: {len(checks)} quoted phrases match reports/results/, 0 failures"
          + f"; {len(data_checks)} data-derived phrases match available inputs; "
          + f"{5 - len(data_checks)} data-derived phrases not checked (inputs absent)")
    print(f"  ({len(noted)} historical figures from the private project are quoted and not checkable here)")


if __name__ == "__main__":
    main()
