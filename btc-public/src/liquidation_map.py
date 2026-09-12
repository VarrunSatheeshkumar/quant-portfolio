"""The liquidation map, and the leverage mix fitted to real forced exits.

Positions opened in a bar are inferred from the change in open interest and the sign
of the price move, spread across a leverage ladder, and converted to the price at
which each cohort is force-closed. The histogram of those prices is the map.

The map is *linear in the leverage weights* -- one cohort firing does not change
whether another fires, and the decay is multiplicative -- so the ladder is run once
per rung and the mix is fitted afterwards. That turns a grid search over a simplex
into four passes plus a search over precomputed series.

The mix is fitted against real forced-order prints, not a proxy. An earlier attempt
used the part of a fall in open interest that lands on an adverse price move; it is
uninformative, because voluntary closing swamps forced closing at five-minute
resolution.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config
from src import audit

P0 = 1000.0
LOGSTEP = np.log1p(config.MAP_BUCKET_PCT)
NBUCKET = 2200                                   # ~1,000 to ~250,000 at 0.25% steps
BUCKET_PRICE = P0 * np.exp(LOGSTEP * np.arange(NBUCKET))


def bucket_of(price):
    return np.floor(np.log(np.maximum(price, P0 * 1.001) / P0) / LOGSTEP).astype(np.int64)


def run_map(close, high, low, vwap, d_oi, oi_prev, decay, mix,
            collect_features=False, hooks=None, track_age=False):
    """One replay of the map. `mix` maps leverage to weight; a single-rung mix gives
    that rung's contribution, which is what makes the calibration cheap.

    `hooks` receives (bar_index, long_map, short_map, total) *before* the bar is
    applied, which is the only correct moment to ask what the map looked like: the
    bar that touches a level is also the bar whose removal step zeroes it.
    """
    n = len(close)
    long_map, short_map = np.zeros(NBUCKET), np.zeros(NBUCKET)
    # Age is carried as a decayed sum of mass x add-bar alongside the decayed mass,
    # so a bucket's age is the notional-weighted mean age of everything sitting at
    # it -- not the age of whichever cohort landed last.
    age_long = np.zeros(NBUCKET) if track_age else None
    age_short = np.zeros(NBUCKET) if track_age else None
    fired_long, fired_short = np.zeros(n), np.zeros(n)
    feats = np.full((n, 8), np.nan) if collect_features else None

    long_mult = {L: 1.0 - 1.0 / L + config.MAINT_MARGIN for L in mix}
    short_mult = {L: 1.0 + 1.0 / L - config.MAINT_MARGIN for L in mix}
    lo_b, hi_b, px_b = bucket_of(low), bucket_of(high), bucket_of(close)
    win = int(np.ceil(np.log1p(config.MAP_RANGE_PCT) / LOGSTEP))
    edges = [int(np.ceil(np.log1p(p) / LOGSTEP)) for p in (0.01, 0.02, 0.03)]

    for i in range(1, n):
        if hooks is not None:
            hooks(i, long_map, short_map, long_map.sum() + short_map.sum(),
                  age_long, age_short)

        long_map *= decay
        short_map *= decay
        if track_age:
            age_long *= decay
            age_short *= decay

        # Price traded through: longs die on the way down, shorts on the way up.
        lb, hb = lo_b[i], hi_b[i]
        if lb >= 0:
            fired_long[i] = long_map[lb:].sum()
            long_map[lb:] = 0.0
            if track_age:
                age_long[lb:] = 0.0
        if hb + 1 <= NBUCKET:
            fired_short[i] = short_map[:hb + 1].sum()
            short_map[:hb + 1] = 0.0
            if track_age:
                age_short[:hb + 1] = 0.0

        do = d_oi[i]
        if np.isfinite(do) and do != 0.0 and np.isfinite(vwap[i]) and vwap[i] > 0:
            if do > 0:
                notional = do * vwap[i]
                up = close[i] >= vwap[i]
                for L, w in mix.items():
                    mult = long_mult[L] if up else short_mult[L]
                    book = long_map if up else short_map
                    b = int(np.floor(np.log(vwap[i] * mult / P0) / LOGSTEP))
                    if 0 <= b < NBUCKET:
                        book[b] += notional * w
                        if track_age:
                            (age_long if up else age_short)[b] += notional * w * i
            elif oi_prev[i] > 0:
                # What remains of an open-interest decline after forced exits is
                # voluntary closing, so both books shrink proportionally.
                keep = max(0.0, 1.0 + do / oi_prev[i])
                long_map *= keep
                short_map *= keep
                if track_age:
                    age_long *= keep
                    age_short *= keep

        if collect_features:
            c = px_b[i]
            a, b_ = max(0, c - win), min(NBUCKET, c + win + 1)
            lm, sm, here = long_map[a:b_], short_map[a:b_], c - a
            below = [lm[max(0, here - e):here + 1].sum() for e in edges]
            above = [sm[here:here + e + 1].sum() for e in edges]
            total = lm.sum() + sm.sum()
            if total > 0:
                both = lm + sm
                big = np.nonzero(both > config.CLUSTER_SHARE * total)[0]
                dist = (np.abs(big - here).min() if len(big)
                        else abs(int(both.argmax()) - here)) * LOGSTEP
            else:
                dist = np.nan
            feats[i] = [below[0], below[1], below[2], above[0], above[1], above[2],
                        total, dist]

    return fired_long, fired_short, feats


def _simplex(step):
    k = int(round(1.0 / step))
    return np.array([[a, b, c, k - a - b - c]
                     for a in range(k + 1) for b in range(k + 1 - a)
                     for c in range(k + 1 - a - b)], float) / k


def calibrate(pred_by_level, obs_long, obs_short, mask, step=0.05):
    """Fit the mix on a variance-stabilised scale.

    Squared error in raw notional puts almost all the weight on a single rung:
    liquidation notional spans four orders of magnitude, so a handful of cascade bars
    carry the entire loss function and the fit reduces to "which rung best flags that
    something big happened". On log1p the same data discriminates between ladders.
    """
    P = np.column_stack([np.concatenate([pred_by_level[L][0][mask],
                                         pred_by_level[L][1][mask]])
                         for L in config.LEVERAGE_LADDER])
    y = np.concatenate([np.asarray(obs_long)[mask], np.asarray(obs_short)[mask]])
    good = np.isfinite(P).all(axis=1) & np.isfinite(y)
    P, y = P[good], y[good]
    if len(y) < 200 or np.std(y) <= 0:
        return dict(config.LEVERAGE_PRIOR), np.nan, len(y)
    ly = np.log1p(np.maximum(y, 0.0))
    ly = ly - ly.mean()
    denom = np.sqrt((ly ** 2).sum())

    best, best_corr = None, -np.inf
    # P and y were checked finite above and every candidate correlation is checked
    # again below, so nothing non-finite can win. The suppression is for the
    # floating-point flags some BLAS builds raise from the padding lanes of a
    # matmul, which are not about this data.
    with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
        for w in _simplex(step):
            lp = np.log1p(P @ w)
            lp = lp - lp.mean()
            d = np.sqrt((lp ** 2).sum())
            if d <= 0:
                continue
            c = float((lp @ ly) / (d * denom))
            if np.isfinite(c) and c > best_corr:
                best_corr, best = c, w
    if best is None:
        return dict(config.LEVERAGE_PRIOR), np.nan, len(y)
    return {L: float(v) for L, v in zip(config.LEVERAGE_LADDER, best)}, best_corr, len(y)


def main():
    config.INTERIM.mkdir(parents=True, exist_ok=True)
    grid = pd.read_parquet(config.GRID_DIR / "grid.parquet")
    grid["ts"] = pd.to_datetime(grid["ts"], utc=True)
    grid = grid.set_index("ts").sort_index()
    g = grid.loc[grid["oi"].notna()].copy()

    close = g["close"].to_numpy(float)
    high, low = g["high"].to_numpy(float), g["low"].to_numpy(float)
    vwap = g["vwap_bar"].fillna(g["close"]).to_numpy(float)
    d_oi = g["oi"].diff().to_numpy(float)
    oi_prev = g["oi"].shift(1).to_numpy(float)
    decay = 0.5 ** (1.0 / config.MAP_HALF_LIFE_BARS)

    obs_long = g["liq_long"]
    obs_short = g["liq_short"]
    have = obs_long.notna().to_numpy()
    train = audit.training_mask(g.index)
    fit_mask = train & have
    if fit_mask.sum() < 500:
        raise SystemExit("no liquidation prints inside the training window")

    pred = {}
    for L in config.LEVERAGE_LADDER:
        pred[L] = run_map(close, high, low, vwap, d_oi, oi_prev, decay, {L: 1.0})[:2]
        print(f"  rung {L}x done", flush=True)

    mix, corr, n_obs = calibrate(pred, obs_long.fillna(0.0), obs_short.fillna(0.0),
                                 fit_mask)
    fl, fs, feats = run_map(close, high, low, vwap, d_oi, oi_prev, decay, mix,
                            collect_features=True)

    names = ["lev_below_1pct", "lev_below_2pct", "lev_below_3pct",
             "lev_above_1pct", "lev_above_2pct", "lev_above_3pct",
             "map_total", "dist_nearest_cluster"]
    out = pd.DataFrame(feats, columns=names, index=g.index)
    out["asymmetry_ratio"] = out["lev_below_2pct"] / out["lev_above_2pct"].replace(0, np.nan)
    out["map_coverage"] = out["map_total"] / (g["oi"] * g["close"])
    out["pred_liq"] = fl + fs
    out.reset_index().to_parquet(config.INTERIM / "map_features.parquet", index=False)
    json.dump({"mix": mix, "log_corr": corr, "n_obs": int(n_obs),
               "n_fit_bars": int(fit_mask.sum()),
               "n_fit_days": int(pd.DatetimeIndex(g.index[fit_mask]).floor("D").nunique())},
              open(config.INTERIM / "leverage_mix.json", "w"), indent=2)
    print(f"map: mix={ {k: round(v, 3) for k, v in mix.items()} }, "
          f"log-scale corr with real prints={corr:.4f}, "
          f"fitted on {fit_mask.sum():,} bars")


if __name__ == "__main__":
    main()
