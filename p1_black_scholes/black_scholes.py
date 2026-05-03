"""
Black-Scholes Options Pricing
==============================
I built this after getting interested in how options are actually priced.
The maths is more interesting than I expected -- the key insight is that
the expected return of the stock doesn't matter, which seems wrong until
you understand the replication argument.

Main references I used:
- Hull's Options, Futures and Other Derivatives (library copy)
- The original Black-Scholes paper (1973) which is surprisingly readable
- Some YouTube explanations of Ito's lemma for the intuition

Model assumes: geometric Brownian motion, constant vol, no dividends,
European exercise only, no transaction costs. All of these are wrong in
practice to varying degrees -- the vol smile at the bottom shows the
most obvious failure.

I've also added a binomial tree as a sanity check on the formula --
it should converge to the BS price as you add more steps.
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm
import os


# ── CORE FORMULA ─────────────────────────────────────────────────────────────

def _d1_d2(S, K, T, r, sigma):
    """
    d1 and d2 -- intermediate quantities used throughout.
    
    The sigma^2/2 in d1 is the Ito correction -- when you apply the chain
    rule to ln(S) for a random process, you get an extra term. This confused
    me for a while; it comes from the second-order Taylor expansion mattering
    for stochastic processes in a way it doesn't for ordinary functions.
    """
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return d1, d2


def bs_call(S, K, T, r, sigma):
    """
    Black-Scholes call: C = S*N(d1) - K*e^(-rT)*N(d2)
    
    S*N(d1)         -- expected stock price received if exercised (prob weighted)
    K*e^(-rT)*N(d2) -- expected strike paid, discounted back to today
    """
    d1, d2 = _d1_d2(S, K, T, r, sigma)
    return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)


def bs_put(S, K, T, r, sigma):
    """Put via put-call parity: P = C - S + K*e^(-rT)"""
    return bs_call(S, K, T, r, sigma) - S + K * np.exp(-r * T)


# ── THE GREEKS ────────────────────────────────────────────────────────────────

def delta(S, K, T, r, sigma, kind='call'):
    """
    Price change per £1 move in stock. Also the hedge ratio.
    ATM call has delta ~0.5. Deep ITM -> 1. Deep OTM -> 0.
    To delta-hedge: short delta shares for every long call.
    """
    d1, _ = _d1_d2(S, K, T, r, sigma)
    return norm.cdf(d1) if kind == 'call' else norm.cdf(d1) - 1


def gamma(S, K, T, r, sigma):
    """
    Rate of change of delta. Same for calls and puts.
    Highest ATM near expiry. Always positive for long options.
    High gamma = delta changes fast = need to rebalance hedge often.
    """
    d1, _ = _d1_d2(S, K, T, r, sigma)
    return norm.pdf(d1) / (S * sigma * np.sqrt(T))


def theta(S, K, T, r, sigma, kind='call'):
    """Daily time decay (divided by 365). Almost always negative for long options."""
    d1, d2 = _d1_d2(S, K, T, r, sigma)
    decay = -(S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T))
    rate_part = (-r * K * np.exp(-r * T) * norm.cdf(d2) if kind == 'call'
                 else r * K * np.exp(-r * T) * norm.cdf(-d2))
    return (decay + rate_part) / 365


def vega(S, K, T, r, sigma):
    """Sensitivity to vol per 1% change. Always positive for long options."""
    d1, _ = _d1_d2(S, K, T, r, sigma)
    return S * norm.pdf(d1) * np.sqrt(T) / 100


def rho(S, K, T, r, sigma, kind='call'):
    """Sensitivity to interest rate per 1% change."""
    _, d2 = _d1_d2(S, K, T, r, sigma)
    if kind == 'call':
        return K * T * np.exp(-r * T) * norm.cdf(d2) / 100
    return -K * T * np.exp(-r * T) * norm.cdf(-d2) / 100


def greeks(S, K, T, r, sigma, kind='call'):
    return {
        'delta': delta(S, K, T, r, sigma, kind),
        'gamma': gamma(S, K, T, r, sigma),
        'theta': theta(S, K, T, r, sigma, kind),
        'vega':  vega(S, K, T, r, sigma),
        'rho':   rho(S, K, T, r, sigma, kind)
    }


# ── IMPLIED VOLATILITY ────────────────────────────────────────────────────────
# Traders quote vol, not price. IV is the vol that makes BS = market price.
# Newton-Raphson works because vega > 0 always (price strictly increases
# in sigma), so there's exactly one solution and it always converges.

def implied_vol(market_price, S, K, T, r, kind='call', guess=0.20, tol=1e-6):
    """
    Newton-Raphson: sigma_new = sigma - (BS(sigma) - target) / vega(sigma)
    Usually converges in ~5 iterations.
    """
    sigma = guess
    for _ in range(100):
        price = bs_call(S, K, T, r, sigma) if kind == 'call' else bs_put(S, K, T, r, sigma)
        v = vega(S, K, T, r, sigma) * 100  # full units for the Newton step
        if abs(v) < 1e-10:
            return None  # vega vanishes for very deep ITM/OTM options
        sigma -= (price - market_price) / v
        if abs(price - market_price) < tol:
            return sigma
    return sigma


# ── BINOMIAL TREE (CRR) ───────────────────────────────────────────────────────
# Cox-Ross-Rubinstein discrete-time approximation.
# Discretise into n steps: at each node price goes up by u or down by d=1/u.
# u is chosen to match vol: u = exp(sigma * sqrt(dt)).
# As n -> inf, converges to BS for European options.
# Advantage over BS: handles American options (early exercise check at each node).

def binomial_tree(S, K, T, r, sigma, n_steps=300, kind='call', exercise='european'):
    dt = T / n_steps
    u  = np.exp(sigma * np.sqrt(dt))
    d  = 1.0 / u
    p  = (np.exp(r * dt) - d) / (u - d)   # risk-neutral probability of up move
    disc = np.exp(-r * dt)

    j  = np.arange(n_steps + 1)
    ST = S * u**j * d**(n_steps - j)
    values = np.maximum(ST - K, 0) if kind == 'call' else np.maximum(K - ST, 0)

    for step in range(n_steps - 1, -1, -1):
        j = np.arange(step + 1)
        S_node = S * u**j * d**(step - j)
        values = disc * (p * values[1:step + 2] + (1 - p) * values[:step + 1])
        if exercise == 'american':
            intrinsic = (np.maximum(S_node - K, 0) if kind == 'call'
                         else np.maximum(K - S_node, 0))
            values = np.maximum(values, intrinsic)

    return float(values[0])


# ── PLOTS ─────────────────────────────────────────────────────────────────────

def plot_price_vs_spot(K=100, T=0.5, r=0.05, sigma=0.20):
    spots = np.linspace(60, 150, 300)
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(spots, [bs_call(s, K, T, r, sigma) for s in spots], 'b-', lw=2, label='Call')
    ax.plot(spots, [bs_put(s, K, T, r, sigma) for s in spots],  'r-', lw=2, label='Put')
    ax.plot(spots, np.maximum(spots - K, 0), 'b--', lw=1, alpha=0.4, label='Call intrinsic')
    ax.axvline(K, color='grey', ls=':', lw=1)
    ax.set_xlabel('Stock Price S'); ax.set_ylabel('Option Price (£)')
    ax.set_title(f'BS Prices  |  K={K}, T={T}yr, r={r:.0%}, σ={sigma:.0%}')
    ax.legend(); ax.grid(alpha=0.3)
    plt.tight_layout(); plt.savefig('plots/price_vs_spot.png', dpi=150); plt.show()
    print("saved plots/price_vs_spot.png")


def plot_greeks(K=100, T=0.5, r=0.05, sigma=0.20):
    spots = np.linspace(60, 150, 300)
    fig, axes = plt.subplots(2, 2, figsize=(11, 7))
    fig.suptitle('Call Greeks vs Stock Price')
    items = [
        ([delta(s, K, T, r, sigma) for s in spots], 'Delta', 'steelblue'),
        ([gamma(s, K, T, r, sigma) for s in spots], 'Gamma', 'tomato'),
        ([theta(s, K, T, r, sigma) for s in spots], 'Theta (daily)', 'forestgreen'),
        ([vega(s, K, T, r, sigma) for s in spots],  'Vega (per 1% vol)', 'darkorange'),
    ]
    for ax, (vals, name, col) in zip(axes.flatten(), items):
        ax.plot(spots, vals, color=col, lw=2)
        ax.axvline(K, color='grey', ls=':', lw=1)
        ax.set_title(name); ax.set_xlabel('S'); ax.grid(alpha=0.3)
    plt.tight_layout(); plt.savefig('plots/greeks.png', dpi=150); plt.show()
    print("saved plots/greeks.png")


def plot_theta_decay(S=100, K=100, r=0.05, sigma=0.20):
    times = np.linspace(0.02, 1.0, 300)
    fig, ax = plt.subplots(figsize=(9, 5))
    for label, k_mult, col in [('ATM (K=100)', 1.0, 'b'),
                                 ('ITM (K=90)',  0.9, 'g'),
                                 ('OTM (K=110)', 1.1, 'r')]:
        ax.plot(times, [bs_call(S, K * k_mult, t, r, sigma) for t in times],
                col + '-', lw=2, label=label)
    ax.set_xlabel('Time to Expiry (years)'); ax.set_ylabel('Call Price (£)')
    ax.set_title('Time Decay'); ax.legend(); ax.grid(alpha=0.3)
    plt.tight_layout(); plt.savefig('plots/theta_decay.png', dpi=150); plt.show()
    print("saved plots/theta_decay.png")


def plot_vol_smile():
    """
    In theory IV should be flat across strikes if BS were the right model.
    In practice OTM puts are more expensive -- the market prices in crash
    risk that lognormal returns can't capture. This is the skew.
    """
    strikes = np.array([80, 85, 90, 95, 100, 105, 110, 115, 120])
    iv_mkt  = np.array([0.28, 0.26, 0.24, 0.22, 0.20, 0.195, 0.195, 0.20, 0.205])
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(strikes, iv_mkt * 100, 'bo-', lw=2, markersize=7, label='Market IV')
    ax.axhline(20, color='red', ls='--', lw=1.5, label='BS flat assumption (20%)')
    ax.axvline(100, color='grey', ls=':', alpha=0.6)
    ax.set_xlabel('Strike'); ax.set_ylabel('Implied Vol (%)')
    ax.set_title('Volatility Skew\n(OTM puts price crash risk the model ignores)')
    ax.legend(); ax.grid(alpha=0.3)
    plt.tight_layout(); plt.savefig('plots/vol_smile.png', dpi=150); plt.show()
    print("saved plots/vol_smile.png")


# ── MAIN ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    os.makedirs('plots', exist_ok=True)

    S, K, T, r, sigma = 100, 100, 0.5, 0.05, 0.20

    print("=" * 50)
    print("  BLACK-SCHOLES OPTIONS PRICING")
    print("=" * 50)
    print(f"\nS={S}, K={K}, T={T}yr, r={r:.0%}, σ={sigma:.0%}\n")

    call = bs_call(S, K, T, r, sigma)
    put  = bs_put(S, K, T, r, sigma)
    print(f"Call: £{call:.4f}")
    print(f"Put:  £{put:.4f}")

    # put-call parity: C - P must equal S - K*e^(-rT)
    lhs, rhs = call - put, S - K * np.exp(-r * T)
    print(f"\nPut-call parity: {lhs:.6f} vs {rhs:.6f}  "
          f"{'✓' if abs(lhs - rhs) < 1e-10 else '✗'}")

    print("\nCall Greeks:")
    for name, val in greeks(S, K, T, r, sigma, 'call').items():
        print(f"  {name:6s}: {val:.5f}")

    # IV round-trip
    test_px = bs_call(S, K, T, r, 0.25)
    iv = implied_vol(test_px, S, K, T, r)
    print(f"\nIV round-trip at σ=25%: recovered {iv:.4f} "
          f"{'✓' if iv and abs(iv - 0.25) < 1e-5 else '✗'}")

    # Binomial tree convergence
    print(f"\nBinomial tree convergence (BS = £{call:.4f}):")
    for n in [10, 50, 200, 1000]:
        tp = binomial_tree(S, K, T, r, sigma, n_steps=n)
        print(f"  n={n:4d}: £{tp:.4f}  err={abs(tp - call):.4f}")

    # American put early-exercise premium
    ep = binomial_tree(S, K, T, r, sigma, n_steps=500, kind='put', exercise='european')
    ap = binomial_tree(S, K, T, r, sigma, n_steps=500, kind='put', exercise='american')
    print(f"\nEuropean put: £{ep:.4f}")
    print(f"American put: £{ap:.4f}  (early-exercise premium: £{ap - ep:.4f})")

    print("\nGenerating plots...")
    plot_price_vs_spot(K, T, r, sigma)
    plot_greeks(K, T, r, sigma)
    plot_theta_decay(S, K, r, sigma)
    plot_vol_smile()
    print("All plots saved to ./plots/")
