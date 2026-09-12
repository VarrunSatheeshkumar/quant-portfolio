"""Constants. The single place values live.

Contract specifications are exchange facts (CME/COMEX/NYMEX/CBOT/ICE) as of 2026.
`mult` is dollars per 1.0 unit of the price *as Yahoo quotes it*, which is not
always the exchange's own unit (grains are quoted in cents/bushel, coffee in
cents/lb), so notional = close * mult is checked for plausibility in s0.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw"
GRID = ROOT / "data" / "grid"
STAGES = ROOT / "data" / "stages"
REPORTS = ROOT / "reports"
STAGE_REPORTS = REPORTS / "stage_reports"

START = "2000-01-01"
END = "2026-09-09"            # last bar used anywhere; fixed so the numbers in WRITEUP.md reproduce
SEED = 17

# ---- hold-out: most recent two years, opened once in s9.
# Purge of 260 business days ~ one year: longer than any lookback used by a signal
# (value uses a five-year mean, but that is a *feature* window not a target
# horizon; the purge guards target leakage, and the longest holding horizon is
# far below a year).
SEALED_START = "2024-09-01"
PURGE_DAYS = 30

# ---- universe. Fields: yfinance ticker, sector, contract months (active),
# mult ($ per 1.0 quote), tick (quote units), spread (typical, in ticks).
UNIVERSE = {
    # equity indices
    "ES":  dict(yf="ES=F",  sector="equity", months=[3, 6, 9, 12], mult=50.0,   tick=0.25,      spread=1),
    "NQ":  dict(yf="NQ=F",  sector="equity", months=[3, 6, 9, 12], mult=20.0,   tick=0.25,      spread=1),
    "YM":  dict(yf="YM=F",  sector="equity", months=[3, 6, 9, 12], mult=5.0,    tick=1.0,       spread=1),
    "NKD": dict(yf="NKD=F", sector="equity", months=[3, 6, 9, 12], mult=5.0,    tick=5.0,       spread=2),
    # rates
    "ZN":  dict(yf="ZN=F",  sector="rates",  months=[3, 6, 9, 12], mult=1000.0, tick=1 / 64,    spread=1),
    "ZB":  dict(yf="ZB=F",  sector="rates",  months=[3, 6, 9, 12], mult=1000.0, tick=1 / 32,    spread=1),
    "ZF":  dict(yf="ZF=F",  sector="rates",  months=[3, 6, 9, 12], mult=1000.0, tick=1 / 128,   spread=1),
    "ZT":  dict(yf="ZT=F",  sector="rates",  months=[3, 6, 9, 12], mult=2000.0, tick=1 / 128,   spread=1),
    # fx
    "6E":  dict(yf="6E=F",  sector="fx",     months=[3, 6, 9, 12], mult=125000.0,   tick=0.00005,   spread=1),
    "6J":  dict(yf="6J=F",  sector="fx",     months=[3, 6, 9, 12], mult=12500000.0, tick=0.0000005, spread=1),
    "6B":  dict(yf="6B=F",  sector="fx",     months=[3, 6, 9, 12], mult=62500.0,    tick=0.0001,    spread=1),
    "6A":  dict(yf="6A=F",  sector="fx",     months=[3, 6, 9, 12], mult=100000.0,   tick=0.0001,    spread=1),
    "6C":  dict(yf="6C=F",  sector="fx",     months=[3, 6, 9, 12], mult=100000.0,   tick=0.00005,   spread=1),
    "6S":  dict(yf="6S=F",  sector="fx",     months=[3, 6, 9, 12], mult=125000.0,   tick=0.0001,    spread=2),
    # energy
    "CL":  dict(yf="CL=F",  sector="energy", months=list(range(1, 13)), mult=1000.0,  tick=0.01,   spread=1),
    "NG":  dict(yf="NG=F",  sector="energy", months=list(range(1, 13)), mult=10000.0, tick=0.001,  spread=1),
    "HO":  dict(yf="HO=F",  sector="energy", months=list(range(1, 13)), mult=42000.0, tick=0.0001, spread=2),
    "RB":  dict(yf="RB=F",  sector="energy", months=list(range(1, 13)), mult=42000.0, tick=0.0001, spread=2),
    # metals
    "GC":  dict(yf="GC=F",  sector="metals", months=[2, 4, 6, 8, 10, 12], mult=100.0,   tick=0.1,    spread=1),
    "SI":  dict(yf="SI=F",  sector="metals", months=[3, 5, 7, 9, 12],     mult=5000.0,  tick=0.005,  spread=2),
    "HG":  dict(yf="HG=F",  sector="metals", months=[3, 5, 7, 9, 12],     mult=25000.0, tick=0.0005, spread=2),
    # agriculture (grains quoted in cents/bushel on Yahoo -> $50 per cent)
    "ZC":  dict(yf="ZC=F",  sector="ags",    months=[3, 5, 7, 9, 12],        mult=50.0,   tick=0.25, spread=1),
    "ZS":  dict(yf="ZS=F",  sector="ags",    months=[1, 3, 5, 7, 8, 9, 11],  mult=50.0,   tick=0.25, spread=1),
    "ZW":  dict(yf="ZW=F",  sector="ags",    months=[3, 5, 7, 9, 12],        mult=50.0,   tick=0.25, spread=1),
    "KC":  dict(yf="KC=F",  sector="ags",    months=[3, 5, 7, 9, 12],        mult=375.0,  tick=0.05, spread=3),
    "SB":  dict(yf="SB=F",  sector="ags",    months=[3, 5, 7, 10],           mult=1120.0, tick=0.01, spread=2),
    "CT":  dict(yf="CT=F",  sector="ags",    months=[3, 5, 7, 10, 12],       mult=500.0,  tick=0.01, spread=3),
}
SECTORS = sorted(set(v["sector"] for v in UNIVERSE.values()))

# ---- reference series for carry (spot / cash / yields). `invert` means Yahoo
# quotes the pair the other way round from the future.
REFERENCES = {
    "SPX":  dict(yf="^GSPC"),  "NDX": dict(yf="^NDX"),   "DJI": dict(yf="^DJI"),   "N225": dict(yf="^N225"),
    "EURUSD": dict(yf="EURUSD=X"), "GBPUSD": dict(yf="GBPUSD=X"), "AUDUSD": dict(yf="AUDUSD=X"),
    "USDJPY": dict(yf="JPY=X"),   "USDCAD": dict(yf="CAD=X"),     "USDCHF": dict(yf="CHF=X"),
    "IRX": dict(yf="^IRX"), "FVX": dict(yf="^FVX"), "TNX": dict(yf="^TNX"), "TYX": dict(yf="^TYX"),
}
CARRY_SPOT = {   # future -> (reference, invert)
    "ES": ("SPX", False), "NQ": ("NDX", False), "YM": ("DJI", False),   # NKD: 14h Tokyo/CME gap, dropped
    "6E": ("EURUSD", False), "6B": ("GBPUSD", False), "6A": ("AUDUSD", False),
    "6J": ("USDJPY", True), "6C": ("USDCAD", True), "6S": ("USDCHF", True),
}
# rates carry inputs: (own-tenor yield, next-shorter tenor yield, maturity yrs,
# shorter maturity yrs, modified duration of the CTD basket, approx)
CARRY_RATES = {
    "ZT": ("ZT2Y", "IRX", 2.0, 0.25, 1.9),   # ZT2Y is interpolated in s3
    "ZF": ("FVX", "ZT2Y", 5.0, 2.0, 4.3),
    "ZN": ("TNX", "FVX", 10.0, 5.0, 7.0),
    "ZB": ("TYX", "TNX", 30.0, 10.0, 14.0),
}
REF_LAG_DAYS = 1                # cash references enter one day late (DECISIONS.md)
CARRY_MIN_DAYS = 15             # basis is not read inside the last 15 trading days of a contract

# ---- costs
COMMISSION_PER_SIDE = 2.50      # dollars per contract, all-in with exchange fees
IMPACT_TICKS = 0.5              # paid on top of half the spread, per side

# ---- signal parameters (fixed in advance, not tuned)
TREND_LOOKBACKS = [20, 50, 100, 200]
VOL_WINDOW = 60                 # trailing days for position-level vol
VALUE_WINDOW = 5 * 252
CARRY_SMOOTH = 20
COV_WINDOW = 250                # trailing days for the portfolio covariance
VOL_TARGET = 0.15               # annualised, portfolio level
SECTOR_CAP = 0.35               # max share of gross risk in any one sector

# ---- expected bands (SPEC §8). Outside these => full audit before recording.
BANDS = {
    "signal_sharpe": (0.2, 0.6),
    "combined_sharpe": (0.5, 1.0),
    "signal_corr": (-0.3, 0.3),
    "effective_breadth": (8, 15),
}
STITCH_TOLERANCE = 0.15         # Sharpe; pre-registered in DECISIONS.md

# ---- execution schedule (pre-registered in s1 on cost alone; no return was read)
REBALANCE_SIGNAL = "M"          # signal scores are sampled on the last trading day of the month
REBALANCE_SIZE = "W"            # vol-scaled sizes are refreshed weekly
EVAL_START = "2002-01-01"       # 200-day MA and 60-day vol need to exist for most markets
CAPITAL = 1e7
PLACEBO_N = 100
