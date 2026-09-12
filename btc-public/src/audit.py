"""Audit machinery: power, purge and embargo, placebo, randomisation.

This is the part that backs every claim, and it is deliberately the first module
written rather than the last. Four results in this repository are negative, and a
negative result is only worth stating if the design could have detected the effect it
failed to find.

The protocol is two-phase and the order is the point: measure the dispersion of a
statistic **without reading the signal**, publish the minimum detectable effect, and
only then commit to a band. Computed afterwards, an MDE is a description. Computed
first, it is a design decision.
"""

import numpy as np
import pandas as pd

import config


# ------------------------------------------------------------------ hold-outs
def sealed_mask(index, blocks=None, purge_days=config.PURGE_DAYS):
    """True where a timestamp falls in a sealed block or its purge gap.

    The purge must exceed the longest target horizon, or a training target opened
    just before the boundary resolves inside the hold-out.
    """
    blocks = blocks or [config.SEALED_RECENT, config.SEALED_2022]
    idx = pd.DatetimeIndex(index)
    gap = pd.Timedelta(days=purge_days)
    m = np.zeros(len(idx), dtype=bool)
    for lo, hi in blocks:
        lo, hi = pd.Timestamp(lo, tz="UTC"), pd.Timestamp(hi, tz="UTC")
        m |= (idx >= lo - gap) & (idx < hi + gap)
    return m


def training_mask(index):
    """Everything that is neither sealed, nor in its purge gap, nor forward-looking."""
    idx = pd.DatetimeIndex(index)
    live = pd.Timestamp(config.LIVE_FORWARD_START, tz="UTC")
    return (~sealed_mask(idx)) & (idx < live)


def in_block(index, block):
    idx = pd.DatetimeIndex(index)
    lo, hi = pd.Timestamp(block[0], tz="UTC"), pd.Timestamp(block[1], tz="UTC")
    return np.asarray((idx >= lo) & (idx < hi))


# ------------------------------------------------------------------ power
def block_bootstrap(values, blocks, stat=np.nanmean, n=2000, seed=config.RANDOM_SEED):
    """Resample whole blocks -- days, months -- never rows.

    Rows inside a block share a regime, so a row bootstrap understates the standard
    error by however much that dependence is worth, which is usually a lot.
    """
    values = np.asarray(values, float)
    blocks = np.asarray(blocks)
    uniq = pd.Index(blocks).unique()
    pos = {b: np.nonzero(blocks == b)[0] for b in uniq}
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        ii = np.concatenate([pos[b] for b in rng.choice(uniq, len(uniq), replace=True)])
        v = stat(values[ii])
        if np.isfinite(v):
            out.append(float(v))
    return np.array(out, float)


def design_power(values, blocks, band=None, exposure=None, n=2000,
                 seed=config.RANDOM_SEED):
    """Phase one: dispersion, MDE, and whether the band is reachable.

    `exposure` is the mean absolute position and is required whenever designs are
    compared. A signal that trades smaller disperses less and its MDE falls with it,
    which reads as better power and is not -- compare on MDE divided by the effect
    you care about, never MDE alone. That error appeared three times in this project
    and was caught three times by this argument.
    """
    boot = block_bootstrap(values, blocks, n=n, seed=seed)
    se = float(boot.std()) if len(boot) else np.nan
    mde = config.POWER_Z * se
    out = {"n": int(np.isfinite(values).sum()), "se": se, "mde": mde,
           "mean": float(np.nanmean(values)),
           "ci_lo": float(np.percentile(boot, 2.5)) if len(boot) else np.nan,
           "ci_hi": float(np.percentile(boot, 97.5)) if len(boot) else np.nan}
    if exposure is not None:
        out["mean_abs_exposure"] = float(exposure)
    if band is not None:
        out["band"] = float(band)
        out["testable"] = bool(np.isfinite(mde) and mde <= band)
        out["sample_multiple_needed"] = float((mde / band) ** 2) if band else np.nan
    return out


# ------------------------------------------------------------------ validation
def block_shuffle(values, blocks, seed=config.RANDOM_SEED):
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
    vals = np.asarray(values, float)
    for b in uniq:
        tgt, src = pos[b], pos[perm[b]]
        k = min(len(tgt), len(src))
        out[tgt[:k]] = vals[src[:k]]
    return out


def placebo_labels(frame, value_col, label_col, cells, n=1000,
                   seed=config.RANDOM_SEED):
    """Same test, labels shuffled at the observed rate, sample held fixed.

    A placebo and a bootstrap answer different questions and this project saw them
    disagree correctly: the placebo asks whether *this* labelling beats an arbitrary
    one on *these* observations, the bootstrap whether the result would replicate on
    a different sample. Report both.
    """
    d = frame.dropna(subset=[value_col, label_col])
    real = matched_difference(d, value_col, label_col, cells)
    if real is None:
        return None
    rng = np.random.default_rng(seed)
    p = float(d[label_col].mean())
    draws = []
    for _ in range(n):
        dd = d.assign(_g=(rng.random(len(d)) < p).astype(int))
        r = matched_difference(dd, value_col, "_g", cells, min_cell=3)
        if r is not None and np.isfinite(r["diff"]):
            draws.append(r["diff"])
    draws = np.array(draws, float)
    if not len(draws):
        return None
    centre = float(draws.mean())
    p95 = float(np.percentile(np.abs(draws - centre), 95))
    return {"real": real["diff"], "placebo_mean": centre, "placebo_abs_p95": p95,
            "clears": bool(abs(real["diff"] - centre) > p95),
            "label_rate": p, "n_placebo": int(len(draws))}


def randomisation(stat_fn, values, blocks, n=300, seed=config.RANDOM_SEED):
    """The standing sanity check on the machinery itself.

    Block-shuffle the target and re-run. Anything that survives means the pipeline
    manufactures results regardless of input, whatever the real-target answer says.
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
            "placebo_abs_p95": float(np.percentile(np.abs(out), 95)),
            "clears": bool(abs(real) > np.percentile(np.abs(out), 95)),
            "n_placebo": int(len(out))}


def matched_difference(frame, value_col, group_col, cells, min_cell=15):
    """Within-cell mean difference between two groups.

    Confounds are separated by construction here rather than argued away afterwards:
    a comparison is only made between observations that share a cell, and a cell with
    no control simply drops out rather than being extrapolated over.
    """
    d = frame.dropna(subset=[value_col, group_col])
    acc = tot = 0.0
    n_cells = n_treated = n_control = 0
    for _, g in d.groupby(list(cells), observed=True):
        a = g.loc[g[group_col] == 1, value_col]
        b = g.loc[g[group_col] == 0, value_col]
        if len(a) < min_cell or len(b) < min_cell:
            continue
        acc += len(a) * (a.mean() - b.mean())
        tot += len(a)
        n_cells += 1
        n_treated += len(a)
        n_control += len(b)
    if tot <= 0:
        return None
    return {"diff": acc / tot, "n_cells": n_cells,
            "n_treated": n_treated, "n_control": n_control}
