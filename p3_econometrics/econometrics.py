"""
Econometrics: OLS Regression on UK Macro Data (2000-2023)
==========================================================
I ran this to look at two well-known macro relationships:
1. The Phillips Curve (unemployment -> wage growth)
2. The Fisher equation (inflation -> interest rates)

Built OLS from scratch rather than using statsmodels, because I wanted
to understand what was actually being computed at each step. The maths
isn't that hard once you see it's just minimising a sum of squares
using matrix calculus.

Main findings: strong positive autocorrelation in residuals (DW = 0.47),
meaning standard errors are understated. I implemented Newey-West HAC
standard errors to correct for this -- the intercept SE comes out 47%
larger than OLS. Also ran a Chow test for the 2022 structural break:
F=4.97, p=0.018, so the Phillips Curve relationship did shift post-pandemic.

Data sources: ONS EARN01 (wages), ONS CPI, BoE base rate, ONS UNEM01.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats
import os


# ── DATA (ONS/BoE, annual, 2000-2023) ────────────────────────────────────────

DATA = {
    'year': list(range(2000, 2024)),
    'inflation': [
        0.8, 1.2, 1.3, 1.4, 1.3, 2.1, 2.3, 2.3, 3.6, 2.2,
        3.3, 4.5, 2.8, 2.6, 1.5, 0.0, 0.7, 2.7, 2.5, 1.8,
        0.9, 2.5, 9.1, 6.8
    ],
    'unemployment': [
        5.4, 5.0, 5.1, 5.0, 4.7, 4.8, 5.4, 5.4, 5.7, 7.6,
        7.8, 8.1, 7.9, 7.6, 6.3, 5.4, 4.9, 4.4, 4.1, 3.8,
        4.5, 4.5, 3.7, 4.2
    ],
    'wage_growth': [
        5.0, 4.8, 4.2, 4.0, 4.8, 4.9, 4.8, 4.9, 4.1, 1.2,
        2.2, 1.8, 2.0, 1.8, 1.8, 2.8, 2.5, 3.2, 3.5, 3.6,
        4.1, 7.2, 7.9, 7.3
    ],
    'base_rate': [
        6.0, 5.25, 4.0, 3.75, 4.75, 4.5, 5.0, 5.75, 4.5, 0.5,
        0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.25, 0.25, 0.75, 0.75,
        0.1, 0.25, 2.25, 5.25
    ]
}


def load_data():
    df = pd.DataFrame(DATA)
    return df


# ── OLS FROM SCRATCH ──────────────────────────────────────────────────────────
# beta_hat = (X^T X)^{-1} X^T y
# This is the matrix form of the normal equations, derived by minimising
# the sum of squared residuals. Using np.linalg.solve rather than
# explicitly inverting (numerically more stable).

class OLS:
    """
    Ordinary Least Squares regression built from the normal equations.
    Supports single or multiple regressors; always adds an intercept.
    """

    def __init__(self):
        self.beta = None
        self.se   = None
        self.t    = None
        self.p    = None
        self.resid = None
        self.fitted = None
        self.r2 = None
        self.adj_r2 = None
        self.n = None
        self.k = None

    def fit(self, x, y):
        y = np.asarray(y, float)
        x = np.asarray(x, float)
        if x.ndim == 1:
            x = x.reshape(-1, 1)

        # prepend column of 1s for intercept
        X = np.hstack([np.ones((len(y), 1)), x])
        self.n, self.k = X.shape

        # normal equations: beta = (X^T X)^{-1} X^T y
        self.beta  = np.linalg.solve(X.T @ X, X.T @ y)
        self.fitted = X @ self.beta
        self.resid  = y - self.fitted

        # unbiased variance estimate -- divide by n-k not n
        # (k parameters estimated consume k degrees of freedom)
        ssr = self.resid @ self.resid
        if self.n > self.k:
            sigma_sq = ssr / (self.n - self.k)
        else:
            sigma_sq = np.nan

        cov_beta = sigma_sq * np.linalg.inv(X.T @ X)
        self.se  = np.sqrt(np.diag(cov_beta))

        # t-statistics and two-tailed p-values
        self.t = self.beta / self.se
        self.p = [2 * (1 - stats.t.cdf(abs(ti), df=self.n - self.k))
                  for ti in self.t]

        # R-squared
        ss_tot = np.sum((y - y.mean())**2)
        self.r2 = 1 - ssr / ss_tot
        if self.n > self.k:
            self.adj_r2 = 1 - (1 - self.r2) * (self.n - 1) / (self.n - self.k)
        else:
            self.adj_r2 = np.nan

        return self

    def summary(self, labels=None):
        if labels is None:
            labels = [f'X{i}' for i in range(self.k - 1)]
        names = ['Intercept'] + list(labels)
        print("-" * 60)
        print(f"{'Variable':<16} {'Coef':>9} {'SE':>9} {'t':>8} {'p':>9}")
        print("-" * 60)
        for i, name in enumerate(names):
            stars = '***' if self.p[i] < 0.01 else '**' if self.p[i] < 0.05 else '*' if self.p[i] < 0.10 else ''
            print(f"{name:<16} {self.beta[i]:>9.4f} {self.se[i]:>9.4f} "
                  f"{self.t[i]:>8.3f} {self.p[i]:>9.4f} {stars}")
        print("-" * 60)
        print(f"R² = {self.r2:.4f}   Adj R² = {self.adj_r2:.4f}   n={self.n}   k={self.k}")


# ── DIAGNOSTIC TESTS ──────────────────────────────────────────────────────────

def durbin_watson(resid):
    """
    DW = sum((e_t - e_{t-1})^2) / sum(e_t^2)
    DW ~= 2: no autocorrelation
    DW < 1.5: positive autocorrelation (common in macro time series)

    If DW << 2, standard errors are understated and t-stats are too big.
    Use newey_west_se() below to get HAC-corrected standard errors.
    """
    e = resid
    dw = np.sum(np.diff(e)**2) / (e @ e)
    print(f"\nDurbin-Watson: {dw:.4f}")
    if dw < 1.5:
        print("  → Positive autocorrelation detected.")
        print("  → Standard errors are likely understated (t-stats too large).")
        print("  → Use newey_west_se() for HAC-corrected inference.")
    elif dw > 2.5:
        print("  → Negative autocorrelation")
    else:
        print("  → No strong autocorrelation")
    return dw


def newey_west_se(X, resid, bandwidth=None):
    """
    Newey-West HAC (heteroscedasticity and autocorrelation consistent) SEs.
    Corrects the understatement of OLS SEs when residuals are autocorrelated.

    Sandwich estimator: V_HAC = n * (X'X)^{-1} * S_HAC * (X'X)^{-1}
    where S_HAC uses the Bartlett kernel to downweight distant lags:
        S_HAC = Gamma(0) + sum_{h=1}^{m} w_h * (Gamma(h) + Gamma(h)')
        Gamma(h) = (1/n) * sum_{t=h+1}^n e_t * e_{t-h} * x_t * x_{t-h}'
        w_h = 1 - h/(m+1)

    Bandwidth m = floor(4*(n/100)^(2/9)) is the standard data-driven choice.
    """
    n, k = X.shape
    if bandwidth is None:
        bandwidth = int(np.floor(4 * (n / 100) ** (2 / 9)))
    XtX_inv = np.linalg.inv(X.T @ X)
    Xe = X * resid[:, None]
    S = (Xe.T @ Xe) / n
    for h in range(1, bandwidth + 1):
        w = 1 - h / (bandwidth + 1)
        Gamma_h = (Xe[h:].T @ Xe[:-h]) / n
        S += w * (Gamma_h + Gamma_h.T)
    V_HAC = n * XtX_inv @ S @ XtX_inv
    return np.sqrt(np.diag(V_HAC))


def jarque_bera(resid):
    """
    Tests normality of residuals.
    JB = n/6 * (skew^2 + kurt^2/4). Under H0 (normal): JB ~ chi2(2).
    Normality matters more in small samples (n=24 here) than in large ones.
    """
    stat, p = stats.jarque_bera(resid)
    skew = stats.skew(resid)
    kurt = stats.kurtosis(resid)
    print(f"\nJarque-Bera: stat={stat:.4f}  p={p:.4f}  skew={skew:.3f}  kurt={kurt:.3f}")
    if p < 0.05:
        print("  → Reject normality at 5%")
    else:
        print("  → Cannot reject normality")
    return stat, p


def confidence_band(x_raw, model, alpha=0.05):
    """
    95% CI for the conditional mean E[y|x] -- i.e. the expected location
    of the regression line, not a prediction interval for individual
    observations (which would also include the sigma^2 noise term).
    """
    x_sorted = np.sort(x_raw)
    X_plot = np.column_stack([np.ones_like(x_sorted), x_sorted])
    y_hat = X_plot @ model.beta
    XtX_inv = np.linalg.inv(
        np.column_stack([np.ones(len(x_raw)), x_raw]).T @
        np.column_stack([np.ones(len(x_raw)), x_raw])
    )
    ssr = model.resid @ model.resid
    sigma_sq = ssr / (model.n - model.k)
    se_pred = np.sqrt(sigma_sq * np.array([x @ XtX_inv @ x for x in X_plot]))
    t_crit = stats.t.ppf(1 - alpha / 2, df=model.n - model.k)
    return x_sorted, y_hat, y_hat - t_crit * se_pred, y_hat + t_crit * se_pred


# ── CHOW STRUCTURAL BREAK TEST ───────────────────────────────────────────────

def chow_test(x_pre, y_pre, x_post, y_post):
    """
    Chow (1960) test for a structural break.
    Tests whether the regression coefficients are stable across two subsamples.

    F = [(RSS_pool - RSS_pre - RSS_post) / k] / [(RSS_pre + RSS_post) / (n - 2k)]

    Under H0 (no break): F ~ F(k, n-2k). Rejection means the relationship
    differs significantly across the split.

    Caveat: post-2022 has only n=2 observations and k=2 parameters, so
    RSS_post = 0 (exact fit). The F-stat is still valid but treat as
    indicative given the tiny post-sample size.
    """
    def ols_rss(x, y):
        X_ = np.column_stack([np.ones(len(y)), np.asarray(x, float)])
        b  = np.linalg.solve(X_.T @ X_, X_.T @ y)
        r  = np.asarray(y, float) - X_ @ b
        return float(r @ r), X_.shape[1]

    x_all = np.concatenate([np.asarray(x_pre, float), np.asarray(x_post, float)])
    y_all = np.concatenate([np.asarray(y_pre, float), np.asarray(y_post, float)])
    n = len(y_all)

    RSS_pool, k = ols_rss(x_all, y_all)
    RSS_pre,  _ = ols_rss(x_pre,  y_pre)
    RSS_post, _ = ols_rss(x_post, y_post)

    F = ((RSS_pool - RSS_pre - RSS_post) / k) / ((RSS_pre + RSS_post) / (n - 2 * k))
    p = float(1 - stats.f.cdf(F, k, n - 2 * k))
    return float(F), p


# ── SUBSAMPLE SPLIT ───────────────────────────────────────────────────────────

def compare_subsamples(df):
    """
    Split at 2022 and run separate regressions, then test for a structural
    break with the Chow test.

    Caveat: post-2022 has only 2 observations, so its slope is exactly
    determined by two points and standard errors aren't meaningful --
    the comparison is illustrative; the Chow test formalises it.
    """
    pre  = df[df['year'] < 2022]
    post = df[df['year'] >= 2022]

    m_pre  = OLS().fit(pre['unemployment'].values,  pre['wage_growth'].values)
    m_post = OLS().fit(post['unemployment'].values, post['wage_growth'].values)

    print("\n--- Phillips Curve: Pre-2022 vs Post-2022 ---")
    print(f"Pre-2022  (n={len(pre)}):  slope = {m_pre.beta[1]:.3f}, intercept = {m_pre.beta[0]:.3f}")
    print(f"Post-2022 (n={len(post)}): slope = {m_post.beta[1]:.3f}, intercept = {m_post.beta[0]:.3f}")
    print("The intercept shift suggests wages grew faster at the same unemployment rate post-2022.")
    print("Supply-side inflation (energy, supply chains) likely explains this.")

    F, p = chow_test(pre['unemployment'].values,  pre['wage_growth'].values,
                     post['unemployment'].values, post['wage_growth'].values)
    sig = "→ Reject H0: significant structural break at 5%" if p < 0.05 else "→ Cannot reject H0"
    print(f"\nChow test: F={F:.3f}, p={p:.3f}  {sig}")
    return m_pre, m_post


# ── VISUALISATIONS ────────────────────────────────────────────────────────────

def plot_time_series(df):
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    fig.suptitle('UK Macro Variables 2000-2023', fontsize=12, fontweight='bold')
    series = [('inflation', 'CPI Inflation (%)', 'steelblue'),
              ('unemployment', 'Unemployment (%)', 'tomato'),
              ('wage_growth', 'Wage Growth (%)', 'forestgreen'),
              ('base_rate', 'BoE Base Rate (%)', 'darkorange')]
    for ax, (col, label, c) in zip(axes.flatten(), series):
        ax.plot(df['year'], df[col], 'o-', color=c, lw=2, markersize=5)
        ax.axvspan(2007.5, 2009.5, alpha=0.1, color='red')
        ax.axvspan(2019.5, 2020.5, alpha=0.1, color='purple')
        ax.set_title(label); ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig('plots/time_series.png', dpi=150); plt.show()
    print("saved plots/time_series.png")


def plot_phillips(df, model):
    x_s, y_hat, lower, upper = confidence_band(df['unemployment'].values, model)
    fig, ax = plt.subplots(figsize=(9, 6))
    sc = ax.scatter(df['unemployment'], df['wage_growth'],
                    c=df['year'], cmap='viridis', s=60, zorder=5)
    plt.colorbar(sc, ax=ax, label='Year')
    ax.plot(x_s, y_hat, 'r-', lw=2, label='OLS fit')
    ax.fill_between(x_s, lower, upper, alpha=0.2, color='red', label='95% CI')
    for _, row in df[df['year'].isin([2009, 2020, 2022, 2023])].iterrows():
        ax.annotate(str(int(row['year'])),
                    (row['unemployment'], row['wage_growth']),
                    xytext=(5, 5), textcoords='offset points', fontsize=9)
    ax.set_xlabel('Unemployment (%)'); ax.set_ylabel('Wage Growth (%)')
    ax.set_title(f"Phillips Curve (2000-2023)\n"
                 f"β₁={model.beta[1]:.3f}  R²={model.r2:.3f}")
    ax.legend(); ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig('plots/phillips_curve.png', dpi=150); plt.show()
    print("saved plots/phillips_curve.png")


def plot_residuals(model, df):
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    fig.suptitle('OLS Residual Diagnostics', fontsize=12)

    axes[0, 0].scatter(model.fitted, model.resid, alpha=0.7, color='steelblue')
    axes[0, 0].axhline(0, color='red', ls='--')
    axes[0, 0].set_xlabel('Fitted'); axes[0, 0].set_ylabel('Residual')
    axes[0, 0].set_title('Residuals vs Fitted'); axes[0, 0].grid(alpha=0.3)

    stats.probplot(model.resid, plot=axes[0, 1])
    axes[0, 1].set_title('Normal Q-Q Plot'); axes[0, 1].grid(alpha=0.3)

    axes[1, 0].plot(df['year'], model.resid, 'o-', color='steelblue', markersize=5)
    axes[1, 0].axhline(0, color='red', ls='--')
    axes[1, 0].set_xlabel('Year'); axes[1, 0].set_ylabel('Residual')
    axes[1, 0].set_title('Residuals Over Time\n(trending = autocorrelation)')
    axes[1, 0].grid(alpha=0.3)

    axes[1, 1].scatter(model.fitted, np.abs(model.resid), alpha=0.7, color='steelblue')
    axes[1, 1].set_xlabel('Fitted'); axes[1, 1].set_ylabel('|Residual|')
    axes[1, 1].set_title('Scale-Location\n(fan shape = heteroscedasticity)')
    axes[1, 1].grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig('plots/residuals.png', dpi=150); plt.show()
    print("saved plots/residuals.png")


def plot_fisher(df, model):
    x_s, y_hat, lower, upper = confidence_band(df['inflation'].values, model)
    fig, ax = plt.subplots(figsize=(9, 6))
    sc = ax.scatter(df['inflation'], df['base_rate'],
                    c=df['year'], cmap='plasma', s=60, zorder=5)
    plt.colorbar(sc, ax=ax, label='Year')
    ax.plot(x_s, y_hat, 'r-', lw=2, label='OLS fit')
    ax.fill_between(x_s, lower, upper, alpha=0.2, color='red', label='95% CI')
    for _, row in df[df['year'].isin([2022, 2023, 2009])].iterrows():
        ax.annotate(str(int(row['year'])),
                    (row['inflation'], row['base_rate']),
                    xytext=(5, 5), textcoords='offset points', fontsize=9)
    ax.set_xlabel('CPI Inflation (%)'); ax.set_ylabel('BoE Base Rate (%)')
    ax.set_title(f"Inflation vs BoE Rate (Fisher relationship)\n"
                 f"β₁={model.beta[1]:.3f}  R²={model.r2:.3f}")
    ax.legend(); ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig('plots/fisher.png', dpi=150); plt.show()
    print("saved plots/fisher.png")


# ── MAIN ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    os.makedirs('plots', exist_ok=True)
    df = load_data()

    print("=" * 60)
    print("  UK ECONOMETRICS: OLS ON MACRO DATA (2000-2023)")
    print("=" * 60)

    # Regression 1: Phillips Curve
    print("\n--- Phillips Curve: Unemployment → Wage Growth ---")
    m1 = OLS().fit(df['unemployment'].values, df['wage_growth'].values)
    m1.summary(labels=['Unemployment'])
    print(f"\n1pp more unemployment → {m1.beta[1]:.3f}pp change in wage growth")
    dw1 = durbin_watson(m1.resid)
    jarque_bera(m1.resid)

    # Newey-West HAC correction
    X_m1 = np.column_stack([np.ones(len(df)), df['unemployment'].values])
    se_nw = newey_west_se(X_m1, m1.resid)
    bw = int(np.floor(4 * (len(df) / 100) ** (2 / 9)))
    print(f"\nNewey-West HAC SEs (bandwidth={bw}):")
    print(f"  Intercept: OLS={m1.se[0]:.4f}  NW-HAC={se_nw[0]:.4f}  "
          f"({(se_nw[0]/m1.se[0]-1)*100:.0f}% larger)")
    print(f"  Slope:     OLS={m1.se[1]:.4f}  NW-HAC={se_nw[1]:.4f}  "
          f"({(se_nw[1]/m1.se[1]-1)*100:.0f}% larger)")

    # Regression 2: Fisher
    print("\n--- Fisher Equation: Inflation → Base Rate ---")
    m2 = OLS().fit(df['inflation'].values, df['base_rate'].values)
    m2.summary(labels=['Inflation'])
    print(f"\nFull Fisher neutrality implies β₁=1. Got β₁={m2.beta[1]:.3f}")
    print("BoE stuck near zero lower bound 2010-2021 explains the weak Fisher result")
    dw2 = durbin_watson(m2.resid)

    # Regression 3: Multiple
    print("\n--- Multiple Regression: Unemployment + Inflation → Wages ---")
    X3 = np.column_stack([df['unemployment'].values, df['inflation'].values])
    m3 = OLS().fit(X3, df['wage_growth'].values)
    m3.summary(labels=['Unemployment', 'Inflation'])
    print(f"\nAdding inflation: R² {m1.r2:.3f} → {m3.r2:.3f}")

    # Pre/post 2022 comparison + Chow test
    compare_subsamples(df)

    print("\nGenerating plots...")
    plot_time_series(df)
    plot_phillips(df, m1)
    plot_residuals(m1, df)
    plot_fisher(df, m2)
    print("\nAll plots saved to ./plots/")
