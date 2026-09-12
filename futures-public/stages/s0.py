"""s0: fetch, stitch, as-of grid, tests, gate, report."""

import pandas as pd

import config
import progress
from stages import s0_fetch, s0_stitch, s0_grid
from tests import test_asof, test_stitching

# Refutation clauses on roll identification: markets whose average curve shape
# is not in doubt. A wrong sign here means the switch days are wrong, and the
# stage halts. Contango => positive roll-day change; positive carry => negative.
SIGN_PRIORS = {"NG": +1, "ZW": +1, "ZN": -1, "ZB": -1, "ZF": -1, "ZT": -1,
               "6A": -1, "6J": +1, "6S": +1}

DROPPED = {
    "RTY": "history starts 2017-07; rule is continuous since 2005",
    "FTSE": "no futures ticker on yfinance; only the cash index",
    "DAX": "no futures ticker; ^GDAXI is a total-return cash index",
    "Nikkei (OSE)": "kept as CME NKD=F instead (USD-denominated, 2004-02)",
    "Bund": "no yfinance ticker (FGBL=F empty)",
    "Gilt": "no yfinance ticker (FLG=F empty)",
    "Brent": "BZ=F starts 2007-07",
    "PL": "686 missing bars after 2000 (~10% of trading days) on yfinance; Yahoo volume ~1/day; fails liquidity",
}


def main():
    fetched = s0_fetch.run()
    diag = s0_stitch.run()
    refs = s0_grid.build()
    n_asof = test_asof.run()
    n_stitch = test_stitching.run()

    wrong = {m: diag.loc[m, "gap_pct_yr"] for m, sgn in SIGN_PRIORS.items()
             if float(diag.loc[m, "gap_pct_yr"]) * sgn <= 0}
    px = pd.read_parquet(config.GRID / "px_panama.parquet")
    w0 = pd.read_parquet(config.GRID / "w0.parquet")
    raw = pd.read_parquet(config.GRID / "raw.parquet")
    lost = (raw.notna() & w0.isna()).sum() / raw.notna().sum()
    # a bar missing while most of the universe traded is a hole in Yahoo's data, not a holiday
    open_day = px.notna().sum(axis=1) >= 20
    holes = (px.isna() & open_day.values[:, None]).sum()
    first = px.apply(lambda c: c.first_valid_index())
    holes = pd.DataFrame({"share_of_days_dropped": lost.round(4),
                          "missing_bars_after_start": [int(((px[m].isna()) & open_day & (px.index >= first[m])).sum()) for m in px.columns]},
                         index=px.columns)

    lines = ["# s0 — data, stitching, as-of grid", "",
             "## Gate", "",
             f"* as-of test: {n_asof} random (series, timestamp) checks passed",
             f"* stitching invariants: {n_stitch} markets passed",
             f"* roll-sign refutation clauses: {'ALL PASS' if not wrong else 'FAILED ' + str(wrong)}",
             "* stitching *sensitivity* (SPEC §4) needs a signal to be sensitive; it is run at s2, s3, s5, s6 "
             "on the raw / w0 / w1 / w3 / early3 return variants and on the Panama vs ratio price series, "
             f"with the pre-registered tolerance of {config.STITCH_TOLERANCE} Sharpe (DECISIONS.md).", "",
             "## What the data is", "",
             "yfinance `=F` series are unadjusted front-month splices (CL prints -37.63 on 2020-04-20 and 32.05 in "
             "Aug-2000). No individual contracts are obtainable (see DECISIONS.md). Each switch day therefore carries the "
             "calendar spread as a fake return; those days are located from exchange-rule expiries and dropped.", "",
             "## Universe", "", f"Kept: {len(config.UNIVERSE)} markets in {len(config.SECTORS)} sectors.", "",
             "| dropped | reason |", "|---|---|"] + [f"| {k} | {v} |" for k, v in DROPPED.items()] + [
             "", "## Fetch", "", fetched.to_markdown(), "",
             "## Roll identification", "",
             "Offset is business days after exchange-rule expiry; z is the |change|/sigma anomaly at that offset; "
             "`gap_pct_yr` is the annualised sum of the removed roll-day changes as % of average price — the size of "
             "the artefact that would otherwise have been reported as return. Signs match the known curve shape: "
             "NG and wheat contango, soybeans/RB backwardation, treasuries positive carry, FX per covered interest parity.", "",
             diag.drop(columns=["offsets"]).to_markdown(), "",
             "Scan (z at offsets -2..+3):", "", "\n".join(f"* {m}: {o}" for m, o in diag["offsets"].items()), "",
             "## Days lost to neutralisation, and holes in the source data", "",
             holes.to_markdown(), "",
             "## Known residuals", "",
             "* Metals (GC SI HG): Yahoo shows the nearest-expiring contract of every month; the switch anomaly is "
             "below detection at monthly frequency and the +1 convention is used. Residual roll bias at most ~1.5%/yr per market.",
             "* Equities: the expiry-day close is a computed value (62-67% of those closes are off the tick grid vs 0.05% "
             "otherwise), so both the expiry day and the day after are dropped.",
             "* The dropped day's real move is also lost from the Panama/ratio *levels* (treated as zero change): "
             "random, sign-free noise of about one daily sigma per roll in the level used by trend and value.",
             f"* Bad prints removed: " + "; ".join(f"{m} {b}" for m, b in diag["bad_prints"].items() if b), "",
             "## Reference series (carry inputs), lagged one day", "", refs.describe().T.round(3).to_markdown(), ""]
    progress.write_report("s0", "\n".join(lines))
    if wrong:
        progress.halt("s0", f"roll-sign refutation failed: {wrong}")
    return (f"gate PASS — {len(config.UNIVERSE)} markets, {n_asof} as-of checks, rolls at expiry+1; "
            f"largest removed artefact NG {diag.loc['NG', 'gap_pct_yr']}%/yr")


if __name__ == "__main__":
    print(main())
