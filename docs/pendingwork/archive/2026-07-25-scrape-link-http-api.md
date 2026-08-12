# Change request — expose `scrape_link` on the HTTP API (`POST /screens`)

**Date:** 2026-07-25 · **From:** orchestrator (consumer) · **Status:** SHIPPED (2026-08-11)
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

## Shipped (2026-08-11)

Branch `feat/scrape-link-http` (worktree `.claude/worktrees/feat+scrape-link-http`).

- `POST /screens` now accepts `{"scrape_link": "<url>"}`, mutually exclusive
  with `filters` (`fincli_api/models/screens.py` `ScreenRequest`; enforced by
  a `model_validator` — both-set or neither-set raises `ValueError`, surfaced
  by FastAPI as its standard 422 request-validation envelope, distinct from
  the `ErrorResponse` envelope used for pipeline failures).
- `scrape_link` is fetched verbatim with NO filter-inventory validation
  (`fincli.app.main.scrape_link_to_dataframe` → the shared `_screen_from_query`
  core, same as `screen_to_dataframe`) — mirrors the CLI's `--scrape-link`
  exactly.
- **Host-allowlist deviation from CLI parity (deliberate):** `scrape_link`
  must be an absolute `http`/`https` URL whose host is `finviz.com` or a
  subdomain of it (e.g. `elite.finviz.com`). The CLI's `--scrape-link` accepts
  any URL because it's a local, single-user process; the API binds `0.0.0.0`
  by default, so an unrestricted URL fetch on this field would be an SSRF
  hole. Documented in `INTEGRATION.md` and the `ScreenRequest.scrape_link`
  field description.
- `filter_history.json` writeback is **structurally impossible** on this
  path, not merely skipped by a flag: the only writeback call site is the
  CLI's interactive picker (`fincli.cli.cli_stock_screener.select_filters_and_values`),
  which the API adapter never touches. Verified by a regression test
  (`tests/integration/api/test_screens_integration.py::test_post_screens_scrape_link_does_not_write_filter_history`).
- Inventory growth (complementary, not a substitute for the passthrough):
  added `fa_sales3years` (`fincli/resource/params/fundamental_params.py`) and
  the missing 3/5/10-year value codes on the existing `ta_perf2` key
  (`fincli/resource/params/technical_params.py`), extracted live from
  Finviz's `screener.ashx?v=111&ft=4` filter dropdowns (2026-08-11) so the
  frozen 9-filter screen's `fa_sales3years_pos` / `ta_perf2_3yup` codes are
  now also expressible via structured `filters`.
- `docs/api/openapi.{yaml,json}` regenerated; `dump_openapi.py --check`
  confirms no drift.
