"""Does price respond to the map? Five pre-registered framings.

The map locates forced flow -- that is measured first, against real prints, and it is
not in doubt. What follows is five separate attempts to turn that into a price
prediction, each specified before it was run.

  1. acceleration   does price accelerate through a mapped cluster relative to an
                    unmapped level the same distance away?
  2. pressure       does the effect appear once flow is scaled by the depth waiting
                    for it -- flow moves price only when it exceeds liquidity?
  3. age            do freshly-formed clusters behave differently from stale ones,
                    a cluster nobody has had time to notice not yet being priced in?
  4. regime         does it appear when liquidity providers are thin?
  5. anticipation   does flow the map *failed* to predict move price where predicted
                    flow does not?

Confounds are separated by construction, not argued away afterwards: every comparison
is made inside cells of size, distance, volatility and time of day, and a cell with no
control drops out rather than being extrapolated over. The age framing additionally
controls for trailing momentum, because an old cluster is by definition a level price
has moved away from and is now returning to -- age and recent direction are
mechanically entangled, and without that control the framing produces a beautifully
monotone effect that is not about age at all.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config
from src import audit
from src.liquidation_map import LOGSTEP, NBUCKET, BUCKET_PRICE, bucket_of, run_map


def _cells(d):
    """Matched cells: size, distance, volatility, time of day -- all four confounds."""
    d = d.copy()
    for col, q, name in [("notional", 5, "size_q"), ("dist", 3, "dist_q"),
                         ("rv24", 3, "vol_q")]:
        if col in d.columns:
            d[name] = pd.qcut(d[col].rank(method="first"), q, labels=False,
                              duplicates="drop")
    d["hour_q"] = pd.DatetimeIndex(d["ts"]).hour // 6
    return d


def _outcomes(rows, g, sign_col):
    """Signed continuation in basis points: positive means price kept going the way
    the forced flow pushed."""
    logpx = np.log(g["close"].to_numpy(float))
    n = len(logpx)
    b = rows["bar"].to_numpy()
    sign = np.where(rows[sign_col].to_numpy() == 1, -1.0, 1.0)
    for name, k in config.FWD_BARS.items():
        nxt = np.minimum(b + k, n - 1)
        rows[f"cont_{name}"] = (logpx[nxt] - logpx[b]) * sign * 1e4
    rows["rv24"] = g["rv_24h"].to_numpy(float)[b]
    rows["ts"] = g.index[b]
    rows["day"] = pd.DatetimeIndex(rows["ts"]).floor("D")
    return rows


def collect(g, mix):
    """One replay, two event streams: bucket touches and liquidation prints."""
    close = g["close"].to_numpy(float)
    high, low = g["high"].to_numpy(float), g["low"].to_numpy(float)
    decay = 0.5 ** (1.0 / config.MAP_HALF_LIFE_BARS)
    lo_b, hi_b, prev_b = bucket_of(low), bucket_of(high), bucket_of(close)
    depth = g["depth"].to_numpy(float)

    liq = g[["liq_long", "liq_short"]]
    prints = pd.read_parquet(config.RAW / "liquidations.parquet")
    prints["ts"] = pd.to_datetime(prints["ts"], utc=True)
    pos = g.index.searchsorted(prints["ts"].to_numpy(), side="left")
    ok = (pos > 0) & (pos < len(g))
    prints = prints[ok].reset_index(drop=True)
    prints["bar"] = pos[ok]
    pbucket = bucket_of(prints["price"].to_numpy(float))
    plong = prints["is_long_liq"].to_numpy().astype(bool)
    by_bar = {}
    for j, bar in enumerate(prints["bar"].to_numpy()):
        by_bar.setdefault(bar, []).append(j)

    touches = []
    p_share = np.full(len(prints), np.nan)
    last_touch = np.full(NBUCKET, -10 ** 9, dtype=np.int64)

    def hook(i, long_map, short_map, total, age_l, age_s):
        if total <= 0:
            return
        for j in by_bar.get(i, ()):
            b = pbucket[j]
            if 0 <= b < NBUCKET:
                same = long_map[b] if plong[j] else short_map[b]
                p_share[j] = same / total
        pb = prev_b[i - 1]
        for direction, blo, bhi in (("down", lo_b[i], pb), ("up", pb, hi_b[i])):
            if bhi < blo:
                continue
            for b in range(max(blo, 0), min(bhi, NBUCKET - 1) + 1):
                if i - last_touch[b] < config.DEDUPE_BARS:
                    continue
                dist = abs(BUCKET_PRICE[b] / close[i - 1] - 1.0)
                if not (1e-9 < dist <= config.MAX_DIST):
                    continue
                mass = long_map[b] + short_map[b]
                share = mass / total
                # An emptied bucket is a legitimate control -- it is the "nothing
                # is here" case the cluster is measured against -- but it has no
                # formation time, so the age framing drops it later.
                age = (i - (age_l[b] + age_s[b]) / mass) if mass > 0 else np.nan
                last_touch[b] = i
                touches.append((i, direction == "down", dist, share, mass, age,
                                mass / depth[i] if depth[i] > 0 else np.nan))

    run_map(close, high, low, g["vwap_bar"].fillna(g["close"]).to_numpy(float),
            g["oi"].diff().to_numpy(float), g["oi"].shift(1).to_numpy(float),
            decay, mix, hooks=hook, track_age=True)

    t = pd.DataFrame(touches, columns=["bar", "is_down", "dist", "share", "notional",
                                       "age_bars", "pressure"])
    t["kind"] = np.where(t["share"] >= config.CLUSTER_SHARE, "cluster",
                         np.where(t["share"] <= config.EMPTY_SHARE, "empty", "mid"))
    t = _outcomes(t, g, "is_down")
    t["is_cluster"] = (t["kind"] == "cluster").astype(int)

    prints["share_same"] = p_share
    prints["dist"] = np.abs(prints["price"].to_numpy(float)
                            / close[np.clip(prints["bar"] - 1, 0, len(close) - 1)] - 1.0)
    prints = _outcomes(prints, g, "is_long_liq")
    prints["predicted"] = np.where(prints["share_same"] >= config.PREDICTED_MIN, 1,
                                   np.where(prints["share_same"] <= config.UNPREDICTED_MAX,
                                            0, np.nan))
    return t, prints


def _slope(d, ycol, xcol, n_boot=1000):
    """Within-cell demeaned slope, day-block bootstrapped."""
    d = d.dropna(subset=[ycol, xcol])
    if len(d) < 500:
        return None
    keys = [k for k in ("dist_q", "vol_q", "hour_q") if k in d.columns]
    grp = d.groupby(keys, observed=True)
    x = (d[xcol] - grp[xcol].transform("mean")).to_numpy(float)
    y = (d[ycol] - grp[ycol].transform("mean")).to_numpy(float)
    ok = np.isfinite(x) & np.isfinite(y)
    x, y, dd = x[ok], y[ok], d.loc[ok]

    def stat(idx):
        xc = x[idx] - x[idx].mean()
        dn = (xc * xc).sum()
        return (xc * (y[idx] - y[idx].mean())).sum() / dn if dn > 0 else np.nan

    days = dd["day"].to_numpy()
    uniq = pd.Index(days).unique()
    pos = {k: np.nonzero(days == k)[0] for k in uniq}
    rng = np.random.default_rng(config.RANDOM_SEED)
    boot = []
    for _ in range(n_boot):
        ii = np.concatenate([pos[k] for k in rng.choice(uniq, len(uniq), replace=True)])
        v = stat(ii)
        if np.isfinite(v):
            boot.append(v)
    boot = np.array(boot, float)
    real = stat(np.arange(len(x)))
    return {"n": int(len(x)), "n_days": int(len(uniq)), "slope": float(real),
            "ci_lo": float(np.percentile(boot, 2.5)),
            "ci_hi": float(np.percentile(boot, 97.5)),
            "mde": float(config.POWER_Z * boot.std())}


def _level(d, ycol, n_boot=2000):
    """The level, which is what would be traded. A difference can be large while the
    level is nothing, and only the level is a one-sided trade."""
    d = d.dropna(subset=[ycol])
    if len(d) < 200:
        return None
    days = d["day"].to_numpy()
    # The day-block bootstrap and the MDE both come from audit, so there is one
    # implementation of each rather than a copy here that can drift from it.
    p = audit.design_power(d[ycol].to_numpy(float), days, band=config.BAND_BPS,
                           n=n_boot)
    return {"n": int(len(d)), "n_days": int(pd.Index(days).nunique()),
            "level_bps": p["mean"], "ci_lo": p["ci_lo"], "ci_hi": p["ci_hi"],
            "mde_bps": p["mde"], "testable": p["testable"]}


def main():
    grid = pd.read_parquet(config.GRID_DIR / "grid.parquet")
    grid["ts"] = pd.to_datetime(grid["ts"], utc=True)
    grid = grid.set_index("ts").sort_index()
    g = grid.loc[grid["oi"].notna()].copy()
    mix = {int(k): v for k, v in
           json.loads((config.INTERIM / "leverage_mix.json").read_text())["mix"].items()}

    touches, prints = collect(g, mix)
    train_t = _cells(touches[audit.training_mask(touches["ts"])])
    train_p = _cells(prints[audit.training_mask(prints["ts"])
                            & prints["predicted"].notna()])

    # ---- ground truth first: does the map locate real forced flow at all?
    # Forced flow arrives over minutes, not instantaneously, so this sums the real
    # prints over the touch bar and the following twenty minutes. Restricted to the
    # sample days where prints exist at all -- elsewhere the absence of a print is
    # an absence of data, not an absence of liquidation.
    liq_tot = (g["liq_long"].fillna(0) + g["liq_short"].fillna(0)).to_numpy()
    have_liq = g["liq_long"].notna().to_numpy()
    win = 3
    bars = touches["bar"].to_numpy()
    ends = np.minimum(bars + win + 1, len(g))
    notional = np.array([liq_tot[b:e].sum() for b, e in zip(bars, ends)])
    covered_flag = np.array([have_liq[b:e].any() for b, e in zip(bars, ends)])
    tt = touches.assign(liq_notional=notional, covered=covered_flag)
    covered = tt[tt["covered"]]
    gt = covered.groupby("kind").apply(
        lambda x: pd.Series({
            "n": len(x),
            "pct_with_liquidation": float((x["liq_notional"] > 0).mean()),
            "mean_liq_notional": float(x["liq_notional"].mean()),
        }), include_groups=False).to_dict("index")
    if "cluster" in gt and "empty" in gt and gt["empty"]["mean_liq_notional"] > 0:
        gt["notional_multiple_cluster_over_empty"] = (
            gt["cluster"]["mean_liq_notional"] / gt["empty"]["mean_liq_notional"])

    # The ratio depends on what counts as a control, so the composition is published
    # rather than left implicit. An emptied bucket holds no map notional at all; it is
    # the cleanest "nothing is here" level available, and it is most of the control
    # group. Restricting the control to buckets that still hold something raises its
    # mean and shrinks the ratio, which is a different comparison, not a better one.
    emp = covered[covered["kind"] == "empty"]
    if len(emp):
        held = emp[emp["notional"] > 0]
        gt["empty_zero_mass_share"] = float((emp["notional"] <= 0).mean())
        if len(held) and held["liq_notional"].mean() > 0:
            gt["notional_multiple_excluding_emptied"] = float(
                gt["cluster"]["mean_liq_notional"] / held["liq_notional"].mean())

    res = {"ground_truth": gt, "framings": {}}
    cells = ("size_q", "dist_q", "vol_q", "hour_q")

    # 1. acceleration -- cluster touches against matched empty ones
    cd = train_t[train_t["kind"].isin(["cluster", "empty"])]
    d1 = audit.matched_difference(cd, "cont_60m", "is_cluster",
                                  [c for c in cells if c in cd.columns])
    res["framings"]["1_acceleration"] = {
        "matched_diff_bps": d1["diff"] if d1 else None,
        "n_cells": d1["n_cells"] if d1 else 0,
        "placebo": audit.placebo_labels(cd, "cont_60m", "is_cluster",
                                        [c for c in cells if c in cd.columns], n=300),
        "abs_move_slope": _slope(train_t.assign(absm=train_t["cont_60m"].abs()),
                                 "absm", "share"),
    }

    # 2. pressure -- mapped notional against the depth waiting for it
    res["framings"]["2_pressure"] = {
        "slope": _slope(train_t.dropna(subset=["pressure"]).assign(
            logp=np.log(train_t.dropna(subset=["pressure"])["pressure"].clip(lower=1e-9))),
            "cont_60m", "logp"),
        "control_notional_only": _slope(train_t.dropna(subset=["pressure"]).assign(
            logn=np.log(train_t.dropna(subset=["pressure"])["notional"].clip(lower=1e-9))),
            "cont_60m", "logn"),
    }

    # 3. age -- raw, then with the confound that produces the same shape
    t3 = train_t.dropna(subset=["age_bars", "share"]).copy()
    t3["log_age"] = np.log1p(t3["age_bars"].clip(lower=0))
    t3["mom_1h"] = (g["ret_1h"].to_numpy(float)[t3["bar"].to_numpy()]
                    * np.where(t3["is_down"], -1.0, 1.0))
    raw_age = _slope(t3, "cont_60m", "log_age")
    keys = [k for k in cells if k in t3.columns]
    grp = t3.groupby(keys, observed=True)
    y = (t3["cont_60m"] - grp["cont_60m"].transform("mean")).to_numpy(float)
    A = np.column_stack([(t3[c] - grp[c].transform("mean")).to_numpy(float)
                         for c in ("log_age", "mom_1h")])
    ok = np.isfinite(y) & np.isfinite(A).all(axis=1)
    beta = np.linalg.lstsq(A[ok], y[ok], rcond=None)[0]
    res["framings"]["3_age"] = {
        "raw_slope": raw_age,
        "controlled_for_momentum": {"beta_log_age": float(beta[0]),
                                    "beta_momentum": float(beta[1]),
                                    "corr_age_momentum": float(
                                        np.corrcoef(A[ok, 0], A[ok, 1])[0, 1])},
    }

    # 4. regime -- thin liquidity
    reg = {}
    for name in ("weekend", "asia"):
        col = g[name].to_numpy()[train_t["bar"].to_numpy()]
        sub = train_t.assign(**{name: col})
        r = audit.matched_difference(sub, "cont_60m", name,
                                     [c for c in cells if c in sub.columns])
        reg[name] = {"matched_diff_bps": r["diff"] if r else None,
                     "n_cells": r["n_cells"] if r else 0}
    res["framings"]["4_regime"] = reg

    # 5. anticipation -- the level after flow the map did not predict
    unpred = train_p[train_p["predicted"] == 0]
    lev = {h: _level(unpred, f"cont_{h}") for h in config.FWD_BARS}
    d5 = audit.matched_difference(train_p, "cont_30m", "predicted",
                                  [c for c in cells if c in train_p.columns])
    res["framings"]["5_anticipation"] = {
        "level_after_unpredicted": lev,
        "matched_diff_bps": d5["diff"] if d5 else None,
        "placebo": audit.placebo_labels(train_p, "cont_30m", "predicted",
                                        [c for c in cells if c in train_p.columns], n=300),
        "band_bps": config.BAND_BPS,
    }

    # rule 5: the standing check that the machinery does not manufacture results
    u = unpred.dropna(subset=["cont_30m"])
    res["randomisation"] = audit.randomisation(
        lambda v: float(np.nanmean(v)), u["cont_30m"].to_numpy(float),
        u["day"].to_numpy(), n=300)

    config.RESULTS.mkdir(parents=True, exist_ok=True)
    json.dump(res, open(config.RESULTS / "event_study.json", "w"), indent=2, default=float)
    m = res["ground_truth"].get("notional_multiple_cluster_over_empty")
    l30 = (lev.get("30m") or {})
    print(f"  ground truth: mapped levels carry {m:.1f}x the liquidation notional"
          if m else "  ground truth: not estimable")
    print(f"  framing 5 level after unpredicted, 30m: "
          f"{l30.get('level_bps', float('nan')):.2f}bps "
          f"CI [{l30.get('ci_lo', float('nan')):.2f}, {l30.get('ci_hi', float('nan')):.2f}] "
          f"MDE {l30.get('mde_bps', float('nan')):.2f} vs band {config.BAND_BPS}")


if __name__ == "__main__":
    main()
