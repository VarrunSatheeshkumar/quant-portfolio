"""Placebo and randomisation. Run both on every result, and run them differently.

They answer different questions and this project saw them disagree, correctly, more
than once:

  * a **placebo** holds the sample fixed and destroys only the thing being claimed --
    shuffle the labels, the selection, the signal values. It asks whether *this*
    signal beats an arbitrary one on *these* observations.
  * a **block bootstrap** resamples whole blocks. It asks whether the result would
    replicate on a different sample of blocks.

A result can clear its placebo decisively and still have a bootstrap interval
covering zero. That is not a contradiction: the labelling is informative and its
generalisation is unestablished. Reporting either alone tells a different and wrong
story.

The randomisation test is the standing sanity check on the machinery itself. Shuffle
the target in blocks and re-run the whole pipeline; anything that survives means the
pipeline manufactures results regardless of input.
"""

import numpy as np
import pandas as pd


def block_shuffle(values, blocks, seed=17):
    """Permute whole blocks, keeping each block's internal path intact.

    An i.i.d. shuffle destroys the target's autocorrelation as well as its alignment,
    which makes the test far too easy to pass.
    """
    rng = np.random.default_rng(seed)
    blocks = np.asarray(blocks)
    uniq = pd.Index(blocks).unique()
    perm = dict(zip(uniq, rng.permutation(np.asarray(uniq))))
    pos = {b: np.nonzero(blocks == b)[0] for b in uniq}
    out = np.full(len(values), np.nan)
    for b in uniq:
        tgt, src = pos[b], pos[perm[b]]
        k = min(len(tgt), len(src))
        out[tgt[:k]] = np.asarray(values)[src[:k]]
    return out


def placebo_selection(base_effect, selected, n=2000, seed=17):
    """Replace the signal's selection with random selection at the same rate.

    The rate matters more than most people expect. In this project a signal that
    looked significantly *worse* than its benchmark turned out to be indistinguishable
    from picking the same number of trades at random -- essentially all of the effect
    was the rate of taking exposure, not the timing of it.
    """
    base_effect = np.asarray(base_effect, float)
    sel = np.asarray(selected, float)
    real = float(np.nanmean(base_effect * sel))
    p = float(np.nanmean(sel))
    rng = np.random.default_rng(seed)
    draws = np.array([float(np.nanmean(base_effect * (rng.random(len(sel)) < p)))
                      for _ in range(n)])
    centre = float(draws.mean())
    p95 = float(np.percentile(np.abs(draws - centre), 95))
    return {"real": real, "placebo_mean": centre, "placebo_abs_p95": p95,
            "clears": bool(abs(real - centre) > p95), "selection_rate": p,
            "n_placebo": int(len(draws))}


def randomisation(stat_fn, values, blocks, n=500, seed=17):
    """Rule 5: block-shuffle the target and re-run the statistic.

    `stat_fn(shuffled_values) -> float`. Returns the real statistic beside the
    distribution of shuffled ones. A version whose machinery produces survivors on a
    shuffled target has a bug, whatever its real-target result says.
    """
    real = float(stat_fn(np.asarray(values, float)))
    out = []
    for i in range(n):
        v = stat_fn(block_shuffle(values, blocks, seed=seed + i))
        if np.isfinite(v):
            out.append(float(v))
    out = np.array(out, float)
    if not len(out):
        return None
    return {"real": real, "placebo_mean": float(out.mean()),
            "placebo_sd": float(out.std()),
            "placebo_abs_p95": float(np.percentile(np.abs(out), 95)),
            "clears": bool(abs(real) > np.percentile(np.abs(out), 95)),
            "n_placebo": int(len(out))}


def staleness_split(effect, time_since_update, threshold_hours=6.0):
    """Split a result by how long ago its slowest input updated.

    When a daily series feeds an intraday model, an apparent improvement that lives
    only in the hours right after the update is the update schedule showing through.
    Make this a refutation clause, not a caveat -- as a caveat it gets written under
    a positive headline and nobody reads it.
    """
    effect = np.asarray(effect, float)
    tsu = np.asarray(time_since_update, float)
    fresh, stale = tsu <= threshold_hours, tsu > threshold_hours
    return {"fresh_mean": float(np.nanmean(effect[fresh])),
            "stale_mean": float(np.nanmean(effect[stale])),
            "n_fresh": int(np.isfinite(effect[fresh]).sum()),
            "n_stale": int(np.isfinite(effect[stale]).sum()),
            "concentrated_in_fresh": bool(
                np.nanmean(effect[fresh]) > 0 >= np.nanmean(effect[stale]))}
