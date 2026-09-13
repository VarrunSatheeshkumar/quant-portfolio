"""Constants. The single place values live, so nothing has to be grepped for."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
RAW = DATA / "raw"
GRID_DIR = DATA / "grid"
INTERIM = DATA / "interim"
REPORTS = ROOT / "reports"
RESULTS = REPORTS / "results"

SYMBOL = "BTCUSDT"

# ---- grid
# 2020-01 is the earliest the free Binance archive retains BTCUSDT perpetual data.
GRID_START = "2020-01-01"
GRID_END = "2026-09-01"
GRID_FREQ = "5min"
METRICS_START = "2020-09-01"      # 5-minute open interest starts here, so the map does

# ---- horizons, in bars
H1, H4 = 12, 48
HORIZONS = {"1h": H1, "4h": H4}

# ---- hold-outs. The repository has no look counter; the sealed blocks have been
# scored repeatedly (see WRITEUP.md, "Sealed-block scoring history").
SEALED_RECENT = ("2025-09-01", "2026-09-01")
SEALED_2022 = ("2022-01-01", "2023-01-01")
LIVE_FORWARD_START = "2026-09-01"
PURGE_DAYS = 3                    # must exceed the longest target horizon

# ---- liquidation map
LEVERAGE_PRIOR = {5: 0.30, 10: 0.30, 20: 0.25, 50: 0.15}
LEVERAGE_LADDER = [5, 10, 20, 50]
MAINT_MARGIN = 0.004
MAP_BUCKET_PCT = 0.0025           # histogram bucket width, 0.25% of spot
MAP_HALF_LIFE_BARS = 7 * 24 * 12 / 2
MAP_RANGE_PCT = 0.25
CLUSTER_SHARE = 0.05              # a "cluster" holds >5% of total map notional
EMPTY_SHARE = 0.005               # an "empty" level holds <0.5%, emptied buckets
                                  # included -- they are the cleanest control there
                                  # is, and excluding them removes 94% of it

# ---- event study
PREDICTED_MIN = 0.02              # same-side map share marking a print as anticipated
UNPREDICTED_MAX = 0.002
DEDUPE_BARS = 12
MAX_DIST = 0.05
FWD_BARS = {"15m": 3, "30m": 6, "60m": 12}

# ---- costs and power
FEES = 0.001                      # 0.10% round trip, taker both sides
BAND_BPS = 10.0                   # an effect below the round trip cannot be traded
POWER_Z = 2.802                   # z(0.975) + z(0.80): 80% power at 5%, two-sided

# ---- walk-forward
TRAIN_MONTHS = 12
MIN_TRAIN_ROWS = 20_000
MIN_TEST_ROWS = 500
RANDOM_SEED = 17
