"""Minimum detectable effect, and the rule that a criterion is not committed without one.

This is the module that would have saved this project the most time. Four separate
versions returned "inconclusive" on power after the work was done, and one committed
to a criterion that no sample length could ever have satisfied.

The protocol is two-phase and the order is the point:

  1. build the trades, forecasts or events; measure the dispersion of the statistic
     **without reading the signal**
  2. publish the MDE; only then commit the band; only then read the result

An MDE computed afterwards is a description. Computed first, it is a design decision.
"""

import numpy as np
import pandas as pd

POWER_Z = 2.802     # z_{0.975} + z_{0.80}: 80% power at 5%, two-sided


def mde_from_se(se, z=POWER_Z):
    """Smallest effect detectable at 80% power given a standard error."""
    return z * se


def block_bootstrap(values, blocks, stat=np.nanmean, n=2000, seed=17):
    """Resample whole blocks -- days, months -- not rows.

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


def newey_west_se(x, lag):
    """Standard error of a mean under overlapping windows. Bartlett kernel.

    A 20-day target sampled daily is 95% overlapping. Non-overlapping subsampling
    throws away data; Newey-West keeps it and corrects the standard error instead,
    which is worth roughly a 30% gain in effective sample size.
    """
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 30:
        return np.nan
    e = x - x.mean()
    s = (e @ e) / n
    for k in range(1, min(lag, n - 1) + 1):
        s += 2.0 * (1.0 - k / (lag + 1.0)) * ((e[k:] @ e[:-k]) / n)
    return float(np.sqrt(max(s, 0.0) / n))


def design_power(values, blocks=None, lag=None, band=None, exposure=None, n=2000,
                 seed=17):
    """The phase-one report: dispersion, MDE, and whether the band is reachable.

    `exposure` is the mean absolute position, and it is required whenever structures
    are compared. A signal that trades smaller disperses less and its MDE falls with
    it, which reads as better power and is not. Compare on **MDE divided by the
    effect you care about**, never on MDE alone.
    """
    values = np.asarray(values, float)
    if blocks is not None:
        boot = block_bootstrap(values, blocks, n=n, seed=seed)
        se = float(boot.std())
    elif lag is not None:
        se = newey_west_se(values, lag)
    else:
        v = values[np.isfinite(values)]
        se = float(v.std() / np.sqrt(len(v))) if len(v) > 2 else np.nan

    mde = mde_from_se(se)
    out = {"n": int(np.isfinite(values).sum()), "se": se, "mde": mde,
           "mean": float(np.nanmean(values))}
    if exposure is not None:
        out["mean_abs_exposure"] = float(exposure)
        out["mde_per_unit_exposure"] = float(mde / exposure) if exposure else np.nan
    if band is not None:
        out["band"] = float(band)
        out["testable"] = bool(np.isfinite(mde) and mde <= band)
        out["sample_multiple_needed"] = (float((mde / band) ** 2)
                                         if np.isfinite(mde) and band else np.nan)
    return out


def annualised_sharpe_is_untestable(years, target_sharpe, z=POWER_Z):
    """Why an annualised-ratio criterion is almost always unsatisfiable.

    For iid per-period returns the standard error of an annualised Sharpe is
    sqrt(periods_per_year / n), and with n = periods_per_year * years that reduces to
    1/sqrt(years). **Trade frequency cancels entirely.** Detecting a Sharpe of 0.5 at
    80% power needs (2.802/0.5)^2 = 31 years, whether you trade monthly or hourly.

    Returns the years required, so the impossibility is a number and not an opinion.
    """
    return float((z / target_sharpe) ** 2), float(z / np.sqrt(years))
