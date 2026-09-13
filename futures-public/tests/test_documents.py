"""Selected literal phrases in README.md and WRITEUP.md, checked against the tracked reports.

Each check rebuilds a phrase from `reports/` (stage reports, RESULTS.md, candidate
reports, the pre-registration design file, the look counter) and asserts it appears in
the document. Whitespace is collapsed before matching. This validates the presence of
the phrase, not its interpretation. Where a figure has no tracked source it is listed
under `untracked` and is not checked.

Run from the repository root: `python -m tests.test_documents`.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config

MINUS = "−"
REP = config.REPORTS


def num(x, dp):
    return f"{x:.{dp}f}".replace("-", MINUS)


def signed(x, dp):
    return f"{x:+.{dp}f}".replace("-", MINUS)


def flat(text):
    return re.sub(r"\s+", " ", text.replace("**", "").replace("`", ""))


def grab(text, pattern, group=1, cast=float):
    m = re.search(pattern, text, flags=re.M)
    if not m:
        raise SystemExit(f"pattern not found in report: {pattern!r}")
    return cast(m.group(group))


def main():
    s1 = (REP / "stage_reports" / "s1.md").read_text()
    s2 = (REP / "stage_reports" / "s2.md").read_text()
    s3 = (REP / "stage_reports" / "s3.md").read_text()
    s5 = (REP / "stage_reports" / "s5.md").read_text()
    s6 = (REP / "stage_reports" / "s6.md").read_text()
    s7 = (REP / "stage_reports" / "s7.md").read_text()
    s8 = (REP / "stage_reports" / "s8.md").read_text()
    s9 = (REP / "stage_reports" / "s9.md").read_text()
    s4 = (REP / "stage_reports" / "s4.md").read_text()
    s0 = (REP / "stage_reports" / "s0.md").read_text()
    res = (REP / "RESULTS.md").read_text()
    cand = {k: (REP / "candidates" / f"{k}.md").read_text()
            for k in ("C14", "C19", "C2", "C9", "C1", "C11", "C15", "C18", "C18_AUDIT", "SPLICE_CHECK")}
    design = json.load(open(REP / "candidates" / "prereg_design.json"))
    looks = json.load(open(REP / "holdout_looks.json"))

    checks = []

    def add(doc, phrase):
        if doc == "both":
            checks.extend([("readme", phrase), ("writeup", phrase)])
        else:
            checks.append((doc, phrase))

    # ---- cost model (s1, RESULTS §1)
    sharpe_assumed = grab(s1, r"band midpoint \(Sharpe ([0-9.]+)\)")
    ratio = grab(s1, r"edge / cost = ([0-9.]+)")
    rt_bp = grab(res, r"universe median ([0-9.]+) bp")
    rt_pct = grab(res, r"bp of notional, ([0-9.]+)% of a daily move")
    add("writeup", f"assumed gross Sharpe of {sharpe_assumed:.1f}")
    add("writeup", f"projected edge/cost ratio is {ratio:.1f}")
    add("writeup", f"median modelled round trip is {rt_bp:.1f} bp, {rt_pct:.1f} % of the median daily dollar move")

    # ---- stitching (SPLICE_CHECK table, s0 offset table)
    rows = re.findall(r"^\| (CL|NG|HO|RB) +\| +\d+ +\| +([0-9.]+) +\| +([0-9.]+) +\| +([0-9.]+) ", cand["SPLICE_CHECK"], flags=re.M)
    assert len(rows) == 4, rows
    eq = [float(r[2]) * 100 for r in rows]
    held = [float(r[3]) * 100 for r in rows]
    add("writeup", f"{min(eq):.1f}–{max(eq):.1f} % of eligible dates")
    add("writeup", f"{min(held):.0f}–{max(held):.0f} % of eligible expiry dates")
    gap = {}
    for m in ("NG", "RB"):
        mm = re.search(r"^\| " + m + r" +\|(.*)$", s0.split("gap_pct_yr")[1], flags=re.M)
        if mm:
            cells = [c.strip() for c in mm.group(1).strip().strip("|").split("|")]
            gap[m] = float(cells[-1])
    if len(gap) == 2:
        add("writeup", f"sum to {gap['NG']:.0f} % a year in natural gas and {num(gap['RB'], 0)} % in gasoline")

    # ---- sector shares (s4 report)
    def share(sec):
        return grab(s4, r"^\| " + sec + r" +\| +[0-9.]+ +\| +[0-9.]+ +\| +([0-9.]+)") * 100
    add("writeup", f"reach {share('ags'):.1f} % (ags), {share('energy'):.1f} % (energy) and {share('fx'):.1f} % (FX)")

    # ---- signals (s2, s3, s5)
    pat_net = r"Sharpe after costs \*\*([0-9.-]+)\*\*"
    trend_net, trend_gross = grab(s2, pat_net), grab(s2, r"\(gross ([0-9.-]+)\)")
    trend_tilt, trend_timing = grab(s2, r"plain block shuffle, gross Sharpe ([0-9.-]+)"), grab(s2, r"timing \+([0-9.]+)")
    trend_bp, trend_cost = grab(s2, r"([0-9.]+) bp gross per side traded"), grab(s2, r"against ([0-9.]+) bp modelled cost")
    add("readme", f"net Sharpe {trend_net:.2f}")
    add("writeup", f"| Trend | {trend_net:.2f} |")
    add("writeup", f"gross Sharpe {trend_gross:.2f}")
    add("writeup", f"block-shuffled path {trend_tilt:.2f}")
    add("writeup", f"difference {trend_timing:.2f}")
    add("writeup", f"{trend_bp:.1f} bp gross per side traded against {trend_cost:.2f} bp modelled cost")
    carry_net, carry_mde = grab(s3, pat_net), grab(s3, r"Sharpe-equivalent ([0-9.]+)")
    add("writeup", f"| Carry | {carry_net:.2f} | 13 covered markets;")
    add("readme", f"MDE in Sharpe units {carry_mde:.2f}")
    trend_mde, value_mde, comb_mde = grab(s2, r"Sharpe-equivalent ([0-9.]+)"), grab(s5, r"Sharpe-equivalent ([0-9.]+)"), grab(s6, r"Sharpe-equivalent ([0-9.]+)")
    add("writeup", f"mean-return MDE in Sharpe units {trend_mde:.2f} / {carry_mde:.2f} / {value_mde:.2f} / {comb_mde:.2f}")
    add("writeup", f"MDE in Sharpe units is {carry_mde:.2f}")
    value_net, value_bp = grab(s5, pat_net), grab(s5, r"\*\*(-?[0-9.]+) bp gross per side traded")
    add("writeup", f"| Value | {num(value_net, 2)} |")
    add("writeup", f"value reports {num(value_bp, 1)} bp gross per side")
    corr_tv = grab(s6, r"^\| value +\| +(-?[0-9.]+)")
    add("writeup", f"correlation with trend is {num(corr_tv, 2)}")

    # ---- combined (s6)
    comb_net, comb_vol = grab(s6, pat_net), grab(s6, r"realised vol ([0-9.]+)%")
    comb_dd, comb_breadth = grab(s6, r"max drawdown (-?[0-9.]+)%"), grab(s6, r"effective breadth median ([0-9.]+)")
    contrib_t, contrib_v = grab(s6, r"\* trend: ([+-][0-9.]+)"), grab(s6, r"\* value: ([+-][0-9.]+)")
    lam = grab(s6, r"λ median ([0-9.]+)")
    add("writeup", f"Net Sharpe {comb_net:.2f}, realised vol {comb_vol:.1f} %; max drawdown {num(round(comb_dd), 0)} %")
    add("writeup", f"diversification ratio squared {comb_breadth:.1f}")
    add("writeup", f"trend {signed(contrib_t, 2)}, value {signed(contrib_v, 2)}")
    add("writeup", f"scale factor λ is {lam:.2f}")
    p95 = grab(res, r"placebo cleared \(p95 ([0-9.]+)\)")
    stats6 = config.STAGES / "s6_stats.json"
    comb_net3 = json.load(open(stats6))["sharpe_net"] if stats6.exists() else None
    if comb_net3 is not None:
        add("writeup", f"net Sharpe ({comb_net3:.3f}) exceeded its implemented 40-draw placebo threshold ({p95:.2f})")
    else:
        add("writeup", f"exceeded its implemented 40-draw placebo threshold ({p95:.2f})")

    # ---- hold-out (s9, looks)
    ho = grab(s9, r"Sharpe after costs \*\*(-?[0-9.]+)\*\*")
    ho_ret = grab(s9, r"annual return (-?[0-9.]+)%")
    ho_t, ho_c, ho_v = grab(s9, r"trend (-?[0-9.]+),"), grab(s9, r"carry ([0-9.]+),"), grab(s9, r"value (-?[0-9.]+)")
    se2 = grab(s9, r"SE ≈ ([0-9.]+)")
    add("both", num(ho, 2))
    add("writeup", f"annual return {num(round(ho_ret), 0)} %; trend {num(ho_t, 2)}, carry {signed(ho_c, 2)}, value {num(ho_v, 2)}")
    add("writeup", f"The figure {se2:.2f} quoted with it is the s9 consistency check")
    assert looks["holdout"]["looks"] == 1

    # ---- candidates
    pat_t = r"t = (-?[0-9.]+)"
    pat_sig = r"\*\*([+-][0-9.]+)σ\*\*"
    add("writeup", f"C9 (t {grab(cand['C9'], pat_t):.2f}) and C1 (t {grab(cand['C1'], pat_t):.2f})")
    add("writeup", f"C11: {signed(grab(cand['C11'], pat_sig), 2)}σ, t = {grab(cand['C11'], pat_t):.2f}")
    add("writeup", f"C15: {signed(grab(cand['C15'], pat_sig), 2)}σ, t = {grab(cand['C15'], pat_t):.2f}")
    d19, t19 = grab(cand["C19"], r"Δbreach_daily = (-?[0-9.]+) pp"), grab(cand["C19"], pat_t)
    add("writeup", f"Δbreach_daily {num(d19, 1)} points, t = {num(t19, 2)}")
    add("writeup", f"{signed(grab(cand['C2'], pat_sig), 2)}σ, t = {grab(cand['C2'], pat_t):.2f}")
    t14, sh14 = grab(cand["C14"], pat_t), grab(cand["C14"], r"shuffle t = (-?[0-9.]+)")
    add("writeup", f"return t = {t14:.2f} and {num(sh14, 2)}")
    c18 = cand["C18"]
    alpha, se18, t18 = grab(c18, r"alpha on BTC \*\*([+-][0-9.]+) %/week"), grab(c18, r"SE ([0-9.]+)"), grab(c18, pat_t)
    n18, p18, cost18 = grab(c18, r"N = ([0-9]+) weeks", cast=int), grab(c18, r"95th pct ([+-][0-9.]+)"), grab(c18, r"cost ≈ ([0-9.]+) %/week")
    add("both", f"gross alpha {signed(alpha, 3)} %/wk, month-block SE {se18:.2f}, t {t18:.2f}")
    add("writeup", f"over {n18} weeks")
    add("writeup", f"95th percentile of their alphas {signed(p18, 2)}")
    add("writeup", f"charged cost, {cost18:.3f} %/wk")
    au = cand["C18_AUDIT"]
    def row(label):
        m = re.search(r"^\| " + re.escape(label) + r" \| ([+-][0-9.]+) \| ([0-9.]+) \| ([+-][0-9.]+) \|", au, flags=re.M)
        if not m:
            raise SystemExit(f"audit row not found: {label}")
        return float(m.group(1)), float(m.group(2)), float(m.group(3))
    early, late, plate, flate = row("total 2020-02 to 2021-12"), row("total 2022-01 to 2026-08"), row("price leg 2022+"), row("funding leg 2022+")
    add("writeup", f"{signed(early[0], 2)} %/wk in 2020–21, {signed(late[0], 2)} %/wk from 2022")
    add("writeup", f"price leg {signed(plate[0], 2)} (t {plate[2]:.1f})")
    add("writeup", f"sub-sample t = {late[2]:.2f}")
    add("writeup", f"is {signed(flate[0], 2)} %/wk (SE {flate[1]:.2f}) after 2021")
    add("writeup", f"recomputed from 0.099 to {design['C18']['clear']:.3f} %/wk")
    add("writeup", f"≈ {(3.86 / 2.3) ** 2:.1f} × the sample")

    # ---- mandates (s8, s7)
    n_att = grab(res, r"([0-9]+) of 500 mandates", cast=int) if re.search(r"[0-9]+ of 500 mandates", res) else grab(s8, r"([0-9]+) of 500 mandates attainable", cast=int)
    add("writeup", f"{n_att} reach a pass probability")
    b_daily, b_dd, b_to = grab(s8, r"breach_daily ([0-9]+)%", cast=int), grab(s8, r"breach_dd ([0-9]+)%", cast=int), grab(s8, r"timeout ([0-9]+)%", cast=int)
    add("writeup", f"daily-loss breach {b_daily} %, drawdown breach {b_dd} %, timeout {b_to} %")
    v_pass, v_cal = grab(s8, r"pass-maximising vol ([0-9]+)%", cast=int), grab(s8, r"vs Calmar-maximising ([0-9]+)%", cast=int)
    add("writeup", f"pass-maximising target for the example mandate is {v_pass} % and the Calmar-maximising target is {v_cal} %")
    add("writeup", f"{grab(s7, r'pass probability ' + chr(92) + '*' + chr(92) + '*([0-9.]+)%'):.1f} % pass rate")

    docs = {"readme": flat((config.ROOT / "README.md").read_text()),
            "writeup": flat((config.ROOT / "WRITEUP.md").read_text())}
    fails = [f"  {doc}: {phrase!r}" for doc, phrase in checks if phrase not in docs[doc]]

    untracked = ["1.9 × one leg's notional", "22 names per leg", "0.19 %/wk", "0.47 %/wk",
                 "−1.18", "0.099", "final 250 observations"]
    if fails:
        print(f"FAIL: {len(fails)} document phrases do not match reports/")
        print("\n".join(fails))
        sys.exit(1)
    print(f"documents: {len(checks)} quoted phrases match reports/, 0 failures")
    print(f"  ({len(untracked)} figures quoted from the private record or from diagnostics on untracked data are not checkable here)")


if __name__ == "__main__":
    main()
