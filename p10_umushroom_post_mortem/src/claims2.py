"""T13 (Plan 2), T30, T31 over deliver/*.txt (Description drafts; not included in the repo copy, see README).
T13: every numeric token must equal (after the stated rounding) a value computed from results.json / results2.json,
or be a fixed fact (dates, rule constants). The map is built in code so each number has a named source."""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DELIVER = ROOT / "deliver"
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
BANNED = ["noise", "will recover", "temporary", "overreact", "oversold", "bounce", "market was wrong",
          "inside the band", "not breached", "ordinary"]


def load():
    R1 = json.loads((ROOT / "out" / "results.json").read_text())
    R2 = json.loads((ROOT / "out" / "results2.json").read_text())
    return R1, R2


def rnd(x, nd=0):
    from decimal import Decimal, ROUND_HALF_UP
    q = Decimal(1) if nd == 0 else Decimal(1).scaleb(-nd)
    v = Decimal(str(float(x))).quantize(q, rounding=ROUND_HALF_UP)
    return str(v)


def gbp(x, nearest=1):
    return f"{int(rnd(float(x) / nearest)) * nearest:,}"


def claims_map():
    R1, R2 = load()
    m = {}
    def add(tok, src):
        m.setdefault(tok, []).append(src)
    p, a, cf, nv = R2["platform"], R2["attr"], R2["counterfactual"]["books"], R2["nvda_20nov"]
    add(gbp(p["nav"]), "platform NAV")
    add(rnd(p["return_pct"], 1), "platform return % (1dp)")
    add("3.9", "P9 2-week sd 3.91"); add("6,432", "P9 VaR95"); add("9,094", "P9 VaR99")
    add(rnd(abs(R2["z"]["platform_vs_3.91"]), 1), "z platform vs 3.91")
    assert rnd(abs(R2["z"]["yahoo_vs_3.91"]), 1) == rnd(abs(R2["z"]["platform_vs_3.91"]), 1)
    assert R2["var_platform"]["var95_breached"] and not R2["var_platform"]["var99_breached"]
    assert R2["var_yahoo"]["var95_breached"] and not R2["var_yahoo"]["var99_breached"]
    add(gbp(cf['halfway']['vs_actual_gbp'], 10), "counterfactual halfway vs actual (nearest 10)")
    add(gbp(cf['equal_risk']['vs_actual_gbp'], 10), "counterfactual ERC vs actual (nearest 10)")
    assert cf["halfway"]["breaches_own_var95"] and cf["equal_risk"]["breaches_own_var95"]
    add(str(R2["calls"]["hits"]), "call hits"); add(str(R2["calls"]["n"] - R2["calls"]["hits"]), "call misses")
    for k in ("market_sector_pct", "crypto_pct", "syre_pct", "report_day_pct", "other_specific_pct"):
        add(rnd(a[k]), f"attr {k}")
    add(rnd(-a["fx_pct"]), "attr fx (offset)"); add(rnd(-a["execution_pct"]), "attr execution (offset)")
    add(str(a["n_variants"]), "sensitivity variants")
    lo, hi = sorted(a["systematic_range_pct"])
    add(f"{rnd(lo)}-{rnd(hi)}", "systematic range")
    add(gbp(-a["nvda_total_gbp"]), "NVDA total P&L")
    add(rnd(-nv["raw_pct"]), "NVDA 20 Nov move")
    add(rnd(-nv["spy_smh"]["predicted_pct"], 1), "NVDA 20 Nov predicted (SPY+SMH)")
    plo, phi = nv["peer_range_pct"]
    add(f"{rnd(-phi)}-{rnd(-plo)}", "peer 20 Nov range")
    add(str(R2["placebo_10d"]["k_at_or_below"]), "placebo k"); add(str(R2["placebo_10d"]["n_windows"]), "placebo N")
    assert set(R2["breach"]["_beyond_minus2"]) == {"NVDA", "BTC-USD", "ETH-USD"}
    d3 = R1["D3"]["beat_and_fell"]["car1_60"]
    add(R1["D3"]["first"][:4], "D3 first year"); add(rnd(R1["D3"]["P_AR0_neg_given_beat_pct"]), "D3 P(AR0<0|beat)")
    add(rnd(d3["mean_pct"], 1), "D3 CAR60 mean"); add(rnd(d3["boot95_pct"][0], 1), "D3 CI lo"); add(rnd(d3["boot95_pct"][1], 1), "D3 CI hi")
    add(str(d3["n"]), "D3 n")
    assert d3["boot95_pct"][0] < 0 < d3["boot95_pct"][1]
    hd = R2["scorecard"]["assets"]["HD"]["rules"]["R2"]["finding"]
    add(rnd(re.search(r"cumulative -(\d+\.\d+)%", hd).group(1), 1), "HD R2 cumulative fall")
    add(rnd(p["cash_pct_nav"]), "cash % of platform NAV")
    sc = R2["scorecard"]["assets"]
    assert sc["NVDA"]["status"] == "REVIEW-TRIM" and sc["HD"]["status"] == "REVIEW"
    assert all(sc[x]["status"] == "HOLD" for x in ("WMT", "AMAT", "BA.L", "RR.L"))
    if "K" in R2:
        K, E = R2["K"], R2["E"]
        for a, r in K["decision_table"].items():
            add(rnd(r["current_pct"], 1), f"K {a} current"); add(rnd(r["w_star_pct"], 1), f"K {a} w*")
            add(rnd(r["target_pct"], 1), f"K {a} target")
        add(gbp(K["nvda_trim_gbp_approx"], 10), "NVDA trim GBP (nearest 10)")
        add(rnd(K["cash_after_pct"]), "cash after trim")
        add(rnd(K["book_after"]["ann_vol_pct"], 1), "1y vol after"); add(rnd(E["headline_held_vol_pct"], 1), "1y vol held (headline)")
        add(rnd(K["book_after"]["ai_crypto_risk_share_pct"]), "AI+crypto risk after"); add(rnd(K["book_before_ai_crypto_risk_pct"]), "AI+crypto risk before")
        add(gbp(-K["nvda_13nov_add"]["pnl_gbp"]), "13 Nov NVDA add loss")
        add(rnd(-K["cash_rule_audit"]["cpi_10nov"]["qqq_10nov_pct"], 2), "QQQ 10 Nov")
        add("156", "E primary window weeks"); add("5", "5% add budget"); add("2.5", "SYRE 2.5% cap")
        add(rnd(E["headline_held_vol_pct"]), "1y vol held (headline, whole %)")
        usd = sum(v for k, v in E["held_weights_pct_yahoo_20nov"].items() if k in USD_NAMES)
        add(rnd(round(usd, 6)), "USD share of NAV (NVDA, WMT, AMAT, HD, BTC, SYRE)")
        add("25", "rebalance band 25% of w* (K decision_table rule)")
        assert all("25% band" in r["action"] for r in K["decision_table"].values() if "band" in r["action"])
    add(rnd(-R2["placebo_10d"]["worst_pct"], 1), "placebo 10d worst window")
    if "H" in R2:
        hb = R2["H"]["book_actual_8.5"]
        h_gate(R2)
        add(hb["first"][:4], "H first year"); add(f'{hb["n_windows"]:,}', "H windows")
        add(str(hb["k_windows_at_or_below"]), "H windows at or below -8.53%"); add(str(hb["n_episodes"]), "H episodes")
        smh = R2["H"]["single"]["SMH"]["forward"]["126"]
        add(rnd(smh["obs_share_pos_pct"]), "H SMH 126 share positive"); add(rnd(smh["unconditional_share_pos_pct"]), "H SMH 126 any date")
    if "G" in R2 and R2["G"]["G2"]["claim_bar_met"]:
        # G2 figures are allowed in a text only when the claim bar is met (g_gate); otherwise no G2 token is available
        g = R2["G"]["G2"]
        g_gate(R2)
        add(rnd(round(g["pooled"]["1"]["s_E"] * 100, 6)), "G2 pooled s_E 1 quarter")
        add(rnd(round(g["pooled"]["20"]["s_E"] * 100, 6)), "G2 pooled s_E 20 quarters")
    if "H" in R2 and "K" in R2:
        v4_gate(R1, R2)
        syre = [x["date"] for x in R1["A"]["implied_fx"] if x["asset"] == "SYRE" and x["side"] == "buy"][0]
        add(str(int(syre[8:10])), "SYRE buy date (19 Nov)")
        for tok, src in v5_gate(R1, R2).items():
            add(tok, src)
    return m


USD_NAMES = ("NVDA", "WMT", "AMAT", "HD", "BTC", "SYRE")
H_VERDICT = "not distinguishable from any other date"


def h_gate(R2):
    """PLAN3 gate: the H sentence may stand only if the 252-session verdict is 'not distinguishable' for both books."""
    for b in ("book_actual_8.5", "book_primary"):
        assert R2["H"][b]["forward"]["252"]["verdict"] == H_VERDICT, b
    assert R2["H"]["single"]["SMH"]["forward"]["126"]["obs_share_pos_pct"] < R2["H"]["single"]["SMH"]["forward"]["126"]["unconditional_share_pos_pct"]


def g_gate(R2):
    """Gate for a text that claims the earnings share rises with the horizon (G2). Call it only when a text makes that
    claim; with no claim there is no requirement. The claim needs claim_bar_met: the pooled 20q-1q difference has its 99%
    lower bound above zero (the 95% interval is too narrow, see horizon.g2 and test T18) and at least three of the four
    companies rise. Both conditions are re-checked here from the published fields."""
    g = R2["G"]["G2"]
    assert g["claim_bar_met"] is True, "G2 rise claimed but the claim bar is not met"
    assert g["pooled_diff_20_1"]["ci99"][0] > 0 and sum(g["rises_per_ticker"].values()) >= 3
    assert sorted(g["exceptions"]) == sorted(t for t, r in g["rises_per_ticker"].items() if not r)


def v4_gate(R1, R2):
    """Audit must-fixes for v4: fills offset and close-price loss beyond VaR99; NVDA above 15% cap at 13 Nov close;
    SYRE bought 19 Nov (day before the 20 Nov cut-off); ETH sold 13 Nov at a loss; AMAT/BTC/SYRE vs w*; Nasdaq and
    chips worse than usual after such falls; three assets beyond -2 sd together."""
    ex = R1["B"]["buckets"]["execution_fill_to_close"]
    assert gbp(ex) == "1,399" and R1["A"]["accounting"]["eth_realised"] < 0
    assert R2["var_yahoo"]["loss_gbp"] + ex > 9094 and R2["var_platform"]["loss_gbp"] + ex > 9094
    assert R2["H"]["book_weights_13nov"]["NVDA"] > 0.15
    fx = R1["A"]["implied_fx"]
    assert [x["date"] for x in fx if x["asset"] == "SYRE" and x["side"] == "buy"] == ["2026-11-19"]
    assert any(x["date"] == "2026-11-13" and x["asset"] == "ETH-USD" and x["side"] == "sell" for x in fx)
    assert any(x["date"] == "2026-11-13" and x["asset"] == "NVDA" and x["side"] == "buy" for x in fx)
    dt = R2["K"]["decision_table"]
    assert rnd(dt["AMAT"]["w_star_pct"], 1) == "6.0" and rnd(dt["AMAT"]["current_pct"], 1) == "10.2"
    w = R2["E"]["w_star_pct"]; h = R2["E"]["held_weights_pct_yahoo_20nov"]
    assert h["BTC"] < w["BTC"] and h["SYRE"] < w["SYRE"]
    for s in ("QQQ", "SMH"):
        f = R2["H"]["single"][s]["forward"]["126"]
        assert f["verdict"] == "different from a random date" and f["obs_share_pos_pct"] < f["unconditional_share_pos_pct"]
    assert all(R2["breach"][a]["z"] < -2 for a in ("NVDA", "BTC-USD", "ETH-USD"))


SLEEVES = {"AI semiconductors": ("NVDA", "AMAT"), "US consumer": ("WMT", "HD"), "UK defence": ("BAE", "RR"),
           "Bitcoin": ("BTC",), "Spyre": ("SYRE",)}
V5_SHARPE = 0.3


def sleeve_pct(weights):
    """Whole-% sleeve totals from per-asset weights (E.w_star_pct or E.held_weights_pct_yahoo_20nov)."""
    return {s: rnd(round(sum(weights[a] for a in names), 6)) for s, names in SLEEVES.items()}


def v5_sleeve_line(R2):
    """The 'Target (held)' sentence of v5, built from E so the text cannot drift from results."""
    E = R2["E"]
    w, h = sleeve_pct(E["w_star_pct"]), sleeve_pct(E["held_weights_pct_yahoo_20nov"])
    return "Risk-budget weight (held): " + "; ".join(f"{s} {w[s]}% ({h[s]}%)" for s in SLEEVES) + f"; cash {rnd(E['cash_pct'])}%."


def _input(name):
    return (ROOT / "data" / "input" / name).read_text()


def _csv(name):
    import csv
    import io
    return list(csv.DictReader(io.StringIO(_input(name))))


def v5_gate(R1, R2):
    """v5 additions. Every new number is asserted against results.json / results2.json or a sourced input file
    (d1_sources.csv, thesis_evidence.csv, macro_events.csv, thesis_rules.json). Returns {token: source}."""
    E, K, out = R2["E"], R2["K"], {}
    # Strategy: objective (ASSUMPTION), loss tolerance
    grid = E["assumptions"]["sharpe_grid"]
    assert grid[len(grid) // 2] == V5_SHARPE and E["assumptions"]["risk_free"] == 0.0 and E["assumptions"]["leverage"] == "none"
    out[rnd(V5_SHARPE, 1)] = "E sharpe_grid mid-point (ASSUMPTION, not a forecast)"
    assert rnd(V5_SHARPE * E["headline_held_vol_pct"]) == "5"
    out["5"] = "objective = Sharpe 0.3 x one-year vol 16.2% = 4.9% over cash (whole %)"
    run = E["runs"]["2026-11-20|156w"]
    assert run["held"]["ann_vol_pct"] == E["headline_held_vol_pct"] and rnd(E["headline_held_vol_pct"]) == "16"
    assert gbp(run["held"]["var95_1y_normal_gbp"], 100) == "24,400" and E["assumptions"]["var_z"] == 1.645
    out["24,400"] = "E one-year 95% VaR, held book, normal (nearest 100)"
    # Macro: one sourced fact per theme
    d1 = {r["event_id"]: r for r in _csv("d1_sources.csv")}
    g = re.search(r"raised: Q4 (\d+\.\d)bn vs (\d+\.\d)bn LSEG", d1["E5"]["guidance"])
    assert d1["E5"]["asset"] == "NVDA" and g.groups() == ("130.0", "125.1") and "no China DC revenue assumed" in d1["E5"]["guidance"]
    out["130.0"] = "d1_sources E5: NVDA Q4 revenue guide (bn)"; out["125.1"] = "d1_sources E5: LSEG consensus (bn)"
    assert d1["E3"]["asset"] == "AMAT" and "guide above consensus" in d1["E3"]["guidance"]
    te = {(r["asset"], r["rule"]): r for r in _csv("thesis_evidence.csv")}
    b = re.search(r"FCF raised >(\d\.\d)bn -> c\.(\d\.\d)bn", te[("BA.L", "R1")]["finding"])
    assert b.groups() == ("2.0", "3.0") and te[("BA.L", "R1")]["source_class"] == "primary"
    out["2.0"] = "thesis_evidence BA.L R1: prior FCF guide (bn)"; out["3.0"] = "thesis_evidence BA.L R1: new FCF guide (bn)"
    assert "guidance reaffirmed" in te[("RR.L", "R1")]["finding"] and "guide raised" in te[("WMT", "R1")]["finding"]
    rule = [l for l in _input("macro_events.csv").splitlines() if "BIS rule on Chinese remote access to AI chips" in l]
    assert len(rule) == 1 and rule[0].startswith("2026-11-16,")
    out["16"] = "macro_events.csv: BIS rule on Chinese remote access to AI chips (16 Nov)"
    cpi = K["cash_rule_audit"]["cpi_10nov"]
    assert (cpi["actual_mom"], cpi["consensus_mom"]) == (0.4, 0.3)
    out["0.4"] = "K cpi_10nov actual m/m (secondary source)"; out["0.3"] = "K cpi_10nov consensus m/m; also Sharpe mid-point"
    fx = R1["A"]["implied_fx"]
    assert fx[0]["date"] == "2026-11-07" and rnd(fx[0]["yahoo_gbpusd_close"], 3) == "1.346"
    assert R1["A"]["platform"]["fx_date"] == "2026-11-20" and rnd(R1["A"]["platform"]["fx"], 3) == "1.309"
    out["1.346"] = "A implied_fx: Yahoo GBPUSD close, 7 Nov"; out["1.309"] = "A platform fx: GBPUSD, 20 Nov"
    assert R1["B"]["buckets"]["fx"] > 0
    # SAA: sleeve targets vs held, AI + crypto at target, cash rule
    assert E["w_star_pct"] == run["sleeve_rp_capped"]["weights_pct"] and run["weeks"] == 156
    assert set(run["sleeve_rp_capped"]["sleeve_risk_share_pct"].values()) == {20.0}
    w, h = sleeve_pct(E["w_star_pct"]), sleeve_pct(E["held_weights_pct_yahoo_20nov"])
    assert w == {"AI semiconductors": "12", "US consumer": "29", "UK defence": "20", "Bitcoin": "14", "Spyre": "8"}
    assert h == {"AI semiconductors": "23", "US consumer": "25", "UK defence": "24", "Bitcoin": "9", "Spyre": "2"}
    assert sum(int(x) for x in w.values()) + int(rnd(E["cash_pct"])) == 100
    assert sum(int(x) for x in h.values()) + int(rnd(E["cash_pct"])) == 100
    for s in SLEEVES:
        out[w[s]] = f"E w* sleeve {s} (whole %)"; out[h[s]] = f"E held sleeve {s} (whole %)"
    assert max(E["w_star_pct"].values()) <= 15.0
    assert rnd(run["sleeve_rp_capped"]["ai_crypto_risk_share_pct"]) == "40"
    out["40"] = "E AI + crypto risk share at w* (two of five sleeves)"
    assert rnd(K["book_before_ai_crypto_risk_pct"]) == "56" and rnd(K["book_after"]["ai_crypto_risk_share_pct"]) == "46"
    dt = K["decision_table"]
    assert not any(r["action"].startswith("ADD") for r in dt.values())          # "none qualifies today"
    for a, r in dt.items():                                                     # why: no HOLD name is below w* with a trigger
        if r["status"] == "HOLD":
            assert not (r["trigger_hit_20nov"] and r["current_pct"] < r["w_star_pct"]), a
    import decide
    assert decide.MAX_ADDS == 0.05 and decide.SYRE_MAX == 0.025 and decide.BAND == 0.25
    assert dt["NVDA"]["status"] == "REVIEW-TRIM" and dt["HD"]["action"] == "HOLD; no adds"
    assert all(dt[a]["status"] == "NO THESIS" for a in ("BTC", "SYRE"))
    # Instruments: the four tests, their consequences, today's flags
    rules = json.loads(_input("thesis_rules.json"))
    assert rules["R1"].startswith("guidance") and rules["R2"].startswith("estimates")
    assert rules["R3"].startswith("regulatory or accounting") and "restatement" in rules["R3"] and "non-reliance" in rules["R3"]
    assert rules["R4"].startswith("management") and "CEO or CFO left unplanned" in rules["R4"]
    assert rules["status"] == "Status: any HARD -> CUT. Two or more SOFT -> REVIEW-TRIM. One SOFT -> REVIEW. None -> HOLD."
    assert rules["price"] == "Price is never a trigger."
    sc = R2["scorecard"]
    assert sc["rules_hash_ok"] and sc["locked_utc"].startswith("2026-11-21T")
    assert sc["assets"]["NVDA"]["triggers"] == ["none", "none", "SOFT", "SOFT"]
    assert sc["assets"]["HD"]["triggers"] == ["none", "SOFT", "none", "watch"]
    assert "SEC enforcement staff examining" in sc["assets"]["NVDA"]["rules"]["R3"]["finding"]
    assert "no permanent successor named" in sc["assets"]["NVDA"]["rules"]["R4"]["finding"]
    # Risk: stress beside VaR
    for v in ("var_platform", "var_yahoo"):
        assert rnd(R2[v]["loss_vs_ai_stress_x"], 1) == "2.4" and gbp(-R2[v]["ai_selloff_stress_gbp"]) == "3,613"
    out["2.4"] = "realised loss / P9 AI sell-off stress"; out["3,613"] = "P9 AI sell-off stress (GBP)"
    return out


# Each offset in the submitted text is bound to its subject in the same sentence, and to its own result field.
OFFSETS = (("execution prices", "execution_pct"), ("Sterling's depreciation", "fx_pct"))


def sentences(text):
    return [x.strip() for x in re.split(r"(?<=[.!?])\s+|\n+", text) if x.strip()]


def offset_claims(text, R2):
    """T43b: every sentence naming an offset's subject states that offset's own share ('offset N% of the loss', N from
    attr[field]), and every 'offset N% of the loss' sentence names exactly one subject. Swapping the 16% and 11% fails."""
    ss = sentences(text)
    for subject, field in OFFSETS:
        phrase = f"offset {rnd(-R2['attr'][field])}% of the loss"
        hits = [x for x in ss if subject in x]
        assert hits and all(phrase in x for x in hits), (subject, phrase, hits)
    for x in ss:
        if re.search(r"offset \d+% of the loss", x):
            assert sum(subject in x for subject, _ in OFFSETS) == 1, x


LEDGER_MARK = "Calls logged on 7th November"


def own_text(path):
    """Text written by us. In *_PASTE.txt the 7 Nov call-ledger block (historical record, copied verbatim) is excluded."""
    txt = pathlib.Path(path).read_text()
    if pathlib.Path(path).name.endswith("_PASTE.txt"):
        txt = txt.split(LEDGER_MARK)[0]
    return txt


FIXED = {"7": "7 Nov", "6": "6 Nov", "20": "20 Nov", "9": "9 Nov", "10": "10 Nov", "12": "12 Nov", "13": "13 Nov",
         "14": "14 Nov", "21": "21 Nov", "9-20": "9-20 Nov", "8": "8-K form", "20261120": "file name", "256": "sha256", "27": "27 Nov (S3)", "3": "3 months", "4.02": "8-K Item 4.02", "10-Q": "form", "8-K": "form", "2002": "D3", "95": "95% (VaR, interval)", "99": "99% VaR",
         "15": "15% limit", "60": "60 days", "²": "V²", "2": "two (sd)", "1": "1 hit"}


def numbers(text):
    return [t.rstrip(",.") for t in re.findall(r"[+-]?£?\d[\d,]*(?:\.\d+)?(?:-\d[\d,]*(?:\.\d+)?)?%?", text)]


def check(path, extra=None):
    m = claims_map()
    ok = set(m) | set(FIXED) | set(extra or {})
    bad = []
    for line in own_text(path).splitlines():
        if "sha256" in line:
            line = re.sub(r"\b[0-9a-f]{64}\b", " ", line)
        for tok in numbers(line):
            t = tok.lstrip("+").lstrip("£").rstrip("%")
            if t.startswith("-") and t[1:] in ok:
                continue
            if t not in ok:
                bad.append(tok)
    return bad


def banned(path):
    hits = []
    for i, line in enumerate(own_text(path).splitlines(), 1):
        if line.lstrip().startswith("Q:"):
            continue
        for b in BANNED:
            if re.search(r"\b" + re.escape(b) + r"\b", line.lower()):
                hits.append((i, b))
    return hits


def words(path):
    return len(pathlib.Path(path).read_text().split())


if __name__ == "__main__":
    files = sorted(DELIVER.glob("*.txt")) or [ROOT / "data" / "input" / "description_final_submitted.txt"]
    for f in files:
        print(f.name, "words", words(f), "unmatched", check(f), "banned", banned(f))
