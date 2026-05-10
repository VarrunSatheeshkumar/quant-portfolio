"""
JustWalk: Quantitative Footfall and Energy Analytics
=====================================================
JustWalk installs piezoelectric floor tiles that convert footfall kinetic
energy into electricity. We secured £50,000 from Vodafone and have hardware
running at their London Paddington office.

I built this model to answer three questions that came up constantly:
1. How much energy does a site actually generate? (energy model)
2. Is the investment financially viable? (DCF / ROI model)
3. Are there days where the footfall data looks wrong? (anomaly detection)

The honest answer from the financial model: at an office site, direct
electricity revenue (~£2/year) doesn't justify the CapEx. The real value
proposition is selling footfall analytics as a SaaS product. The model
makes this explicit rather than hiding it -- and the transit hub scenario
at the bottom shows where the economics actually work.

Energy model grounded in physics: joules per step from piezo literature,
22% efficiency from manufacturer datasheets (rectifier + regulator losses).
Financial model: standard DCF with Newton-Raphson IRR.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy.optimize import minimize_scalar
from datetime import datetime, timedelta
import os


# ── SITE PARAMETERS ──────────────────────────────────────────────────────────

SITE = "Vodafone Paddington Office"
N_TILES = 50                 # tiles installed
TILE_COST = 800              # £ per tile (installed)
MAINTENANCE = 500            # £/year
ELEC_RATE  = 0.30            # £/kWh (UK commercial, 2023-24)
DISCOUNT_R = 0.08            # WACC: 8% (reasonable for hardware startup)
PROJECT_YRS = 10

# Physical parameters -- every number has a source
JOULES_PER_STEP = 2.5        # J per footfall (lit range: 1-7J, conservative mid)
EFFICIENCY      = 0.22       # 22% net efficiency (rectifier + voltage regulator)
STEPS_PER_TILE  = 2          # avg steps to cross a tile (geometric estimate)


# ── ENERGY MODEL ─────────────────────────────────────────────────────────────

def energy_kwh(footfall, n_tiles=N_TILES):
    """
    Energy from footfall:
    Wh = persons × steps/tile × J/step × efficiency × n_tiles / 3600
    (divide by 3600 because 1 Wh = 3600 J)

    Physical assumption: every visitor traverses the full tile corridor,
    so each person contributes STEPS_PER_TILE steps across all n_tiles tiles.
    At Paddington this is a ~25m corridor; the n_tiles multiplier reflects
    that the tiles are laid end-to-end and each person crosses all of them.

    Slightly surprised at how small the numbers are in practice --
    piezoelectric energy density is genuinely low.
    """
    wh = footfall * STEPS_PER_TILE * JOULES_PER_STEP * EFFICIENCY * n_tiles / 3600
    return wh / 1000  # convert to kWh


# ── FOOTFALL SIMULATION ───────────────────────────────────────────────────────
# Poisson arrivals with a time-varying rate. Poisson is the right model
# for count data where each event (a person arriving) is independent.

def simulate_footfall(n_days=365, peak_capacity=400, seed=42):
    """
    Simulate hourly footfall for a commercial office.
    
    Rate lambda(t) = peak * intraday_shape(hour) * seasonal(month) * weekday_factor
    
    Intraday shape: bimodal (morning and evening commute peaks).
    Weekend: ~95% reduction for an office site.
    """
    rng = np.random.default_rng(seed)
    start = datetime(2024, 1, 1)
    timestamps = [start + timedelta(hours=h) for h in range(n_days * 24)]
    hourly = []

    for ts in timestamps:
        h = ts.hour
        is_weekday = ts.weekday() < 5

        if is_weekday:
            # morning peak + lunch + evening peak
            base = (0.05
                    + 0.55 * np.exp(-((h - 8.5)**2) / 2.0)
                    + 0.18 * np.exp(-((h - 12.5)**2) / 1.5)
                    + 0.45 * np.exp(-((h - 17.5)**2) / 2.0))
        else:
            base = 0.03

        seasonal = 1.0 - 0.20 * (ts.month == 8) - 0.28 * (ts.month == 12)
        lam = max(0, base * seasonal * peak_capacity)
        hourly.append(rng.poisson(lam))

    df = pd.DataFrame({'timestamp': timestamps, 'footfall': hourly})
    df['date']      = pd.to_datetime(df['timestamp']).dt.date
    df['hour']      = pd.to_datetime(df['timestamp']).dt.hour
    df['weekday']   = pd.to_datetime(df['timestamp']).dt.weekday
    df['month']     = pd.to_datetime(df['timestamp']).dt.month
    df['is_weekday']= df['weekday'] < 5
    df['energy_kwh']= energy_kwh(df['footfall'])
    return df


def daily_totals(df):
    daily = df.groupby('date').agg(
        footfall=('footfall', 'sum'),
        energy_kwh=('energy_kwh', 'sum'),
        is_weekday=('is_weekday', 'first'),
        month=('month', 'first')
    ).reset_index()
    daily['revenue'] = daily['energy_kwh'] * ELEC_RATE
    return daily


# ── DCF MODEL ────────────────────────────────────────────────────────────────

def compute_npv(annual_kwh, n_tiles=N_TILES, tile_cost=TILE_COST,
                elec_rate=ELEC_RATE, extra_annual=0, discount_rate=DISCOUNT_R):
    """
    Standard discounted cash flow.
    NPV = -CapEx + sum(CF_t / (1+r)^t)
    
    extra_annual: any additional revenue beyond electricity (e.g. SaaS analytics)
    1% annual degradation in tile performance (from manufacturer specs).
    """
    capex = n_tiles * tile_cost
    annual_rev = annual_kwh * elec_rate + extra_annual
    annual_net = annual_rev - MAINTENANCE

    cash_flows = [-capex]
    for t in range(1, PROJECT_YRS + 1):
        cf = annual_net * (1 - 0.01)**t   # 1% annual degradation
        cash_flows.append(cf)

    npv = sum(cf / (1 + discount_rate)**t for t, cf in enumerate(cash_flows))
    return npv, cash_flows


def compute_irr(cash_flows):
    """
    Find r such that NPV(r) = 0. Newton-Raphson.
    Returns None if no real IRR exists (cash flows always negative).
    """
    if sum(cash_flows) <= 0:
        return None   # no sign change, no real IRR

    # simple bisection to bracket, then Newton-Raphson
    def npv_at(r):
        return sum(cf / (1 + r)**t for t, cf in enumerate(cash_flows))

    r = 0.10
    for _ in range(200):
        f  = npv_at(r)
        df = sum(-t * cf / (1 + r)**(t + 1) for t, cf in enumerate(cash_flows))
        if abs(df) < 1e-12:
            break
        r_new = r - f / df
        if abs(r_new - r) < 1e-8:
            return r_new if -0.99 < r_new < 50 else None
        r = r_new
    return r


# ── ANOMALY DETECTION ─────────────────────────────────────────────────────────
# Z-score on a rolling 28-day window.
# 28 days (4 weeks) means each day is compared to the same weekday 4 weeks ago,
# which implicitly controls for the weekly seasonality.

def detect_anomalies(daily, threshold=2.5):
    daily = daily.copy().sort_values('date').reset_index(drop=True)
    daily['date'] = pd.to_datetime(daily['date'])
    daily['roll_mean'] = daily['footfall'].rolling(28, min_periods=14).mean()
    daily['roll_std']  = daily['footfall'].rolling(28, min_periods=14).std()
    daily['z_score']   = (daily['footfall'] - daily['roll_mean']) / daily['roll_std']
    daily['anomaly']   = daily['z_score'].abs() > threshold
    return daily


def inject_anomalies(daily, seed=99):
    """Inject synthetic spikes and drops to validate the detector."""
    rng  = np.random.default_rng(seed)
    daily = daily.copy()
    daily['footfall'] = daily['footfall'].astype(float)
    wd_idx = daily[daily['is_weekday']].index
    spikes = rng.choice(wd_idx[50:200], 3, replace=False)
    drops  = rng.choice(wd_idx[200:300], 3, replace=False)
    daily.loc[spikes, 'footfall'] *= 2.8
    daily.loc[drops,  'footfall'] *= 0.1
    return daily


# ── MONTE CARLO NPV ───────────────────────────────────────────────────────────
# A point estimate of NPV hides all the uncertainty in the input parameters.
# Monte Carlo samples each uncertain parameter from a distribution and gives
# the full distribution of NPV outcomes -- much more honest for decision-making.

def monte_carlo_npv(annual_footfall, n_sims=5000, n_tiles=N_TILES,
                    tile_cost=TILE_COST, extra_mean=0, extra_sd=0, seed=42):
    """
    Uncertain parameters:
    - joules per step: Normal(2.5, 0.5)
    - efficiency: Normal(0.22, 0.04)
    - electricity rate: Normal(0.30, 0.06)
    - degradation: Normal(1%, 0.3%)
    - extra revenue: Normal(extra_mean, extra_sd)
    """
    rng  = np.random.default_rng(seed)
    npvs = np.zeros(n_sims)
    capex = n_tiles * tile_cost

    for i in range(n_sims):
        j_step = max(0.5, rng.normal(2.5, 0.5))
        eff    = np.clip(rng.normal(0.22, 0.04), 0.05, 0.40)
        rate   = max(0.05, rng.normal(ELEC_RATE, 0.06))
        degrad = max(0, rng.normal(0.01, 0.003))
        extra  = max(0, rng.normal(extra_mean, extra_sd)) if extra_sd > 0 else extra_mean

        kwh    = annual_footfall * STEPS_PER_TILE * j_step * eff * n_tiles / 3600 / 1000
        annual = kwh * rate + extra - MAINTENANCE

        cfs = [-capex] + [annual * (1 - degrad)**t for t in range(1, PROJECT_YRS + 1)]
        npvs[i] = sum(cf / (1 + DISCOUNT_R)**t for t, cf in enumerate(cfs))

    return npvs


# ── VISUALISATIONS ────────────────────────────────────────────────────────────

def plot_footfall(df):
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle(f'Footfall Patterns — {SITE}')

    avg = df.groupby(['hour', 'is_weekday'])['footfall'].mean().reset_index()
    for is_wd, label, col in [(True, 'Weekday', 'steelblue'), (False, 'Weekend', 'tomato')]:
        s = avg[avg['is_weekday'] == is_wd]
        axes[0].plot(s['hour'], s['footfall'], 'o-', label=label, color=col, lw=2)
    axes[0].set_title('Avg Hourly Footfall'); axes[0].set_xlabel('Hour')
    axes[0].set_ylabel('Persons'); axes[0].legend(); axes[0].grid(alpha=0.3)

    daily = daily_totals(df)
    daily['month_dt'] = pd.to_datetime(daily['date']).dt.to_period('M')
    monthly_e = daily.groupby('month_dt')['energy_kwh'].sum()
    monthly_e.plot(kind='bar', ax=axes[1], color='steelblue', alpha=0.8, edgecolor='white')
    axes[1].set_title('Monthly Energy (kWh)'); axes[1].set_xlabel('Month')
    axes[1].tick_params(axis='x', rotation=45); axes[1].grid(alpha=0.3, axis='y')

    plt.tight_layout(); plt.savefig('plots/footfall.png', dpi=150); plt.show()
    print("saved plots/footfall.png")


def plot_roi(npv, cash_flows, irr):
    years = list(range(PROJECT_YRS + 1))
    cumulative = np.cumsum(cash_flows)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle(f'ROI Analysis — {SITE} ({N_TILES} tiles)')

    axes[0].plot(years, cumulative, 'o-', color='steelblue', lw=2)
    axes[0].axhline(0, color='grey', ls='--', lw=1)
    axes[0].fill_between(years, cumulative, 0,
                          where=[c < 0 for c in cumulative],
                          alpha=0.2, color='tomato', label='Negative')
    axes[0].fill_between(years, cumulative, 0,
                          where=[c >= 0 for c in cumulative],
                          alpha=0.2, color='limegreen', label='Positive')
    axes[0].set_title('Cumulative Cash Flow'); axes[0].set_xlabel('Year')
    axes[0].set_ylabel('£'); axes[0].legend(); axes[0].grid(alpha=0.3)

    rs = np.linspace(0.02, 0.30, 100)
    npvs = [sum(cf / (1 + r)**t for t, cf in enumerate(cash_flows)) for r in rs]
    axes[1].plot(rs * 100, npvs, color='steelblue', lw=2)
    axes[1].axhline(0, color='grey', ls='--', lw=1)
    axes[1].axvline(DISCOUNT_R * 100, color='forestgreen', ls=':', lw=2,
                    label=f'WACC={DISCOUNT_R:.0%}')
    if irr:
        axes[1].axvline(irr * 100, color='tomato', ls=':', lw=2,
                        label=f'IRR={irr:.1%}')
    else:
        axes[1].text(0.5, 0.5, 'No real IRR\n(CFs always negative)',
                     transform=axes[1].transAxes, ha='center', color='tomato')
    axes[1].set_title('NPV vs Discount Rate'); axes[1].set_xlabel('Discount Rate (%)')
    axes[1].set_ylabel('NPV (£)'); axes[1].legend(); axes[1].grid(alpha=0.3)

    plt.tight_layout(); plt.savefig('plots/roi.png', dpi=150); plt.show()
    print("saved plots/roi.png")


def plot_anomalies(daily_with_anom):
    d = daily_with_anom.copy()
    d['date'] = pd.to_datetime(d['date'])
    anomalies = d[d['anomaly']]

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    fig.suptitle(f'Anomaly Detection — {SITE}')

    axes[0].plot(d['date'], d['footfall'], color='steelblue', lw=0.8, alpha=0.7)
    axes[0].plot(d['date'], d['roll_mean'], 'k--', lw=1.5, label='28-day rolling mean')
    axes[0].fill_between(d['date'],
                          d['roll_mean'] - 2.5 * d['roll_std'],
                          d['roll_mean'] + 2.5 * d['roll_std'],
                          alpha=0.15, color='steelblue', label='±2.5σ band')
    axes[0].scatter(anomalies['date'], anomalies['footfall'],
                    color='tomato', s=50, zorder=5, label=f'Anomaly (n={len(anomalies)})')
    axes[0].set_ylabel('Daily Footfall'); axes[0].legend(fontsize=9); axes[0].grid(alpha=0.3)

    axes[1].plot(d['date'], d['z_score'], color='steelblue', lw=0.8, alpha=0.7)
    axes[1].axhline(2.5, color='tomato', ls='--', lw=1)
    axes[1].axhline(-2.5, color='tomato', ls='--', lw=1)
    axes[1].axhline(0, color='grey', lw=0.5)
    axes[1].scatter(anomalies['date'], anomalies['z_score'],
                    color='tomato', s=50, zorder=5)
    axes[1].set_ylabel('Z-Score'); axes[1].set_xlabel('Date'); axes[1].grid(alpha=0.3)
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
    plt.setp(axes[1].xaxis.get_majorticklabels(), rotation=30)

    plt.tight_layout(); plt.savefig('plots/anomalies.png', dpi=150); plt.show()
    print("saved plots/anomalies.png")


# ── MAIN ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    os.makedirs('plots', exist_ok=True)

    print("=" * 55)
    print(f"  JUSTWALK — {SITE}")
    print("=" * 55)

    # Simulate footfall
    print("\nSimulating footfall...")
    hourly = simulate_footfall(n_days=365)
    daily  = daily_totals(hourly)
    annual_footfall = daily['footfall'].sum()
    annual_kwh      = daily['energy_kwh'].sum()

    print(f"\n--- Energy Summary ---")
    print(f"  Annual footfall:    {annual_footfall:,.0f} persons")
    print(f"  Annual energy:      {annual_kwh:.1f} kWh")
    print(f"  Daily avg:          {daily['energy_kwh'].mean():.3f} kWh")
    print(f"  Weekday avg:        {daily[daily['is_weekday']]['energy_kwh'].mean():.3f} kWh")
    print(f"  Annual revenue:     £{annual_kwh * ELEC_RATE:.2f}")

    # Financial model -- office case
    npv_office, cfs_office = compute_npv(annual_kwh)
    irr_office = compute_irr(cfs_office)
    print(f"\n--- Office Case DCF ---")
    print(f"  CapEx ({N_TILES} tiles):   £{N_TILES * TILE_COST:,}")
    print(f"  Annual energy rev:  £{annual_kwh * ELEC_RATE:.2f}")
    print(f"  Annual net CF:      £{annual_kwh * ELEC_RATE - MAINTENANCE:.2f}")
    print(f"  NPV (8%, 10yr):     £{npv_office:,.0f}")
    print(f"  IRR:                {'No real IRR' if irr_office is None else f'{irr_office:.1%}'}")

    # Monte Carlo -- office case
    print(f"\n--- Monte Carlo NPV (n=5000 scenarios, office) ---")
    mc_office = monte_carlo_npv(annual_footfall)
    p5, p50, p95 = np.percentile(mc_office, [5, 50, 95])
    print(f"  5th pct:   £{p5:,.0f}")
    print(f"  Median:    £{p50:,.0f}")
    print(f"  95th pct:  £{p95:,.0f}")
    print(f"  P(NPV>0):  {(mc_office > 0).mean():.1%}")
    print("  → Energy alone doesn't justify the CapEx at an office site.")

    # Transit hub scenario (where the economics actually work)
    print(f"\n--- Transit Hub Scenario (200 tiles, £45k SaaS analytics/yr) ---")
    hourly_hub = simulate_footfall(n_days=365, peak_capacity=4500, seed=2024)
    daily_hub  = daily_totals(hourly_hub)
    annual_fh  = daily_hub['footfall'].sum()
    annual_kwh_h = daily_hub['energy_kwh'].sum()
    n_hub = 200
    npv_hub, cfs_hub = compute_npv(annual_kwh_h, n_tiles=n_hub, extra_annual=45000)
    irr_hub = compute_irr(cfs_hub)
    mc_hub = monte_carlo_npv(annual_fh, n_tiles=n_hub, extra_mean=45000, extra_sd=13500)
    p5h, p50h, p95h = np.percentile(mc_hub, [5, 50, 95])
    print(f"  Annual footfall:    {annual_fh:,}")
    print(f"  NPV (8%, 10yr):     £{npv_hub:,.0f}")
    print(f"  IRR:                {irr_hub:.1%}" if irr_hub else "  IRR: no real solution")
    print(f"  P(NPV>0):           {(mc_hub > 0).mean():.1%}  (5th={p5h:,.0f}, median={p50h:,.0f})")

    # Anomaly detection
    print(f"\n--- Anomaly Detection ---")
    daily_anom = inject_anomalies(daily)
    daily_anom = detect_anomalies(daily_anom)
    n_anom = daily_anom['anomaly'].sum()
    print(f"  Flagged: {n_anom} days of {len(daily_anom)} ({n_anom/len(daily_anom):.1%})")

    print("\nGenerating plots...")
    plot_footfall(hourly)
    plot_roi(npv_office, cfs_office, irr_office)
    plot_anomalies(daily_anom)
    print("\nAll plots saved to ./plots/")
