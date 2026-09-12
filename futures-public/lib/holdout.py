"""Purge, embargo, and the hold-out bookkeeping that keeps a project honest.

A sealed block is only a hold-out if it is opened once. This module makes the look
count explicit and persistent, because the discipline is social as much as technical
and a counter on disk is harder to argue with than an intention.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd


def sealed_mask(index, blocks, purge_days):
    """True where a timestamp falls in a sealed block or its purge gap.

    Purge must exceed the longest target horizon. A 20-day target needs at least 25
    days of gap, not 3 -- otherwise a training target opened just before the boundary
    resolves inside the hold-out.
    """
    idx = pd.DatetimeIndex(index)
    gap = pd.Timedelta(days=purge_days)
    m = np.zeros(len(idx), dtype=bool)
    for lo, hi in blocks:
        lo, hi = pd.Timestamp(lo, tz="UTC"), pd.Timestamp(hi, tz="UTC")
        m |= ((idx >= lo - gap) & (idx < hi + gap))
    return m


def training_mask(index, blocks, purge_days, live_start=None):
    idx = pd.DatetimeIndex(index)
    m = ~sealed_mask(idx, blocks, purge_days)
    if live_start is not None:
        m &= idx < pd.Timestamp(live_start, tz="UTC")
    return m


def in_block(index, block):
    idx = pd.DatetimeIndex(index)
    lo, hi = pd.Timestamp(block[0], tz="UTC"), pd.Timestamp(block[1], tz="UTC")
    return np.asarray((idx >= lo) & (idx < hi))


class LookCounter:
    """Persistent count of how many times each sealed block has been scored.

    A result on a block with two or more looks is not a hold-out result and should
    never be a headline number. Recording that is the whole point.
    """

    def __init__(self, path):
        self.path = Path(path)
        self.data = json.loads(self.path.read_text()) if self.path.exists() else {}

    def look(self, name, note=""):
        e = self.data.setdefault(name, {"looks": 0, "history": []})
        e["looks"] += 1
        e["history"].append({"note": note, "at": pd.Timestamp.utcnow().isoformat()})
        self.path.write_text(json.dumps(self.data, indent=2))
        return e["looks"]

    def count(self, name):
        return self.data.get(name, {}).get("looks", 0)
