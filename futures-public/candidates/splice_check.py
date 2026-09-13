"""Verify the splice premise against exchange settlement data.

EIA republishes NYMEX daily settlements for the first and second nearby contracts
of crude (RCLC1/2), natural gas (RNGC1/2), heating oil / ULSD and RBOB. Those are
exchange numbers, not a vendor's splice, so they can say whether Yahoo's `=F`
series (a) holds the expiring contract through its last trading day, (b) switches
to the new front the next business day, and (c) leaks the calendar spread as that
day's price change. Every expiry is checked; five per market are printed by hand.
"""

import io
import re
import sys

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, ".")
import config                      # noqa: E402
from stages import rolls           # noqa: E402

H = {"User-Agent": "Mozilla/5.0"}
EIA = {   # market -> (contract-1 series, contract-2 series, folder)
    "CL": ("RCLC1", "RCLC2", "pet"),
    "NG": ("RNGC1", "RNGC2", "ng"),
    "HO": ("EER_EPD2F_PE1_Y35NY_DPG", "EER_EPD2F_PE2_Y35NY_DPG", "pet"),
    "RB": ("EER_EPMRR_PE1_Y35NY_DPG", "EER_EPMRR_PE2_Y35NY_DPG", "pet"),
}
TOL = {"CL": 0.011, "NG": 0.006, "HO": 0.0006, "RB": 0.0006}   # EIA rounds: CL 2 dp, NG 2-3 dp, HO/RB 3 dp (Yahoo 3-4 dp)
MONTHS = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def fetch_series(series, folder):
    cache = config.RAW / "cand" / f"eia_{series}.parquet"
    if cache.exists():
        s = pd.read_parquet(cache)["v"]
        if s.dropna().empty:
            raise ValueError(f"{series}: cached EIA series has no settlements")
        return s
    url = f"https://www.eia.gov/dnav/{folder}/hist/{series}D.htm"
    response = requests.get(url, headers=H, timeout=90)
    response.raise_for_status()
    s = parse_hist_page(response.text)
    cache.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"v": s}).to_parquet(cache)
    return s


def parse_hist_page(html):
    """The EIA history page is one row per week: a 'YYYY Mon-DD to Mon-DD' cell then
    five value cells, Monday to Friday, blank where there was no trading."""
    out = {}
    rows = re.findall(r"<td class=.B6.>(?:&nbsp;|\s)*(\d{4}) (\w{3})-\s*(\d+) to [^<]*</td>((?:\s*<td class=.B3.>[^<]*</td>){5})", html)
    for y, mon, d, cells in rows:
        start = pd.Timestamp(year=int(y), month=MONTHS[mon], day=int(d))
        vals = re.findall(r"<td class=.B3.>([^<]*)</td>", cells)
        for i, v in enumerate(vals):
            v = v.replace("&nbsp;", "").strip()
            if v:
                out[start + pd.Timedelta(days=i)] = float(v)
    if not out:
        raise ValueError("EIA history page contains no settlement observations")
    s = pd.Series(out).sort_index()
    s.index.name = "date"
    return s


def check_market(m):
    c1 = fetch_series(EIA[m][0], EIA[m][2])
    c2 = fetch_series(EIA[m][1], EIA[m][2])
    y = pd.read_parquet(config.RAW / f"{m}.parquet")["close"]
    y.index = pd.DatetimeIndex(y.index).tz_localize(None).normalize() if getattr(y.index, "tz", None) is not None else pd.DatetimeIndex(y.index).normalize()
    j = pd.concat([y.rename("yahoo"), c1.rename("c1"), c2.rename("c2")], axis=1).loc["2000-01-01":config.END].dropna(subset=["yahoo", "c1"])
    if j.empty or j.c2.dropna().empty:
        raise ValueError(f"{m}: no overlapping Yahoo/C1/C2 settlement observations")
    j["match_c1"] = (j.yahoo - j.c1).abs() <= TOL[m]
    j["match_c2"] = (j.yahoo - j.c2).abs() <= TOL[m]
    exp = rolls.expiries(m, config.UNIVERSE[m]["months"], j.index.min(), j.index.max())
    rows = []
    for e in exp:
        pos = j.index.searchsorted(e)
        if pos >= len(j) - 1 or pos < 1:
            continue
        E = j.index[pos] if j.index[pos] == e else None          # expiry day must be a bar
        if E is None:
            continue
        S = j.index[pos + 1]                                        # the next bar: expected switch day
        r = dict(expiry=E.date(), switch=S.date(),
                 yahoo_E=j.yahoo[E], c1_E=j.c1[E], c2_E=j.c2.get(E, np.nan),
                 yahoo_S=j.yahoo[S], c1_S=j.c1[S],
                 held_to_expiry=bool(j.match_c1[E]) and not bool(j.match_c2[E]),
                 new_front_on_switch=bool(j.match_c1[S]),
                 spread_E=float(j.c2.get(E, np.nan) - j.c1[E]),            # the fake part of the switch-day change
                 yahoo_change_S=float(j.yahoo[S] - j.yahoo[E]),
                 real_move_S=float(j.c1[S] - j.c2.get(E, np.nan)))            # the new contract's own move
        rows.append(r)
    if not rows:
        raise ValueError(f"{m}: no eligible expiry/switch observations")
    t = pd.DataFrame(rows)
    if not np.isfinite(t[["yahoo_E", "c1_E", "c2_E", "yahoo_S", "c1_S"]].to_numpy()).all():
        raise ValueError(f"{m}: missing or non-finite settlements at an eligible expiry/switch")
    t["identity_ok"] = (t.yahoo_change_S - (t.spread_E + t.real_move_S)).abs() <= 3 * TOL[m]
    t2 = t[pd.to_datetime(t.expiry) >= "2002-01-01"]
    j2 = j.loc["2002-01-01":]
    if t2.empty or j2.empty:
        raise ValueError(f"{m}: no eligible observations from 2002 onward")
    overall = dict(market=m, days=len(j), share_days_equal_c1=float(j.match_c1.mean()),
                   share_days_equal_c1_2002on=float(j2.match_c1.mean()),
                   held_to_expiry_2002on=float(t2.held_to_expiry.mean()), new_front_2002on=float(t2.new_front_on_switch.mean()),
                   n_expiries=len(t), held_to_expiry=float(t.held_to_expiry.mean()),
                   new_front_on_switch=float(t.new_front_on_switch.mean()),
                   identity_ok=float(t.identity_ok.mean()),
                   mean_spread_E=float(t.spread_E.mean()), share_spread_pos=float((t.spread_E > 0).mean()),
                   mean_abs_spread_E=float(t.spread_E.abs().mean()), mean_abs_real_move=float(t.real_move_S.abs().mean()))
    return overall, t, j


def main():
    checked = {}
    for m in EIA:
        try:
            checked[m] = check_market(m)
        except Exception as e:      # noqa: BLE001
            raise RuntimeError(f"splice check incomplete for {m}: {e}; no verdict or report written") from e
    lines = ["# Splice premise check — Yahoo `=F` against NYMEX settlements (via EIA)", "",
             "Premise under test: Yahoo's series holds each contract through its last trading day (exchange rule, `stages/rolls.py`), "
             "switches to the new front on the next bar, and that bar's close-to-close change equals the calendar spread at expiry "
             "plus the new contract's own move. Settlements are NYMEX's, republished by EIA for the two nearest contracts.", ""]
    summ = []
    for m, (o, t, j) in checked.items():
        summ.append(o)
        t.to_parquet(config.RAW / "cand" / f"splice_check_{m}.parquet")
        # five by hand: spread across the sample, including the largest spread and April 2020 for CL
        pick = t.iloc[np.unique(np.linspace(0, len(t) - 1, 4).astype(int))]
        big = t.iloc[[int(t.spread_E.abs().idxmax())]]
        five = pd.concat([pick, big]).drop_duplicates("expiry").head(5)
        lines += [f"## {m}", "",
                  f"* {o['days']} overlapping days; Yahoo close equals NYMEX contract-1 settlement on **{o['share_days_equal_c1']:.1%}** of them",
                  f"* {o['n_expiries']} expiries: held to expiry {o['held_to_expiry']:.1%}; new front on the next bar {o['new_front_on_switch']:.1%}; "
                  f"switch-day change = spread + new contract's move on {o['identity_ok']:.1%}",
                  f"* mean spread at expiry (C2 − C1) {o['mean_spread_E']:+.4f} ({o['share_spread_pos']:.0%} positive); "
                  f"mean |spread| {o['mean_abs_spread_E']:.4f} vs mean |real move| of the new contract {o['mean_abs_real_move']:.4f}",
                  "", "Five expiries by hand:", "",
                  five[["expiry", "switch", "yahoo_E", "c1_E", "c2_E", "yahoo_S", "c1_S", "spread_E", "real_move_S", "yahoo_change_S",
                        "held_to_expiry", "new_front_on_switch", "identity_ok"]].to_markdown(index=False), ""]
        # where does it fail? list the failures
        bad = t[~(t.held_to_expiry & t.new_front_on_switch)]
        if len(bad):
            lines += [f"Expiries where the premise does not hold ({len(bad)}):", "",
                      bad[["expiry", "switch", "yahoo_E", "c1_E", "c2_E", "yahoo_S", "c1_S"]].head(25).to_markdown(index=False), ""]
    S = pd.DataFrame(summ)
    lines += ["## Verdict", "", S.round(4).to_markdown(index=False), ""]
    ok = len(S) >= 3 and (S.held_to_expiry_2002on.min() >= 0.9) and (S.new_front_2002on.min() >= 0.9)
    lines += ["**PREMISE " + ("HOLDS" if ok else "FAILS") + "** — " +
              ("Yahoo holds the expiring contract through its last trading day and the switch-day change carries the calendar spread; "
               "C1 and C2 stand. Checked on energy only: EIA republishes NYMEX settlements and nothing free does the same for CBOT/COMEX/ICE. "
               "For grains and softs the s0 switch signature (|change| anomaly z = 10–20 at expiry+1) is the only evidence; for metals the "
               "premise is known to differ (nearest contract of any month) and they are excluded from C2 by construction."
               if ok else "the splice does not behave as assumed; C1 and C2 are withdrawn and the ranking must be rewritten.")]
    (config.REPORTS / "candidates").mkdir(parents=True, exist_ok=True)
    (config.REPORTS / "candidates" / "SPLICE_CHECK.md").write_text("\n".join(lines))
    print(S.round(4).to_string())
    print("PREMISE", "HOLDS" if ok else "FAILS")


if __name__ == "__main__":
    main()
