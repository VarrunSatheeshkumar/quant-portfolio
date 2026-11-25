#!/bin/zsh
# One-command rerun of the post-mortem (as-of 20 Nov 2026, the last session of the competition window).
#
#   ./run_all.sh              rebuild out/ from the saved Yahoo snapshot in data/raw/ (no network);
#                             if data/raw/ has no snapshot, download one first
#   ./run_all.sh --download   take a fresh Yahoo price and estimates snapshot, then rebuild
#
# data/raw/ is not tracked in git (Yahoo data is not redistributed), so a fresh clone downloads.
# A fresh download is close to, not identical with, the published out/: Yahoo revises adjusted closes,
# and the estimates snapshot is taken on the day you run it. See README.md, "Data".
set -e
set -o pipefail   # a failing test fails the script even through | tail
cd "$(dirname "$0")"
PY=.venv/bin/python
[ -x $PY ] || { python3 -m venv .venv && $PY -m pip install -q -r requirements.txt; }
cd src
if [ "$1" = "--download" ] || [ ! -f ../data/raw/prices_latest.txt ]; then
  echo "NOTE: fresh Yahoo download. Results will be labelled 20 Nov but use today's estimates and revised closes;"
  echo "      they are a fresh-data rerun, not the published out/ (that needs the 21 Nov 20:59 UTC snapshot);" >&2
  echo "      tests that pin figures from that snapshot will skip." >&2
  ../$PY -W ignore snapshot_estimates.py > /dev/null      # timestamped yfinance estimates snapshot
  ../$PY -W ignore download_prices.py > /dev/null         # prices (raw/adj/OHLC) with download timestamp
fi
../$PY -W ignore run_all.py --asof 2026-11-20            # out/results.json and CSVs
../$PY -W ignore run_plan2.py core E K H G               # out/results2.json
../$PY -W ignore stress.py > /dev/null                   # out/stress_observed.json
../$PY -W ignore latest.py > /dev/null                   # out/latest_25nov.json (pitch mark-to-market, 25 Nov close)
cd ..
$PY -m pytest -q -p no:warnings tests/ | tail -8
echo "results: out/results.json, out/results2.json, out/stress_observed.json, out/latest_25nov.json"
