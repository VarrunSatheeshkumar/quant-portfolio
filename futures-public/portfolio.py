"""Portfolio construction: sector caps, covariance shrinkage, portfolio-level vol
targeting, effective breadth. Operates on contracts and dollar returns.

The layer that matters is the portfolio one. Per-position sizing makes each market
risk the same amount on its own; it says nothing about what thirty of them risk
together, and in a risk-off episode they risk far more than the sum of parts
suggests. The book is therefore rescaled so that its *implied* vol under the
current shrunk covariance equals the target.
"""

import numpy as np
import pandas as pd

import backtest
import config


def shrink_constant_correlation(R):
    """Ledoit-Wolf (2004) shrinkage of a correlation matrix toward the constant-
    correlation target. Intensity from the closed form; the sample matrix of 27
    markets on 250 days is too noisy to invert or even to trust as a scalar."""
    n = R.shape[0]
    rbar = (R.sum() - n) / (n * (n - 1))
    F = np.full_like(R, rbar)
    np.fill_diagonal(F, 1.0)
    return F, rbar


def shrunk_cov(std_ret, window):
    """Trailing covariance of standardised $ returns, shrunk. Returns Sigma for the
    last day of the window (correlation only; vols are applied by the caller)."""
    x = std_ret.tail(window).dropna(how="all")
    x = x.dropna(axis=1, thresh=int(0.7 * len(x)))
    x = x.fillna(0.0)
    T = len(x)
    if T < 60 or x.shape[1] < 3:
        return None
    X = x.values - x.values.mean(axis=0)
    S = X.T @ X / T
    d = np.sqrt(np.diag(S))
    R = S / np.outer(d, d)
    F, rbar = shrink_constant_correlation(R)
    # Ledoit-Wolf (2004) intensity on unit-variance data: pi = sum of asymptotic
    # variances of the sample correlations, rho = the part shared with the target
    Xs = X / d
    pi_mat = ((Xs[:, :, None] * Xs[:, None, :]) ** 2).mean(axis=0) - R ** 2
    pi_hat = pi_mat.sum()
    theta_ii = (Xs[:, :, None] ** 3 * Xs[:, None, :]).mean(axis=0) - R
    theta_jj = (Xs[:, :, None] * Xs[:, None, :] ** 3).mean(axis=0) - R
    off = ~np.eye(R.shape[0], dtype=bool)
    rho_hat = np.trace(pi_mat) + 0.5 * rbar * (theta_ii + theta_jj)[off].sum()
    gamma = ((F - R) ** 2).sum()
    kappa = (pi_hat - rho_hat) / gamma if gamma > 0 else 0.0
    delta = float(np.clip(kappa / T, 0.0, 1.0))
    Rs = delta * F + (1 - delta) * R
    return pd.DataFrame(Rs, index=x.columns, columns=x.columns), delta


def sector_cap(pos, dvol, cap=config.SECTOR_CAP):
    """Scale down any sector whose share of standalone risk exceeds the cap."""
    risk = (pos.abs() * dvol)
    total = risk.sum(axis=1)
    out = pos.copy()
    for sec in config.SECTORS:
        cols = [m for m in pos.columns if config.UNIVERSE[m]["sector"] == sec]
        share = risk[cols].sum(axis=1) / total
        scale = (cap / share).clip(upper=1.0).fillna(1.0)
        out[cols] = pos[cols].mul(scale, axis=0)
    return out


def target_portfolio(pos, ret_usd, dvol, target=config.VOL_TARGET, window=config.COV_WINDOW,
                     freq=config.REBALANCE_SIZE, lam_cap=5.0):
    """Rescale the whole book weekly so implied vol = target. Returns scaled
    positions, the scale series, implied vol, effective breadth, shrinkage."""
    std_ret = ret_usd / dvol
    dates = pos.index
    on = pd.Series(dates, index=dates).groupby(dates.to_period("W") if freq == "W" else dates.to_period("M")).transform("last")
    rebal = dates[dates == on.values]
    lam, ivol, neff, deltas = {}, {}, {}, {}
    cache = None
    for t in rebal:
        res = shrunk_cov(std_ret.loc[:t].iloc[:-1], window)     # strictly before t
        if res is None:
            continue
        R, delta = res
        w = pos.loc[t].reindex(R.index).fillna(0.0)
        dv = dvol.loc[t].reindex(R.index)
        risk = (w * dv).fillna(0.0).values
        var = risk @ R.values @ risk
        pvol = np.sqrt(max(var, 0.0)) * np.sqrt(backtest.ANN) / config.CAPITAL
        if pvol <= 0:
            continue
        lam[t] = min(target / pvol, lam_cap)
        ivol[t] = pvol
        neff[t] = (np.abs(risk).sum() ** 2) / var if var > 0 else np.nan
        deltas[t] = delta
    lam = pd.Series(lam).reindex(dates).ffill()
    scaled = pos.mul(lam, axis=0)
    return scaled, lam, pd.Series(ivol), pd.Series(neff), pd.Series(deltas)


def combine_scores(scores):
    """Equal-weight mean of the available scores per market-day. A market with no
    carry (commodities) is driven by the signals it has; NaN never counts as zero."""
    stack = pd.concat(scores, axis=1)
    return stack.T.groupby(level=1).mean().T
