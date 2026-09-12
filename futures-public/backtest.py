"""The one backtest engine every stage uses. Dollars per contract throughout.

A position is a number of contracts. Its P&L on day t is contracts held at the
close of t-1 times the neutralised price change on t times the multiplier. Costs
are paid on every change in contracts and on every roll. Nothing here knows what
a signal is; it is handed positions and returns and produces numbers.
"""

import numpy as np
import pandas as pd

import config
from lib import power, validate

ANN = 252


def dollar_vol(ret_usd, window=config.VOL_WINDOW):
    """Trailing std of the $ change per contract, known at the close of t-1."""
    return ret_usd.rolling(window, min_periods=window // 2).std().shift(1)


def contracts(signal, dvol, budget):
    """Contracts so that a unit signal risks `budget` dollars a day in that market."""
    c = signal * (budget / dvol)
    return c.replace([np.inf, -np.inf], np.nan)


def cost_per_side(px):
    """Dollars to trade one contract once: commission plus half the spread plus impact."""
    out = {}
    for m, s in config.UNIVERSE.items():
        tick_value = s["tick"] * s["mult"]
        out[m] = config.COMMISSION_PER_SIDE + (0.5 * s["spread"] + config.IMPACT_TICKS) * tick_value
    return pd.Series(out)


def roll_days():
    out = {}
    for m in config.UNIVERSE:
        out[m] = pd.DatetimeIndex(pd.read_parquet(config.STAGES / f"s0_rolls_{m}.parquet")["roll_day"])
    return out


def pnl(pos, ret_usd, rolls=None, side_cost=None):
    """Gross and cost $ P&L by market. pos is contracts held at the close of each day."""
    held = pos.shift(1)
    gross = held * ret_usd
    if side_cost is None:
        side_cost = cost_per_side(None)
    trade = pos.diff().abs().fillna(pos.abs())
    cost = trade * side_cost
    if rolls is not None:
        for m, days in rolls.items():
            on = held.index.isin(days)
            cost.loc[on, m] += held.loc[on, m].abs() * 2 * side_cost[m]
    return gross, cost.where(held.notna())


def sharpe(x):
    x = pd.Series(x).dropna()
    return float(x.mean() / x.std() * np.sqrt(ANN)) if len(x) > 20 and x.std() > 0 else np.nan


def turnover(pos, px, capital):
    """One-sided notional traded per year as a multiple of capital."""
    notional = (pos.diff().abs() * px.abs() * pd.Series({m: s["mult"] for m, s in config.UNIVERSE.items()})).sum(axis=1)
    return float(notional.mean() * ANN / capital)


def summary(gross, cost, capital):
    g = gross.sum(axis=1) / capital
    c = cost.sum(axis=1) / capital
    net = g - c
    blocks = net.index.to_period("M")
    se = power.block_bootstrap(net.values, blocks.astype(str), n=1000).std()
    return dict(sharpe_gross=sharpe(g), sharpe_net=sharpe(net), ann_vol=float(net.std() * np.sqrt(ANN)),
                ann_return=float(net.mean() * ANN), ann_cost=float(c.mean() * ANN),
                daily_mean=float(net.mean()), daily_se=float(se), mde_daily=float(power.mde_from_se(se)),
                mde_sharpe=float(power.mde_from_se(se) / net.std() * np.sqrt(ANN)),
                max_dd=max_drawdown(net), n_days=int(net.notna().sum()))


def max_drawdown(r):
    eq = (1 + r.fillna(0)).cumprod()
    return float((eq / eq.cummax() - 1).min())


def placebo(signal, dvol, budget, ret_usd, rolls, capital, n=100, seed=config.SEED):
    """Random signals with the same persistence and the same average |exposure|.

    The real signal's average holding period sets the flip rate of a random sign
    process, so turnover is matched; the scale is matched to mean |signal|.
    """
    rng = np.random.default_rng(seed)
    s = signal
    flips = (np.sign(s).diff().abs() > 0).sum() / s.notna().sum()
    scale = s.abs().mean()
    out = []
    for _ in range(n):
        fake = pd.DataFrame(index=s.index, columns=s.columns, dtype=float)
        for m in s.columns:
            flip = rng.random(len(s)) < float(flips[m])
            sign = np.cumprod(np.where(flip, -1, 1)) * rng.choice([-1, 1])
            fake[m] = sign * float(scale[m])
        fake = fake.where(s.notna())
        pos = contracts(fake, dvol, budget)
        g, c = pnl(pos, ret_usd, rolls)
        out.append(sharpe((g.sum(axis=1) - c.sum(axis=1)) / capital))
    return np.array(out)


def block_shuffled_returns(ret_usd, seed=config.SEED, flip=False):
    """Returns with whole months permuted (same permutation for every market).

    A permutation destroys timing but keeps every market's unconditional drift,
    so a signal with a standing directional tilt still collects (or pays) that
    drift on shuffled data: the plain shuffle measures the tilt. With flip=True
    each block's sign is also flipped at random (the same flip across markets),
    which removes the drift too; that is the test of the machinery, expected ~0.
    """
    blocks = ret_usd.index.to_period("M").astype(str)
    out = ret_usd.copy()
    for m in ret_usd.columns:
        out[m] = validate.block_shuffle(ret_usd[m].values, blocks, seed=seed)
    if flip:
        rng = np.random.default_rng(seed + 1)
        uniq = pd.Index(blocks).unique()
        sign = pd.Series(rng.choice([-1.0, 1.0], len(uniq)), index=uniq).reindex(blocks).values
        out = out.mul(sign, axis=0)
    return out


def rebalance(target, freq):
    """Hold the target position computed on the last trading day of each period.

    "W" = weekly (last business day of the week), "M" = monthly, "D" = every day.
    A discrete signal re-evaluated daily churns; sampling it on a schedule is the
    standard remedy and costs one parameter that is fixed before any return is read.
    """
    if freq == "D":
        return target
    if freq == "W":
        key = target.index.to_period("W")
    elif freq == "M":
        key = target.index.to_period("M")
    else:
        raise ValueError(freq)
    last = pd.Series(target.index, index=target.index).groupby(key).transform("last")
    on = pd.Series(target.index == last.values, index=target.index)
    return target.loc[on].reindex(target.index).ffill()
