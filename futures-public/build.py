"""Run incomplete stages, rebuilding missing outputs and their downstream stages.

An already inspected hold-out is retained, never re-scored. A failed gate halts
the run; --force-from and --only select the stages to revisit.
"""

import argparse
import importlib

import config
import progress


def required_outputs(stage):
    """Files required before accepting a stored s0-s8 completion checkpoint."""
    paths = [config.STAGE_REPORTS / f"{stage}.md"]
    if stage == "s0":
        variants = ["raw", "w0", "w1", "w3", "early3", "px_raw", "px_panama", "px_ratio"]
        paths += [config.RAW / f"{name}.parquet" for name in [*config.UNIVERSE, *config.REFERENCES]]
        paths += [config.GRID / f"{name}.parquet" for name in variants + ["refs", "refs_asof"]]
        paths += [config.STAGES / f"s0_{name}.parquet" for name in variants + ["roll_diag"]]
        paths += [config.STAGES / f"s0_rolls_{name}.parquet" for name in config.UNIVERSE]
    else:
        outputs = {
            "s1": ["costs.parquet"],
            "s2": ["score.parquet", "positions.parquet", "net.parquet", "net_by_market.parquet", "stats.json"],
            "s3": ["score.parquet", "carry_annual.parquet", "positions.parquet", "net.parquet", "net_by_market.parquet", "stats.json"],
            "s4": ["positions.parquet", "net.parquet", "scale.parquet", "neff.parquet", "sector_shares.parquet"],
            "s5": ["score.parquet", "positions.parquet", "net.parquet", "net_by_market.parquet", "stats.json"],
            "s6": ["positions.parquet", "net.parquet", "neff.parquet", "stats.json"],
            "s7": ["by_vol.parquet", "by_vol_trendcarry.parquet", "base_outcomes.parquet"],
            "s8": ["sweep.parquet", "best.parquet", "sweep_trendcarry.parquet", "best_trendcarry.parquet"],
        }
        paths += [config.STAGES / f"{stage}_{name}" for name in outputs[stage]]
    return paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force-from", choices=progress.STAGES, default=None)
    ap.add_argument("--only", choices=progress.STAGES, default=None)
    a = ap.parse_args()
    p = progress.load()
    started = a.force_from is None
    rebuilding = False
    for s in progress.STAGES:
        if a.only and s != a.only:
            continue
        if not started:
            started = (s == a.force_from)
            if not started:
                continue
        if s == "s9":
            mod = importlib.import_module("stages.s9")
            line = mod.retained_result()
            if line is not None:
                progress.mark(s, "retained", summary=line)
                print(f"{s}: {line}")
                continue
        else:
            missing = [path for path in required_outputs(s) if not path.is_file() or path.stat().st_size == 0]
            if a.force_from is None and not rebuilding and p.get(s, {}).get("status") == "complete" and not missing:
                print(f"{s}: complete, outputs present, skipping")
                continue
            if missing:
                print(f"{s}: {len(missing)} required output(s) missing or empty; rebuilding")
            if not rebuilding:
                # Persist invalidation before running, so an interruption cannot
                # leave old downstream completions looking current on restart.
                for downstream in progress.STAGES[progress.STAGES.index(s) + 1:-1]:
                    progress.mark(downstream, "pending", summary=f"upstream {s} is being rebuilt")
                rebuilding = True
            mod = importlib.import_module(f"stages.{s}")
        progress.mark(s, "running")
        line = mod.main()          # halts inside on gate failure
        progress.mark(s, "complete", summary=line)
        progress.commit(s, line)
        print(f"{s}: {line}")


if __name__ == "__main__":
    main()
