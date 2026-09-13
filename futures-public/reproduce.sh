#!/bin/sh
# End-to-end reproduction of every number in WRITEUP.md. Roughly an hour on a laptop;
# needs network access to Yahoo Finance, TreasuryDirect, Binance and EIA (all keyless).
set -e
cd "$(dirname "$0")"
python3 build.py                              # s0..s9: data, stitching, costs, signals, portfolio, simulator, sweep, hold-out
python3 candidates/fetch.py                   # SPY, VIX, Treasury auction dates, Binance funding and klines
python3 candidates/splice_check.py            # Yahoo splice against NYMEX settlements (EIA)
python3 candidates/prereg.py                  # design dispersions and MDEs at N = 20 (no mean printed)
for c in C14 C19 C2 C9 C1 C11 C15 C18; do python3 candidates/run.py $c; done
python3 candidates/audit_c18.py
python3 -m tests.test_documents         # selected literal phrases in README.md and WRITEUP.md against reports/
echo "done: see reports/RESULTS.md and reports/candidates/"
