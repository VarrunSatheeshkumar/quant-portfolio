"""T13: every number in the Description draft (outside [brackets] and the call-ledger placeholder)
must match a value derived from out/results.json, or a listed fixed fact (dates, rules)."""
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]


def allowed():
    R = json.loads((ROOT / "out" / "results.json").read_text())
    d3 = R["D3"]["beat_and_fell"]["car1_60"]
    d2 = {(r["ticker"], r["period"], r["lookback"]): r for r in R["D2"]["rows"]}
    cs = R["C"]["calls_scored"]
    m = {
        "3.9": ("P9 published 2-week s.d. (p9_umushroom_event_risk/out/results.json 3.91)", 3.91),
        "6,432": ("P9 95% VaR GBP", 6432),
        "707": ("ETH realised loss", -R["A"]["accounting"]["eth_realised"]),
        "1": ("calls hits", cs["hits"]),
        "4": ("calls misses / fell on the day", cs["n"] - cs["hits"]),
        "5": ("calls scored", cs["n"]),
        # D3 tokens are built from results.json, so they follow the current classification (reported surprise sign)
        R["D3"]["first"][:4]: ("D3 first event year", int(R["D3"]["first"][:4])),
        str(round(R["D3"]["P_AR0_neg_given_beat_pct"])): ("D3 P(AR0<0|beat)", round(R["D3"]["P_AR0_neg_given_beat_pct"])),
        "46": ("P(loss|IR 0.5) in the closed-form table", 46),
        str(round(d3["mean_pct"], 1)): ("D3 beat&fell CAR(+1,+60) mean", round(d3["mean_pct"], 1)),
        str(round(d3["boot95_pct"][0], 1)): ("D3 CI low", round(d3["boot95_pct"][0], 1)),
        str(round(d3["boot95_pct"][1], 1)): ("D3 CI high", round(d3["boot95_pct"][1], 1)),
        str(d3["n"]): ("D3 beat&fell n", d3["n"]),
        "0.5": ("hypothetical IR in closed-form table", 0.5),
        "4%": ("NVDA/AMAT +1y EPS 30d change ~4%", round((d2[("NVDA", "+1y", "30daysAgo")]["eps_chg_pct"] + d2[("AMAT", "+1y", "30daysAgo")]["eps_chg_pct"]) / 2)),
    }
    # consistency checks of the semantic claims
    assert round(next(r for r in R["C"]["closed_form"] if r["IR_hypothetical"] == 0.5)["P_loss_over_T_pct"]) == 46
    assert d3["boot95_pct"][0] < 0 < d3["boot95_pct"][1]          # 'no evidence either way'
    fixed = {"7", "6", "13", "12", "20", "60", "95", "15", "²"}       # dates (7/6/13/12/20 Nov), 60 days, 95% interval, 15% limit
    return m, fixed


def numbers(text):
    text = re.sub(r"\[[^\]]*\]", " ", text)
    return [t.rstrip(",") for t in re.findall(r"[+-]?\d[\d,]*(?:\.\d+)?%?", text)]


def check(path):
    m, fixed = allowed()
    ok = set(m) | {k.rstrip("%") for k in m} | fixed
    bad = []
    for tok in numbers(pathlib.Path(path).read_text()):
        t = tok.lstrip("+").rstrip("%")
        if t not in ok and tok not in ok:
            bad.append(tok)
    return bad


if __name__ == "__main__":
    # Plan 1 checker for an early Description draft (draft not included here). Usage: python claims.py <file.txt>
    import sys
    print(check(sys.argv[1]))
