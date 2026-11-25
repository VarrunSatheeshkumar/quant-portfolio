"""Component J: thesis-break scorecard. Status is a pure function of data/input/thesis_evidence.csv
under the frozen rules.

Two copies of the rules are kept:
  thesis_rules.original.json  the file hashed at 2026-11-21T21:00:26Z, byte for byte (digest in thesis_rules.lock)
  thesis_rules.json           the publication copy the code reads: the original with the wording edits in
                              PUBLICATION_EDITS applied and nothing else (digest in thesis_rules.published.lock)
rules_hash_ok() checks both digests and that the publication copy is exactly the original with those edits."""
import csv
import hashlib
import json

from config import ROOT

INP = ROOT / "data" / "input"
NO_THESIS = {"BTC-USD": "variance allocation, no directional call", "SYRE": "no documented case (the team has not written one)"}

# (original text, published text). Wording only: no rule, threshold or status mapping changes.
PUBLICATION_EDITS = [
    ("copied verbatim 2026-11-21 UK evening, before any evidence collection",
     "copied 2026-11-21 UK evening; hashed 21:00:26 UTC before the final flags were recorded, after S1 had been read "
     "(see R2) and after the snapshot used as S2 was downloaded (21 Nov 20:58:35 UTC). Publication copy: wording edits listed in "
     "src/scorecard.py; the hashed original is thesis_rules.original.json"),
    ("Disclosure: the planner had seen S1", "Disclosure: S1 had been read"),
    ("when setting the 2% bar", "when the 2% bar was set"),
]


def _sha(name):
    return hashlib.sha256((INP / name).read_bytes()).hexdigest()


def published_from_original():
    txt = (INP / "thesis_rules.original.json").read_text()
    for old, new in PUBLICATION_EDITS:
        assert txt.count(old) == 1, old
        txt = txt.replace(old, new)
    return txt


def rules_hash_ok():
    """True only if (1) the original still has the digest locked at 21:00:26Z, (2) the publication copy has the digest
    recorded in thesis_rules.published.lock, and (3) the publication copy equals the original with PUBLICATION_EDITS."""
    h, t = (INP / "thesis_rules.lock").read_text().split()
    hp = (INP / "thesis_rules.published.lock").read_text().split()[0]
    ok = (_sha("thesis_rules.original.json") == h and _sha("thesis_rules.json") == hp
          and (INP / "thesis_rules.json").read_text() == published_from_original())
    return ok, t


def status_of(triggers):
    t = [x for x in triggers if x in ("HARD", "SOFT")]
    if "HARD" in t:
        return "CUT"
    n = t.count("SOFT")
    return "REVIEW-TRIM" if n >= 2 else "REVIEW" if n == 1 else "HOLD"


def score(rows=None):
    rows = rows if rows is not None else list(csv.DictReader(open(INP / "thesis_evidence.csv")))
    out = {}
    for r in rows:
        out.setdefault(r["asset"], {"rules": {}, "triggers": []})
        out[r["asset"]]["rules"][r["rule"]] = {k: r[k] for k in ("finding", "trigger", "url", "source_class")}
        out[r["asset"]]["triggers"].append(r["trigger"])
    for a, v in out.items():
        v["status"] = status_of(v["triggers"])
    for a, why in NO_THESIS.items():
        out[a] = {"rules": {}, "triggers": [], "status": "NO THESIS", "note": why}
    return out


if __name__ == "__main__":
    s = score()
    ok, t = rules_hash_ok()
    print("rules hash ok", ok, t)
    for a, v in s.items():
        print(a, v["status"], v["triggers"])
