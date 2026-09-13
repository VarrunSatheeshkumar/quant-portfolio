"""A21/E6/E7: liquidation print days by first-of-month, OI coverage (>=2020-09-01), sealed (+/-3d purge) vs training. Run from btc-public/."""
import pandas as pd
l = pd.read_parquet("data/raw/liquidations.parquet"); t = pd.to_datetime(l["ts"], utc=True)
d = pd.DatetimeIndex(sorted(t.dt.normalize().unique()))
U = lambda s: pd.Timestamp(s, tz="UTC")
blk = lambda x: ((x>=U("2021-12-29"))&(x<U("2023-01-04")))|((x>=U("2025-08-29"))&(x<U("2026-09-04")))
first = d[d.day==1]; oi = first>=U("2020-09-01")
print("distinct print dates", len(d), "| all on the 1st:", bool((d.day==1).all()))
print("1st-of-month print days", len(first), "| OI-covered", int(oi.sum()), "| OI-covered & sealed(+purge)", int((blk(first)&oi).sum()),
      "| OI-covered training (<2026-09-01)", int(((~blk(first))&oi&(first<U("2026-09-01"))).sum()))
