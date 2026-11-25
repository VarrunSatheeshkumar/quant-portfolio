"""Shared configuration. All estimation uses data with date <= CUTOFF."""
import pathlib
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "out"
CUTOFF = pd.Timestamp("2026-11-06")
PERIOD_START = pd.Timestamp("2026-11-07")
PERIOD_END = pd.Timestamp("2026-11-20")
SEED = 20261119
EST_WINDOW = (pd.Timestamp("2026-05-01"), CUTOFF)   # matches P9

HOLDINGS = ["NVDA", "WMT", "AMAT", "HD", "BA.L", "RR.L", "BTC-USD", "ETH-USD"]
FACTORS = ["SPY", "QQQ", "SMH", "SOXX", "XLP", "XLY", "XHB", "^FTSE", "ISF.L", "ITA"]
PEERS = ["AMD", "AVGO", "TSM", "MU", "LRCX", "KLAC", "ASML", "COST", "TGT", "KR", "LOW"]
OTHER = ["SYRE", "GBPUSD=X"]
ALL_TICKERS = HOLDINGS + FACTORS + PEERS + OTHER
USD = {"NVDA", "WMT", "AMAT", "HD", "BTC-USD", "ETH-USD", "SYRE", "SPY", "QQQ", "SMH", "SOXX",
       "XLP", "XLY", "XHB", "ITA", "AMD", "AVGO", "TSM", "MU", "LRCX", "KLAC", "ASML", "COST",
       "TGT", "KR", "LOW"}
PENCE = {"BA.L", "RR.L", "ISF.L"}   # quoted in GBp on Yahoo

# factor model per holding (market, sector); UK sector ITA is US-listed -> lagged one day + FX adj
FACTOR_MAP = {"NVDA": ("SPY", "SMH"), "AMAT": ("SPY", "SMH"), "WMT": ("SPY", "XLP"),
              "HD": ("SPY", "XLY"), "BA.L": ("^FTSE", "ITA"), "RR.L": ("^FTSE", "ITA")}
PEER_MAP = {"NVDA": ["AMD", "AVGO", "TSM", "MU", "LRCX", "KLAC", "ASML"],
            "AMAT": ["AMD", "AVGO", "TSM", "MU", "LRCX", "KLAC", "ASML"],
            "WMT": ["COST", "TGT", "KR"], "HD": ["LOW"]}

# ---- Plan 2 ----
ASOF = pd.Timestamp("2026-11-20")
SYRE_HISTORY_START = pd.Timestamp("2023-11-28")   # SYRE ticker effective (rename from Aeglea; Spyre acquired Jun 2023). Source: patsnap/RTTNews summary + SEC 8-K 0001193125-23-283693
P9_VAR95 = 6432
P9_VAR99 = 9094
SEED2 = 20261122
