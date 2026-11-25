"""D2 snapshot: yfinance eps_trend / eps_revisions / earnings history / earnings dates.
Saves raw output to data/raw/estimates_<UTC timestamp>/ . Run tonight and again after the 20 Nov close.
Raw data is untrusted: saved as CSV, never executed.
"""
import datetime as dt
import json
import pathlib
import sys
import warnings

warnings.filterwarnings("ignore")
import yfinance as yf

ROOT = pathlib.Path(__file__).resolve().parents[1]
TICKERS = ["NVDA", "WMT", "AMAT", "HD", "BA.L", "RR.L"]
METHODS = ["get_eps_trend", "get_eps_revisions", "get_earnings_history",
           "get_earnings_estimate", "get_revenue_estimate", "get_growth_estimates"]


def main():
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = ROOT / "data" / "raw" / f"estimates_{ts}"
    out.mkdir(parents=True, exist_ok=True)
    manifest = {"downloaded_utc": ts, "yfinance": yf.__version__, "files": {}}
    for t in TICKERS:
        tk = yf.Ticker(t)
        for m in METHODS + ["get_earnings_dates"]:
            key = f"{t}_{m}"
            try:
                df = tk.get_earnings_dates(limit=60) if m == "get_earnings_dates" else getattr(tk, m)()
                if df is None or len(df) == 0:
                    manifest["files"][key] = "EMPTY"
                    continue
                f = out / f"{t.replace('.', '_')}_{m}.csv"
                df.to_csv(f)
                manifest["files"][key] = f.name
            except Exception as e:  # noqa
                manifest["files"][key] = f"ERROR: {type(e).__name__}: {e}"[:300]
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(out)
    print(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    sys.exit(main())
