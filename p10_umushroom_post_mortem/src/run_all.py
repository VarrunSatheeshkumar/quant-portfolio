"""Run every component and write out/results.json (+ CSV tables). Usage: python run_all.py [--asof YYYY-MM-DD]"""
import argparse
import json
import warnings

warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd

from config import OUT, SEED
import attribution
import data
import event_study
import fundamentals
import ledger
import p9_replica as p9
import power


def default_asof():
    px = data.load(kind="raw", tickers=["NVDA", "WMT", "AMAT", "HD", "BA.L", "RR.L", "GBPUSD=X", "BTC-USD"])
    us = px[["NVDA", "WMT", "AMAT", "HD"]].dropna().index.max()
    return min(us, px["GBPUSD=X"].dropna().index.max(), px["BTC-USD"].dropna().index.max())


def clean(o):
    """JSON-safe copy: numpy scalars to Python, NaN and infinities to None (strict JSON has no NaN)."""
    if isinstance(o, float) and not np.isfinite(o):
        return None
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.floating,)):
        return float(o) if np.isfinite(o) else None
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (pd.Timestamp, pd.Period)):
        return str(o)
    return o


def dumps(o):
    """Strict JSON (allow_nan=False): fails rather than write a bare NaN."""
    return json.dumps(clean(o), indent=1, default=str, allow_nan=False)


def main(asof=None):
    OUT.mkdir(exist_ok=True)
    asof = pd.Timestamp(asof) if asof else default_asof()
    R = {"asof": str(asof.date()), "prices_downloaded_utc": data._ts(), "seed": SEED}

    # A
    resA, led = ledger.main(asof)
    R["A"] = resA
    R["A"]["implied_fx"] = ledger.implied_fx().assign(date=lambda d: d.date.astype(str)).to_dict(orient="records")
    R["A"]["fills_vs_range"] = ledger.fill_vs_range().to_dict(orient="records")
    total = resA["nav_yahoo_asof"] - 100000
    realised_pct = 100 * total / 100000
    pv = led["value"].iloc[-1].round(2).to_dict()
    R["A"]["value_by_asset_asof"] = pv

    # B base + sensitivities
    base = attribution.attribute(asof, led=led)
    loss = -base["total_pnl"]
    b = base["buckets"]
    R["B"] = {"total_pnl": base["total_pnl"], "buckets": b, "sum_gap": base["sum_gap"],
              "pct_of_loss": {k: round(100 * -v / loss, 1) for k, v in b.items()} if loss > 0 else None,
              "per_asset": base["per_asset"].to_dict(orient="index"),
              "betas": {k: {kk: (round(vv, 4) if isinstance(vv, float) else vv) for kk, vv in v.items()} for k, v in base["betas"].items()},
              "flagged_unscheduled": attribution.flag_unscheduled(base).assign(date=lambda d: d.date.astype(str)).round(3).to_dict(orient="records")}
    fs = base["fx_scope"]
    assert abs(fs["core_us_equities_gbp"] - (b["fx"] + b["fx_local_cross"])) < 0.015
    R["B"]["fx_scope"] = {**fs, "core_pct_of_loss": round(100 * fs["core_us_equities_gbp"] / loss, 2) if loss > 0 else None,
                          "all_dollar_pct_of_loss": round(100 * fs["all_dollar_holdings_gbp"] / loss, 2) if loss > 0 else None,
                          "note": "The fx and fx_local_cross buckets cover the four US equities. Bitcoin, Ethereum and Spyre "
                                  "are dollar-quoted too; their currency effect (same daily FX and cross terms) is inside "
                                  "their own buckets and is added here only to show the effect across all dollar holdings."}
    base["per_asset"].to_csv(OUT / "attribution_per_asset.csv")
    base["daily"].to_csv(OUT / "attribution_daily.csv", index=False)
    systematic = b["market"] + b["sector"] + b["fx"] + b["fx_local_cross"] + b["crypto_BTC"] + b["ETH_closed_realised"]
    R["B"]["grouped"] = {"market_sector_fx_crypto": round(systematic, 2),
                         "company_specific_AR": round(b["event_scheduled_AR"] + b["event_unscheduled_AR"] + b["residual_AR"], 2),
                         "execution": b["execution_fill_to_close"]}
    sens = {}
    for bw in ("p9", 252, 504):
        for ew in ("0", "0,+1", "-1,+1"):
            for sm in ("etf", "peers"):
                for ai in (False, True):
                    try:
                        s = attribution.attribute(asof, beta_window=bw, event_window=ew, sector_mode=sm, alpha_in=ai, led=led)
                    except Exception as e:  # noqa
                        sens[f"bw={bw}|ew={ew}|{sm}|alpha={ai}"] = {"error": str(e)[:200]}
                        continue
                    sb = s["buckets"]
                    sens[f"bw={bw}|ew={ew}|{sm}|alpha={ai}"] = {
                        "market": sb["market"], "sector": sb["sector"], "fx": sb["fx"],
                        "sched_AR": sb["event_scheduled_AR"], "residual_AR": sb["residual_AR"], "alpha": sb["alpha"],
                        "mkt_sec_fx_crypto": round(sb["market"] + sb["sector"] + sb["fx"] + sb["fx_local_cross"] + sb["crypto_BTC"] + sb["ETH_closed_realised"], 2),
                        "company_AR": round(sb["event_scheduled_AR"] + sb["event_unscheduled_AR"] + sb["residual_AR"] + sb["alpha"], 2),
                        "gap": s["sum_gap"]}
    R["B"]["sensitivity"] = sens
    u = attribution.attribute(asof, led=led, unsched_file="events_unscheduled_sensitivity.csv")
    R["B"]["nvda_ceo_day_as_event"] = {k: u["buckets"][k] for k in ("event_scheduled_AR", "event_unscheduled_AR", "residual_AR")}
    pd.DataFrame(sens).T.to_csv(OUT / "attribution_sensitivity.csv")

    # C
    w9, c9 = power.held_weights("2026-11-09")
    w13, c13 = power.held_weights("2026-11-13")
    m_p9, m9, m13 = p9.model(), p9.model(w9), p9.model(w13)
    sig = {"P9_published_3.91": 3.91, "P9_weights_yahoo": m_p9["two_week_sd_pct"], "held_9Nov_yahoo": m9["two_week_sd_pct"],
           "held_13Nov_yahoo": m13["two_week_sd_pct"]}
    n_days = int(((data.load(kind="raw", tickers=["NVDA"])["NVDA"].dropna().index >= "2026-11-09") &
                  (data.load(kind="raw", tickers=["NVDA"])["NVDA"].dropna().index <= asof)).sum())
    sig_scaled = {k + f"_scaled_{n_days}of10": v * (n_days / 10) ** 0.5 for k, v in sig.items()}
    port = power.portfolio_daily_gbp(w9)
    port_dm = port - port.mean()
    plat = resA["platform"]                     # the platform reading for this valuation date, or None
    platform_pct = plat["platform_return_pct"] if plat else None
    R["C"] = {
        "realised_pct": round(realised_pct, 4), "platform_pct": platform_pct,
        "platform_valuation_date": plat["valuation_date"] if plat else None, "us_sessions_invested": n_days,
        "z_full_horizon": power.z_scores(realised_pct, sig), "z_partial_horizon": power.z_scores(realised_pct, sig_scaled),
        "z_platform_figure": power.z_scores(platform_pct, sig) if plat else None,
        "var95_not_breached": bool(-total < 6432),
        "p9_replica": {k: v for k, v in m_p9.items() if k != "cov_daily"},
        "p9_sample_cov_sd_pct": p9.model(use_sample=True)["two_week_sd_pct"],
        "held_weights_9Nov": w9, "cash_9Nov": c9, "held_weights_13Nov": w13, "cash_13Nov": c13,
        "held9_model": {k: v for k, v in m9.items() if k != "cov_daily"},
        "placebo_raw": power.placebo(port, realised_pct, (n_days, 9, 10)),
        "placebo_demeaned": power.placebo(port_dm, realised_pct, (n_days, 9, 10)),
        "placebo_mean_daily_pct": round(100 * float(port.mean()), 4),
        "bootstrap_10d": {s: power.block_bootstrap(port, seed=s, realised_pct=realised_pct) for s in (SEED, 1, 2)},
        "bootstrap_10d_demeaned": power.block_bootstrap(port_dm, seed=SEED, realised_pct=realised_pct),
        "closed_form": power.closed_form(), "mde_P9": power.mde(3.91), "mde_held": power.mde(m9["two_week_sd_pct"]),
        "binomial": power.binom_table(), "calls": power.call_moves(asof)}
    calls = [c for c in R["C"]["calls"] if "hit" in c]
    R["C"]["calls_scored"] = {"hits": sum(c["hit"] for c in calls), "n": len(calls),
                              "all_abs_moves_below_implied": all(c["abs_move_lt_implied"] for c in calls)}

    # D2
    d2, snap = fundamentals.decompose()
    d2.to_csv(OUT / "d2_eps_vs_price.csv", index=False)
    R["D2"] = {"snapshot": snap, "rows": d2.to_dict(orient="records"), "revisions": fundamentals.revisions()}
    us = d2[(d2.period == "+1y") & (d2.lookback == "30daysAgo") & d2.ticker.isin(["NVDA", "WMT", "AMAT", "HD"])]
    R["D2"]["us_avg_fwd_eps_chg_30d_pct"] = round(float(us.eps_chg_pct.mean()), 2)
    R["D2"]["us_avg_price_chg_30d_pct"] = round(float(us.price_chg_pct.mean()), 2)

    # D3
    d3, dfe = event_study.run()
    R["D3"] = d3
    R["D3"]["alignment_T9"] = event_study.alignment(dfe)
    dfe.to_csv(OUT / "d3_events.csv", index=False)

    (OUT / "results.json").write_text(dumps(R))
    print(f"wrote {OUT/'results.json'} asof {R['asof']}")
    return R


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--asof", default=None)
    a = ap.parse_args()
    main(a.asof)
