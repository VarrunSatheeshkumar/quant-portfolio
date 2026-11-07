"""Event-adjusted risk model for the UMushroom UK Investment Competition 2026 portfolio.

Horizon: the 10 trading days from the 9 Nov open to the 20 Nov close (Stage 1 locks 22 Nov).

Method
1. Daily closes (1 May - 6 Nov 2026) converted to sterling; log returns on US trading days.
2. Past earnings-reaction days are dropped so they are not counted twice (verified dates only).
3. Diffusive covariance: Ledoit-Wolf shrinkage of the daily covariance, scaled to 10 days.
4. Event (jump) risk: each report inside the window adds variance from its options-implied move.
   An implied move m is the expected absolute move, so the jump s.d. is m * sqrt(pi/2) (normal).
   Jumps are assumed independent of each other and of diffusion (see caveats).
5. Outputs: 2-week portfolio volatility, VaR, Euler risk contributions, sleeve shares,
   correlations, an equal-risk-contribution comparison and volatility-based deploy thresholds.

Run: python -I model.py data/prices.txt out/
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf

HORIZON_DAYS = 10
CAPITAL_GBP = 100_000

ASSETS = ["NVDA", "AMAT", "WMT", "HD", "BAE", "RR", "BTC", "ETH"]
NAMES = {"NVDA": "NVIDIA", "AMAT": "Applied Materials", "WMT": "Walmart", "HD": "Home Depot",
         "BAE": "BAE Systems", "RR": "Rolls-Royce", "BTC": "Bitcoin", "ETH": "Ethereum"}
WEIGHTS = {"NVDA": 0.15, "AMAT": 0.10, "WMT": 0.10, "HD": 0.10,
           "BAE": 0.10, "RR": 0.10, "BTC": 0.10, "ETH": 0.05}  # cash 20% carries no risk
SLEEVES = {"AI / semis": ["NVDA", "AMAT"], "US consumer": ["WMT", "HD"],
           "UK industrials": ["BAE", "RR"], "Crypto": ["BTC", "ETH"]}
RISK_ON = ["NVDA", "AMAT", "BTC", "ETH"]

# Expected absolute move on the report inside the window, in %. None = no scheduled report.
IMPLIED_MOVE = {"NVDA": 9.0, "AMAT": 10.4, "WMT": 4.6, "HD": 4.2,
                "BAE": 3.0, "RR": 3.0, "BTC": None, "ETH": None}
IMPLIED_SOURCE = {"NVDA": "options, 6 Nov", "AMAT": "options, 6 Nov", "WMT": "options, Aug level",
                  "HD": "options, Aug level", "BAE": "assumed, no listed options",
                  "RR": "assumed, no listed options", "BTC": "-", "ETH": "-"}

# Earnings-reaction days in the sample (verified report dates only); dropped from the diffusive fit.
PAST_EVENT_DAYS = ["2026-05-19", "2026-05-21", "2026-07-30", "2026-08-18", "2026-08-20", "2026-08-27"]


def load_prices(path):
    series, ccy = {}, {}
    for line in Path(path).read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        sym, cur, body = line.split("|")
        pts = {}
        for item in body.split(";"):
            d, p = item.split(",")
            d = d if len(d) == 10 else "2026-" + d
            pts[pd.Timestamp(d)] = float(p)
        series[sym] = pd.Series(pts).sort_index()
        ccy[sym] = cur
    return series, ccy


def gbp_returns(series, ccy):
    calendar = series["NVDA"].index  # US trading days
    fx = series["GBPUSD"].reindex(calendar).ffill()
    px = {}
    for a in ASSETS:
        s = series[a].reindex(calendar).ffill()  # UK holidays carry the last close
        px[a] = s / fx if ccy[a] == "USD" else s
    prices = pd.DataFrame(px).dropna()
    return np.log(prices).diff().dropna(), prices


def euler(w, cov):
    sigma = math.sqrt(w @ cov @ w)
    rc = w * (cov @ w) / sigma
    return sigma, rc


def equal_risk_weights(cov, total, iters=5000):
    w = np.full(len(cov), total / len(cov))
    for _ in range(iters):
        mrc = cov @ w
        w = w * (1 / (w * mrc)) ** 0.5
        w = w / w.sum() * total
    return w


def main(price_file, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    series, ccy = load_prices(price_file)
    rets_all, prices = gbp_returns(series, ccy)
    drop = [pd.Timestamp(d) for d in PAST_EVENT_DAYS if pd.Timestamp(d) in rets_all.index]
    rets = rets_all.drop(index=drop)

    w = np.array([WEIGHTS[a] for a in ASSETS])
    lw = LedoitWolf().fit(rets.values)
    cov_d = lw.covariance_ * HORIZON_DAYS
    cov_sample = np.cov(rets.values, rowvar=False) * HORIZON_DAYS

    jump_sd = np.array([(IMPLIED_MOVE[a] or 0) / 100 * math.sqrt(math.pi / 2) for a in ASSETS])
    cov_j = np.diag(jump_sd ** 2)
    cov_t = cov_d + cov_j

    sig_d, _ = euler(w, cov_d)
    sig_j = math.sqrt(w @ cov_j @ w)
    sig_t, rc = euler(w, cov_t)
    share = rc / sig_t

    daily_sd = np.sqrt(np.diag(lw.covariance_))
    corr = pd.DataFrame(lw.covariance_ / np.outer(daily_sd, daily_sd), index=ASSETS, columns=ASSETS)

    naive = w * np.array([IMPLIED_MOVE[a] or 0 for a in ASSETS])  # the brief's weight x implied move
    erc = equal_risk_weights(cov_t, w.sum())
    sig_erc, _ = euler(erc, cov_t)

    def sensitivity(uk_move=None, use_sample=False, keep_events=False):
        r = rets_all if keep_events else rets
        c = (np.cov(r.values, rowvar=False) if use_sample else LedoitWolf().fit(r.values).covariance_) * HORIZON_DAYS
        im = dict(IMPLIED_MOVE)
        if uk_move is not None:
            im["BAE"] = im["RR"] = uk_move
        j = np.diag([((im[a] or 0) / 100 * math.sqrt(math.pi / 2)) ** 2 for a in ASSETS])
        s, rcs = euler(w, c + j)
        on = sum(rcs[ASSETS.index(a)] for a in RISK_ON) / s
        return round(100 * s, 2), round(100 * on, 1)

    sens = {
        "Base case": sensitivity(),
        "UK update moves 0%": sensitivity(uk_move=0.0),
        "UK update moves 5%": sensitivity(uk_move=5.0),
        "Sample covariance (no shrinkage)": sensitivity(use_sample=True),
        "Past event days kept in": sensitivity(keep_events=True),
    }

    per_asset = []
    for i, a in enumerate(ASSETS):
        per_asset.append({
            "asset": NAMES[a], "weight_pct": round(100 * w[i], 1),
            "ann_vol_pct": round(100 * daily_sd[i] * math.sqrt(252), 1),
            "two_week_sd_pct": round(100 * math.sqrt(cov_t[i, i]), 1),
            "implied_move_pct": IMPLIED_MOVE[a], "implied_source": IMPLIED_SOURCE[a],
            "risk_share_pct": round(100 * share[i], 1),
            "naive_share_pct": round(100 * naive[i] / naive.sum(), 1) if naive.sum() else None,
            "erc_weight_pct": round(100 * erc[i], 1),
            "deploy_trigger_daily_pct": round(-200 * daily_sd[i], 1),
        })

    sleeves = {k: round(100 * sum(share[ASSETS.index(a)] for a in v), 1) for k, v in SLEEVES.items()}
    sleeve_capital = {k: round(100 * sum(WEIGHTS[a] for a in v), 1) for k, v in SLEEVES.items()}
    results = {
        "sample": {"first": str(rets_all.index[0].date()), "last": str(rets_all.index[-1].date()),
                   "days_used": len(rets), "event_days_dropped": [str(d.date()) for d in drop],
                   "shrinkage": round(float(lw.shrinkage_), 3)},
        "last_prices_gbp": {NAMES[a]: round(float(prices[a].iloc[-1]), 2) for a in ASSETS},
        "portfolio": {
            "two_week_sd_pct": round(100 * sig_t, 2),
            "two_week_sd_gbp": round(CAPITAL_GBP * sig_t),
            "diffusive_sd_pct": round(100 * sig_d, 2), "event_sd_pct": round(100 * sig_j, 2),
            "event_share_of_variance_pct": round(100 * sig_j ** 2 / sig_t ** 2, 1),
            "var95_gbp": round(CAPITAL_GBP * 1.645 * sig_t), "var99_gbp": round(CAPITAL_GBP * 2.326 * sig_t),
            "risk_on_capital_pct": round(100 * sum(WEIGHTS[a] for a in RISK_ON), 1),
            "risk_on_risk_share_pct": round(100 * sum(share[ASSETS.index(a)] for a in RISK_ON), 1),
            "diversification_ratio": round(float(w @ np.sqrt(np.diag(cov_t)) / sig_t), 2),
            "erc_two_week_sd_pct": round(100 * sig_erc, 2),
        },
        "sleeve_risk_share_pct": sleeves, "sleeve_capital_pct": sleeve_capital,
        "per_asset": per_asset,
        "correlations": corr.round(2).rename(index=NAMES, columns=NAMES).to_dict(),
        "sensitivity_sd_pct_and_risk_on_share_pct": sens,
    }
    (out / "results.json").write_text(json.dumps(results, indent=2))
    corr.round(2).rename(index=NAMES, columns=NAMES).to_csv(out / "correlations.csv")
    pd.DataFrame(per_asset).to_csv(out / "per_asset.csv", index=False)
    plot(per_asset, out / "risk_vs_capital.png")
    print(json.dumps(results, indent=2))


def plot(rows, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    names = [r["asset"] for r in rows][::-1]
    cap = [r["weight_pct"] / 0.8 for r in rows][::-1]  # share of invested capital
    risk = [r["risk_share_pct"] for r in rows][::-1]
    y = np.arange(len(names))
    fig, ax = plt.subplots(figsize=(7.5, 4.2), dpi=160)
    ax.barh(y + 0.19, cap, height=0.36, color="#B8C4D6", label="Share of invested capital")
    ax.barh(y - 0.19, risk, height=0.36, color="#2F5D9E", label="Share of 2-week portfolio risk")
    ax.set_yticks(y, names)
    ax.set_xlabel("%")
    ax.set_title("Risk concentrates in NVIDIA, Applied Materials and crypto", loc="left", fontsize=11)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(path)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
