"""E17: distribution of the option-fill parquet against fetch.py's schedule (Fridays from 2021-01-01, 00:00-04:00 UTC). Run from btc-public/."""
import pandas as pd
o = pd.read_parquet("data/raw/option_fills.parquet"); t = pd.to_datetime(o["ts"], utc=True)
print("n fills", len(o), "| distinct entry_day", o["entry_day"].nunique(), o["entry_day"].min(), "->", o["entry_day"].max())
print("by year", t.dt.year.value_counts().sort_index().to_dict())
print("by weekday (0=Mon)", t.dt.weekday.value_counts().sort_index().to_dict())
print("by hour UTC", t.dt.hour.value_counts().sort_index().to_dict())
