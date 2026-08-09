# Change request — expose `scrape_link` on the HTTP API (`POST /screens`)

**Date:** 2026-07-25 · **From:** orchestrator (consumer) · **Status:** OPEN
**Cross-refs:** orchestrator issues
[#17 (ledger populate)](https://github.com/yonatan-levin/strade-orchestrator/issues/17) ·
[#19 (ranked_theses scrape_link)](https://github.com/yonatan-levin/strade-orchestrator/issues/19)

## Ask

Accept a direct Finviz screener URL on the HTTP surface, mirroring the CLI:

```json
POST /screens
{"scrape_link": "https://finviz.com/screener.ashx?v=111&f=...&o=-pe"}
```

mutually exclusive with `filters`, same semantics as `fincli --scrape-link URL`
(fetch the URL verbatim; no filter-inventory validation; `filter_history.json`
not overwritten).

## Why (consumer evidence, 2026-07-18 DCF-bug session)

- The orchestrator's screen flow uses `POST /screens` with `filters`, validated
  against `GET /filters`. Two Finviz filters in the owner's frozen screen have
  **no key in the inventory**: `fa_sales3years_pos` and `ta_perf2_3yup`.
- Dropping them is not an approximation: the 9-filter screen matches **101**
  tickers; the 7-filter subset matches **227** (2.2× overcount).
- The CLI already supports this exactly (`fincli --scrape-link URL`, documented
  in README/CONTRACTS §"--scrape-link"; replicated the 101-row ground truth on
  2026-07-18) — the capability gap is HTTP-only.
- Consequence today: the orchestrator's scheduled ORCH-6 ledger-populate loop
  shells out to `fincli` instead of using the adapter's HTTP mode, and
  `ranked_theses` cannot serve the frozen screen at all until this lands
  (orchestrator #19 depends on it for HTTP mode).

## Notes

- Filter-inventory growth (adding the 2 missing keys) would be a complementary
  fix but does not replace this: a raw-URL passthrough stays correct as Finviz
  adds filter vocabulary.
- Written by an orchestrator session per owner instruction; left uncommitted
  for the algo_beta harness to pick up (delegation model).
