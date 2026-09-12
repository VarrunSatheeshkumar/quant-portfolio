"""Model A: forecast realised volatility, and score it on the sealed blocks.

Walk-forward: fit on the trailing twelve months, predict the next, roll. Every
normalising constant comes from the training window only -- a full-sample mean is a
statistic of the future at every point before the end of the sample.

Two masks, not one. Training excludes the sealed blocks; *prediction* does not, or a
sealed month never appears as a test row, never receives a forecast, and the block
comes back empty rather than scored. That bug is easy to miss because the output is
full of nulls rather than an error.
"""

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config
from src import audit

warnings.filterwarnings("ignore")

FEATURES = [
    "lev_below_1pct", "lev_below_2pct", "lev_below_3pct",
    "lev_above_1pct", "lev_above_2pct", "lev_above_3pct",
    "asymmetry_ratio", "dist_nearest_cluster", "map_coverage",
    "funding_rate", "premium_index", "oi_vol_ratio",
    "liq_long_1h", "liq_short_1h", "liq_long_4h", "liq_short_4h",
    "log_rv_1h", "log_rv_4h", "log_rv_24h", "log_garch", "log_dvol",
    "hour_sin", "hour_cos", "dow",
]


def garch_forecast(returns, horizons, train_mask):
    """GARCH(1,1) fitted on training data, filtered forward over everything.

    The k-step variance forecast is analytic, so the horizon sum is closed form
    rather than simulated per bar.
    """
    from arch import arch_model
    r = returns.fillna(0.0).to_numpy(float) * 100.0
    res = arch_model(r[train_mask], vol="Garch", p=1, o=0, q=1, dist="normal",
                     mean="Zero", rescale=False).fit(disp="off", show_warning=False)
    omega, alpha, beta = (res.params["omega"], res.params["alpha[1]"],
                          res.params["beta[1]"])
    persist = alpha + beta
    uncond = omega / max(1e-12, 1.0 - persist)

    h = np.empty(len(r))
    h[0] = uncond
    for i in range(1, len(r)):
        h[i] = omega + alpha * r[i - 1] ** 2 + beta * h[i - 1]

    out = {}
    h1 = omega + alpha * r ** 2 + beta * h
    for name, H in horizons.items():
        if persist >= 1.0:
            total = h * H
        else:
            geo = (1.0 - persist ** H) / (1.0 - persist)
            total = uncond * H + (h1 - uncond) * geo
        out[name] = np.sqrt(np.maximum(total, 1e-12)) / 100.0
    return out, {"omega": float(omega), "alpha": float(alpha), "beta": float(beta)}


def slices(index, train_mask, test_mask):
    """Monthly test slices, each fitted on the trailing window that precedes it.

    The purge gap sits between the end of training and the start of testing so a
    target opened at the end of training cannot resolve inside the test month.
    """
    index = pd.DatetimeIndex(index)
    for m in pd.period_range(index.min(), index.max(), freq="M"):
        test_lo = m.start_time.tz_localize("UTC")
        test_hi = (m + 1).start_time.tz_localize("UTC")
        train_lo = test_lo - pd.DateOffset(months=config.TRAIN_MONTHS)
        train_hi = test_lo - pd.Timedelta(days=config.PURGE_DAYS)
        tr = train_mask & (index >= train_lo) & (index < train_hi)
        te = test_mask & (index >= test_lo) & (index < test_hi)
        if tr.sum() < config.MIN_TRAIN_ROWS or te.sum() < config.MIN_TEST_ROWS:
            continue
        yield tr, te


def fit_predict(X, y, tr, te, alpha=1.0):
    mu, sd = X[tr].mean(axis=0), X[tr].std(axis=0)
    sd[sd == 0] = 1.0
    model = Ridge(alpha=alpha).fit((X[tr] - mu) / sd, y[tr])
    return model.predict((X[te] - mu) / sd)


def r2(y, p):
    ok = np.isfinite(y) & np.isfinite(p)
    if ok.sum() < 10:
        return np.nan
    return 1.0 - ((y[ok] - p[ok]) ** 2).sum() / ((y[ok] - y[ok].mean()) ** 2).sum()


def qlike(rv, pv):
    """Lower is better. It punishes under-forecasting variance hard, which is why a
    model fitted for squared error in logs can beat a baseline on R2 and lose on
    QLIKE -- a real disagreement about which errors matter, not a contradiction."""
    ok = np.isfinite(rv) & np.isfinite(pv) & (pv > 0) & (rv > 0)
    if ok.sum() < 10:
        return np.nan
    return float(np.mean(np.log(pv[ok]) + rv[ok] / pv[ok]))


def build_panel():
    grid = pd.read_parquet(config.GRID_DIR / "grid.parquet")
    grid["ts"] = pd.to_datetime(grid["ts"], utc=True)
    grid = grid.set_index("ts").sort_index()
    mp = pd.read_parquet(config.INTERIM / "map_features.parquet")
    mp["ts"] = pd.to_datetime(mp["ts"], utc=True)
    mp = mp.set_index("ts").sort_index()
    mp = mp.drop(columns=[c for c in mp.columns if c in grid.columns], errors="ignore")

    df = grid.join(mp, how="left")
    df = df.loc[df["map_total"].notna()]
    for w in ("1h", "4h", "24h"):
        df[f"log_rv_{w}"] = np.log(df[f"rv_{w}"].replace(0, np.nan))
    # DVOL is annualised implied vol in percent; the target is realised vol over an
    # hour. Comparing them unconverted once produced an R2 of -212.
    df["log_dvol"] = np.log(df["dvol"].replace(0, np.nan) / 100.0)
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
    for c in ["lev_below_1pct", "lev_below_2pct", "lev_below_3pct", "lev_above_1pct",
              "lev_above_2pct", "lev_above_3pct", "map_total",
              "liq_long_1h", "liq_short_1h", "liq_long_4h", "liq_short_4h"]:
        df[c] = np.log1p(df[c].clip(lower=0))
    df["asymmetry_ratio"] = np.log(df["asymmetry_ratio"].replace(0, np.nan)).clip(-5, 5)
    return df


def main():
    df = build_panel()
    train_ok = audit.training_mask(df.index)

    garch, gp = garch_forecast(df["ret_5m"], config.HORIZONS, train_ok)
    for name in config.HORIZONS:
        df[f"garch_{name}"] = garch[name]
    df["log_garch"] = np.log(df["garch_1h"])

    feats = [c for c in FEATURES if c in df.columns]
    X = np.nan_to_num(df[feats].to_numpy(float), nan=0.0, posinf=0.0, neginf=0.0)
    have = df[feats].notna().mean(axis=1).gt(0.6).to_numpy()

    out = pd.DataFrame(index=df.index)
    scores = {}
    for name in config.HORIZONS:
        y = df[f"tgt_logrv_{name}"].to_numpy(float)
        usable = train_ok & np.isfinite(y) & have
        oos = pd.Series(np.nan, index=df.index)
        for tr, te in slices(df.index, usable, have):
            oos.iloc[np.nonzero(te)[0]] = fit_predict(X, y, tr, te)
        out[f"sigma_hat_{name}"] = np.exp(oos)
        out[f"garch_{name}"] = df[f"garch_{name}"]

        p, gch = oos.to_numpy(), np.log(df[f"garch_{name}"].to_numpy())
        rvt = np.log(df[f"rv_{name}"].replace(0, np.nan)).to_numpy()
        dvl = df["log_dvol"].to_numpy() + np.log(np.sqrt(
            config.HORIZONS[name] * 5.0 / (365 * 24 * 60)))
        row = {}
        for label, mask in [("train", train_ok),
                            ("sealed_2022", audit.in_block(df.index, config.SEALED_2022)),
                            ("sealed_recent", audit.in_block(df.index, config.SEALED_RECENT))]:
            ev = mask & np.isfinite(p) & np.isfinite(y)
            if ev.sum() < 500:
                continue
            row[label] = {
                "n": int(ev.sum()), "looks": 0 if label == "train" else 1,
                "r2_model": r2(y[ev], p[ev]), "r2_garch": r2(y[ev], gch[ev]),
                "r2_trailing_rv": r2(y[ev], rvt[ev]), "r2_dvol": r2(y[ev], dvl[ev]),
                "gain_over_garch": r2(y[ev], p[ev]) - r2(y[ev], gch[ev]),
                "qlike_model": qlike(np.exp(2 * y[ev]), np.exp(2 * p[ev])),
                "qlike_garch": qlike(np.exp(2 * y[ev]), np.exp(2 * gch[ev])),
            }
        scores[name] = row

    out["asymmetry_ratio"] = df["asymmetry_ratio"]
    out["dist_nearest_cluster"] = df["dist_nearest_cluster"]
    out.reset_index().to_parquet(config.INTERIM / "model_a.parquet", index=False)
    config.RESULTS.mkdir(parents=True, exist_ok=True)
    json.dump({"scores": scores, "garch": gp},
              open(config.RESULTS / "vol_model.json", "w"), indent=2, default=float)

    for h, row in scores.items():
        for label, v in row.items():
            print(f"  {h} {label:14s} R2 {v['r2_model']:.4f} vs GARCH "
                  f"{v['r2_garch']:.4f}  gain {v['gain_over_garch']:+.4f}  "
                  f"(looks={v['looks']})")


if __name__ == "__main__":
    main()
