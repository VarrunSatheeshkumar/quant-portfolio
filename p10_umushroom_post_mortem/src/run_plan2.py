"""Plan 2 runner: writes out/results2.json. Components that are not built yet are simply absent."""
import json
import sys
import warnings

warnings.filterwarnings("ignore")
import pandas as pd

from config import OUT
import counterfactual
import ledger
import plan2_core as p2
import scorecard
from run_all import clean, dumps

ASOF = "2026-11-20"


def main(parts=("core",)):
    f = OUT / "results2.json"
    R = json.loads(f.read_text()) if f.exists() else {}
    R1 = json.loads((OUT / "results.json").read_text())
    assert R1["asof"] == ASOF, "run run_all.py --asof 2026-11-20 first"
    R["asof"] = ASOF
    if "core" in parts:
        pnl = R1["B"]["total_pnl"]
        snap, snap_meta = ledger.platform_snapshot(ASOF)   # the reading valued at the 20 Nov close
        R["platform"] = {"valuation_date": snap_meta["valuation_date"], "observed": snap_meta["observed"], "nav": snap["nav_gbp"], "return_pct": snap["return_pct"], "cash": snap["cash_gbp"],
                         "cash_pct_nav": round(100 * snap["cash_gbp"] / snap["nav_gbp"], 2),
                         "identity_pnl": round(snap["nav_gbp"] - 100000, 2),
                         "yahoo_nav": R1["A"]["nav_yahoo_asof"], "yahoo_minus_platform": round(R1["A"]["nav_yahoo_asof"] - snap["nav_gbp"], 2)}
        R["var_yahoo"] = p2.var_flags(pnl)
        R["var_platform"] = p2.var_flags(snap["nav_gbp"] - 100000)
        R["z"] = {"yahoo_vs_3.91": round(R1["C"]["realised_pct"] / 3.91, 3),
                  "platform_vs_3.91": round(snap["return_pct"] / 3.91, 3),
                  "platform_vs_held_4.19": round(snap["return_pct"] / R1["C"]["held9_model"]["two_week_sd_pct"], 3)}
        b = R1["B"]["buckets"]
        loss = -pnl
        pct = lambda v: round(100 * -v / loss, 1)
        sens = [v for v in R1["B"]["sensitivity"].values() if "error" not in v]
        R["attr"] = {"market_sector_pct": pct(b["market"] + b["sector"]), "crypto_pct": pct(b["crypto_BTC"] + b["ETH_closed_realised"]),
                     "fx_pct": pct(b["fx"] + b["fx_local_cross"]), "fx_scope": "fx_pct: the four US equities only",
                     "fx_all_dollar_holdings_pct": pct(R1["B"]["fx_scope"]["all_dollar_holdings_gbp"]),
                     "report_day_pct": pct(b["event_scheduled_AR"] + b["event_unscheduled_AR"]),
                     "other_specific_pct": pct(b["residual_AR"] + b["alpha"]), "execution_pct": pct(b["execution_fill_to_close"]),
                     "syre_pct": pct(b["satellite_SYRE"]),
                     "systematic_pct": pct(R1["B"]["grouped"]["market_sector_fx_crypto"]),
                     "systematic_range_pct": [round(100 * -v["mkt_sec_fx_crypto"] / loss, 3) for v in (max(sens, key=lambda v: v["mkt_sec_fx_crypto"]), min(sens, key=lambda v: v["mkt_sec_fx_crypto"]))],
                     "n_variants": len(sens), "nvda_total_gbp": R1["B"]["per_asset"]["NVDA"]["total"]}
        R["nvda_20nov"] = p2.nvda_day()
        peers = {k: v for k, v in R["nvda_20nov"]["moves_20nov_pct"].items() if k in ("AMD", "AVGO", "TSM", "MU", "LRCX", "KLAC", "ASML")}
        R["nvda_20nov"]["peer_range_pct"] = [min(peers.values()), max(peers.values())]
        R["breach"] = p2.breach_diagnosis()
        R["deploy"] = p2.deploy_audit()
        R["sharpe"] = p2.own_sharpe(ASOF)
        R["counterfactual"] = counterfactual.run(ASOF)
        ok, t = scorecard.rules_hash_ok()
        R["scorecard"] = {"rules_hash_ok": ok, "locked_utc": t, "assets": scorecard.score()}
        R["calls"] = R1["C"]["calls_scored"] | {"binom_one_sided": R1["C"]["binomial"]["P(<=1 of 6|0.5)"], "binom_two_sided": R1["C"]["binomial"]["two_sided_1of6"]}
        import numpy as np, power
        port = power.portfolio_daily_gbp(R1["C"]["held_weights_9Nov"])
        roll = (1 + port).rolling(10).apply(np.prod, raw=True).dropna() - 1
        R["placebo_10d"] = {"n_windows": int(len(roll)), "k_at_or_below": int((roll * 100 <= R1["C"]["realised_pct"]).sum()),
                            "worst_pct": round(100 * float(roll.min()), 2), "weights": "held 9 Nov", "history": "2 years to 6 Nov"}
    if "E" in parts or "K" in parts:
        import numpy as np
        import strategic as E
        import decide
        v = R1["A"]["value_by_asset_asof"]; nav = R1["A"]["nav_yahoo_asof"]
        m = {"NVDA": "NVDA", "AMAT": "AMAT", "WMT": "WMT", "HD": "HD", "BA.L": "BAE", "RR.L": "RR", "BTC-USD": "BTC", "SYRE": "SYRE"}
        hw = {m[k]: x / nav for k, x in v.items() if k in m}
        cash = 1 - sum(hw.values())
        A8 = list(E.TICK); A7 = [a for a in A8 if a != "SYRE"]
        runs, covs = {}, {}
        for end in ("2026-11-06", "2026-11-20"):
            for weeks, assets in ((156, A8), (260, A7)):
                h2, c2 = dict(hw), cash
                if "SYRE" not in assets:
                    c2 += h2.pop("SYRE")
                res, cov = E.run(h2, c2, R["platform"]["nav"], end, weeks, assets)
                runs[f"{end}|{weeks}w"] = res; covs[f"{end}|{weeks}w"] = cov
        prim = runs["2026-11-20|156w"]
        w_star = dict(zip(prim["assets"], prim["_w"]["sleeve"]))
        held_vols = [r["held"]["ann_vol_pct"] for r in runs.values()]
        R["E"] = {"assumptions": E.ASSUMPTIONS, "held_weights_pct_yahoo_20nov": {a: round(100 * x, 2) for a, x in hw.items()},
                  "cash_pct": round(100 * cash, 2), "runs": runs, "held_vol_range_pct": [min(held_vols), max(held_vols)],
                  "headline_held_vol_pct": max(held_vols), "w_star_pct": {a: round(100 * x, 2) for a, x in w_star.items()},
                  "w_star_rule": "sleeve risk parity, 156 weeks, data to 20 Nov, capped 15% (fixed in PLAN2 before numbers)",
                  "horizon_table_HYPOTHETICAL": E.horizon_table(),
                  "syre_history_start": "2023-11-28 ticker change; 156w window starts 2023-11-17/12-01 (post Jun 2023 merger)"}
        sc = scorecard.score()
        st = {m[k]: x["status"] for k, x in sc.items() if k in m}
        # The deployment rule is in sterling: a name counts as triggered only if its sterling move crossed the trigger
        # (hit_gbp). A local-currency crossing is kept as a diagnostic. The frozen 20 Nov table used either currency,
        # which marked Bitcoin as triggered (-5.01% in dollars, -4.58% in sterling against -4.6%); see
        # out/book_frozen_20261120.correction.json. Bitcoin has no thesis, so its action is the same either way.
        h20 = [h for h in R["deploy"]["hits"] if h["date"] == "2026-11-20" and h["asset"] in m]
        hits = {m[h["asset"]] for h in h20 if h["hit_gbp"]}
        hits_local = {m[h["asset"]] for h in h20 if h["hit_local"]}
        rows, target, cash_after = decide.actions(st, hw, w_star, {a: (a in hits) for a in hw})
        for a in rows:
            rows[a]["trigger_hit_local_20nov_diagnostic"] = a in hits_local
        w_after = np.array([target[a] for a in prim["assets"]])
        after = E.describe(w_after, covs["2026-11-20|156w"], prim["assets"], R["platform"]["nav"])
        tx = ledger.load_tx()
        add13 = tx[(tx.date == "2026-11-13") & (tx.asset == "NVDA")].iloc[0]
        fx20 = R["counterfactual"]["fx"]
        nvda20 = ledger.platform_snapshot(ASOF)[0]["quoted_prices"]["NVDA"]   # platform mark, 20 Nov close
        R["K"] = {"decision_table": rows, "cash_after_pct": round(100 * cash_after, 2), "book_after": after,
                  "book_before_ai_crypto_risk_pct": prim["held"]["ai_crypto_risk_share_pct"],
                  "nvda_trim_gbp_approx": round((hw["NVDA"] - target["NVDA"]) * R["platform"]["nav"]),
                  "nvda_13nov_add": {"units": add13.units, "cost_gbp": -add13.gbp_cash,
                                     "value_20nov_gbp": round(add13.units * nvda20 / fx20, 2),
                                     "pnl_gbp": round(add13.units * nvda20 / fx20 + add13.gbp_cash, 2),
                                     "passes_gate_today": False, "why": "R4 (CEO exit 12 Nov, no permanent successor) live from 12 Nov -> REVIEW: no adds"},
                  "cash_rule_audit": {"cpi_10nov": {"actual_mom": 0.4, "consensus_mom": 0.3, "core_actual": 0.3, "core_consensus": 0.2,
                                                    "source": "https://investinglive.com/news/us-october-core-cpi-vs-0-2-expected/ ; https://stockanalysis.com/news/us-cpi-rises-october-2026/ (secondary)",
                                                    "qqq_10nov_pct": -0.68, "clause_triggered": False, "why": "hot CPI but Nasdaq proxy QQQ -0.68% > -2%"},
                                      "wmt_13nov_add_trigger": False, "wmt_moves_9_13nov_pct": [0.11, -0.09, 0.10, 0.41, 1.51],
                                      "nvda_13nov_add_after_trigger": "NVDA hit -5.0% trigger on 10 Nov (-5.47%); add made 13 Nov",
                                      "untraded_hits": "sterling: BTC 14 Nov; NVDA, AMAT 20 Nov (BTC 20 Nov crossed in dollars only: -5.01% local, -4.58% sterling, trigger -4.6%)"},
                  "note": "Recommendations only. The team decides and trades; the model places no orders."}
    if "H" in parts:
        import drawdown as H
        mp = {"NVDA": "NVDA", "WMT": "WMT", "AMAT": "AMAT", "HD": "HD", "BAE": "BA.L", "RR": "RR.L", "BTC": "BTC-USD"}
        w13 = {mp[k]: v for k, v in R1["C"]["held_weights_13Nov"].items() if k in mp}
        thr, n = H.realised_10d(w13)
        rb = H.book_returns(w13)
        out = {"book_weights_13nov": w13, "book_realised_6_20nov_pct": round(100 * thr, 2), "sessions": n,
               "book_primary": H.analyse(rb, thr), "book_actual_8.5": H.analyse(rb, -0.0853)}
        # sensitivity: equities only from 2004
        weq = {k: v for k, v in w13.items() if k != "BTC-USD"}
        out["book_equities_2004"] = H.analyse(H.book_returns(weq, start="2004-01-01"), H.realised_10d(weq)[0])
        out["single"] = {}
        for t in ("NVDA", "AMAT", "BTC-USD", "SMH", "QQQ", "SPY"):
            # Bitcoin trades every day: sample it on US sessions on both sides, so the competition fall (10 sessions,
            # 6-20 Nov) is compared with ten-session windows, not ten-calendar-day ones
            r = H.local_returns(t, us_calendar=(t == "BTC-USD"))
            mv, n_sess = H.realised_10d(ticker=t, us_calendar=(t == "BTC-USD"))
            assert n_sess == 10, (t, n_sess)
            roll_sd = float(((1 + r).rolling(10).apply(lambda x: x.prod(), raw=True) - 1).std())
            if mv > -1.5 * roll_sd:
                out["single"][t] = {"realised_10d_pct": round(100 * mv, 2), "own_10d_sd_pct": round(100 * roll_sd, 2), "result": "no event"}
                continue
            a = H.analyse(r, mv)
            a["realised_10d_pct"] = round(100 * mv, 2); a["own_10d_sd_pct"] = round(100 * roll_sd, 2)
            a["selected"] = t in ("NVDA", "AMAT", "BTC-USD")
            out["single"][t] = a
        R["H"] = out
    if "G" in parts:
        import horizon as G
        import drawdown as H
        mp = {"NVDA": "NVDA", "WMT": "WMT", "AMAT": "AMAT", "HD": "HD", "BAE": "BA.L", "RR": "RR.L", "BTC": "BTC-USD"}
        w13 = {mp[k]: v for k, v in R1["C"]["held_weights_13Nov"].items() if k in mp}
        panels = {t: G.quarterly_panel(t) for t in G.US}
        R["G"] = {"G1": G.g1(), "G2": G.g2(panels={t: v[0] for t, v in panels.items()}),
                  "G2_floor_sensitivity_TTM_gt_0_LABELLED_SENSITIVITY": G.g2(n_draws=2000, panels={t: v[0] for t, v in panels.items()}, floor=1e-9),
                  "G2_rows_dropped": {t: v[1] for t, v in panels.items()},
                  "G2_split_check_T19": G.split_check(), "G3": G.g3(book=H.book_returns(w13, start="2010-01-01")),
                  "G4": "CUT (PLAN2 section 7 cut list)", "G2_UK": "CUT (PLAN2 section 7: UK names in G2 dropped); not sourced",
                  "caveat": G.CAVEAT}
    OUT.joinpath("results2.json").write_text(dumps(R))
    print("wrote results2.json", list(R))
    return R


if __name__ == "__main__":
    main(tuple(sys.argv[1:]) or ("core",))
