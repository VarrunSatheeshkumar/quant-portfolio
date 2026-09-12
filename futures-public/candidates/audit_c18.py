"""C18 audit: a cleared result above its plausible band is audited before it is recorded.
Refutation clauses: (1) the alpha is mostly funding accrual with a price leg that works
against it; (2) it lives in 2020-21 only; (3) it depends on names that vanish inside
the sample; (4) it does not survive a realistic cost; (5) beta is doing the work."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C          # noqa: E402

f = pd.read_parquet(C.CAND / "binance_funding.parquet")
k = pd.read_parquet(C.CAND / "binance_klines_1d.parquet")
px = k.pivot(index="open_time", columns="symbol", values="close").sort_index()
fr = f.pivot_table(index=f["fundingTime"].dt.normalize(), columns="symbol", values="fundingRate", aggfunc="sum").reindex(px.index).fillna(0.0).where(px.notna())
w = C.c18_weekly()
rows = []
for i, (t, row) in enumerate(w.iterrows()):
    if i + 1 >= len(w):
        break
    t1 = w.index[i + 1]
    ret = px.loc[t1] / px.loc[t] - 1
    fund = fr.loc[t + pd.Timedelta(days=1): t1].sum()
    lo, hi = row["long"], row["short"]
    rows.append(dict(date=t, price=ret.reindex(lo).mean() - ret.reindex(hi).mean(),
                     funding=-fund.reindex(lo).mean() + fund.reindex(hi).mean(),
                     missing_t1=int(ret.reindex(list(lo) + list(hi)).isna().sum()),
                     sig_lo=float(fr.loc[t - pd.Timedelta(days=7): t - pd.Timedelta(days=1)].sum().reindex(lo).mean()),
                     sig_hi=float(fr.loc[t - pd.Timedelta(days=7): t - pd.Timedelta(days=1)].sum().reindex(hi).mean())))
a = pd.DataFrame(rows).set_index("date") * 1.0
a[["price", "funding", "sig_lo", "sig_hi"]] *= 100
tot = a.price + a.funding
def line(name, s):
    se = C.block_se(s.values, s.index)
    return f"| {name} | {s.mean():+.3f} | {se:.3f} | {s.mean()/se:+.2f} | {len(s)} |"
_, df = C.alpha_on_btc(w.ls * 100, w.btc * 100)
X = np.column_stack([np.ones(len(df)), df.x.values]); beta = np.linalg.lstsq(X, df.y.values, rcond=None)[0]
L = ["# C18 audit — before recording a result above its band", "",
     "Long-short weekly return decomposed into the price leg and the funding leg (both %/week, month-block SE).", "",
     "| component / period | mean | SE | t | weeks |", "|---|---|---|---|---|",
     line("total (all)", tot), line("price leg (all)", a.price), line("funding leg (all)", a.funding),
     line("total 2020-02 to 2021-12", tot.loc[:"2021-12-31"]), line("total 2022-01 to 2026-08", tot.loc["2022-01-01":]),
     line("price leg 2022+", a.price.loc["2022-01-01":]), line("funding leg 2022+", a.funding.loc["2022-01-01":]), "",
     f"* signal at entry: bottom-quintile funding {a.sig_lo.mean():+.3f} %/week, top-quintile {a.sig_hi.mean():+.3f} %/week (7-day sums)",
     f"* beta of the long-short on BTC: {beta[1]:+.3f}; alpha {beta[0]:+.3f} vs raw mean {df.y.mean():+.3f} %/week",
     f"* names in a leg with no price a week later (dropped from the leg mean): {int(a.missing_t1.sum())} of {int((w.long.str.len() + w.short.str.len()).sum())} leg-slots ({a.missing_t1.sum() / (w.long.str.len() + w.short.str.len()).sum():.2%})",
     f"* cost sensitivity at 41% weekly turnover: 20 bp round trip → {0.41*0.20:.2f}; 50 bp → {0.41*0.50:.2f}; 100 bp → {0.41*1.00:.2f} %/week against +{tot.mean():.2f}",
     "* survivorship: the universe is perpetuals still trading in 2026-09 with ≥ 3 years of history; perpetuals delisted before then are absent. A high-funding name that died would have paid the short leg; a negative-funding name that died would have cost the long leg. The direction of the bias is not determinable from this data and is recorded as an open limitation.", "",
     "## Verdict", ""]
clauses = [("price leg works against the funding (price t <= -2)", a.price.mean() / C.block_se(a.price.values, a.price.index) <= -2),
           ("lives in 2020-21 only (2022+ total t < 2)", tot.loc["2022-01-01":].mean() / C.block_se(tot.loc["2022-01-01":].values, tot.loc["2022-01-01":].index) < 2),
           ("depends on names vanishing mid-week (> 2% of leg-slots)", a.missing_t1.sum() / (w.long.str.len() + w.short.str.len()).sum() > 0.02),
           ("does not survive 50 bp round trip", tot.mean() - 0.41 * 0.50 <= 0),
           ("beta does the work (|beta| > 0.3)", abs(beta[1]) > 0.3)]
for name, fired in clauses:
    L.append(f"* {name}: **{'FIRED' if fired else 'not fired'}**")
ok = not any(f for _, f in clauses)
L += ["", "**AUDIT " + ("PASSED — recorded as cleared, with the survivorship limitation attached." if ok else "FAILED — recorded as cleared-but-suspect; see fired clauses.") + "**"]
(C.config.REPORTS / "candidates" / "C18_AUDIT.md").write_text("\n".join(L))
print("\n".join(L))
