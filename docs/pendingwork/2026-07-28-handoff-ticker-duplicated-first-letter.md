# Handoff — Fix duplicated-first-letter ticker parse (next session)

> Project: **algo_beta / fin_cli** · Issue: **#14** (yonatan-levin/fin_cli)
> Created 2026-07-28 · Priority: HIGH — the primary key of every screen row is
> wrong, and it fails silently (exit 0 with corrupted data).

## Context
Under the current (redesigned) Finviz screener layout, parsed ticker symbols come
back with the **first letter duplicated** — `KKTOS` for KTOS, `AACM` for ACM,
`BBABA` for BABA, `CCCJ` for CCJ — in BOTH the HTTP `POST /screens`
`stocks[].ticker` field and the CLI CSV `Symbol` column. Observed 2026-07-18 on a
227-row screen (every row) and again via `--scrape-link` (101 rows, every row).
The hyperlink cell still holds the correct ticker (`stock?t=KTOS&...`), which is
the current consumer workaround — the Strade orchestrator runs extract the true
ticker from the href, not the parsed field.

Likely cause: the redesigned row markup nests the ticker text (icon/logo `<span>`
+ the anchor text), so the cell-text extraction concatenates two nodes. This is
`error_class: parsing` / layout-drift territory — but it currently returns
**success (exit 0 / HTTP 200) with corrupted data** instead of failing loudly.

## Expected behavior
- Correct ticker symbols on the current layout.
- If the layout can't be parsed unambiguously, FAIL LOUDLY (exit 4 / `error_class:
  parsing` per the published contract) — never return corrupted tickers with exit 0.

## Key code (fin_cli)
- HTML row parsing / cell extraction: `fincli/stock_screening/parsers/stock_table.py`,
  `fincli/stock_screening/content/stock_table.py`, locators in
  `fincli/stock_screening/locators/stock_table_locators.py`.
- Contract/exit codes: `fincli/app/exit_codes.py`.

## Acceptance (from issue #14)
- [ ] Tickers parse correctly on the current Finviz layout (fixture captured from live HTML).
- [ ] Contract test: a mismatch between the anchor href (`stock?t=X`) and the cell
      text FAILS the parse rather than passing corrupted data.
- [ ] Regression test with the redesigned-layout fixture.

## Notes
- Delegated project: work in fin_cli's own repo/harness + worktree + gates.
- Capture a REAL current-layout HTML fixture (the bug is layout-specific; an old
  fixture won't reproduce it) — same fixture-vs-live lesson that bit the midas work.
- Once fixed, the Strade orchestrator can stop extracting the ticker from the href.

## Refs
- Issue #14 (full repro). Origin: 2026-07-18 screen run (session memory
  `validation-review-issues-2026-07-18`).
