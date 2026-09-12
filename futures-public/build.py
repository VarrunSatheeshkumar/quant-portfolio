"""Orchestrator. `python build.py` runs every stage not yet complete;
`python build.py --force-from s4` re-runs from s4 onward. A stage marks itself
complete only when its gate passes; a failed gate halts the run."""

import argparse
import importlib

import progress


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force-from", default=None)
    ap.add_argument("--only", default=None)
    a = ap.parse_args()
    p = progress.load()
    started = a.force_from is None
    for s in progress.STAGES:
        if a.only and s != a.only:
            continue
        if not started:
            started = (s == a.force_from)
            if not started:
                continue
        if a.force_from is None and p.get(s, {}).get("status") == "complete":
            print(f"{s}: complete, skipping")
            continue
        progress.mark(s, "running")
        mod = importlib.import_module(f"stages.{s}")
        line = mod.main()          # halts inside on gate failure
        progress.mark(s, "complete", summary=line)
        progress.commit(s, line)
        print(f"{s}: {line}")


if __name__ == "__main__":
    main()
