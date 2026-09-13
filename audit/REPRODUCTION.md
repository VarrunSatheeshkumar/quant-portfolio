# Reproduction: generated outputs and retained evidence

This record separates the saved network runs of 2026-09-13 from the later local guard tests. It reports what the tools did; it does not restore an untouched hold-out or validate the scientific interpretation of a result. The saved clone identified itself as local revision `1433ea5`; the report comparison uses portfolio baseline `f0bf041`. Original machine-specific paths in the copied logs are replaced with placeholders.

| Project | What the saved log establishes | Retained or unverified |
| --- | --- | --- |
| BTC | [The log](reproduction/btc-run.log) records fetching, grid construction, the as-of check, map calibration, document checks and `pipeline complete`. | It explicitly skips the five tracked result JSONs. The wrapper then records a timeout marker; no process exit code was captured, so an exit-0 or precise runtime claim is not made. |
| Futures | [The log](reproduction/futures-run.log) records s0–s8, the candidate chain, document checks and `reproduce.sh exit=0`. | s9 retained the historical hold-out. `RESULTS.md` is therefore a retained historical summary, not a fresh evaluation of the rebuilt programme. |

The [file comparison](reproduction/comparison.json) records SHA-256 hashes. The five BTC result JSONs are identical because the runner skipped them. All ten futures stage reports and the ten candidate Markdown reports other than `LOG.md` are identical between the saved clone and baseline. The execution log and progress record differ. Identical historical hold-out reports establish retention, not another scoring.

The BTC fetch log records different premium-index, DVOL and option-fill counts from the archive described in the ledger. In particular, the new option file has 524,945 fills; the archived diagnostic records 633,631. The instrument and economics stages were not rerun, so their tracked results still refer to the archived sample. Matching grid row counts alone does not establish identical grid values.

## Current command behaviour

- BTC `python run.py`: run missing data stages and checks; skip an existing stage artifact by default. Use `--only` or `--force-from` to force a stage only when its upstream data are available. A partial data cache permits only the document checks whose individual source files exist.
- Futures `./reproduce.sh`: rebuild stages whose required outputs are missing and invalidate downstream completion records; then run the candidate chain. An already scored s9 requires both nonempty historical reports and records retention. Missing reports stop the run without scoring. The splice check stops on missing or empty inputs instead of emitting a research verdict.

The final changes to these guards were tested locally with fixtures; the long network runs were not repeated after those changes. Recorded successful downloads describe one run on one day, not a guarantee about future endpoint availability.

Generated reports preserve historical labels such as `CLEARED`, `net alpha` and `AUDIT PASSED`. The [BTC write-up](../btc-public/WRITEUP.md) and [futures write-up](../futures-public/WRITEUP.md) state which interpretations remain permitted. In particular, the historical C18 cost proxy is not a net-alpha estimate with costs entered into the weekly series.
