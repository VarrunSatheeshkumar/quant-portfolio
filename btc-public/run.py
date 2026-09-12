"""Run the pipeline end to end. Stages are skipped if their output already exists.

    python run.py                 # everything, resuming where it left off
    python run.py --force-from map
    python run.py --only vol_model

Data is fetched from public sources into `data/`, which is gitignored. Nothing in
this repository contains sealed-block or live-window data.
"""

import argparse
import subprocess
import sys
from pathlib import Path

import config

STAGES = [
    ("fetch", "src.fetch", config.RAW / "futures_klines_5m.parquet"),
    ("grid", "src.grid", config.GRID_DIR / "grid.parquet"),
    ("asof_test", "tests.test_asof", None),
    ("map", "src.liquidation_map", config.INTERIM / "map_features.parquet"),
    ("vol_model", "src.vol_model", config.RESULTS / "vol_model.json"),
    ("har", "src.har", config.RESULTS / "har.json"),
    ("event_study", "src.event_study", config.RESULTS / "event_study.json"),
    ("instrument", "src.instrument", config.RESULTS / "instrument.json"),
    ("economics", "src.economics", config.RESULTS / "economics.json"),
    ("doc_test", "tests.test_documents", None),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force-from")
    ap.add_argument("--only")
    args = ap.parse_args()

    names = [s[0] for s in STAGES]
    if args.only:
        todo = [s for s in STAGES if s[0] == args.only]
    elif args.force_from:
        i = names.index(args.force_from)
        todo = STAGES[i:]
    else:
        todo = STAGES

    for name, module, artifact in todo:
        if artifact is not None and artifact.exists() and not args.only \
                and not args.force_from:
            print(f"{name}: already done, skipping")
            continue
        print(f"=== {name} ===", flush=True)
        r = subprocess.run([sys.executable, "-m", module], cwd=config.ROOT)
        if r.returncode != 0:
            # A stage that cannot verify its own output stops the run rather than
            # passing bad data downstream.
            sys.exit(f"HALT: {name} failed with code {r.returncode}")
    print("pipeline complete")


if __name__ == "__main__":
    main()
