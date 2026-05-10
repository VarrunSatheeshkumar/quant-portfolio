# Markowitz Portfolio Optimisation

Mean-variance portfolio optimisation across five UK-relevant asset classes. The central idea from the original 1952 paper: portfolio risk isn't just about how volatile individual assets are, it's about how they move together. Two volatile assets with negative correlation can combine into something calmer than either alone.

## What it does

- Builds a covariance matrix from volatilities and correlations
- Computes the efficient frontier via constrained quadratic optimisation (SLSQP)
- Identifies the minimum variance portfolio and maximum Sharpe ratio (tangency) portfolio
- Plots the Capital Market Line showing how mixing the tangency portfolio with a risk-free asset dominates the frontier
- Demonstrates the model's biggest practical problem: optimal weights swing dramatically with small changes in estimated returns
- Implements Ledoit-Wolf covariance shrinkage and compares the resulting frontier against the raw sample estimate

## The maths

**Portfolio variance:**

```
sigma^2_p = w^T Sigma w = sum_i sum_j w_i w_j sigma_i sigma_j rho_ij
```

The cross terms are where diversification comes from. When rho_ij < 1, portfolio vol is less than the weighted average of individual vols. With rho = -1 you can construct a riskless portfolio.

Worked example (two assets, 20% vol each):
- rho = 1.0 → sigma_p = 20% (no benefit)
- rho = 0.0 → sigma_p = 14.1%
- rho = -0.5 → sigma_p = 10.0%

**The optimisation:**

```
Minimise   w^T Sigma w
subject to w^T mu = mu_target
           w^T 1 = 1
           w_i >= 0  (long-only)
```

Quadratic objective, linear constraints — solved numerically using scipy SLSQP. The efficient frontier comes from solving this for 200 different target return levels.

**Tangency portfolio and CML:** The tangency portfolio maximises the Sharpe ratio. Mixed with a risk-free asset, it traces the Capital Market Line — every point on the CML dominates the corresponding frontier point at the same risk level.

## The estimation problem

The optimiser needs expected returns as input. These are very hard to estimate — the standard error of the sample mean for equities is roughly sigma/sqrt(T). With 10 years of data and 20% vol, you have a ±13% confidence interval around your 7% return estimate.

The demo shows this concretely: two simulated 10-year windows give wildly different "optimal" portfolios from identical underlying assets. The model concentrates bets wherever you happened to overestimate — the Michaud (1989) "error maximisation" critique.

## Ledoit-Wolf covariance shrinkage

The same estimation problem affects the covariance matrix. With T observations and p assets, extreme eigenvalues of the sample covariance matrix are systematically biased — the largest are too large, the smallest too small. The optimiser treats noisy small eigenvalues as real structure and piles into them.

Ledoit-Wolf (2004) fixes this by shrinking the sample covariance towards a scaled identity matrix:

```
Sigma_shrunk = (1 - alpha) * Sigma_sample + alpha * mu_bar * I
```

where mu_bar is the average eigenvalue (preserves the scale of the matrix) and alpha is chosen analytically to minimise the expected estimation error. `sklearn.covariance.LedoitWolf` computes the optimal alpha from the data — you don't pick it by hand.

The effect is a better-conditioned matrix that produces more stable, more diversified portfolios. The code runs all three frontiers — true, sample, and shrunk — and plots them together. The LW frontier sits closer to the true one than the raw sample frontier does.

## Crisis correlation

Correlations are not constant. In 2008 and March 2020, almost everything fell simultaneously as correlations spiked toward 1. The model's diversification promise fails exactly when you need it. The code has a simulation showing what this looks like.

## Running

```bash
pip install numpy scipy matplotlib scikit-learn
python markowitz.py
```

Plots saved to `./plots/`: correlation matrix, efficient frontier with CML, composition along frontier, crisis correlation demo, shrinkage comparison.
