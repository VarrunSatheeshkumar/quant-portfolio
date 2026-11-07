"""Compare the current portfolio, a halfway-to-equal-risk portfolio and the full equal-risk portfolio.

Run: python -I compare.py data/prices.txt out/
"""
import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.covariance import LedoitWolf

spec = importlib.util.spec_from_file_location("model", Path(__file__).with_name("model.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

# Halfway weights, rounded to 0.5% so they can be entered as orders; still sum to 80%.
HALFWAY = {"NVDA": 0.11, "AMAT": 0.075, "WMT": 0.125, "HD": 0.11,
           "BAE": 0.12, "RR": 0.10, "BTC": 0.10, "ETH": 0.06}


def build_cov(price_file):
    series, ccy = m.load_prices(price_file)
    rets, _ = m.gbp_returns(series, ccy)
    rets = rets.drop(index=[pd.Timestamp(d) for d in m.PAST_EVENT_DAYS if pd.Timestamp(d) in rets.index])
    cov_d = LedoitWolf().fit(rets.values).covariance_ * m.HORIZON_DAYS
    jump = np.diag([((m.IMPLIED_MOVE[a] or 0) / 100 * math.sqrt(math.pi / 2)) ** 2 for a in m.ASSETS])
    return cov_d + jump


def summarise(label, w, cov):
    sig, rc = m.euler(w, cov)
    share = rc / sig
    sd_asset = np.sqrt(np.diag(cov))
    # Stress: NVIDIA and AMAT each fall by their implied move, crypto falls one two-week s.d.
    shock = {"NVDA": -m.IMPLIED_MOVE["NVDA"] / 100, "AMAT": -m.IMPLIED_MOVE["AMAT"] / 100,
             "BTC": -sd_asset[m.ASSETS.index("BTC")], "ETH": -sd_asset[m.ASSETS.index("ETH")]}
    stress = sum(w[m.ASSETS.index(a)] * s for a, s in shock.items()) * m.CAPITAL_GBP
    idx = [m.ASSETS.index(a) for a in m.RISK_ON]
    return {
        "portfolio": label,
        "two_week_sd_pct": round(100 * sig, 2),
        "two_week_sd_gbp": round(m.CAPITAL_GBP * sig),
        "var95_gbp": round(m.CAPITAL_GBP * 1.645 * sig),
        "p_loss_over_5k_pct": round(100 * norm.cdf(-5000 / (m.CAPITAL_GBP * sig)), 1),
        "risk_on_capital_pct": round(100 * w[idx].sum(), 1),
        "risk_on_risk_share_pct": round(100 * share[idx].sum(), 1),
        "ai_semis_risk_share_pct": round(100 * (share[0] + share[1]), 1),
        "ai_selloff_stress_gbp": round(stress),
        "ai_rally_gbp": round(-stress),
        "risk_share_by_asset_pct": {m.NAMES[a]: round(100 * share[i], 1) for i, a in enumerate(m.ASSETS)},
    }


def main(price_file, out_dir):
    cov = build_cov(price_file)
    cur = np.array([m.WEIGHTS[a] for a in m.ASSETS])
    half = np.array([HALFWAY[a] for a in m.ASSETS])
    erc = m.equal_risk_weights(cov, cur.sum())
    assert abs(half.sum() - cur.sum()) < 1e-9
    rows = [summarise("Current", cur, cov), summarise("Halfway", half, cov), summarise("Equal risk", erc, cov)]
    trades = [{"asset": m.NAMES[a], "current_pct": round(100 * cur[i], 1), "halfway_pct": round(100 * half[i], 1),
               "change_pct": round(100 * (half[i] - cur[i]), 1), "change_gbp": round(m.CAPITAL_GBP * (half[i] - cur[i])),
               "equal_risk_pct": round(100 * erc[i], 1)} for i, a in enumerate(m.ASSETS)]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "compare.json").write_text(json.dumps({"summary": rows, "trades": trades}, indent=2))
    plot(rows, out / "compare_risk_share.png")
    print(json.dumps({"summary": rows, "trades": trades}, indent=2))


def plot(rows, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    assets = list(rows[0]["risk_share_by_asset_pct"].keys())
    colours = ["#2F5D9E", "#5B84C4", "#8FA8D1", "#C9D3E6", "#D9A441", "#E8C27A", "#7A9E7E", "#A9C6AC"]
    fig, ax = plt.subplots(figsize=(7.5, 3.4), dpi=160)
    for j, r in enumerate(rows):
        left = 0
        for k, a in enumerate(assets):
            v = r["risk_share_by_asset_pct"][a]
            ax.barh(j, v, left=left, color=colours[k], label=a if j == 0 else None, edgecolor="white", linewidth=0.6)
            left += v
    ax.set_yticks(range(len(rows)), [f'{r["portfolio"]}\n2-wk vol {r["two_week_sd_pct"]}%' for r in rows])
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("Share of two-week portfolio risk (%)")
    ax.set_title("Halfway cuts the AI and crypto share of risk from 80% to 68%", loc="left", fontsize=11)
    ax.legend(frameon=False, fontsize=7, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.32))
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(path)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
