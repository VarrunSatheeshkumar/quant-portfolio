# Markowitz Portfolio Optimisation

Mean-variance portfolio optimisation across five UK-relevant asset classes. The central idea from the original 1952 paper: portfolio risk isn't just about how volatile individual assets are, it's about how they move together. Two volatile assets with negative correlation can combine into something calmer than either alone.

## What it does

- Builds a covariance matrix from volatilities and correlations
- Computes the efficient frontier via constrained quadratic optimisation (SLSQP)
- Identifies the minimum variance portfolio and maximum Sharpe ratio (tangency) portfolio
- Plots the Capital Market Line showing how mixing the tangency portfolio with a risk-free asset dominates the frontier
- Demonstrates the model's biggest practical problem: optimal weights swing dramatically with small changes in estimated returns

## The maths

**Portfolio variance:**

```
σ²_p = wᵀ Σ w = Σᵢ Σⱼ wᵢ wⱼ σᵢ σⱼ ρᵢⱼ
```

The cross terms `wᵢwⱼσᵢσⱼρᵢⱼ` are where diversification comes from. When ρᵢⱼ < 1, portfolio vol is less than the weighted average of individual vols. With ρ = -1 you can construct a riskless portfolio. This is why correlation matters more than individual volatility.

Worked example (two assets, 20% vol each):
- ρ = 1.0 → σ_p = 20% (no benefit)
- ρ = 0.0 → σ_p = 14.1%
- ρ = -0.5 → σ_p = 10.0%

**The optimisation:**

```
Minimise   wᵀ Σ w
subject to wᵀ μ = μ_target
           wᵀ 1 = 1
           wᵢ ≥ 0  (long-only)
```

Quadratic objective, linear constraints — this is a QP problem solved numerically using scipy SLSQP. The efficient frontier comes from solving this for 200 different target return levels.

**Why the frontier is a curve:** σ_p = √(wᵀΣw) is a square root of a quadratic, which traces a hyperbola in (σ, μ) space. If all assets were perfectly correlated, it would be a line. The leftward bend is diversification.

**Tangency portfolio and CML:** The tangency portfolio maximises the Sharpe ratio. If you can also hold a risk-free asset, mix it with the tangency portfolio to get the Capital Market Line. Every point on the CML dominates the corresponding point on the frontier at the same risk level.

## The estimation problem

This is the model's central practical issue, and I think it's worth being direct about it. The optimiser needs expected returns as input. These are very hard to estimate — the standard error of the sample mean for equities is roughly σ/√T, which is enormous. With 10 years of data and 20% vol, you have a ±13% confidence interval around your 7% return estimate.

The demonstration in the code shows this concretely: two different simulated 10-year windows of returns give wildly different "optimal" portfolios, even though the underlying assets are identical. The model concentrates bets in whichever assets you happened to overestimate — this is the Michaud (1989) "error maximisation" critique.

In practice the fixes are: constrain weight ranges, use Bayesian return estimates (Black-Litterman), or use minimum variance / risk parity which don't need return inputs at all.

## Crisis correlation

The other major failure: correlations are not constant. In 2008 and March 2020, almost everything fell simultaneously as correlations spiked toward 1. The model's diversification promise fails exactly when you need it. The code has a simulation showing what this looks like.

## Running

```bash
pip install numpy scipy matplotlib
python markowitz.py
```

Plots saved to `./plots/`: correlation matrix, efficient frontier, composition along frontier, crisis correlation demo.
