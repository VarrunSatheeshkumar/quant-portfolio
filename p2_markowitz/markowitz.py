"""
Markowitz Mean-Variance Portfolio Optimisation
===============================================
The core insight: what matters for portfolio risk isn't just how volatile
each asset is individually, but how they move together. Two volatile assets
with negative correlation can combine into something calmer than either alone.

I built this after reading the original Markowitz (1952) paper, which is
only about 15 pages and is remarkably clear. The efficient frontier is the
set of portfolios that maximise return for each level of risk -- anything
inside that boundary is suboptimal.

One thing I found really interesting in practice: the model is very sensitive
to the expected return inputs, which are nearly impossible to estimate reliably.
I demonstrate this at the bottom by showing how the "optimal" portfolio changes
dramatically depending on which historical period you use to estimate returns.
That's a known problem with the model and it's worth being upfront about.

References: Markowitz (1952) JPE, Hull for intuition, scipy docs for SLSQP.
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import minimize
import os


# ── ASSET PARAMETERS ─────────────────────────────────────────────────────────
# Five UK-relevant asset classes with roughly realistic long-run parameters.
# These are annual figures.

ASSETS = ['UK Equities', 'US Equities', 'UK Gilts', 'Gold', 'UK Property']

MU = np.array([0.07, 0.09, 0.02, 0.05, 0.06])   # expected annual returns

VOLS = np.array([0.15, 0.17, 0.06, 0.16, 0.14])  # annual volatilities

CORR = np.array([
    # UK eq  US eq  Gilts  Gold  Property
    [1.00,   0.82,  -0.10, -0.05, 0.60],
    [0.82,   1.00,  -0.15, -0.02, 0.55],
    [-0.10, -0.15,   1.00,  0.25, 0.00],
    [-0.05, -0.02,   0.25,  1.00, 0.05],
    [0.60,   0.55,   0.00,  0.05, 1.00],
])


def build_cov(vols, corr):
    """Covariance matrix: sigma_ij = sigma_i * sigma_j * rho_ij"""
    return np.outer(vols, vols) * corr


# ── PORTFOLIO STATISTICS ──────────────────────────────────────────────────────

def port_return(w, mu):
    """E[R_p] = w^T * mu"""
    return float(w @ mu)


def port_vol(w, cov):
    """
    sigma_p = sqrt(w^T Sigma w)
    The off-diagonal terms (cross-products) are where diversification comes from.
    When rho < 1, portfolio vol is less than the weighted average of individual vols.
    """
    return float(np.sqrt(w @ cov @ w))


def sharpe(w, mu, cov, rf=0.04):
    """(return - risk_free) / vol. Risk-free rate roughly BoE rate neighbourhood."""
    r = port_return(w, mu)
    v = port_vol(w, cov)
    return (r - rf) / v if v > 0 else 0


# ── EFFICIENT FRONTIER ────────────────────────────────────────────────────────

def min_var_portfolio(cov):
    """
    Minimum variance portfolio: leftmost point on the frontier.
    No return constraint -- just minimise variance.
    Long-only (no short selling): bounds = [(0,1)] for each weight.
    """
    n = cov.shape[0]
    result = minimize(
        fun=lambda w: port_vol(w, cov),
        x0=np.ones(n) / n,
        method='SLSQP',
        bounds=[(0, 1)] * n,
        constraints=[{'type': 'eq', 'fun': lambda w: w.sum() - 1}],
        options={'ftol': 1e-12}
    )
    return result.x


def max_sharpe_portfolio(mu, cov, rf=0.04):
    """
    Tangency portfolio: highest Sharpe ratio.
    This is the risky portfolio you'd combine with the risk-free asset
    to build any point on the Capital Market Line.
    """
    n = len(mu)
    result = minimize(
        fun=lambda w: -sharpe(w, mu, cov, rf),
        x0=np.ones(n) / n,
        method='SLSQP',
        bounds=[(0, 1)] * n,
        constraints=[{'type': 'eq', 'fun': lambda w: w.sum() - 1}],
        options={'ftol': 1e-12}
    )
    return result.x


def efficient_frontier(mu, cov, n_pts=200, rf=0.04):
    """
    Compute the frontier by sweeping target returns from MVP to max.
    For each target, minimise variance subject to hitting that return.
    """
    n = len(mu)
    mvp_w = min_var_portfolio(cov)
    min_ret = port_return(mvp_w, mu)
    max_ret = mu.max() * 0.99

    targets = np.linspace(min_ret, max_ret, n_pts)
    vols_out, rets_out, weights_out = [], [], []

    for target in targets:
        res = minimize(
            fun=lambda w: port_vol(w, cov),
            x0=np.ones(n) / n,
            method='SLSQP',
            bounds=[(0, 1)] * n,
            constraints=[
                {'type': 'eq', 'fun': lambda w: w.sum() - 1},
                {'type': 'eq', 'fun': lambda w, t=target: port_return(w, mu) - t}
            ],
            options={'ftol': 1e-12}
        )
        if res.success:
            vols_out.append(port_vol(res.x, cov))
            rets_out.append(port_return(res.x, mu))
            weights_out.append(res.x)

    return np.array(vols_out), np.array(rets_out), weights_out


def random_portfolios(mu, cov, n=5000, rf=0.04, seed=42):
    """
    Random weight portfolios to show the feasible region.
    The frontier sits on the left edge of this cloud.
    """
    rng = np.random.default_rng(seed)
    vols_r, rets_r, sharpes_r = [], [], []
    for _ in range(n):
        w = rng.random(len(mu))
        w /= w.sum()
        vols_r.append(port_vol(w, cov))
        rets_r.append(port_return(w, mu))
        sharpes_r.append(sharpe(w, mu, cov, rf))
    return np.array(vols_r), np.array(rets_r), np.array(sharpes_r)


# ── ESTIMATION INSTABILITY DEMO ───────────────────────────────────────────────
# This is the model's biggest practical problem.
# Expected returns estimated from historical data are very noisy --
# standard error of the sample mean is sigma/sqrt(T), which is huge.
# The optimiser treats noisy estimates as truth and concentrates bets
# accordingly. Show this by using different time windows.

def estimation_instability_demo(cov, seed=99):
    """
    Simulate two different 'historical periods' giving different return estimates.
    Show how dramatically the optimal weights change as a result.
    """
    rng = np.random.default_rng(seed)
    n = len(MU)

    # Period 1: simulate 10 years of annual returns
    r1 = rng.multivariate_normal(MU, cov, size=10)
    mu_est1 = r1.mean(axis=0)

    # Period 2: different 10-year window
    r2 = rng.multivariate_normal(MU, cov, size=10)
    mu_est2 = r2.mean(axis=0)

    w1 = max_sharpe_portfolio(mu_est1, cov)
    w2 = max_sharpe_portfolio(mu_est2, cov)
    w_true = max_sharpe_portfolio(MU, cov)

    print("\n--- Estimation Instability (same model, different data windows) ---")
    print(f"{'Asset':<15} {'True μ':>8} {'Est1 μ':>8} {'Est2 μ':>8}")
    for i, name in enumerate(ASSETS):
        print(f"{name:<15} {MU[i]:>8.1%} {mu_est1[i]:>8.1%} {mu_est2[i]:>8.1%}")

    print(f"\n{'Asset':<15} {'Optimal w':>10} {'Window 1 w':>12} {'Window 2 w':>12}")
    for i, name in enumerate(ASSETS):
        print(f"{name:<15} {w_true[i]:>10.1%} {w1[i]:>12.1%} {w2[i]:>12.1%}")
    print("\nDramatic swings in weights from tiny changes in estimated returns.")
    print("This is the model's central practical problem.")
    return w1, w2, w_true


# ── VISUALISATIONS ────────────────────────────────────────────────────────────

def plot_frontier(mu, cov, vols, rets, mvp_w, ms_w, rf=0.04):
    rand_v, rand_r, rand_sh = random_portfolios(mu, cov)

    fig, ax = plt.subplots(figsize=(10, 7))
    sc = ax.scatter(rand_v * 100, rand_r * 100, c=rand_sh,
                    cmap='YlOrRd', alpha=0.3, s=10)
    plt.colorbar(sc, ax=ax, label='Sharpe Ratio')
    ax.plot(vols * 100, rets * 100, 'b-', lw=2.5, label='Efficient Frontier')

    ms_vol = port_vol(ms_w, cov)
    ms_ret = port_return(ms_w, mu)
    mv_vol = port_vol(mvp_w, cov)
    mv_ret = port_return(mvp_w, mu)

    ax.scatter(ms_vol * 100, ms_ret * 100, color='gold', s=200,
               edgecolors='black', zorder=10, label='Max Sharpe (Tangency)')
    ax.scatter(mv_vol * 100, mv_ret * 100, color='limegreen', s=200,
               edgecolors='black', zorder=10, label='Min Variance')

    # Capital Market Line
    cml_v = np.linspace(0, ms_vol * 1.5, 100)
    cml_r = rf + (ms_ret - rf) / ms_vol * cml_v
    ax.plot(cml_v * 100, cml_r * 100, 'k--', lw=1.5, alpha=0.6, label='CML')
    ax.scatter(0, rf * 100, color='black', s=80, zorder=10,
               label=f'Risk-free ({rf:.0%})')

    for i, name in enumerate(ASSETS):
        ax.scatter(VOLS[i] * 100, mu[i] * 100, marker='D', s=70, zorder=8)
        ax.annotate(name, (VOLS[i] * 100, mu[i] * 100),
                    xytext=(5, 3), textcoords='offset points', fontsize=8)

    ax.set_xlabel('Volatility (%)'); ax.set_ylabel('Expected Return (%)')
    ax.set_title('Markowitz Efficient Frontier')
    ax.legend(fontsize=9); ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig('plots/frontier.png', dpi=150)
    plt.show()
    print("saved plots/frontier.png")


def plot_weights(vols, weights_list):
    weights_arr = np.array(weights_list)
    colours = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.stackplot(vols * 100, weights_arr.T, labels=ASSETS, colors=colours, alpha=0.8)
    ax.set_xlabel('Portfolio Volatility (%)'); ax.set_ylabel('Weight')
    ax.set_title('Portfolio Composition Along the Efficient Frontier')
    ax.legend(loc='upper left', fontsize=9); ax.set_ylim(0, 1); ax.grid(alpha=0.2)
    plt.tight_layout()
    plt.savefig('plots/weights.png', dpi=150)
    plt.show()
    print("saved plots/weights.png")


def plot_correlation(corr):
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(corr, cmap='RdYlGn', vmin=-1, vmax=1)
    plt.colorbar(im, ax=ax)
    ax.set_xticks(range(len(ASSETS))); ax.set_yticks(range(len(ASSETS)))
    ax.set_xticklabels(ASSETS, rotation=30, ha='right', fontsize=9)
    ax.set_yticklabels(ASSETS, fontsize=9)
    for i in range(len(ASSETS)):
        for j in range(len(ASSETS)):
            ax.text(j, i, f'{corr[i,j]:.2f}', ha='center', va='center', fontsize=10)
    ax.set_title('Asset Correlation Matrix\n(crisis: most correlations spike toward +1)')
    plt.tight_layout()
    plt.savefig('plots/correlations.png', dpi=150)
    plt.show()
    print("saved plots/correlations.png")


def plot_crisis_corr():
    """
    Diversification tends to fail in crises when you need it most.
    Correlations spike because a single common factor (panic, deleveraging)
    overwhelms the individual asset dynamics.
    """
    rng = np.random.default_rng(0)
    normal = rng.multivariate_normal([0, 0], [[1, 0.3], [0.3, 1]], 250)
    crisis = rng.multivariate_normal([0, 0], [[1, 0.88], [0.88, 1]], 63)

    fig, axes = plt.subplots(1, 2, figsize=(11, 5))
    fig.suptitle('Correlation Breakdown in Crises', fontweight='bold')
    for ax, data, label, col in zip(
        axes, [normal, crisis],
        ['Normal (ρ ≈ 0.3)', 'Crisis (ρ ≈ 0.9)'],
        ['steelblue', 'tomato']
    ):
        rho_emp = np.corrcoef(data[:, 0], data[:, 1])[0, 1]
        ax.scatter(data[:, 0], data[:, 1], alpha=0.5, color=col, s=20)
        ax.set_title(f'{label}\n(empirical ρ = {rho_emp:.2f})')
        ax.set_xlabel('UK Equity Return'); ax.set_ylabel('US Equity Return')
        ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig('plots/crisis_corr.png', dpi=150)
    plt.show()
    print("saved plots/crisis_corr.png")


# ── MAIN ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    os.makedirs('plots', exist_ok=True)
    cov = build_cov(VOLS, CORR)

    print("=" * 55)
    print("  MARKOWITZ PORTFOLIO OPTIMISATION")
    print("=" * 55)

    mvp_w = min_var_portfolio(cov)
    ms_w  = max_sharpe_portfolio(MU, cov)

    print("\n--- Minimum Variance Portfolio ---")
    for name, w in zip(ASSETS, mvp_w):
        print(f"  {name:<15}: {w:.1%}")
    print(f"  Return: {port_return(mvp_w, MU):.2%}, Vol: {port_vol(mvp_w, cov):.2%}, "
          f"Sharpe: {sharpe(mvp_w, MU, cov):.3f}")

    print("\n--- Maximum Sharpe (Tangency) Portfolio ---")
    for name, w in zip(ASSETS, ms_w):
        print(f"  {name:<15}: {w:.1%}")
    print(f"  Return: {port_return(ms_w, MU):.2%}, Vol: {port_vol(ms_w, cov):.2%}, "
          f"Sharpe: {sharpe(ms_w, MU, cov):.3f}")

    print("\nComputing efficient frontier...")
    vols, rets, weights_list = efficient_frontier(MU, cov)

    # Estimation instability demonstration
    estimation_instability_demo(cov)

    print("\nGenerating plots...")
    plot_correlation(CORR)
    plot_frontier(MU, cov, vols, rets, mvp_w, ms_w)
    plot_weights(vols, weights_list)
    plot_crisis_corr()
    print("\nAll plots saved to ./plots/")
