# Audit guide

Start with the project write-ups for the questions, measurements and decisions. This directory supplies supporting evidence and records the limits of that evidence.

| Record | What it provides |
| --- | --- |
| [Claim ledger](CLAIM_LEDGER.md) | Sources, assumptions and permitted wording for reviewed assertions. Withdrawn claims remain visible as audit history. Coverage was a spot check, not an exhaustive certification. |
| [Evidence record](EVIDENCE_RECORD.md) | The historical inspection and registration record, with later corrections identified. Private documents are described by filename and commit hash; the original private repositories are not included. |
| [Worked examples](WORKED_EXAMPLES.json) | Preserved inputs for the BTC touch and C18 week shown in the write-ups. Individual construction examples add no aggregate conclusion. |
| [Reproduction record](REPRODUCTION.md) | Saved logs, file comparisons and the distinction between rebuilt outputs and retained historical reports. |
| [Diagnostics](diagnostics/) | Scripts and saved outputs cited by ledger rows; these require cached data to rerun. The source data are not bundled here. |

Ledger class (a) denotes a stored or directly computed measurement, (b) an assumption-dependent calculation or interpretation, and (c) a documentary/operational statement or an explicitly stated author decision. A class label does not exempt a statement from source checking. In particular, sample counts are measurements; a decision to stop is a decision.

Diagnostic scripts d2–d4 expect `btc-public/` as the working directory; d1 and d5 expect `futures-public/`. Their existing `.out` files can be read without running anything. The records include previously reported measurements of inspected periods; publishing them does not make those periods untouched hold-outs. Private-source citations are provenance disclosures, not publicly reproducible proof.

P1–P6 are outside the research ledger's statistical audit. The portfolio's summaries of those projects should be read with their own methods and data limitations.
