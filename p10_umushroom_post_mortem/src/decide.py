"""Component K: decision table from scorecard status, held weights, w* (sleeve risk parity, 156w, data to 20 Nov,
capped 15%) and 20 Nov deploy-trigger hits. Precedence fixed in PLAN2 3-K. Recommendations only: no orders."""
MAX_ADDS = 0.05
BAND = 0.25
SYRE_MAX = 0.025


def actions(status, current, w_star, trigger_hit, cap=0.15):
    """status/current/w_star/trigger_hit: dicts keyed by asset. Returns (rows, target weights, cash)."""
    rows, target, adds = {}, {}, 0.0
    order = sorted(current, key=lambda a: a)
    for a in order:
        st, c, w = status[a], current[a], w_star.get(a)
        if st == "CUT":
            t, act = 0.0, "EXIT"
        elif st == "REVIEW-TRIM":
            t, act = min(c, w), f"TRIM to {100*min(c, w):.1f}%; no adds"
        elif st == "REVIEW":
            t, act = c, "HOLD; no adds"
        elif st == "NO THESIS":
            if a == "SYRE":
                t = min(c, SYRE_MAX)
                act = (f"HOLD at {100*t:.1f}% (<= 2.5%), no documented case; EXIT unless the team documents a case"
                       if c <= SYRE_MAX else f"TRIM to 2.5% or EXIT")
            else:
                t, act = min(c, w), ("HOLD (at or below risk budget)" if c <= w else f"TRIM to {100*w:.1f}%")
        elif st == "HOLD":
            t, act = c, "HOLD"
            if trigger_hit.get(a) and c < w:
                add = min(w - c, cap - c, MAX_ADDS - adds)
                if add > 0:
                    t, adds, act = c + add, adds + add, f"ADD {100*add:.1f}% (trigger hit, below w*)"
            elif trigger_hit.get(a):
                act = "HOLD (trigger hit but at/above w*: no add)"
            if w and abs(t / w - 1) > BAND and t == c:
                act += f"; outside 25% band of w* {100*w:.1f}% -> rebalance at next quarterly date"
        else:
            raise ValueError(st)
        if t > cap + 1e-12:   # a holding that drifted above the cap without a trade (e.g. NVIDIA after a rebound)
            act += f"; above the {100*cap:.0f}% cap -> trim to {100*cap:.0f}% at the next scorecard review"
            t = cap
        target[a] = t
        rows[a] = {"status": st, "current_pct": round(100 * c, 2), "w_star_pct": (round(100 * w, 2) if w is not None else None),
                   "target_pct": round(100 * t, 2), "action": act, "trigger_hit_20nov": bool(trigger_hit.get(a))}
    assert adds <= MAX_ADDS + 1e-12
    cash = 1 - sum(target.values())
    assert abs(cash + sum(target.values()) - 1) < 1e-12 and cash >= -1e-12
    return rows, target, cash
