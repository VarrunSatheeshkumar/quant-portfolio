"""Can any option structure resolve a volatility signal of the size at stake?

Eight structures are costed the same way -- straddles at two hedging frequencies,
three calendar spreads, and a variance-replicating strip at two widths and two tenors
-- and every one is compared on the same statistic: the minimum detectable effect on
a paired per-trade difference, in basis points of underlying, against a band set by
the round-trip cost.

The decisive measurement has no instrument in it. An idealised variance swap with no
spread, no fees and no hedging error is a lower bound on what any tradeable structure
could achieve. If that cannot see the effect either, the binding constraint is not
the instrument and not the sample: it is the dispersion of the quantity being
measured, and no structure reduces the variance of the thing it measures.

A warning the strip itself provides: a truncated replication has *lower* dispersion
than the swap it approximates, which is impossible for a faithful one. It measures
less of the thing. Reporting its precision as an achievement would look like progress.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config
from src import audit

DAYS_YEAR = 365.0
OPT_TAKER, OPT_SETTLE, OPT_FEE_CAP = 0.0003, 0.00015, 0.125
HEDGE_FEE = 0.0005
N_GRID, MIN_STRIKES = 41, 8
RECENT_START = pd.Timestamp("2021-01-01", tz="UTC")


def _years(ts):
    ts = pd.DatetimeIndex(ts)
    return float((ts.max() - ts.min()).total_seconds() / (365.25 * 86400))


def _d1(S, K, T, sig):
    return (np.log(S / K) + 0.5 * sig ** 2 * T) / (sig * np.sqrt(T))


def bs_price(S, K, T, sig, is_call):
    d1 = _d1(S, K, T, sig)
    d2 = d1 - sig * np.sqrt(T)
    call = S * norm.cdf(d1) - K * norm.cdf(d2)
    put = K * norm.cdf(-d2) - S * norm.cdf(-d1)
    return np.where(is_call, call, put)


def bs_delta(S, K, T, sig, is_call):
    nd1 = norm.cdf(_d1(S, K, T, sig))
    return np.where(is_call, nd1, nd1 - 1.0)


def bs_vega(S, K, T, sig):
    return S * norm.pdf(_d1(S, K, T, sig)) * np.sqrt(T)


def _fit_smile(k, iv, w):
    """Volume-weighted quadratic in log-moneyness. Deliberately not richer: a fuller
    parameterisation would mostly be fitting the extrapolation, which this refuses."""
    A = np.column_stack([np.ones_like(k), k, k ** 2])
    W = np.sqrt(np.clip(w, 1e-9, None))
    try:
        beta, *_ = np.linalg.lstsq(A * W[:, None], iv * W, rcond=None)
        return beta
    except np.linalg.LinAlgError:
        return None


def build_strip(day_fills, lo_d, hi_d, target_d, width):
    """A 1/K^2-weighted strip of out-of-the-money options: the static replication of a
    variance swap, whose defining property is dollar gamma constant in spot. The grid
    never extrapolates past the strikes that actually traded."""
    d = day_fills.dropna(subset=["expiry", "strike", "index_price", "iv"])
    d = d[(d["iv"] > 0) & (d["amount"] > 0) & (d["price"] > 0)]
    if len(d) < 30:
        return None
    t0, S = d["ts"].min(), float(d["index_price"].median())
    d = d.assign(days=(d["expiry"] - t0).dt.total_seconds() / 86400.0)
    s = d[(d["days"] >= lo_d) & (d["days"] <= hi_d)]
    if not len(s) or s["strike"].nunique() < MIN_STRIKES:
        return None
    exp = s.iloc[(s["days"] - target_d).abs().argsort()]["expiry"].iloc[0]
    e = s[s["expiry"] == exp]
    T = float((exp - t0).total_seconds() / 86400.0) / DAYS_YEAR
    if T <= 0 or e["strike"].nunique() < MIN_STRIKES:
        return None

    g = e.groupby("strike").apply(
        lambda x: pd.Series({"iv": float((x["iv"] * x["amount"]).sum()
                                         / x["amount"].sum()) / 100.0,
                             "vol": float(x["amount"].sum())}),
        include_groups=False).reset_index()
    k = np.log(g["strike"].to_numpy(float) / S)
    beta = _fit_smile(k, g["iv"].to_numpy(float), g["vol"].to_numpy(float))
    if beta is None:
        return None
    k_lo, k_hi = float(k.min()), float(k.max())

    def smile(kk):
        kk = np.clip(kk, k_lo, k_hi)
        return np.clip(beta[0] + beta[1] * kk + beta[2] * kk ** 2, 0.05, 4.0)

    atm = float(smile(np.array([0.0]))[0])
    span = (3.0 * atm * np.sqrt(T)) if width == "narrow" else max(abs(k_lo), abs(k_hi))
    gk = np.linspace(max(-span, k_lo), min(span, k_hi), N_GRID)
    if gk[-1] - gk[0] < 0.05:
        return None
    K, iv = S * np.exp(gk), smile(gk)
    is_call = K >= S
    prices = bs_price(S, K, T, iv, is_call)
    w = np.gradient(K) / K ** 2
    k_var = float(2.0 / T * np.sum(w * prices))

    rel = np.nan
    bs_, ss_ = e[e["direction"] == "buy"], e[e["direction"] == "sell"]
    if len(bs_) > 3 and len(ss_) > 3:
        pb = float((bs_["price"] * bs_["amount"]).sum() / bs_["amount"].sum())
        ps = float((ss_["price"] * ss_["amount"]).sum() / ss_["amount"].sum())
        if pb > ps > 0:
            rel = (pb - ps) / 2.0 / (0.5 * (pb + ps))
    return {"ts": t0, "S": S, "T": T, "days": T * DAYS_YEAR, "expiry": exp,
            "K": K, "iv": iv, "is_call": is_call, "w": w, "prices": prices,
            "k_var_vol": float(np.sqrt(max(k_var, 0.0))), "atm_iv": atm,
            "strip_value": float(np.sum(w * prices)), "rel_half_spread": rel}


def run_strip(st, px, side, rel_default):
    """Hold to expiry, delta-hedged hourly, normalised to the dollar vega of one
    at-the-money straddle so the number sits in the same table as the straddles."""
    S0, K, iv, T0, w = st["S"], st["K"], st["iv"], st["T"], st["w"]
    atm_vega = 2.0 * bs_vega(S0, np.array([S0]), T0, st["atm_iv"])[0]
    strip_vega = float(np.sum(w * bs_vega(S0, K, T0, iv)))
    if not np.isfinite(strip_vega) or strip_vega <= 0 or atm_vega <= 0:
        return None
    scale = atm_vega / strip_vega

    rel = st["rel_half_spread"] if np.isfinite(st["rel_half_spread"]) else rel_default
    cross = float(np.sum(w * st["prices"])) * scale * rel
    fee = float(np.sum(np.minimum(OPT_TAKER * S0,
                                  OPT_FEE_CAP * st["prices"] * scale * w)))
    path = px.loc[(px.index >= st["ts"]) & (px.index <= st["expiry"])]
    hourly = path.resample("1h").last().dropna()
    if len(hourly) < 5:
        return None

    hedge_pnl = hedge_cost = prev = 0.0
    for i in range(len(hourly) - 1):
        S = float(hourly.iloc[i])
        T = max(1e-8, (st["expiry"] - hourly.index[i]).total_seconds() / 86400.0 / DAYS_YEAR)
        dlt = side * scale * float(np.sum(w * bs_delta(S, K, T, iv, st["is_call"])))
        hedge_cost += abs(dlt - prev) * S * HEDGE_FEE
        hedge_pnl += -dlt * (float(hourly.iloc[i + 1]) - S)
        prev = dlt
    ST = float(hourly.iloc[-1])
    hedge_cost += abs(prev) * ST * HEDGE_FEE
    payoff = float(np.sum(w * np.where(st["is_call"], np.maximum(ST - K, 0.0),
                                       np.maximum(K - ST, 0.0)))) * scale
    total = side * (payoff - st["strip_value"] * scale) + hedge_pnl - cross - fee - hedge_cost
    return {"pnl": total / S0, "cost": (cross + fee + hedge_cost) / S0,
            "atm_vega": atm_vega}


def pick_straddle(day_fills, target_days):
    """At-the-money straddle at the expiry nearest `target_days`, both legs actually
    traded. Entry uses real fills with their direction: a taker buy print bounds the
    ask, a taker sell print bounds the bid."""
    d = day_fills.dropna(subset=["expiry", "strike", "index_price"])
    d = d[(d["price"] > 0) & (d["amount"] > 0)]
    if len(d) < 10:
        return None
    t0, S0 = d["ts"].min(), float(d["index_price"].median())
    d = d.assign(days=(d["expiry"] - t0).dt.total_seconds() / 86400.0)
    d = d[d["days"] > 1.5]
    if not len(d):
        return None
    exp = d.iloc[(d["days"] - target_days).abs().argsort()]["expiry"].iloc[0]
    e = d[d["expiry"] == exp]
    both = e.groupby("strike")["is_call"].nunique()
    strikes = both[both == 2].index.to_numpy(float)
    if not len(strikes):
        return None
    K = float(strikes[np.abs(strikes - S0).argmin()])
    leg = {}
    for is_call, tag in ((True, "call"), (False, "put")):
        g = e[(e["strike"] == K) & (e["is_call"] == is_call)]
        if not len(g):
            return None
        def vw(x, col="price"):
            w = x["amount"].to_numpy(float)
            return float((x[col].to_numpy(float) * w).sum() / w.sum()) if len(x) else np.nan
        b, sl = g[g["direction"] == "buy"], g[g["direction"] == "sell"]
        pb, ps = (vw(b) if len(b) else np.nan), (vw(sl) if len(sl) else np.nan)
        half = (pb - ps) / 2.0 if np.isfinite(pb) and np.isfinite(ps) and pb > ps else np.nan
        leg[tag] = {"all": vw(g), "buy": pb, "sell": ps, "half": half,
                    "iv": vw(g, "iv") / 100.0}
    halves = [leg[t]["half"] for t in leg if np.isfinite(leg[t]["half"])]
    if not halves:
        return None
    fb = float(np.mean(halves))
    for t in leg:
        if not np.isfinite(leg[t]["half"]):
            leg[t]["half"] = fb
        if not np.isfinite(leg[t]["buy"]):
            leg[t]["buy"] = leg[t]["all"] + fb
        if not np.isfinite(leg[t]["sell"]):
            leg[t]["sell"] = leg[t]["all"] - fb
    iv = float(np.nanmean([leg["call"]["iv"], leg["put"]["iv"]]))
    if not np.isfinite(iv) or iv <= 0:
        return None
    return {"ts": t0, "S0": S0, "K": K, "expiry": exp,
            "days": float((exp - t0).total_seconds() / 86400.0), "iv": iv,
            "ask": leg["call"]["buy"] + leg["put"]["buy"],
            "bid": leg["call"]["sell"] + leg["put"]["sell"]}


def run_straddle(tr, px, side, hedge="1h"):
    """Delta-hedged to expiry. Hedge frequency is a design parameter, not a nicety:
    a straddle's dollar gamma peaks at its strike and decays away from it, so the
    hedging error the test creates itself sets the dispersion."""
    S0, K, T0, iv = tr["S0"], tr["K"], tr["days"] / DAYS_YEAR, tr["iv"]
    prem = (tr["ask"] if side > 0 else tr["bid"]) * S0
    if not np.isfinite(prem) or prem <= 0:
        return None
    fees = 2 * min(OPT_TAKER * S0, OPT_FEE_CAP * prem / 2) * (1 + OPT_SETTLE / OPT_TAKER)
    path = px.loc[(px.index >= tr["ts"]) & (px.index <= tr["expiry"])]
    steps = path.resample(hedge).last().dropna()
    if len(steps) < 3:
        return None
    hedge_pnl = hedge_cost = prev = 0.0
    for i in range(len(steps) - 1):
        S = float(steps.iloc[i])
        T = max(1e-6, (tr["expiry"] - steps.index[i]).total_seconds() / 86400.0 / DAYS_YEAR)
        d = side * float(bs_delta(S, np.array([K, K]), T, iv,
                                  np.array([True, False])).sum())
        hedge_cost += abs(d - prev) * S * HEDGE_FEE
        hedge_pnl += -d * (float(steps.iloc[i + 1]) - S)
        prev = d
    ST = float(steps.iloc[-1])
    hedge_cost += abs(prev) * ST * HEDGE_FEE
    payoff = max(ST - K, 0.0) + max(K - ST, 0.0)
    total = side * (payoff - prem) + hedge_pnl - fees - hedge_cost
    return {"pnl": total / S0, "cost": (fees + hedge_cost) / S0}


def straddle_and_calendar(fills, px):
    """Two straddle hedge frequencies and two calendar weightings.

    A calendar cannot escape the problem either: vega-matching leaves the position net
    long gamma on the near leg, gamma-matching leaves it net short vega. With two
    straddles you are always exposed to one mismatch or the other.
    """
    rows = []
    for day, dd in fills.groupby("entry_day"):
        s7 = pick_straddle(dd, 7)
        s30 = pick_straddle(dd, 30)
        if s7:
            for hedge, tag in (("1D", "straddle_7d_daily_hedge"),
                               ("1h", "straddle_7d_hourly_hedge")):
                a = run_straddle(s7, px, 1, hedge)
                b = run_straddle(s7, px, -1, hedge)
                if a and b:
                    rows.append({"structure": tag, "ts": s7["ts"],
                                 "long_pnl": a["pnl"], "short_pnl": b["pnl"],
                                 "cost": a["cost"]})
        if s7 and s30:
            T7, T30 = s7["days"] / DAYS_YEAR, s30["days"] / DAYS_YEAR
            v7 = 2 * bs_vega(s7["S0"], np.array([s7["K"]]), T7, s7["iv"])[0]
            v30 = 2 * bs_vega(s30["S0"], np.array([s30["K"]]), T30, s30["iv"])[0]
            g7 = 2 * norm.pdf(_d1(s7["S0"], s7["K"], T7, s7["iv"])) / (
                s7["S0"] * s7["iv"] * np.sqrt(T7))
            g30 = 2 * norm.pdf(_d1(s30["S0"], s30["K"], T30, s30["iv"])) / (
                s30["S0"] * s30["iv"] * np.sqrt(T30))
            for ratio, tag in ((v7 / v30 if v30 else np.nan, "calendar_7_30_vega"),
                               (g7 / g30 if g30 else np.nan, "calendar_7_30_gamma")):
                if not np.isfinite(ratio) or ratio <= 0:
                    continue
                a7 = run_straddle(s7, px, 1, "1h")
                b30 = run_straddle(s30, px, -1, "1h")
                if a7 and b30:
                    rows.append({"structure": tag, "ts": s7["ts"],
                                 "long_pnl": a7["pnl"] - ratio * (-b30["pnl"]),
                                 "short_pnl": -(a7["pnl"] - ratio * (-b30["pnl"])),
                                 "cost": a7["cost"] + ratio * b30["cost"]})
    return pd.DataFrame(rows)


def main():
    grid = pd.read_parquet(config.GRID_DIR / "grid.parquet",
                           columns=["ts", "close"])
    grid["ts"] = pd.to_datetime(grid["ts"], utc=True)
    px = grid.set_index("ts")["close"].dropna()
    r2 = np.log(px).diff() ** 2

    fills = pd.read_parquet(config.RAW / "option_fills.parquet")
    fills["ts"] = pd.to_datetime(fills["ts"], utc=True)
    fills["expiry"] = pd.to_datetime(fills["expiry"], utc=True)

    # Entry days are spaced one tenor apart -- Fridays for the weekly strip, month
    # starts for the monthly one -- so trades do not overlap. Entering daily would
    # multiply the trade count without adding independent observations, and the
    # standard error on the mean would be understated by exactly that factor.
    span = pd.date_range(fills["entry_day"].min(), fills["entry_day"].max(), freq="D")

    def schedule(freq):
        return set(pd.date_range(span[0], span[-1], freq=freq).normalize())

    rows = []
    for name, (lo, hi, tgt, width, freq) in {
            "strip_7d_narrow": (4.0, 10.0, 7.0, "narrow", "W-FRI"),
            "strip_7d_wide": (4.0, 10.0, 7.0, "wide", "W-FRI"),
            "strip_30d_narrow": (20.0, 40.0, 30.0, "narrow", "MS"),
            "strip_30d_wide": (20.0, 40.0, 30.0, "wide", "MS")}.items():
        days = schedule(freq)
        strips = []
        for _day, dd in fills.groupby("entry_day"):
            if pd.Timestamp(_day).normalize() not in days:
                continue
            st = build_strip(dd, lo, hi, tgt, width)
            if st:
                strips.append(st)
        if not strips:
            continue
        rels = [s["rel_half_spread"] for s in strips if np.isfinite(s["rel_half_spread"])]
        rel_default = float(np.median(rels)) if rels else 0.05
        for st in strips:
            bars = int(np.clip(round(st["days"] * 288), 12, 288 * 45))
            i0 = px.index.searchsorted(st["ts"])
            rv = float(r2.iloc[i0:i0 + bars].sum()) * (DAYS_YEAR / st["days"])
            rec = {"structure": name, "ts": st["ts"], "S": st["S"],
                   "days": st["days"], "k_var_vol": st["k_var_vol"],
                   "atm_iv": st["atm_iv"], "realised_vol": float(np.sqrt(max(rv, 0.0)))}
            ok = True
            for side, tag in ((1, "long"), (-1, "short")):
                r = run_strip(st, px, side, rel_default)
                if r is None:
                    ok = False
                    break
                rec[f"{tag}_pnl"] = r["pnl"]
                rec["cost"] = r["cost"]
                rec["atm_vega"] = r["atm_vega"]
            if ok:
                rows.append(rec)

    t = pd.DataFrame(rows)
    if not len(t):
        raise SystemExit("no strips built")
    t = t[audit.training_mask(t["ts"])]

    out = {"structures": {}, "idealised": {}, "idealised_2021_on": {},
           "validation": {}}

    sc = straddle_and_calendar(fills, px)
    if len(sc):
        sc = sc[audit.training_mask(sc["ts"])]
        for name, g in sc.groupby("structure"):
            x = (g["long_pnl"] - g["short_pnl"]).dropna()
            if len(x) < 5:
                continue
            sd_p = float(x.std() * np.sqrt(0.5))
            out["structures"][name] = {
                "n_train_trades": int(len(x)),
                "sd_per_trade_bps": float(sd_p * 1e4),
                "mde_bps": float(config.POWER_Z * sd_p / np.sqrt(len(x)) * 1e4),
                "mean_cost_bps": float(g["cost"].mean() * 1e4)}

    for name, g in t.groupby("structure"):
        x = (g["long_pnl"] - g["short_pnl"]).dropna()
        n = len(x)
        if n < 5:
            continue
        sd_paired = float(x.std() * np.sqrt(0.5))
        out["structures"][name] = {
            "n_train_trades": int(n),
            # Per-trade dispersion, kept because the economics stage needs the
            # spread of outcomes and not only the MDE built from it.
            "sd_per_trade_bps": float(sd_paired * 1e4),
            "mde_bps": float(config.POWER_Z * sd_paired / np.sqrt(n) * 1e4),
            "mean_cost_bps": float(g["cost"].mean() * 1e4)}

        # The floor: no hedging error, no spread, no fees. A variance swap on vega
        # notional pays (RV^2 - K^2) / (2K).
        kv, rv = g["k_var_vol"].to_numpy(float), g["realised_vol"].to_numpy(float)
        pnl = g["atm_vega"].to_numpy(float) * (rv ** 2 - kv ** 2) / (2 * np.maximum(kv, 1e-6))
        pnl_bps = pnl / g["S"].to_numpy(float)
        sd_i = float(np.std(2.0 * pnl_bps) * np.sqrt(0.5))
        out["idealised"][name] = {
            "n_train_trades": int(len(pnl_bps)),
            "mde_bps": float(config.POWER_Z * sd_i / np.sqrt(len(pnl_bps)) * 1e4),
            "mean_short_variance_pnl_bps": float(-np.mean(pnl_bps) * 1e4),
            "years_of_sample": _years(g["ts"])}

        # The same floor from 2021 onward. 2020 contains the March dislocation, and
        # the dispersion of realised variance in that year is several times any
        # other -- so the full sample gives a *higher* floor, not a lower one. The
        # conservative claim is the one made on the calmer sub-sample, and that is
        # the figure quoted: if even 2021-onward cannot resolve the band, the
        # full sample certainly cannot.
        q = g[g["ts"] >= RECENT_START]
        if len(q) >= 5:
            kq, rq = q["k_var_vol"].to_numpy(float), q["realised_vol"].to_numpy(float)
            pq = q["atm_vega"].to_numpy(float) * (rq ** 2 - kq ** 2) / (2 * np.maximum(kq, 1e-6))
            pq_bps = pq / q["S"].to_numpy(float)
            sd_q = float(np.std(2.0 * pq_bps) * np.sqrt(0.5))
            out["idealised_2021_on"][name] = {
                "n_train_trades": int(len(pq_bps)),
                "mde_bps": float(config.POWER_Z * sd_q / np.sqrt(len(pq_bps)) * 1e4),
                "mean_short_variance_pnl_bps": float(-np.mean(pq_bps) * 1e4),
                "years_of_sample": _years(q["ts"])}

        out["validation"][name] = {
            "median_k_var_minus_atm_volpts": float(np.median((kv - g["atm_iv"].to_numpy(float)) * 100)),
            "median_variance_risk_premium_volpts": float(np.median((kv - rv) * 100))}

    best = min(v["mde_bps"] for v in out["structures"].values())
    floor_name = min(out["idealised_2021_on"],
                     key=lambda k: out["idealised_2021_on"][k]["mde_bps"])
    floor = out["idealised_2021_on"][floor_name]
    best_ideal = floor["mde_bps"]
    out["n_structures_costed"] = len(out["structures"])
    out["band_bps"] = config.BAND_BPS
    out["best_structure_mde_bps"] = best
    out["best_idealised_mde_bps"] = best_ideal
    out["best_idealised_structure"] = floor_name
    out["best_idealised_mde_full_sample_bps"] = min(
        v["mde_bps"] for v in out["idealised"].values())
    out["ceiling_broken"] = bool(best_ideal < 2 * config.BAND_BPS)
    out["sample_multiple_needed"] = float((best_ideal / config.BAND_BPS) ** 2)
    # Years, not trades: the sample multiple buys nothing if it is bought by
    # trading more often, because overlapping trades are not new observations.
    out["years_needed"] = float(out["sample_multiple_needed"] * floor["years_of_sample"])

    config.RESULTS.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(config.RESULTS / "instrument.json", "w"), indent=2, default=float)
    print(f"  {out['n_structures_costed']} structures costed")
    print(f"  best tradeable structure MDE {best:.1f}bps; "
          f"idealised zero-cost floor {best_ideal:.1f}bps against a "
          f"{config.BAND_BPS:.0f}bps band")
    print(f"  reaching the band would need {out['sample_multiple_needed']:.0f}x the "
          f"sample, roughly {out['years_needed']:.0f} years")
    print(f"  (full sample including 2020: floor "
          f"{out['best_idealised_mde_full_sample_bps']:.1f}bps)")


if __name__ == "__main__":
    main()
