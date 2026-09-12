"""Exchange-rule expiry dates, one function per family.

These are the public last-trading-day rules of CME/COMEX/NYMEX/CBOT/ICE. Yahoo's
front-month splice switches contract on or one business day after these dates
(verified on printed data in the s0 report). Metals are the exception: Yahoo shows
the nearest-expiring contract of *any* month, illiquid ones included.
"""

import pandas as pd

BD = pd.offsets.BDay


def nth_weekday(year, month, weekday, n):
    d = pd.Timestamp(year=year, month=month, day=1)
    off = (weekday - d.weekday()) % 7
    return d + pd.Timedelta(days=off + 7 * (n - 1))


def last_bday(year, month):
    d = pd.Timestamp(year=year, month=month, day=1) + pd.offsets.MonthEnd(0)
    while d.weekday() >= 5:
        d -= pd.Timedelta(days=1)
    return d


def prev_month(year, month):
    return (year - 1, 12) if month == 1 else (year, month - 1)


def expiry(name, year, month):
    """Last trading day of the contract for delivery month `month`."""
    if name in ("ES", "NQ", "YM"):
        return nth_weekday(year, month, 4, 3)                 # third Friday
    if name == "NKD":
        return nth_weekday(year, month, 4, 2)                 # second Friday
    if name in ("ZN", "ZB"):
        return last_bday(year, month) - BD(7)
    if name in ("ZF", "ZT"):
        return last_bday(year, month)
    if name in ("6E", "6J", "6B", "6A", "6C", "6S"):
        return nth_weekday(year, month, 2, 3) - BD(2)         # 2 bdays before 3rd Wednesday
    if name == "CL":
        py, pm = prev_month(year, month)
        d25 = pd.Timestamp(year=py, month=pm, day=25)
        d25 = d25 if d25.weekday() < 5 else d25 - BD(1)
        return d25 - BD(3)
    if name == "NG":
        return pd.Timestamp(year=year, month=month, day=1) - BD(3)
    if name in ("HO", "RB", "SB"):
        py, pm = prev_month(year, month)
        return last_bday(py, pm)
    if name in ("GC", "SI", "HG", "PL"):
        return last_bday(year, month) - BD(2)                 # third-last business day
    if name in ("ZC", "ZS", "ZW"):
        return pd.Timestamp(year=year, month=month, day=15) - BD(1)
    if name == "KC":
        return last_bday(year, month) - BD(8)
    if name == "CT":
        return last_bday(year, month) - BD(16)                # 17 bdays from month end
    raise KeyError(name)


def contract_months(name, months):
    """Metals on Yahoo run through every month; everyone else through the listed ones."""
    if name in ("GC", "SI", "HG", "PL"):
        return list(range(1, 13))
    return months


def expiries(name, months, start, end):
    out = []
    for y in range(start.year, end.year + 2):
        for m in contract_months(name, months):
            e = expiry(name, y, m)
            if start <= e <= end:
                out.append(e)
    return pd.DatetimeIndex(sorted(set(out)))
