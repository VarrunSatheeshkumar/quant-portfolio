"""What the volatility forecast is worth per trade, in basis points.

The instrument stage answers a statistical question -- can a structure resolve a
10bps effect -- and that is not the same as whether the effect pays. This stage
converts Model A's out-of-sample improvement into an expected P&L per trade and puts
it next to the measured cost of each structure, so the ceiling can be read
economically rather than only as a power calculation.

The conversion, in one step. If a forecast has incremental correlation rho with a
payoff whose per-trade dispersion is sigma, and you trade the sign of the forecast
with constant notional, then for jointly normal (forecast, payoff) the expected
P&L per trade is

    E[p . sign(f)] = rho . sqrt(2/pi) . sigma

which is the whole calculation. Everything else here is stating what has to be
assumed to get rho and sigma into the same units, and each assumption is generous
to the trade -- so the number this produces is a ceiling on the edge, sitting next
to a cost that is measured rather than assumed.
"""

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config

SQRT_2_OVER_PI = float(np.sqrt(2.0 / np.pi))

# The benchmark the edge is measured against. Improvement over GARCH is not
# tradeable improvement: an option strike already embeds a forecast at least as good
# as a heterogeneous autoregression, so only what Model A adds beyond HAR could
# possibly be paid for. The intraday cascade is the harder of the two HARs and the
# one used here.
BENCHMARK = "har_intraday"

ASSUMPTIONS = [
    "Skill transfers across horizon: Model A's measured gain at 1h and 4h is assumed "
    "to hold undiminished at the 7-day tenor of the traded structures. It will not "
    "-- forecast skill decays with horizon -- so this inflates the edge.",
    "Incremental correlation is the square root of incremental R-squared, and that "
    "correlation is assumed to survive the change from log realised volatility, "
    "where it was measured, to the variance payoff of the structure.",
    "None of the improvement over HAR is assumed to be in the option price already; "
    "any part of it that is has already been paid for and is not edge.",
    "The rule is to trade the sign of the forecast error each period at constant "
    "vega notional, with the forecast and the payoff jointly normal.",
    "Per-trade dispersion is the structure's own measured paired P&L dispersion on "
    "training trades, and cost is its measured round-trip cost -- both from the "
    "instrument stage, neither assumed.",
    "The same rho is assumed for every structure, which flatters any structure whose "
    "dispersion comes from noise a volatility forecast cannot see.",
]


def main():
    har = json.load(open(config.RESULTS / "har.json"))
    inst = json.load(open(config.RESULTS / "instrument.json"))

    # One rho per (horizon, block) cell, from the incremental R-squared over the
    # benchmark. Negative gains would mean no edge to convert; clip rather than take
    # the root of a negative number.
    gains = {}
    for h, row in har["scores"].items():
        for label, v in row.items():
            gains[f"{h}_{label}"] = {"gain": v[f"gain_over_{BENCHMARK}"],
                                     "looks": v["looks"]}
    rho = {k: float(np.sqrt(max(v["gain"], 0.0))) for k, v in gains.items()}

    sealed = {k: r for k, r in rho.items() if not k.endswith("_train")}
    rho_lo, rho_hi = min(sealed.values()), max(sealed.values())

    rows = {}
    for name, s in inst["structures"].items():
        sd = s["sd_per_trade_bps"]
        lo, hi = rho_lo * SQRT_2_OVER_PI * sd, rho_hi * SQRT_2_OVER_PI * sd
        rows[name] = {
            "edge_bps_low": lo,
            "edge_bps_high": hi,
            "cost_bps": s["mean_cost_bps"],
            "net_bps_low": lo - s["mean_cost_bps"],
            "net_bps_high": hi - s["mean_cost_bps"],
            # Expected edge scales with the structure's own dispersion, so raw bps
            # of net edge ranks the noisiest structure first and compares nothing.
            "net_over_sd_low": (lo - s["mean_cost_bps"]) / sd,
            "sd_per_trade_bps": sd,
            "mde_bps": s["mde_bps"],
            # The question that decides it: is the edge, at its most generous, large
            # enough that this sample could tell it from zero?
            "edge_exceeds_mde": bool(hi > s["mde_bps"]),
            "n_train_trades": s["n_train_trades"],
        }

    # Headline on the cheapest structure, not the highest net edge. Cost is
    # measured; rho is assumed common across structures, and a ranking built on the
    # assumed quantity would be reporting the assumption back.
    best = min(rows, key=lambda k: rows[k]["cost_bps"])
    b = rows[best]

    # edge/MDE = rho.sqrt(2/pi).sqrt(n)/z, in which dispersion cancels entirely. No
    # choice of structure makes the edge resolvable; only more independent trades do.
    need = float((config.POWER_Z / (rho_lo * SQRT_2_OVER_PI)) ** 2)
    payload = {
        "benchmark": BENCHMARK,
        "incremental_r2_over_benchmark": gains,
        "rho_sealed_low": rho_lo,
        "rho_sealed_high": rho_hi,
        "structures": rows,
        "best_net_structure": best,
        "best_net_bps_low": b["net_bps_low"],
        "best_net_bps_high": b["net_bps_high"],
        "best_edge_bps_low": b["edge_bps_low"],
        "best_edge_bps_high": b["edge_bps_high"],
        "best_cost_bps": b["cost_bps"],
        "best_mde_bps": b["mde_bps"],
        "independent_trades_needed": need,
        "years_needed_weekly": need / 52.0,
        "any_edge_resolvable": any(v["edge_exceeds_mde"] for v in rows.values()),
        # The two together, which is what a trader needs: a structure that both pays
        # after costs and shows an edge its own sample could tell from zero. The
        # separate flags each hide the other half -- the two strips can resolve their
        # edge but lose a full percent per trade to costs.
        "any_positive_and_resolvable": any(
            v["net_bps_low"] > 0 and v["edge_exceeds_mde"] for v in rows.values()),
        "n_structures_net_positive": sum(
            1 for v in rows.values() if v["net_bps_low"] > 0),
        "assumptions": ASSUMPTIONS,
    }
    json.dump(payload, open(config.RESULTS / "economics.json", "w"),
              indent=2, default=float)

    print(f"  benchmark {BENCHMARK}: incremental R2 on sealed blocks "
          f"{min(v['gain'] for k, v in gains.items() if not k.endswith('_train')):+.4f} "
          f"to {max(v['gain'] for k, v in gains.items() if not k.endswith('_train')):+.4f}"
          f"  (rho {rho_lo:.3f} to {rho_hi:.3f})")
    for name, v in sorted(rows.items(), key=lambda kv: kv[1]["cost_bps"]):
        print(f"  {name:26s} edge {v['edge_bps_low']:6.1f}-{v['edge_bps_high']:6.1f}bps"
              f"  cost {v['cost_bps']:6.1f}bps  net {v['net_bps_low']:+7.1f} to "
              f"{v['net_bps_high']:+7.1f}  MDE {v['mde_bps']:6.1f}")
    print(f"  best net: {best} at {b['net_bps_low']:+.1f} to {b['net_bps_high']:+.1f}bps "
          f"per trade; resolvable in this sample: {b['edge_exceeds_mde']}")
    print(f"  net positive after costs: {payload['n_structures_net_positive']} of "
          f"{len(rows)}; both net positive and resolvable: "
          f"{payload['any_positive_and_resolvable']}")
    print(f"  edge exceeds MDE only after {need:.0f} independent trades, or "
          f"{need / 52.0:.0f} years weekly")


if __name__ == "__main__":
    main()
