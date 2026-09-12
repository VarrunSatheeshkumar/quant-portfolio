"""Stage bookkeeping: reports/progress.json, stage reports, and halting."""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

import config

STAGES = ["s0", "s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8", "s9"]
PATH = config.REPORTS / "progress.json"


def load():
    if PATH.exists():
        return json.loads(PATH.read_text())
    return {s: {"status": "pending"} for s in STAGES}


def save(p):
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps(p, indent=2))


def mark(stage, status, **info):
    p = load()
    p[stage] = dict(status=status, at=datetime.now(timezone.utc).isoformat(timespec="seconds"), **info)
    save(p)


def write_report(stage, text):
    config.STAGE_REPORTS.mkdir(parents=True, exist_ok=True)
    (config.STAGE_REPORTS / f"{stage}.md").write_text(text)


def halt(stage, why):
    """A failed gate stops the run. Nothing downstream is worth computing."""
    mark(stage, "failed", why=why)
    print(f"HALT {stage}: {why}")
    sys.exit(2)


def commit(stage, msg):
    """Commit after each completed stage, only when FUTURES_AUTOCOMMIT=1 is set."""
    if os.environ.get("FUTURES_AUTOCOMMIT") != "1":
        return
    subprocess.run(["git", "add", "-A"], cwd=config.ROOT, check=False)
    subprocess.run(["git", "commit", "-q", "-m", f"{stage}: {msg}"],
                   cwd=config.ROOT, check=False)
