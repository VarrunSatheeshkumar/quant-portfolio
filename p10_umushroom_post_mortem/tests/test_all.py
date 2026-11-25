"""Plan test section T1-T43. Run: .venv/bin/python -m pytest -q tests/ (from this folder)."""
import json
import math
import pathlib
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest
from scipy import stats

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import attribution  # noqa: E402
import data  # noqa: E402
import event_study  # noqa: E402
import ledger  # noqa: E402
import p9_replica as p9  # noqa: E402
import power  # noqa: E402

R = json.loads((ROOT / "out" / "results.json").read_text())
ASOF = R["asof"]

# The Description drafts (deliver/V2_DESCRIPTION_v2..v5*.txt, V2_NEXT_STEPS.txt) are not included in the repo copy;
# only the submitted text is (data/input/description_final_submitted.txt, checked by T41). Tests that read the drafts
# skip when the folder is absent; their results-side gates (claims2.v4_gate, v5_gate, h_gate) still run, and g_gate
# runs wherever a text claims a G2 rise (its logic is tested in T48).
DELIVER = ROOT / "deliver"
needs_drafts = pytest.mark.skipif(not (DELIVER / "V2_DESCRIPTION_v2.txt").exists(),
                                  reason="Description drafts (deliver/) not included in the repo copy")

# Checks that pin figures read from the archived Yahoo snapshot of 21 Nov 2026 20:59 UTC (the Description's numbers,
# trigger patterns, gate outcomes). On a fresh download they are not expected to hold and are skipped, not failed;
# everything else (identities, ledger, leakage, synthetic recovery, date bounds) runs on any snapshot.
ARCHIVED_SNAPSHOT = "20261121T205901Z"
archived_only = pytest.mark.skipif(data._ts() != ARCHIVED_SNAPSHOT,
                                   reason="pins figures from the archived 21 Nov snapshot; this is a fresh download")


def test_T1_ledger():
    """Ledger cash and every unit count the platform shows. Cash differs by 1p (ledger £15,884.58, platform
    £15,884.57); units: the seven quoted on 19 Nov (no trades in those names after that) and Spyre from 20 Nov."""
    a = ledger.accounting()
    s20, _ = ledger.platform_snapshot("2026-11-20")
    s19, _ = ledger.platform_snapshot("2026-11-19")
    assert a["cash"] == 15884.58 and s20["cash_gbp"] == 15884.57 and round(a["cash"] - s20["cash_gbp"], 2) == 0.01
    assert len(s19["quoted_units"]) == 7
    for asset, u in s19["quoted_units"].items():
        assert abs(a["units"][asset] - u) < 1e-6, asset
    assert abs(a["units"]["SYRE"] - s20["syre_fill"]["units"]) < 1e-6 and abs(s19["pending"]["SYRE"]["units"] - 29.8102) < 1e-6
    assert abs(a["units"]["SYRE"] - 29.8102) < 1e-6
    assert abs(a["open_cost"] - 83408.24) < 0.005
    unreal = 91466.50 - 15884.57 - 83408.24
    assert abs(unreal + a["eth_realised"] - (91466.50 - 100000)) <= 0.02
    assert abs(a["units"]["NVDA"] - 123.5688) < 1e-6
    assert abs(a["units"]["WMT"] - 126.8802) < 1e-6
    assert abs(a["units"]["ETH-USD"]) < 1e-9
    assert abs(a["eth_realised"] - (-707.18)) < 0.005


def _nav22(btc_usd=None, fx=None):
    raw = data.load(None, "2026-11-20", kind="raw")
    fx = fx or float(raw["GBPUSD=X"].dropna().iloc[-1])
    acc = ledger.accounting()
    tot, usd = acc["cash"], 0.0
    for a, u in acc["units"].items():
        if abs(u) < 1e-9:
            continue
        p = float(raw[a].dropna().iloc[-1])
        if a == "BTC-USD" and btc_usd:
            p = btc_usd
        g = u * p / fx if a in data.USD else u * p
        tot += g
        usd += g if a in data.USD else 0
    return tot, usd, fx


def test_T2_nav_platform_22nov():
    """Yahoo 20 Nov closes + platform BTC mark USD 60,320.75 (read 21 Nov) vs platform NAV 91,466.50, 0.25%."""
    tot, _, _ = _nav22(btc_usd=60320.75)
    print("NAV 20 Nov closes, BTC 60,320.75:", tot)
    assert abs(tot - 91466.50) <= 0.0025 * 91466.50


def test_T2b_implied_fx():
    """GBPUSD that closes the gap at 20 Nov closes must be within 0.5% of Yahoo's 20 Nov close."""
    tot, usd, fx = _nav22()
    implied = fx * usd / (usd + (91466.50 - tot))
    print("implied platform GBPUSD", implied, "Yahoo", fx)
    assert abs(implied / fx - 1) <= 0.005


def test_T3_buckets_sum():
    """Buckets sum to the P&L, and each asset-day's components sum to its holding P&L, in every one of the 36
    attribution variants and the CEO-day sensitivity (not only the base case)."""
    led = ledger.daily(ASOF)
    variants = [dict(beta_window=bw, event_window=ew, sector_mode=sm, alpha_in=ai)
                for bw in ("p9", 252, 504) for ew in ("0", "0,+1", "-1,+1") for sm in ("etf", "peers") for ai in (False, True)]
    variants.append(dict(unsched_file="events_unscheduled_sensitivity.csv"))
    assert len(variants) == 37
    for kw in variants:
        res = attribution.attribute(ASOF, led=led, **kw)
        assert abs(res["sum_gap"]) <= 0.05, kw
        d = res["daily"].set_index(["date", "asset"])
        comp = d[["fx", "cross", "market", "sector", "alpha", "event_sched", "event_unsched", "residual"]].sum(axis=1)
        for (t, a), v in comp.items():
            assert abs(v - led["hold_pnl"].loc[t, a]) <= 0.05, (kw, t, a, v, led["hold_pnl"].loc[t, a])
    # the saved sensitivity table agrees
    assert all(abs(v["gap"]) <= 0.05 for v in R["B"]["sensitivity"].values())


def test_T4_leakage():
    with pytest.raises(AssertionError):
        data.load_pre(None, "2026-11-07")
    def snap():
        b = {a: attribution.estimate_betas(a, pd.Timestamp("2026-05-01")) for a in attribution.EQUITIES}
        m = p9.model()
        port = power.portfolio_daily_gbp(power_weights)
        return b, m["two_week_sd_pct"], m["cov_daily"], port.values
    power_weights = {"NVDA": .15, "AMAT": .1, "WMT": .1, "HD": .1, "BAE": .1, "RR": .1, "BTC": .1, "ETH": .05}
    b0, s0, c0, p0 = snap()
    data._NOISE.update(on=True, seed=7)
    try:
        b1, s1, c1, p1 = snap()
        assert not np.array_equal(data.load(kind="adj").loc["2026-11-09":, "NVDA"].values, data.load(kind="adj").loc["2026-11-09":, "NVDA"].values * 0 + 1)
    finally:
        data._NOISE.update(on=False)
    assert s0 == s1 and np.array_equal(c0, c1) and np.array_equal(p0, p1)
    for a in b0:
        assert b0[a]["b_m"] == b1[a]["b_m"] and b0[a]["b_s"] == b1[a]["b_s"]


def test_T5_d3_no_leak():
    """Estimation ends >= 11 sessions before each reaction day, and every outcome window (to day +60) ends on or
    before the 6 Nov cutoff, so no part of the competition window enters the historical reference."""
    df = pd.read_csv(ROOT / "out" / "d3_events.csv", parse_dates=["day0", "last_outcome_day"])
    assert (df.est_gap_sessions >= 11).all()
    assert (df.last_outcome_day <= data.CUTOFF).all() and (df.day0 < df.last_outcome_day).all()
    assert pd.Timestamp(R["D3"]["last_outcome_day"]) <= data.CUTOFF
    rm = R["D3"]["removed"]
    assert (rm["listed_events"] - rm["unknown_sign"] - rm["forward_window_after_cutoff"] - rm["short_estimation_history"]
            - rm["duplicate_rows_same_sign"] - rm["conflicting_duplicates_rows"]) == R["D3"]["n_events"] == len(df)


def test_T5b_d3_classification():
    """Beat / miss / tie follows the sign of the reported Surprise(%), falling back to the rounded EPS comparison only
    where the surprise is missing; rows with a surprise but no rounded EPS are kept; one row per report; reports whose
    duplicate rows disagree in sign are left out and counted. On the archived snapshot: NVIDIA's Aug 2015 report (EPS
    0.19 against 0.19, surprise +66.67%) is a beat, and the two conflicting reports (Walmart 13 Aug 2002, NVIDIA 9 Nov
    2006) are excluded."""
    df = pd.read_csv(ROOT / "out" / "d3_events.csv", parse_dates=["day0"])
    rep = df[df.sign_source == "surprise"]
    assert (np.sign(rep.surprise_pct) == rep.sign).all()
    eps = df[df.sign_source == "eps"]
    assert eps.surprise_pct.isna().all() and (np.sign(eps.eps_act - eps.eps_est) == eps.sign).all()
    assert set(df.sign_source) <= {"surprise", "eps"}
    assert (df.beat == (df.sign > 0)).all() and (df.miss == (df.sign < 0)).all()
    assert not df.duplicated(["ticker", "day0"]).any()
    # the classifier itself, on hand-made rows
    import event_study
    assert event_study.classify(0.19, 0.19, 66.67) == (1, "surprise")
    assert event_study.classify(0.15, 0.16, -1.0) == (-1, "surprise")
    assert event_study.classify(float("nan"), float("nan"), 15.98) == (1, "surprise")
    assert event_study.classify(0.4, 0.4, float("nan")) == (0, "eps")
    assert event_study.classify(float("nan"), 0.01, float("nan"))[0] is None
    t = pd.Timestamp("2010-01-04")
    dd = pd.DataFrame({"ticker": ["X", "X", "Y", "Y", "Z"], "day0": [t, t, t, t, t], "sign": [1, -1, 1, 1, 0],
                       "surprise_pct": [2.0, -3.0, 1.0, 4.0, np.nan]})
    kept, dup = event_study.dedupe(dd)
    assert list(kept.ticker) == ["Y", "Z"] and dup["same_sign"] == 1 and dup["conflict_rows"] == 2 and dup["conflict_reports"] == 1
    rm = R["D3"]["removed"]
    assert rm["conflicting_duplicates_reports"] == len(rm["conflicting_duplicates"])
    assert R["D3"]["n_beats"] == int(df.beat.sum()) and R["D3"]["beat_and_fell"]["car1_60"]["n"] == int((df.beat & (df.ar0 < 0)).sum())
    if (data.RAW / "estimates_20261121T205835Z").exists() and R["D3"]["snapshot"] == "estimates_20261121T205835Z":
        nv = df[(df.ticker == "NVDA") & (df.day0.dt.strftime("%Y-%m") == "2015-08")]
        assert len(nv) == 1 and bool(nv.beat.iloc[0]) and abs(nv.surprise_pct.iloc[0] - 66.67) < 1e-9
        assert sorted(rm["conflicting_duplicates"]) == ["NVDA 2006-11-10: +5.08%, -7.56%", "WMT 2002-08-13: -3.64%, +2.34%"]
        assert not ((df.ticker == "WMT") & (df.day0 == "2002-08-13")).any()
        assert (R["D3"]["n_beats"], R["D3"]["beat_and_fell"]["car1_60"]["n"]) == (326, 148)


def test_T6_synthetic_attribution():
    rng = np.random.default_rng(1)
    n = 300
    m = rng.normal(0, 0.01, n)
    s = 0.8 * m + rng.normal(0, 0.008, n)
    sp = s - 0.8 * m
    r = 1.3 * m + 0.7 * sp + rng.normal(0, 0.002, n)
    b = attribution.fit_betas(r[:250], m[:250], s[:250])
    # realised window: 10 days, planted -5% event on day 5, FX path
    P, X, u = 100.0, 0.75, 100.0
    truth = {"market": 0, "sector": 0, "fx": 0, "event": 0}
    est = {"market": 0, "sector": 0, "fx": 0, "event": 0}
    for k in range(250, 260):
        ev = -0.05 if k == 255 else 0.0
        rk = 1.3 * m[k] + 0.7 * sp[k] + ev
        X1 = X * (1 + rng.normal(0, 0.004))
        P1 = P * (1 + rk)
        base = u * P * X
        truth["market"] += base * 1.3 * m[k]; truth["sector"] += base * 0.7 * sp[k]
        truth["fx"] += u * P * (X1 - X); truth["event"] += base * ev
        sd = attribution.split_day(u, P, P1, X, X1, b, m[k], s[k])
        est["market"] += sd["market"]; est["sector"] += sd["sector"]; est["fx"] += sd["fx"]
        if k == 255:
            est["event"] += sd["ar"]
        P, X = P1, X1
    for k in truth:
        assert abs(est[k] - truth[k]) <= max(0.10 * abs(truth[k]), 20.0), (k, est, truth)


def _observed_quarters():
    """Quarter labels of the beat-and-fell sample, as observed (number of quarters and events per quarter)."""
    df = pd.read_csv(ROOT / "out" / "d3_events.csv")
    bf = df[df.beat & (df.ar0 < 0)]
    q, _ = pd.factorize(bf.quarter)
    return q


def _sim_event_study(drift, n_sims=2000, seed=11):
    rng = np.random.default_rng(seed)
    rej = 0
    q = _observed_quarters()
    n, n_q = len(q), q.max() + 1
    assert (n, n_q) == (R["D3"]["beat_and_fell"]["car1_60"]["n"], R["D3"]["beat_and_fell"]["car1_60"]["clusters"])
    for _ in range(n_sims):
        common = rng.normal(0, 0.02, n_q)[q]
        car = drift + common + rng.standard_t(4, n) * 0.06 / math.sqrt(2)
        t, p, *_ = event_study.cluster_t(car, q)
        rej += p < 0.05
    return rej / n_sims


def test_T7_null_size():
    rate = _sim_event_study(0.0)
    print("T7 rejection rate", rate)
    assert 0.03 <= rate <= 0.07


def test_T8_power_reported():
    rate = _sim_event_study(0.03, n_sims=1000)
    print("T8 power at +3% planted 20-day drift", rate)
    (ROOT / "out" / "t8_power.txt").write_text(str(rate))


def test_T9_alignment():
    al = R["D3"]["alignment_T9"]
    assert sum(v["day0_highest"] for v in al.values()) >= 3


def test_T10_p9_replication():
    s = R["C"]["p9_replica"]["two_week_sd_pct"]
    assert 3.6 <= s <= 4.2


def test_T11_sign_stability():
    """Plan 2: per-bucket sign stability across the 36 variants; required only for buckets a deliverable quotes
    as a single sign. Others are quoted as a range (the Description quotes the systematic share as 81-97%)."""
    sens = {k: v for k, v in R["B"]["sensitivity"].items() if "error" not in v}
    assert len(sens) == 36
    stab = {b: {"neg": sum(v[b] < 0 for v in sens.values()), "pos": sum(v[b] > 0 for v in sens.values())}
            for b in ("market", "sector", "fx", "sched_AR", "residual_AR", "mkt_sec_fx_crypto", "company_AR")}
    print(stab)
    (ROOT / "out" / "t11_sign_stability.json").write_text(json.dumps(stab))
    assert stab["market"]["neg"] == 36 and stab["mkt_sec_fx_crypto"]["neg"] == 36 and stab["fx"]["pos"] == 36


@pytest.mark.parametrize("draws", [10000, 50000])
def test_T12_seeds(draws):
    port = power.portfolio_daily_gbp(R["C"]["held_weights_9Nov"])
    res = [power.block_bootstrap(port, n=draws, seed=s) for s in (power.SEED, 1, 2)]
    lo = [x["p2_5_pct"] for x in res]; hi = [x["p97_5_pct"] for x in res]
    print(draws, lo, hi)
    # Tolerance = 4 Monte Carlo standard errors of a 2.5%/97.5% quantile (normal approx: sqrt(p(1-p)/n) / density).
    # The old fixed 0.2 pt was ~2.2 SE at 10,000 draws, so three seeds broke it by chance about 1 run in 4.
    sd = res[0]["sd_pct"]
    se = math.sqrt(0.025 * 0.975 / draws) / (math.exp(-1.96 ** 2 / 2) / math.sqrt(2 * math.pi) / sd)
    assert max(lo) - min(lo) < 4 * se and max(hi) - min(hi) < 4 * se, (se, lo, hi)


@needs_drafts
def test_T13_claims():
    import claims2
    for f in sorted((ROOT / "deliver").glob("*.txt")):
        if f.name == "RESULTS2.txt":
            continue
        unmatched = claims2.check(f)
        assert unmatched == [], (f.name, unmatched)


def test_T14_repo_untouched():
    """Originally: the separate read-only clone of this repo was clean at P9's commit 53af9f5. In the repo copy the model
    reads P9 from the sibling folder, so the check is now: P9's input files to this model exist and have no uncommitted
    changes, and P9's model.py and out/ are unchanged since 53af9f5 (the commit the results were computed against).
    Edits to P9's README do not trip it."""
    p9 = ROOT.parent / "p9_umushroom_event_risk"
    for f in ("per_asset.csv", "correlations.csv", "compare.json", "results.json"):
        assert (p9 / "out" / f).exists(), f
    if subprocess.run(["git", "-C", str(ROOT), "rev-parse"], capture_output=True).returncode != 0:
        pytest.skip("not a git checkout")
    paths = [str(p9 / "out"), str(p9 / "model.py")]
    st = subprocess.run(["git", "-C", str(ROOT.parent), "status", "--porcelain", "--"] + paths,
                        capture_output=True, text=True).stdout
    diff = subprocess.run(["git", "-C", str(ROOT.parent), "diff", "--quiet", "53af9f5", "HEAD", "--"] + paths)
    assert st.strip() == "" and diff.returncode == 0


# ---------------- Plan 2 ----------------
R2 = json.loads((ROOT / "out" / "results2.json").read_text())


def test_T15_syre_fill():
    """Report, do not block: implied GBPUSD vs Yahoo close of candidate fill dates; fill inside the day's range."""
    implied = 29.8102 * 97.63 / 2206.99
    o = pd.read_csv(data.RAW / f"prices_{data._ts()}_ohlc.csv", header=[0, 1], index_col=0, parse_dates=True)
    out = {}
    for d in ("2026-11-19", "2026-11-20"):
        fx = float(o[("Close", "GBPUSD=X")].loc[d])
        lo, hi = float(o[("Low", "SYRE")].loc[d]), float(o[("High", "SYRE")].loc[d])
        out[d] = {"spread_pct": round(100 * (fx / implied - 1), 3), "inside_range": lo <= 97.63 <= hi,
                  "flag": not (-0.5 <= 100 * (fx / implied - 1) <= 0.1 and lo <= 97.63 <= hi)}
    print("SYRE implied", implied, out)
    (ROOT / "out" / "t15_syre.json").write_text(json.dumps({"implied_gbpusd": implied, "by_date": out}))
    assert abs(implied - 1.3187) < 0.0005


def test_T16_var_flags():
    for k in ("var_yahoo", "var_platform"):
        v = R2[k]
        assert v["var95_breached"] == (v["loss_gbp"] > 6432) and v["var99_breached"] == (v["loss_gbp"] > 9094)
    assert R2["var_platform"]["var95_breached"]
    if (ROOT / "deliver" / "V2_DESCRIPTION_v2.txt").exists():
        txt = (ROOT / "deliver" / "V2_DESCRIPTION_v2.txt").read_text()
        assert "95% VaR was breached" in txt


def test_T25_rules_lock():
    """(a) The hashed original (thesis_rules.original.json) still has the digest locked at 2026-11-21T21:00:26Z; the
    publication copy the code reads has its own recorded digest and differs from the original only by the wording edits
    listed in scorecard.PUBLICATION_EDITS. (b) Full-timestamp order: every evidence row was recorded after the lock.
    What this establishes: the final flags were recorded after the rules were hashed. It does not establish that no
    evidence was seen first: the first estimates snapshot (S1, 19 Nov) informed the 2% bar (disclosed in R2), and the
    snapshot used as S2 was downloaded at 20:58:35 UTC, before the lock."""
    import csv, hashlib, scorecard
    INP = ROOT / "data/input"
    h, t = (INP / "thesis_rules.lock").read_text().split()
    assert hashlib.sha256((INP / "thesis_rules.original.json").read_bytes()).hexdigest() == h
    hp = (INP / "thesis_rules.published.lock").read_text().split()[0]
    assert hashlib.sha256((INP / "thesis_rules.json").read_bytes()).hexdigest() == hp != h
    assert (INP / "thesis_rules.json").read_text() == scorecard.published_from_original()
    orig, pub = json.loads((INP / "thesis_rules.original.json").read_text()), json.loads((INP / "thesis_rules.json").read_text())
    assert {k: v for k, v in orig.items() if k not in ("source", "R2")} == {k: v for k, v in pub.items() if k not in ("source", "R2")}
    assert "planner" not in (INP / "thesis_rules.json").read_text()
    assert scorecard.rules_hash_ok() == (True, t)
    lock = pd.Timestamp(t)
    for r in csv.DictReader(open(INP / "thesis_evidence.csv")):
        assert pd.Timestamp(r["collected_utc"]) > lock, r
        assert r["url"].strip() and (r["url"] != "not sourced" or r["source_class"] == "not sourced")
    s1 = pd.Timestamp("2026-11-19T17:46:03Z"); s2 = pd.Timestamp("2026-11-21T20:58:35Z")
    names = {p.name for p in data.RAW.glob("estimates_*")}
    if {"estimates_20261119T174603Z", "estimates_20261121T205835Z"} <= names:
        assert s1 < s2 < lock


def test_T26_scorecard_logic():
    import scorecard
    cases = {("none", "none"): "HOLD", ("SOFT",): "REVIEW", ("SOFT", "SOFT"): "REVIEW-TRIM",
             ("SOFT", "HARD"): "CUT", ("HARD",): "CUT", ("watch", "SOFT"): "REVIEW", ("watch",): "HOLD"}
    for trig, want in cases.items():
        assert scorecard.status_of(list(trig)) == want
    rows = [{"asset": "X", "rule": f"R{i}", "finding": "", "trigger": t, "url": "u", "source_class": "primary"}
            for i, t in enumerate(["none", "SOFT", "SOFT", "watch"], 1)]
    s = scorecard.score(rows)
    assert s["X"]["status"] == "REVIEW-TRIM" and s["BTC-USD"]["status"] == "NO THESIS" and s["SYRE"]["status"] == "NO THESIS"


def test_T29_counterfactual_actual():
    import counterfactual
    cf = R2["counterfactual"]
    led = ledger.daily("2026-11-20")
    assert abs(cf["actual_pnl"] - (float(led["nav"].iloc[-1]) - 100000)) <= 1.0
    for k, b in cf["books"].items():
        assert abs(sum(b["weights"].values()) - 0.80) < 1e-6
        assert abs(sum(b["pnl_by_asset"].values()) - b["pnl"]) <= 1.0


@needs_drafts
def test_T30_banned_phrases():
    import claims2
    for f in (ROOT / "deliver").glob("*.txt"):
        if f.name == "RESULTS2.txt":
            continue
        assert claims2.banned(f) == [], (f.name, claims2.banned(f))


def test_T30b_banned_phrases_final():
    """T30 applied to the submitted Description, which is in the repo copy."""
    import claims2
    f = ROOT / "data" / "input" / "description_final_submitted.txt"
    assert claims2.banned(f) == [], claims2.banned(f)


@needs_drafts
def test_T31_lengths():
    import claims2
    d = ROOT / "deliver"
    assert 300 <= claims2.words(d / "V2_DESCRIPTION_v2.txt") <= 350
    if (d / "V2_DESCRIPTION_v3.txt").exists():
        assert 330 <= claims2.words(d / "V2_DESCRIPTION_v3.txt") <= 380
    if (d / "V2_DESCRIPTION_v4.txt").exists():
        assert 330 <= claims2.words(d / "V2_DESCRIPTION_v4.txt") <= 440
    if (d / "V2_DESCRIPTION_v5.txt").exists():
        assert 440 <= claims2.words(d / "V2_DESCRIPTION_v5.txt") <= 610
    if (d / "V2_NEXT_STEPS.txt").exists():
        assert claims2.words(d / "V2_NEXT_STEPS.txt") <= 450
    if (d / "V2_PITCH_5_SLIDES.txt").exists():
        import re
        txt = (d / "V2_PITCH_5_SLIDES.txt").read_text()
        for block in re.findall(r"ON SLIDE:\n(.*?)\nSPEAKER NOTES:", txt, re.S):
            assert len(block.split()) <= 60, block[:80]


def test_T23_strategic_invariants():
    import strategic as E
    for k, run in R2["E"]["runs"].items():
        assert run["min_eig"] > 0, k
        for p in ("held", "erc_capped", "sleeve_rp_capped"):
            w = run[p]["weights_pct"]
            assert max(w.values()) <= 15.0 + 1e-4, (k, p)
            assert abs(sum(run[p]["risk_share_pct"].values()) - 100) < 0.05, (k, p)
            assert abs(sum(w.values()) - run["held"]["invested_pct"]) < 0.05, (k, p)
    # uncapped ERC: equal shares; Euler shares sum to 1
    rng = np.random.default_rng(3)
    A = rng.normal(size=(6, 6)); cov = A @ A.T + 6 * np.eye(6)
    w = E.erc(cov, 0.8)
    sig, sh = E.euler_shares(w, cov)
    assert abs(sh.sum() - 1) < 1e-9 and np.ptp(sh) < 1e-4 and abs(w.sum() - 0.8) < 1e-9
    wc = E.cap_weights(np.array([.3, .2, .1, .1, .05, .05]), 0.8)
    assert wc.max() <= 0.15 + 1e-12 and abs(wc.sum() - 0.8) < 1e-9


def test_T24_erc_ties_to_p9():
    """ERC logic on P9's own covariance (rebuilt from its out files: corr x diffusive vol x 10/252 + jump^2)
    must reproduce P9's ERC weights within 0.3 pt. The Yahoo-data replica is reported, not gated (data differ, as T10)."""
    import math
    P9 = ROOT.parent / "p9_umushroom_event_risk" / "out"
    pa = pd.read_csv(P9 / "per_asset.csv")
    corr = pd.read_csv(P9 / "correlations.csv", index_col=0).values
    vol = pa.ann_vol_pct.values / 100 * math.sqrt(10 / 252)
    jump = pa.implied_move_pct.fillna(0).values / 100 * math.sqrt(math.pi / 2)
    cov = corr * np.outer(vol, vol) + np.diag(jump ** 2)
    w = p9.equal_risk_weights(cov, 0.8)
    got = (100 * w).round(1)
    print("ERC on P9 cov", got, "P9", pa.erc_weight_pct.values)
    assert np.max(np.abs(100 * w - pa.erc_weight_pct.values)) <= 0.3


def test_T27_decision_logic():
    import decide
    cur = {"A": .13, "B": .10, "C": .05, "D": .12, "BTC": .09, "SYRE": .023, "E": .10, "F": .08}
    ws = {"A": .06, "B": .06, "C": .10, "D": .14, "BTC": .13, "SYRE": .08, "E": .10, "F": .12}
    st = {"A": "REVIEW-TRIM", "B": "CUT", "C": "HOLD", "D": "REVIEW", "BTC": "NO THESIS", "SYRE": "NO THESIS", "E": "HOLD", "F": "HOLD"}
    hits = {"C": True, "D": True, "E": True, "F": True}
    rows, t, cash = decide.actions(st, cur, ws, hits)
    assert t["A"] == .06 and t["B"] == 0 and t["D"] == .12 and t["BTC"] == .09 and t["SYRE"] == .023
    assert abs(t["C"] - .10) < 1e-12              # add 5% (to w*), uses the whole 5% budget
    assert t["F"] == .08 and t["E"] == .10          # F: budget exhausted by C; E: at w*, no add
    assert sum(t[a] - cur[a] for a in cur if t[a] > cur[a]) <= .05 + 1e-12
    assert abs(cash + sum(t.values()) - 1) < 1e-12 and max(t.values()) <= .15
    rows2, t2, _ = decide.actions({"X": "HOLD"}, {"X": .14}, {"X": .20}, {"X": True})
    assert abs(t2["X"] - .15) < 1e-12               # cap binds
    _, t3, _ = decide.actions({"SYRE": "NO THESIS"}, {"SYRE": .04}, {"SYRE": .08}, {})
    assert t3["SYRE"] == .025
    # real table
    K = R2["K"]["decision_table"]
    assert abs(sum(v["target_pct"] for v in K.values()) + R2["K"]["cash_after_pct"] - 100) < 0.05


@archived_only
def test_T28_triggers_from_p9_file():
    P9 = ROOT.parent / "p9_umushroom_event_risk" / "out"
    pa = pd.read_csv(P9 / "per_asset.csv")
    trig = R2["deploy"]["triggers_from_p9_file"]
    name = {"NVIDIA": "NVDA", "Applied Materials": "AMAT", "Walmart": "WMT", "Home Depot": "HD", "BAE Systems": "BA.L",
            "Rolls-Royce": "RR.L", "Bitcoin": "BTC-USD", "Ethereum": "ETH-USD"}
    for r in pa.itertuples():
        assert trig[name[r.asset]] == r.deploy_trigger_daily_pct
    h20 = {(h["asset"], h["hit_local"], h["hit_gbp"]) for h in R2["deploy"]["hits"] if h["date"] == "2026-11-20"}
    assert ("NVDA", True, True) in h20 and ("AMAT", True, True) in h20 and ("BTC-USD", True, False) in h20
    # the deployment rule is in sterling: the decision table uses hit_gbp; hit_local is kept as a diagnostic
    K = R2["K"]["decision_table"]
    for a, k in (("NVDA", "NVDA"), ("AMAT", "AMAT"), ("BTC-USD", "BTC")):
        h = [x for x in R2["deploy"]["hits"] if x["date"] == "2026-11-20" and x["asset"] == a][0]
        assert K[k]["trigger_hit_20nov"] == h["hit_gbp"] and K[k]["trigger_hit_local_20nov_diagnostic"] == h["hit_local"]
    assert K["BTC"]["trigger_hit_20nov"] is False and K["BTC"]["trigger_hit_local_20nov_diagnostic"] is True


def _w13():
    mp = {"NVDA": "NVDA", "WMT": "WMT", "AMAT": "AMAT", "HD": "HD", "BAE": "BA.L", "RR": "RR.L", "BTC": "BTC-USD"}
    return {mp[k]: v for k, v in R["C"]["held_weights_13Nov"].items() if k in mp}


def test_T20_gh_leakage():
    import drawdown as H
    w = _w13()
    def snap():
        r = H.book_returns(w)
        a = H.analyse(r, -0.0719, n_draws=500)
        g = None
        try:
            import horizon as G
            g = G.leak_snapshot()
        except ImportError:
            pass
        return r.values.copy(), json.dumps(a, sort_keys=True), g
    r0, a0, g0 = snap()
    data._NOISE.update(on=True, seed=11)
    try:
        r1, a1, g1 = snap()
    finally:
        data._NOISE.update(on=False)
    assert np.array_equal(r0, r1) and a0 == a1
    if g0 is not None:
        assert g0 == g1
    r = H.book_returns(w)
    assert r.index.max() <= data.CUTOFF


def test_T21_synthetic_h():
    import drawdown as H
    rng = np.random.default_rng(5)
    rej, n_sims = 0, 300
    for k in range(n_sims):
        r = pd.Series(rng.normal(0.0004, 0.012, 3000), index=pd.bdate_range("2010-01-01", periods=3000))
        a = H.analyse(r, -0.06, h_fwd=(126,), n_draws=400, seed=k)
        f = a["forward"][126]
        if "verdict" in f and f["verdict"] != "not distinguishable from any other date":
            rej += 1
    rate = rej / n_sims
    print("T21 size (mean OR share outside 2.5-97.5)", rate)
    # two criteria (mean, share) each at 5%: size up to ~10% expected; Plan bar 3-7% applies to a single criterion
    pw, n2 = 0, 100
    for k in range(n2):
        x = rng.normal(0.0004, 0.012, 3000)
        r = pd.Series(x, index=pd.bdate_range("2010-01-01", periods=3000))
        cum = np.cumprod(1 + x)
        roll = cum[10:] / cum[:-10] - 1
        eps = H._episodes_strict(pd.Series(roll), -0.06, 21)
        for e in eps:          # plant +5% over the next 126 sessions after each episode
            j = e + 10
            x[j + 1:j + 127] += 0.05 / 126
        a = H.analyse(pd.Series(x, index=r.index), -0.06, h_fwd=(126,), n_draws=400, seed=k)
        pw += a["forward"][126].get("pctile_mean", 50) > 97.5
    print("T21 power, planted +5% rebound", pw / n2)
    (ROOT / "out" / "t21.json").write_text(json.dumps({"size_either": rate, "power_mean": pw / n2}))
    assert rate <= 0.12


def test_T21b_single_criterion_size():
    import drawdown as H
    rng = np.random.default_rng(9)
    rej, n_sims = 0, 1000
    for k in range(n_sims):
        r = pd.Series(rng.normal(0.0004, 0.012, 3000), index=pd.bdate_range("2010-01-01", periods=3000))
        f = H.analyse(r, -0.06, h_fwd=(126,), n_draws=400, seed=k)["forward"][126]
        if "pctile_mean" in f:
            rej += not (2.5 <= f["pctile_mean"] <= 97.5)
    print("T21b size (mean only)", rej / n_sims)
    (ROOT / "out" / "t21b.json").write_text(json.dumps({"size_mean_only": rej / n_sims, "n_sims": n_sims}))
    assert 0.03 <= rej / n_sims <= 0.07


def test_T22_spacing():
    import drawdown as H
    rb = H.book_returns(_w13())
    cum = np.cumprod(1 + rb.values)
    roll = pd.Series(cum[10:] / cum[:-10] - 1)
    for s in (10, 21, 42):
        e = H._episodes_strict(roll, -0.0719, s)
        assert all(b - a > s for a, b in zip(e, e[1:])), s
    print(R2["H"]["book_primary"]["episodes_by_spacing"])


def test_T32_seed_stability_h():
    import drawdown as H
    rb = H.book_returns(_w13())
    res = [H.analyse(rb, -0.0719, n_draws=20000, seed=s)["forward"] for s in (1, 2, 3)]
    for h in ("126", "252"):
        m = [r[int(h)]["rand_mean_2.5_97.5_pct"] for r in res]
        sh = [r[int(h)]["rand_share_2.5_97.5_pct"] for r in res]
        for j in (0, 1):
            assert np.ptp([x[j] for x in m]) < 1.0, (h, m)
            assert np.ptp([x[j] for x in sh]) < 3.0, (h, sh)


def test_T17_identity():
    for k in ("G2", "G2_floor_sensitivity_TTM_gt_0_LABELLED_SENSITIVITY"):
        g = R2["G"][k]
        for t, d in list(g["per_ticker"].items()) + [("pooled", g["pooled"])]:
            for h, v in d.items():
                assert abs(v["s_E"] + v["s_PE"] - 1) < 2e-3, (k, t, h)   # rounded to 3 dp in JSON
    import horizon as G
    rng = np.random.default_rng(0)
    x, y = rng.normal(size=50), rng.normal(size=50)
    a, b = G.s_e(x, y)
    assert abs(a + b - 1) < 1e-9


def _synthetic_panel(rng, n, phi, se=0.05, sv=0.08, rw_multiple=False):
    e = np.cumsum(rng.normal(0, se, n)) + np.log(2.0)
    m = np.zeros(n)
    for k in range(1, n):
        m[k] = (m[k - 1] if rw_multiple else phi * m[k - 1]) + rng.normal(0, sv)
    return pd.DataFrame({"price": np.exp(e + m + 3), "ttm": np.exp(e), "q": np.arange(n), "date": pd.date_range("2000-01-01", periods=n, freq="QS")})


def test_T18_synthetic_g():
    import horizon as G
    rng = np.random.default_rng(18)
    se, sv, phi = 0.05, 0.08, 0.7
    sm2 = sv ** 2 / (1 - phi ** 2)
    errs = []
    for h in (1, 4, 12, 20):
        est = []
        for _ in range(200):
            p = _synthetic_panel(rng, 400, phi, se, sv)
            x, y, q, _ = G.changes(p, h, floor=0)
            est.append(G.s_e(x, y)[0])
        analytic = h * se ** 2 / (h * se ** 2 + 2 * sm2 * (1 - phi ** h))
        errs.append(abs(np.mean(est) - analytic))
        print("T18 h", h, round(np.mean(est), 3), round(analytic, 3))
    assert max(errs) <= 0.10
    # Null: both random walks, so no true difference between horizons. With the revised estimator (within-company means
    # recomputed in each bootstrap draw), count false 'rise' claims under the old gate (95% lower bound > 0, three of four
    # companies rising) and the current gate (99% lower bound > 0, three of four), and how often each interval excludes
    # zero. Run on the panels this test has always drawn (continuing rng 18) and on a fresh set (new seed) that played no
    # part in choosing the 99% bar.
    def null_run(r, n_sims=1000, recentre="draw", panel_list=None):
        c = {"n_sims": n_sims, "false_claims_old_gate_95": 0, "false_claims_new_gate_99": 0,
             "ci95_lo_above_0": 0, "ci95_hi_below_0": 0, "ci99_lo_above_0": 0, "ci99_hi_below_0": 0}
        drawn = []
        for k in range(n_sims):
            panels = (panel_list[k] if panel_list is not None else
                      {t: _synthetic_panel(r, 100, 1.0, se, sv, rw_multiple=True) for t in G.US})
            drawn.append(panels)
            g = G.g2(n_draws=400, seed=k, panels=panels, floor=0, recentre=recentre)
            d, three = g["pooled_diff_20_1"], sum(g["rises_per_ticker"].values()) >= 3
            c["false_claims_old_gate_95"] += bool(d["ci95"][0] > 0 and three)
            c["false_claims_new_gate_99"] += bool(g["claim_bar_met"])
            assert g["claim_bar_met"] == bool(d["ci99"][0] > 0 and three)
            c["ci95_lo_above_0"] += d["ci95"][0] > 0; c["ci95_hi_below_0"] += d["ci95"][1] < 0
            c["ci99_lo_above_0"] += d["ci99"][0] > 0; c["ci99_hi_below_0"] += d["ci99"][1] < 0
        return c, drawn
    orig, panels18 = null_run(rng)
    fresh, _ = null_run(np.random.default_rng(20261125))
    before, _ = null_run(None, recentre="fixed", panel_list=panels18)       # previous estimator, same panels
    runs = {"original_panels_rng18": orig, "fresh_panels_rng20261125": fresh,
            "previous_estimator_fixed_means_original_panels": before}
    print("T18 null", runs)
    (ROOT / "out" / "t18.json").write_text(json.dumps({
        "estimator": "pooled 20q-1q slope difference; within-company means recomputed in each bootstrap draw",
        "old_gate": "95% lower bound > 0 and at least 3 of 4 companies rising",
        "new_gate": "99% lower bound > 0 and at least 3 of 4 companies rising (claim_bar_met)",
        "null_runs": runs, "abs_errs": errs}, indent=1))
    for c in (orig, fresh):
        assert c["false_claims_new_gate_99"] / c["n_sims"] <= 0.10


def test_T19_eps_integrity():
    sc = R2["G"]["G2_split_check_T19"]
    assert set(sc) == {"NVDA 2021-07-20", "NVDA 2024-06-10", "WMT 2024-02-26"}
    for k, v in sc.items():
        assert 0.5 <= v <= 2, (k, v)
    for t, d in R2["G"]["G2"]["dropped_floor"].items():
        assert all(isinstance(n, int) for n in d.values())


def test_T32_seed_stability_g():
    import horizon as G
    panels = {t: G.quarterly_panel(t)[0] for t in G.US}
    res = [G.g2(n_draws=20000, seed=s, panels=panels) for s in (1, 2, 3)]
    for h in ("1", "4", "12", "20"):
        for j in (0, 1):
            vals = [r["pooled_ci95"][int(h)][j] for r in res]
            assert np.ptp(vals) < 0.03, (h, vals)
    d = [r["pooled_diff_20_1"]["ci95"] for r in res]
    assert np.ptp([x[0] for x in d]) < 0.03 and np.ptp([x[1] for x in d]) < 0.03


V3_HEADINGS = ["Investment Strategy Overview", "Macroeconomic and Geopolitical Considerations", "Strategic Asset Allocation",
               "Investment Instrument Selection", "Risk Management"]


@pytest.mark.parametrize("ver", ["v3", "v4", "v5"])
def test_T33_v3_structure(ver):
    """PLAN3: five jury headings in order on their own lines; horizon matches the 7 Nov record; ESG and no-rebound wording."""
    f = ROOT / "deliver" / f"V2_DESCRIPTION_{ver}.txt"
    if not f.exists():
        pytest.skip("Description draft not included in the repo copy")
    txt = f.read_text()
    lines = [l.strip() for l in txt.splitlines()]
    idx = [lines.index(h) for h in V3_HEADINGS]
    assert idx == sorted(idx)
    for s in ("event-driven", "did not screen on ESG", "do not claim", "95% VaR", "breached", "1 hit, 5 misses", "overrode"):
        assert s in txt, s
    assert not any(ch in txt for ch in "#*`"), "markdown symbol in plain-text paste"


@archived_only
def test_T34_h_g_gates():
    """PLAN3: H sentence needs 'not distinguishable' at 252 sessions for both books (+ caveat); the README quotes it, so
    h_gate always runs. A G2 rise claim (the drafts' '57%' sentence) needs claim_bar_met (g_gate) and the exceptions
    wording; with no claim there is no G2 requirement."""
    import claims2
    claims2.h_gate(R2)
    txt = "\n".join((ROOT / "deliver" / f"V2_DESCRIPTION_{v}.txt").read_text() for v in ("v3", "v4", "v5")
                    if (ROOT / "deliver" / f"V2_DESCRIPTION_{v}.txt").exists())
    if "22 of 3,044" in txt:
        assert claims2.H_VERDICT in txt and "hindsight-chosen" in txt and "chips fared worse" in txt
    if "57%" in txt:
        claims2.g_gate(R2)
        for s in ("held for Home Depot and Applied Materials, not Walmart", "NVIDIA's five-year sample is too small",
                  "partly by construction"):
            assert s in txt, s


@pytest.mark.parametrize("ver", ["v3", "v4", "v5"])
def test_T35_paste_file(ver):
    """PASTE = vN text, blank line, then the platform call ledger byte-for-byte from 'Calls logged on 7th November'."""
    d = ROOT / "deliver"
    if not (d / f"V2_DESCRIPTION_{ver}_PASTE.txt").exists():
        pytest.skip("Description draft not included in the repo copy")
    src = (ROOT / "data" / "input" / "description_current_platform.txt").read_bytes()
    ledger = src[src.index(b"Calls logged on 7th November"):]
    assert (d / f"V2_DESCRIPTION_{ver}_PASTE.txt").read_bytes() == (d / f"V2_DESCRIPTION_{ver}.txt").read_bytes() + b"\n" + ledger


@archived_only
def test_T36_v4_audit_fixes():
    """Audit must-fixes: each new v4 sentence is backed by results (claims2.v4_gate) and present; no 'recommended' trim."""
    import claims2
    R1 = json.loads((ROOT / "out" / "results.json").read_text())
    claims2.v4_gate(R1, R2)
    f = ROOT / "deliver" / "V2_DESCRIPTION_v4.txt"
    if not f.exists():
        return
    txt = f.read_text()
    assert "recommended" not in txt and txt.count("trim under review; no adds") == 2
    for s in ("Why we do not sell on the fall alone", "the Nasdaq and chips fared worse", "Six large-cap shares, Bitcoin and Spyre",
              "offset 16%", "passed the 99% figure", "one risk block", "Today's rules bar the last two"):
        assert s in txt, s


V5_MUST_KEEP = ["(-8.5%)", "2.2 standard deviations", "the two-week 95% VaR (£6,432) was breached, short of the 99% (£9,094)",
                "1 hit, 5 misses", "we overrode it", "event-driven", "could not show skill",
                "On 13 Nov we sold Ethereum at a loss and added to NVIDIA a day after its chief executive left, above our 15% cap",
                "on 19 Nov we bought Spyre with no written case", "Today's rules bar the last two",
                "favourable 9 Nov fills (Applied Materials below the day's range) offset 16%, else the loss would have passed the 99% figure",
                "NVIDIA 13.0% against 6.2% (trim under review; no adds)", "Applied Materials 10.2% against 6.0%",
                "We do not claim prices will rebound", "we did not screen on ESG", "defence stocks", "ESG-constrained investors"]
V5_NEW = ["Objective (assumption, not forecast): Sharpe 0.3, about 5% a year over sterling cash, our chosen benchmark, at current volatility",
          "16% yearly volatility; one-year 95% VaR £24,400 (normal tails)",
          "16 Nov US rule on Chinese remote AI-chip access", "$130.0bn against $125.1bn expected, assuming no China data-centre sales",
          "Applied Materials guided above consensus", "from over £2.0bn to about £3.0bn", "Rolls-Royce reaffirmed.",
          "October CPI 0.4% monthly against 0.3% expected", "Walmart raised guidance", "Home Depot's estimates fell 1.7%",
          "sterling fell from 1.346 to 1.309 dollars", "five sleeves, a fifth of risk each, 15% name cap",
          "Spyre: cap 2.5% or exit", "56% of risk now, 46% after such a trim, 40% only at full budget weights",
          "names with a thesis that pass every test and sit below budget", "at most 5% of NAV; none qualified on 20 Nov", "four tests, written 21 Nov, after the fall",
          "guidance cut; falling estimates; regulatory or accounting event; unplanned chief executive or finance chief exit",
          "A hard failure sells; two soft flags put a trim under review; one bars adds",
          "NVIDIA has two (reported, unconfirmed SEC examination; no permanent chief executive); Home Depot one",
          "2.4 times our AI sell-off stress (£3,613); we now stress with the realised fall", "a restatement or non-reliance filing sells NVIDIA",
          "59% in dollars, unhedged by choice; sterling's fall offset 11% of the loss, by luck", "17% cash",
          "scorecard re-run 27 Nov and each results date; quarterly rebalance outside a 25% band"]


@archived_only
def test_T37_v5():
    """v5: every added number is asserted against results or a sourced input file (claims2.v5_gate); the honest record
    and the pending-decision wording are kept; the sleeve line is rebuilt from E; H / G2 only with their gates and caveats;
    v4 files are unchanged by v5 work (no 'recommended' trim, plain text)."""
    import claims2
    R1 = json.loads((ROOT / "out" / "results.json").read_text())
    claims2.v4_gate(R1, R2)
    facts = claims2.v5_gate(R1, R2)
    for tok in ("0.3", "5", "24,400", "130.0", "125.1", "2.0", "3.0", "16", "0.4", "1.346", "1.309", "40", "2.4", "3,613"):
        assert tok in facts, tok
    f = ROOT / "deliver" / "V2_DESCRIPTION_v5.txt"
    if not f.exists():
        return
    txt = f.read_text()
    for s in V5_MUST_KEEP + V5_NEW:
        assert s in txt, s
    assert claims2.v5_sleeve_line(R2) in txt
    assert "recommended" not in txt and "forecast" in txt and "will rebound" in txt
    assert claims2.check(f) == [] and claims2.banned(f) == []
    if "22 of 3,044" in txt:
        claims2.h_gate(R2)
        assert claims2.H_VERDICT in txt and "hindsight-chosen" in txt and "chips fared worse" in txt
    if "57%" in txt:
        claims2.g_gate(R2)
        for s in ("held for Home Depot and Applied Materials, not Walmart", "NVIDIA's five-year sample is too small",
                  "partly by construction"):
            assert s in txt, s
    assert all(ord(ch) < 128 or ch in "£" for ch in txt), "non-ASCII character other than £"
    assert not any(ch in txt for ch in "#*`_|"), "markdown symbol in plain-text paste"
    paste = (ROOT / "deliver" / "V2_DESCRIPTION_v5_PASTE.txt").read_text()
    assert paste.startswith(txt) and paste.count(claims2.LEDGER_MARK) == 1 and paste.rstrip().endswith("( for scoring purposes).")
    assert len(paste) <= 4300


def test_T40_observed_stress():
    """Description, Risk: 'future stress testing now uses the observed decline'. stress.py applies each holding's
    6-20 Nov GBP move to the held, trimmed and full-budget books."""
    import stress
    S = stress.run()
    sh = S["shocks_gbp_pct"]
    assert sh["NVDA"] < -25 and sh["BTC"] < -15 and sh["WMT"] > 0          # the sell-off that happened
    for b in S["books"].values():
        for s in ("full", "ai_crypto"):
            v = b[s]
            assert abs(sum(v["per_asset_gbp"].values()) - v["pnl_gbp"]) < 0.05
    # scaled-to-platform-NAV figure vs the same shocks on the rebuilt positions: within £5 (rounded weights, NAV basis)
    assert abs(S["books"]["held_20nov"]["full"]["pnl_gbp"] - S["held_20nov_full_on_rebuilt_positions_gbp"]) < 5
    # the book as held is hit harder than P9's assumed AI sell-off in both scenarios (the point of the new stress)
    for s in ("full", "ai_crypto"):
        assert S["books"]["held_20nov"][s]["pnl_gbp"] < S["p9_ai_stress_gbp"]
    # the trim must lower the loss in both scenarios
    assert S["books"]["after_nvda_trim"]["full"]["pnl_gbp"] > S["books"]["held_20nov"]["full"]["pnl_gbp"]
    assert S["books"]["after_nvda_trim"]["ai_crypto"]["pnl_gbp"] > S["books"]["held_20nov"]["ai_crypto"]["pnl_gbp"]
    # buy-and-hold stress on the 13 Nov book vs H's daily-rebalanced realised return: same period, within 1 pt
    c = S["check_13nov_book"]
    assert abs(c["stress_pct"] - c["H_realised_pct"]) < 1.0


@archived_only
def test_T41_final_submitted_description():
    """Numeric-token check on the Description as submitted (Varrun's reworded v5, pasted 23 Nov): every number in the
    text must equal, after rounding, some value derived from the results or a listed fixed fact. It does not check which
    claim a number supports (swapping two sleeve targets would still pass); T43b binds the key sentences to their
    fields. Known exceptions: '1.335' (platform's implied 7 Nov rate is 1.3357 -> 1.336; locked text, recorded in the
    README) and '81'/'97%' (the en-dash range 81-97%, checked here against attr.systematic_range_pct = 80.5-97.2)."""
    import claims2
    unmatched = claims2.check(ROOT / "data" / "input" / "description_final_submitted.txt")
    assert sorted(unmatched) == sorted(["1.335", "81", "97%"]), unmatched
    lo, hi = R2["attr"]["systematic_range_pct"]
    assert round(lo) == 81 and round(hi) == 97
    assert round(R["A"]["implied_fx"][0]["implied_gbpusd"], 3) == 1.336   # documents the 1.335 discrepancy


def test_T42_latest_mark_to_market():
    """Pitch update: the unchanged 20 Nov book revalued at the 25 Nov close (the last common US/UK equity close before
    the 26 Nov pitch)."""
    import latest
    L = latest.run()
    book = json.loads((ROOT / "out" / "book_frozen_20261120.json").read_text())
    h = L["holdings"]
    assert {k: v["units"] for k, v in h.items()} == {
        {"BA.L": "BAE", "RR.L": "RR", "BTC-USD": "BTC"}.get(t, t): u for t, u in book["units"].items() if u > 0}
    assert abs(sum(v["value_gbp"] for v in h.values()) + L["cash_gbp"] - L["nav_gbp"]) < 0.05
    assert abs(sum(v["weight_pct"] for v in h.values()) + L["cash_pct"] - 100) < 0.1
    # change since 20 Nov adds up across holdings (cash unchanged, no trades)
    assert abs(sum(v["change_since_20nov_gbp"] for v in h.values()) - L["change_since_20nov_yahoo_gbp"]) < 0.05
    assert abs(sum(L["risk"]["risk_share_pct"].values()) - 100) < 0.1
    # independent checks straight from the snapshot (catch a pence or FX-direction slip)
    snap = json.loads((ROOT / "data" / "input" / "prices_25nov_snapshot.json").read_text())
    fx = snap["GBPUSD=X"]["price"]
    assert 1.2 < L["gbpusd"] < 1.45
    assert abs(h["BAE"]["value_gbp"] - 650.0542 * snap["BA.L"]["price"] / 100) < 0.05
    assert abs(h["NVDA"]["value_gbp"] - 123.5688 * snap["NVDA"]["price"] / fx) < 0.05
    for k, v in h.items():
        assert abs(v["change_since_20nov_gbp"]) < 0.25 * (v["value_gbp"] - v["change_since_20nov_gbp"]), k


def test_T43_ledger_correction():
    """The frozen book's ledger hash and the published ledger differ only by the Spyre trade date (20 vs 19 Nov),
    documented in out/book_frozen_20261120.correction.json. Final units, cash, closing NAV and cumulative P&L are the
    same under both dates; the daily path is not (19 Nov NAV +£6.78; 20 Nov daily P&L), and the correction says so.
    The hashes and the endpoint and path identities are checked on any snapshot; the recorded NAV and daily P&L amounts
    come from the archived snapshot and are pinned only there."""
    import hashlib
    corr = json.loads((ROOT / "out" / "book_frozen_20261120.correction.json").read_text())
    book = json.loads((ROOT / "out" / "book_frozen_20261120.json").read_text())
    led = (ROOT / "data" / "input" / "transactions.csv").read_bytes()
    assert hashlib.sha256(led).hexdigest() == corr["corrected_ledger_hash"]
    assert book["transactions_sha256"] == corr["frozen_hash_kept"]
    assert hashlib.sha256(led.replace(b"2026-11-19,SYRE", b"2026-11-20,SYRE")).hexdigest() == book["transactions_sha256"]
    # invariance limited to the endpoint; the daily path differences are the ones recorded in the correction
    import io
    tx19 = ledger.load_tx()
    tx20 = pd.read_csv(io.BytesIO(led.replace(b"2026-11-19,SYRE", b"2026-11-20,SYRE")), parse_dates=["date"])
    tx20["signed_units"] = np.where(tx20.side == "sell", -tx20.units, np.where(tx20.side == "buy", tx20.units, 0.0))
    assert ledger.accounting(tx19)["cash"] == ledger.accounting(tx20)["cash"] == book["cash_gbp"]
    assert ledger.accounting(tx19)["units"] == ledger.accounting(tx20)["units"]
    nav19 = ledger.daily("2026-11-20")["nav"]
    orig = ledger.load_tx
    try:
        ledger.load_tx = lambda: tx20
        nav20 = ledger.daily("2026-11-20")["nav"]
    finally:
        ledger.load_tx = orig
    # On every snapshot: same closing NAV under both dates, and the 19 Nov difference is exactly Spyre's 19 Nov
    # fill-to-close (units x 19 Nov sterling close - cost), handed back in the 20 Nov daily P&L.
    assert abs(nav19.iloc[-1] - nav20.iloc[-1]) < 0.005
    full = ledger.daily("2026-11-20")
    syre = tx19[tx19.asset == "SYRE"].iloc[0]
    fill_to_close = syre.units * full["gbp"].loc["2026-11-19", "SYRE"] + syre.gbp_cash
    assert abs(full["exec_pnl"].loc["2026-11-19", "SYRE"] - fill_to_close) < 1e-6
    gap19 = float(nav19.loc["2026-11-19"] - nav20.loc["2026-11-19"])
    dp19 = float(nav19.diff().loc["2026-11-20"]); dp20 = float(nav20.diff().loc["2026-11-20"])
    assert abs(gap19 - fill_to_close) < 1e-6 and abs((dp20 - dp19) - gap19) < 1e-6
    # The recorded amounts are figures from the archived snapshot: pinned there only (a fresh download revises closes)
    if data._ts() == ARCHIVED_SNAPSHOT:
        d = corr["daily_path_difference"]
        assert round(float(nav19.iloc[-1]), 2) == book["nav_yahoo_20nov"] and book["prices_file"] == ARCHIVED_SNAPSHOT
        assert round(gap19, 2) == d["nav_19nov_gbp"]
        assert (round(dp19, 2), round(dp20, 2)) == (d["pnl_20nov_gbp_published_ledger"], d["pnl_20nov_gbp_frozen_ledger"])


@archived_only
def test_T43b_named_claims():
    """The submitted Description's key sentences checked against their specific result fields (T41 only checks
    that every number appears somewhere)."""
    import claims2
    txt = (ROOT / "data" / "input" / "description_final_submitted.txt").read_text()
    vp = R2["var_platform"]
    assert "The two-week 95% VaR (£6,432) was breached, while the 99% VaR (£9,094) was not" in txt
    assert (vp["var95"], vp["var99"], vp["var95_breached"], vp["var99_breached"]) == (6432, 9094, True, False)
    assert "deviation of 2.2 standard deviations" in txt and round(-R2["z"]["platform_vs_3.91"], 1) == 2.2
    assert "£91,467 (-8.5%)" in txt and int(R2["platform"]["nav"] + 0.5) == 91467   # half rounds up, as written
    assert round(R2["platform"]["return_pct"], 1) == -8.5
    assert "1 was successful and 5 were unsuccessful" in txt and (R2["calls"]["hits"], R2["calls"]["n"]) == (1, 6)
    assert "56% of portfolio risk currently, falling to 46% after the proposed trim and 40% at full budget" in txt
    e = R2["E"]["runs"]["2026-11-20|156w"]
    assert (round(R2["K"]["book_before_ai_crypto_risk_pct"]), round(R2["K"]["book_after"]["ai_crypto_risk_share_pct"]),
            round(e["sleeve_rp_capped"]["ai_crypto_risk_share_pct"])) == (56, 46, 40)
    lo, hi = R2["attr"]["systematic_range_pct"]
    assert "Approximately 81–97% of the portfolio loss" in txt and (round(lo), round(hi)) == (81, 97)
    # each offset bound to its subject in the same sentence and to its own field; a swap of the two must fail
    claims2.offset_claims(txt, R2)
    assert (round(-R2["attr"]["execution_pct"]), round(-R2["attr"]["fx_pct"])) == (16, 11)
    swapped = txt.replace("offset 16%", "offset @@").replace("offset 11%", "offset 16%").replace("offset @@", "offset 11%")
    assert swapped != txt
    with pytest.raises(AssertionError):
        claims2.offset_claims(swapped, R2)
    detached = txt.replace("Sterling's depreciation offset 11% of the loss,", "Sterling's depreciation mattered. It offset 11% of the loss,")
    assert detached != txt
    with pytest.raises(AssertionError):
        claims2.offset_claims(detached, R2)
    assert "2.4 times our original AI sell-off stress estimate (£3,613)" in txt
    assert round(vp["loss_vs_ai_stress_x"], 1) == 2.4 and vp["ai_selloff_stress_gbp"] == -3613
    assert "one-year 95% VaR of £24,400" in txt and round(e["held"]["var95_1y_normal_gbp"], -2) == 24400
    # the sleeve line, sleeve by sleeve: targets and held weights bound to E (catches swapped sleeves)
    w, h = claims2.sleeve_pct(R2["E"]["w_star_pct"]), claims2.sleeve_pct(R2["E"]["held_weights_pct_yahoo_20nov"])
    line = "; ".join(f"{s} {w[s]}% ({h[s]}%)" for s in claims2.SLEEVES) + f"; cash {claims2.rnd(R2['E']['cash_pct'])}%."
    assert "Risk-budget weights, with current allocations in brackets: " + line in txt, line
    assert "AI semiconductors 12% (23%); US consumer 29% (25%)" in txt
    sw = txt.replace("AI semiconductors 12% (23%); US consumer 29% (25%)", "AI semiconductors 29% (25%); US consumer 12% (23%)")
    assert "Risk-budget weights, with current allocations in brackets: " + line not in sw
    # NVIDIA and Applied Materials against budget, from the decision table
    K = R2["K"]["decision_table"]
    assert (f"NVIDIA at {claims2.rnd(K['NVDA']['current_pct'], 1)}% against {claims2.rnd(K['NVDA']['w_star_pct'], 1)}%" in txt
            and f"Applied Materials at {claims2.rnd(K['AMAT']['current_pct'], 1)}% against {claims2.rnd(K['AMAT']['w_star_pct'], 1)}%" in txt)


def test_T44_strict_json():
    """Every JSON file in out/ parses under a strict parser (no NaN or Infinity), and the writers refuse NaN."""
    def bad(c):
        raise ValueError(f"non-standard JSON constant {c}")
    for f in sorted((ROOT / "out").glob("*.json")):
        json.loads(f.read_text(), parse_constant=bad)
    import run_all
    # the project's own writer (run_all.dumps writes results.json and results2.json), fed non-finite values of every
    # kind it can meet, must produce text a strict parser accepts, with each non-finite value written as null
    obj = {"x": float("nan"), "y": np.float64("inf"), "z": [np.nan, -np.inf, np.float32("nan")], "ok": np.float64(1.5),
           "nested": {"t": (float("-inf"), 2)}, "frame": pd.Series([1.0, np.nan]).to_dict()}
    out = run_all.dumps(obj)
    assert "NaN" not in out and "Infinity" not in out
    back = json.loads(out, parse_constant=bad)
    assert back == {"x": None, "y": None, "z": [None, None, None], "ok": 1.5, "nested": {"t": [None, 2]},
                    "frame": {"0": 1.0, "1": None}}


def test_T45_ledger_daily_later_start():
    """ledger.daily with a start after the first trades: opening units and cash come from the earlier trades, opening
    positions are marked from the preceding close, and NAV, units, daily holding P&L and daily execution P&L all match
    the full run on every shared date (first day included: -£799.39 holding P&L on 19 Nov in the archived snapshot);
    only fills inside the window are booked as execution."""
    full = ledger.daily("2026-11-20")
    for start in ("2026-11-10", "2026-11-14", "2026-11-19"):
        late = ledger.daily("2026-11-20", start=start)
        assert late["nav"].index[0] == pd.Timestamp(start)
        for k in ("nav", "units", "cash", "value", "hold_pnl", "exec_pnl"):
            assert np.allclose(late[k].values, full[k].loc[start:].values, atol=1e-6), (start, k)
    late = ledger.daily("2026-11-20", start="2026-11-19")
    assert abs(late["hold_pnl"].loc["2026-11-19"].sum()) > 1          # opening positions do earn holding P&L on day one
    if data._ts() == ARCHIVED_SNAPSHOT:
        assert round(float(late["hold_pnl"].loc["2026-11-19"].sum()), 2) == -799.39
    ex = late["exec_pnl"].sum()
    assert set(ex[ex.abs() > 1e-9].index) <= {"SYRE"}           # the only fill on or after 19 Nov
    assert abs(late["exec_pnl"].loc["2026-11-19", "SYRE"] - full["exec_pnl"].loc["2026-11-19", "SYRE"]) < 1e-9


def test_T46_random_date_spacing():
    """The random-date sampler uses the same spacing rule as the episodes (gaps > spacing sessions): the smallest
    allowed gap (spacing + 1) occurs, no smaller gap does, and both ends of the history can be drawn."""
    import drawdown as H
    N, n, spacing = 12, 2, 4
    allf = 2.0 ** np.arange(N)                       # each draw's sum identifies the two dates drawn
    means, _ = H.random_dates(allf, n, spacing, 4000, np.random.default_rng(0))
    pairs = set()
    for m in means:
        s = int(round(m * n))
        pairs.add(tuple(i for i in range(N) if s >> i & 1))
    gaps = {b - a for a, b in pairs}
    assert min(gaps) == spacing + 1 and max(gaps) == N - 1
    assert len(pairs) == sum(1 for a in range(N) for b in range(a + spacing + 1, N))   # every allowed pair is reachable


def test_T47_platform_reading_by_valuation_date():
    """results.json carries the platform reading for its own valuation date, never an earlier one, and every price and
    FX lookup in the reconciliation is bounded to that date. Reproduces the audit's offline check: a later FX mark
    present in the price file (as after a fresh download) must not leak into the 20 Nov reconciliation."""
    A, C = R["A"], R["C"]
    assert A["platform"]["valuation_date"] == ASOF == C["platform_valuation_date"]
    assert C["platform_pct"] == A["platform"]["platform_return_pct"] == round(100 * (91466.50 / 100000 - 1), 4)
    assert abs(C["z_platform_figure"]["P9_published_3.91"]["z"] - C["platform_pct"] / 3.91) < 1e-3
    assert A["platform"]["fx_date"] <= ASOF and all(not r["src"].startswith("yahoo") or r["src"][6:] <= ASOF for r in A["platform"]["rows"])
    old = A["platform_reconciliation_2026-11-19_intraday"]
    assert old["valuation_date"] == "2026-11-19" and old["fx_date"] <= "2026-11-19" and old["pending_excluded"] == ["SYRE"]
    assert all(v["match"] for v in old["units_check"].values())
    # the 19 Nov reading lacks quotes for some holdings while later closes are in the price file: each fallback must be
    # a close on or before 19 Nov, and the result is labelled a mixed-time reconstruction
    fb = [r for r in old["rows"] if r["src"].startswith("yahoo")]
    assert fb and all(r["src"][6:] <= "2026-11-19" for r in fb)
    assert old["timing"].startswith("mixed-time reconstruction") and A["platform"]["timing"].startswith("same-time")
    assert R2["platform"]["valuation_date"] == ASOF and R2["platform"]["nav"] == 91466.50
    with pytest.raises(KeyError):
        ledger.platform_snapshot("2026-11-25")
    # inject a later row (the 25 Nov FX mark) into the loaded prices and recompute the 20 Nov reconciliation
    snap25 = json.loads((ROOT / "data" / "input" / "prices_25nov_snapshot.json").read_text())
    orig = data.load
    def load_with_later_row(start=None, end=None, kind="adj", tickers=None):
        df = data._read(kind)
        extra = df.iloc[[-1]].copy(); extra.index = [pd.Timestamp("2026-11-25")]
        extra["GBPUSD=X"] = snap25["GBPUSD=X"]["price"]
        df = pd.concat([df[df.index < extra.index[0]], extra])
        if tickers is not None:
            df = df[list(tickers)]
        return df.loc[start:end]
    try:
        data.load = load_with_later_row
        rec = ledger.platform_reconciliation(ASOF)
    finally:
        data.load = orig
    assert rec["fx_date"] == ASOF and rec["fx"] == A["platform"]["fx"] and rec["nav_at_platform_prices"] == A["platform"]["nav_at_platform_prices"]
    # missing-quote case: drop Home Depot's platform quote, put a later (25 Nov) Home Depot close and FX mark into the
    # price file, and check the fallback takes Home Depot's 20 Nov close, not the later one
    orig_snap = ledger.platform_snapshot
    def snap_without_hd(valuation_date):
        snap, meta = orig_snap(valuation_date)
        snap = json.loads(json.dumps(snap)); snap["quoted_prices"].pop("HD")
        return snap, meta
    def load_with_later_hd(start=None, end=None, kind="adj", tickers=None):
        df = data._read(kind)
        extra = df.iloc[[-1]].copy(); extra.index = [pd.Timestamp("2026-11-25")]
        extra["GBPUSD=X"] = snap25["GBPUSD=X"]["price"]; extra["HD"] = 2 * float(df["HD"].dropna().iloc[-1])
        df = pd.concat([df[df.index < extra.index[0]], extra])
        if tickers is not None:
            df = df[list(tickers)]
        return df.loc[start:end]
    try:
        data.load, ledger.platform_snapshot = load_with_later_hd, snap_without_hd
        rec = ledger.platform_reconciliation(ASOF)
    finally:
        data.load, ledger.platform_snapshot = orig, orig_snap
    hd = [r for r in rec["rows"] if r["asset"] == "HD"][0]
    hd20 = float(data.load(None, ASOF, kind="raw")["HD"].dropna().iloc[-1])
    assert hd["src"] == f"yahoo {ASOF}" and hd["price"] == hd20 and rec["fx_date"] == ASOF


def test_T48_g2_claim_gate_logic():
    """The G2 gate requires claim_bar_met for a claimed rise and re-derives it from the published fields: it fails when
    the bar is not met (the published result: only AMAT and HD rise), fails when only two companies rise even with the 99%
    lower bound above zero, and passes with three rising and the bound above zero. Without the bar no G2 token is
    allowed in a text, so an unchecked G2 number cannot pass the numeric-token check."""
    import copy
    import claims2
    g = R2["G"]["G2"]
    if not g["claim_bar_met"]:
        with pytest.raises(AssertionError):
            claims2.g_gate(R2)
    def fake(bar, lo99, rises):
        r = copy.deepcopy(R2)
        r["G"]["G2"].update(claim_bar_met=bar, rises_per_ticker=rises, exceptions=[t for t, x in rises.items() if not x])
        r["G"]["G2"]["pooled_diff_20_1"]["ci99"] = [lo99, 0.8]
        return r
    two = {"NVDA": False, "WMT": False, "AMAT": True, "HD": True}
    three = {"NVDA": False, "WMT": True, "AMAT": True, "HD": True}
    for bad in (fake(False, 0.2, two), fake(True, 0.2, two), fake(True, -0.01, three), fake(False, 0.2, three)):
        with pytest.raises(AssertionError):
            claims2.g_gate(bad)
    claims2.g_gate(fake(True, 0.2, three))
    if data._ts() == ARCHIVED_SNAPSHOT:                  # published result: bar not met, so no G2 token is allowed
        assert g["claim_bar_met"] is False and sorted(g["exceptions"]) == ["NVDA", "WMT"]
        m = claims2.claims_map()
        assert not any(src.startswith("G2") for srcs in m.values() for src in srcs)
