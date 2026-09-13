"""A9/E5: traded notional of the C18 book per week, from the cached book. Equal weights 1/n per leg,
rebalanced to equal weight weekly; drift ignored. Run from futures-public/."""
import sys, numpy as np, pandas as pd
sys.path.insert(0, "."); from candidates import common as C
w = C.c18_weekly(); prev = None; rows = []
for t, row in w.iterrows():
    L, S = set(row["long"]), set(row["short"]); wt = {}
    for n in L: wt[n] = 1.0/len(L)
    for n in S: wt[n] = wt.get(n, 0) - 1.0/len(S)
    if prev is not None:
        pL, pS = prevsets
        rows.append(dict(traded=sum(abs(wt.get(n,0)-prev.get(n,0)) for n in set(wt)|set(prev)),
                         entries=len((L-pL)|(S-pS)), exits=len((pL-L)|(pS-S)), flips=len((L&pS)|(S&pL)),
                         gross=sum(abs(v) for v in wt.values())))
    prev, prevsets = wt, (L, S)
d = pd.DataFrame(rows)
print("weeks", len(w), "formation", w.index.min().date(), "->", w.index.max().date())
print("names/leg mean", round(np.mean([len(x) for x in w["long"]]),1), "max", max(len(x) for x in w["long"]))
print("union turnover (run.py definition) mean", round(w["turnover"].mean(),4), "charged 0.20*turnover =", round(w["turnover"].mean()*0.20,3), "%/wk")
print("gross sum|w| mean", round(d.gross.mean(),3))
print("sum|dw| per week, one-leg units: mean", round(d.traded.mean(),3), "median", round(d.traded.median(),3))
print("entries/exits/flips per week (both legs):", round(d.entries.mean(),1), round(d.exits.mean(),1), round(d.flips.mean(),1))
for bp in (5,10,25): print(f"cost at {bp} bp/side on sum|dw|: {d.traded.mean()*bp/1e4*100:.3f} %/wk")
