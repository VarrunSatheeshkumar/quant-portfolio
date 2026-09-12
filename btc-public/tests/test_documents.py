"""Every number quoted in the prose, checked against the run that produced it.

A report drifts from its results the moment someone reruns a stage and forgets to
retype a figure, and nothing catches it because prose does not fail. This does. Each
check below rebuilds the exact phrase from `reports/results/` and asserts it appears
in the document, so a changed number breaks the build rather than the reader's trust.

Whitespace is collapsed before matching, so line wrapping in the documents is free.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config

MINUS = "−"      # the documents use a typographic minus, not a hyphen


def num(x, dp):
    """Format the way the documents do, including the typographic minus."""
    return f"{x:.{dp}f}".replace("-", MINUS)


def flat(text):
    """Collapse whitespace and drop markdown emphasis.

    A figure is the same figure whether or not the prose bolds it, so line wrapping
    and `**` must not decide whether a check passes.
    """
    return re.sub(r"\s+", " ", text.replace("**", "").replace("`", ""))


def main():
    R = config.RESULTS
    vol = json.load(open(R / "vol_model.json"))["scores"]
    har = json.load(open(R / "har.json"))["scores"]
    ev = json.load(open(R / "event_study.json"))
    ins = json.load(open(R / "instrument.json"))
    eco = json.load(open(R / "economics.json"))

    gt = ev["ground_truth"]
    f5 = ev["framings"]["5_anticipation"]["level_after_unpredicted"]["30m"]
    pl = ev["framings"]["5_anticipation"]["placebo"]

    def sealed(d, h, key):
        return [d[h][b][key] for b in ("sealed_2022", "sealed_recent")]

    harp = json.load(open(R / "har.json"))
    dwm = [g for h in har for g in sealed(har, h, "gain_over_har_dwm")]
    i1 = sealed(har, "1h", "gain_over_har_intraday")
    i4 = sealed(har, "4h", "gain_over_har_intraday")

    checks = [
        # ---- the finding
        ("summary", f"{int(gt['cluster']['n'])} cluster touches"),
        ("summary", f"{gt['notional_multiple_cluster_over_empty']:.1f} times the "
                    "liquidation notional"),
        # The control definition, checked against the threshold the code applies and
        # the composition it publishes -- the ratio moves by more than 2x on this, so
        # the clause defining it is a figure and gets checked like one.
        ("summary", f"under {config.EMPTY_SHARE * 100:.1f}% of map notional, emptied "
                    f"buckets included — {gt['empty_zero_mass_share'] * 100:.0f}% of "
                    f"the control; excluding them gives "
                    f"{gt['notional_multiple_excluding_emptied']:.1f}x"),
        ("writeup", f"under {config.EMPTY_SHARE * 100:.1f}% of the map's notional, "
                    f"emptied buckets included — "
                    f"{gt['empty_zero_mass_share'] * 100:.0f}% of the control group. "
                    f"Excluding them gives "
                    f"{gt['notional_multiple_excluding_emptied']:.1f}x"),
        ("summary", f"${gt['cluster']['mean_liq_notional'] / 1e6:.2f}m against"),
        ("summary", f"${gt['empty']['mean_liq_notional'] / 1e3:.0f}k"),
        ("summary", f"{f5['n']:,} touches over {f5['n_days']} print-covered days"),
        ("summary", f"detectable effect of {f5['mde_bps']:.1f}bps against a "
                    f"{ev['framings']['5_anticipation']['band_bps']:.0f}bps band"),
        ("summary", f"level was {num(f5['level_bps'], 1)}bps, CI "
                    f"[{num(f5['ci_lo'], 1)}, {num(f5['ci_hi'], 1)}]"),

        # ---- the volatility model, against GARCH and against both HARs
        ("summary", f"R² of {num(vol['1h']['sealed_2022']['r2_model'], 3)} against "
                    f"{num(vol['1h']['sealed_2022']['r2_garch'], 3)} and "
                    f"{num(vol['1h']['sealed_recent']['r2_model'], 3)} against "
                    f"{num(vol['1h']['sealed_recent']['r2_garch'], 3)} at one hour, "
                    f"{num(vol['4h']['sealed_2022']['r2_model'], 3)} against "
                    f"{num(vol['4h']['sealed_2022']['r2_garch'], 3)} and "
                    f"{num(vol['4h']['sealed_recent']['r2_model'], 3)} against "
                    f"{num(vol['4h']['sealed_recent']['r2_garch'], 3)} at four hours"),
        ("summary", f"loses by {min(dwm):.2f} to {max(dwm):.2f} R² in the sealed "
                    "blocks"),
        ("summary", f"by {i1[0]:.3f} and {i1[1]:.3f} at one hour and "
                    f"{i4[0]:.3f} and {i4[1]:.3f} at four hours"),
        ("summary", f"intraday HAR wins "
                    f"{harp['sealed_cells_lost_on_qlike']['har_intraday']} of the "
                    f"{harp['n_sealed_cells']} sealed cells"),

        # ---- the instrument ceiling, statistical and economic
        ("summary", f"best resolves {ins['best_structure_mde_bps']:.1f}bps against a "
                    f"{ins['band_bps']:.0f}bps band"),
        ("summary", f"worth {eco['best_edge_bps_low']:.1f} to "
                    f"{eco['best_edge_bps_high']:.1f}bps per trade"),
        ("summary", f"round-trip cost of {eco['best_cost_bps']:.1f}bps"),
        ("summary", f"MDE is {eco['best_mde_bps']:.1f}bps"),
        ("summary", f"tell +{eco['best_net_bps_low']:.1f}bps from zero"),
        ("summary", f"{eco['independent_trades_needed']:.0f} independent trades "
                    f"would: {eco['years_needed_weekly']:.0f} years of weekly ones"),
        ("summary", f"MDE of {ins['best_idealised_mde_bps']:.1f}bps"),
        ("summary", f"needs {ins['sample_multiple_needed']:.0f} times the sample"),
        ("summary", f"roughly {ins['years_needed']:.0f} years"),

        # ---- README
        ("readme", f"{gt['notional_multiple_cluster_over_empty']:.1f}x the "
                   "liquidation notional"),

        # ---- WRITEUP.md, which quotes the same results in prose
        ("writeup", f"every one of the {int(gt['cluster']['n'])} cluster touches"),
        ("writeup", f"{gt['notional_multiple_cluster_over_empty']:.1f} times the "
                    f"liquidation notional"),
        ("writeup", f"${gt['cluster']['mean_liq_notional'] / 1e6:.2f}m against "
                    f"${gt['empty']['mean_liq_notional'] / 1e3:.0f}k"),
        ("writeup", f"{f5['n']:,} touches across {f5['n_days']} print-covered days"),
        ("writeup", f"effect of {f5['mde_bps']:.1f}bps against a "
                    f"{ev['framings']['5_anticipation']['band_bps']:.0f}bps band"),
        ("writeup", f"{num(f5['level_bps'], 1)}bps, 95% CI "
                    f"[{num(f5['ci_lo'], 1)}, {num(f5['ci_hi'], 1)}]"),
        ("writeup", f"real {num(pl['real'], 1)}bps against a shuffled 95th "
                    f"percentile of {pl['placebo_abs_p95']:.1f}bps"),
        ("writeup", f"R² of {num(vol['1h']['sealed_2022']['r2_model'], 3)} against "
                    f"{num(vol['1h']['sealed_2022']['r2_garch'], 3)} and "
                    f"{num(vol['1h']['sealed_recent']['r2_model'], 3)} against "
                    f"{num(vol['1h']['sealed_recent']['r2_garch'], 3)} at one hour, "
                    f"{num(vol['4h']['sealed_2022']['r2_model'], 3)} against "
                    f"{num(vol['4h']['sealed_2022']['r2_garch'], 3)} and "
                    f"{num(vol['4h']['sealed_recent']['r2_model'], 3)} against "
                    f"{num(vol['4h']['sealed_recent']['r2_garch'], 3)} at four hours"),
        ("writeup", f"loses by {min(dwm):.2f} to {max(dwm):.2f} R² in the sealed "
                    f"blocks"),
        ("writeup", f"by +{i1[0]:.3f} and +{i1[1]:.3f} at one hour and +{i4[0]:.3f} "
                    f"and +{i4[1]:.3f} at four"),
        ("writeup", f"beats Model A in "
                    f"{harp['sealed_cells_lost_on_qlike']['har_intraday']} of the "
                    f"{harp['n_sealed_cells']} sealed cells"),
        ("writeup", f"worth {eco['best_edge_bps_low']:.1f} to "
                    f"{eco['best_edge_bps_high']:.1f}bps per trade"),
        ("writeup", f"round trip of {eco['best_cost_bps']:.1f}bps"),
        ("writeup", f"detectable effect is {eco['best_mde_bps']:.1f}bps"),
        ("writeup", f"+{eco['best_net_bps_low']:.1f}bps of net expectation"),
        ("writeup", f"resolves {ins['best_structure_mde_bps']:.1f}bps against a "
                    f"{ins['band_bps']:.0f}bps band"),
        ("writeup", f"effect of {ins['best_idealised_mde_bps']:.1f}bps"),
        ("writeup", f"needs {ins['sample_multiple_needed']:.0f} times the sample"),
        ("writeup", f"roughly {ins['years_needed']:.0f} years"),
        ("writeup", f"{eco['independent_trades_needed']:.0f} of them, about "
                    f"{eco['years_needed_weekly']:.0f} years of weekly ones"),
    ]

    # Claims that are counts rather than measurements, checked the same way.
    n_struct = ins["n_structures_costed"]
    assert n_struct == 8, n_struct
    checks.append(("summary", "Eight structures were costed"))
    n_pos = eco["n_structures_net_positive"]
    assert n_pos == 1, n_pos
    checks.append(("summary", f"other {n_struct - n_pos} lose more to cost"))

    docs = {"summary": flat((config.REPORTS / "SUMMARY.md").read_text()),
            "readme": flat((config.ROOT / "README.md").read_text()),
            "writeup": flat((config.ROOT / "WRITEUP.md").read_text())}

    # Word forms the documents use for small integers, so "other seven" matches a
    # count of seven rather than the digit.
    words = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven",
             8: "eight", 9: "nine", 10: "ten"}
    fails = []
    for doc, phrase in checks:
        text = docs[doc]
        alt = phrase
        for n, w in words.items():
            alt = re.sub(rf"\b{n}\b", w, alt)
        if phrase not in text and alt not in text:
            fails.append(f"  {doc}: {phrase!r}")

    # The one figure in SUMMARY.md that this repository cannot reproduce: the variant
    # count and the six-basis-point edge come from the private project the public one
    # was cut down from. Named here so nobody mistakes the omission for an oversight.
    # Figures the prose quotes that this repository cannot reproduce, because they
    # belong to components the public cut does not contain: the variant count and the
    # six-basis-point edge (variant mining and the direction model), and the four
    # audit catches in WRITEUP.md. Named here so the omission is deliberate.
    unverifiable = ["82,152", "six basis points", "ten-basis-point", "0.108",
                    "700,000", "648 rows", "0.52"]
    noted = [u for u in unverifiable
             if flat(u) in docs["summary"] or flat(u) in docs["writeup"]]

    if fails:
        print(f"FAIL: {len(fails)} document figures do not match reports/results/")
        print("\n".join(fails))
        sys.exit(1)
    print(f"documents: {len(checks)} quoted figures match reports/results/, "
          f"0 failures")
    print(f"  ({len(noted)} historical figures from the private project are quoted "
          f"and not checkable here)")


if __name__ == "__main__":
    main()
