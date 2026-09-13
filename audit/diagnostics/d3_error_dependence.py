"""E4: training-row dependence of Model A log-vol forecast errors at 1h and 4h. Run from btc-public/."""
import pandas as pd, numpy as np
g = pd.read_parquet("data/grid/grid.parquet"); g = g.set_index(pd.DatetimeIndex(g["ts"]))[["tgt_logrv_1h","tgt_logrv_4h"]]
m = pd.read_parquet("data/interim/model_a.parquet"); m = m.set_index(pd.DatetimeIndex(m["ts"]))
if g.index.tz is None: g.index = g.index.tz_localize("UTC")
j = m.join(g, how="inner"); U = lambda s: pd.Timestamp(s, tz="UTC")
tr = ~(((j.index>=U("2021-12-29"))&(j.index<U("2023-01-04")))|((j.index>=U("2025-08-29"))&(j.index<U("2026-09-04")))|(j.index>=U("2026-09-01")))
t = j[tr].dropna(subset=["sigma_hat_1h","sigma_hat_4h","tgt_logrv_1h","tgt_logrv_4h"])
e1 = np.log(t["sigma_hat_1h"]) - t["tgt_logrv_1h"]; e4 = np.log(t["sigma_hat_4h"]) - t["tgt_logrv_4h"]
print("training rows", len(t), "| R2 1h/4h", round(1-np.var(e1)/np.var(t["tgt_logrv_1h"]),3), round(1-np.var(e4)/np.var(t["tgt_logrv_4h"]),3))
print("corr(err1h, err4h) row-level", round(np.corrcoef(e1,e4)[0,1],3))
d = pd.DataFrame({"e1":e1**2,"e4":e4**2}).groupby(t.index.floor("D")).mean()
print("corr(daily MSE 1h, 4h)", round(d.corr().iloc[0,1],3), "over", len(d), "days")
print("autocorr err1h lag 1/12/288:", round(e1.autocorr(1),3), round(e1.autocorr(12),3), round(e1.autocorr(288),3))
print("autocorr err4h lag 1/48/288:", round(e4.autocorr(1),3), round(e4.autocorr(48),3), round(e4.autocorr(288),3))
print("autocorr daily MSE1h lag 1/7/30:", round(d.e1.autocorr(1),3), round(d.e1.autocorr(7),3), round(d.e1.autocorr(30),3))
