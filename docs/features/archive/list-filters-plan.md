# List-Filters — Implementation Plan

> **For executing agents:** This plan translates an already-approved spec into sequenced tasks. Do NOT re-design — the spec at `docs/features/list-filters-spec.md` is the source of truth for *what* and *why*. This plan owns *how* and *in what order*. Each task maps to one commit per spec §10.2. Tasks are gated by VERIFIER → REVIEWER → QA → HUMAN per the pipeline-mode precedent.

---

## §1 — Plan Status & Cross-References

| Field | Value |
|---|---|
| Plan Status | DRAFT (pending HUMAN approval) |
| Drafted | 2026-05-21 |
| Author | ARCH (plan-and-create Phase 1, on top of HUMAN-approved spec) |
| Spec source | `docs/features/list-filters-spec.md` (DRAFT @ commit `15922d7`) |
| Spec status transition | DRAFT → IN_PROGRESS when T1 starts; → SHIPPED on T3 commit (then archived) |
| Related precedents | `docs/features/archive/pipeline-mode-spec.md` (six-task multi-commit rollout with VERIFIER/REVIEWER/QA/HUMAN gates between commits; archive-on-ship banner pattern) |
| Cycle | plan-and-create → execute |
| Owner agent rotation | ARCH (this file) → HUMAN-approve plan → BACKEND (T1, T2, T3) with VERIFIER + REVIEWER + QA + HUMAN gates between each |
| Iteration cap per gate | 2–3 round-trips, then escalate to HUMAN (per §6 below) |

**Section-level mapping back to spec** (so the executing agent can verify nothing in this plan contradicts an approved decision):

| Plan section | Spec section it implements |
|---|---|
| §3 task T1 (helpers) | Spec §5.3 (label algorithm) + §5.4 (inventory walker) + §11 rows 1–2, 4 + §7.5 acceptance |
| §3 task T2 (CLI wiring) | Spec §5.1 (CLI surface + mutex) + §5.5 (output emission) + §11 rows 3, 5–7 + §7.1–§7.4 acceptance |
| §3 task T3 (doc sweep + archive) | Spec §10.2 commit 3 + §12 (INTEGRATION.md) + §13 (all spec updates) + §11 rows 8–13 + §7.6 acceptance |

---

## §2 — Summary

Three sequential tasks ship the `--list-filters --json` feature in the order recommended by spec §10.2: (T1) pure-Python helpers (`attr_to_label` + `list_valid_filters_with_labels`) with their unit tests, fully independent of CLI wiring; (T2) Click option wiring + mutex extension + `_emit_filter_inventory` helper + CLI/integration tests; (T3) the doc sweep across INTEGRATION.md (NEW), CONTRACTS.md, MODULE_REFERENCE, THESIS, FEEDBACK-LOG, README, TESTING, plus the spec archive-with-banner. Each task commits independently and passes through the full VERIFIER → REVIEWER → QA → HUMAN gate before the next starts. T1 has one genuine subagent-parallelism opportunity (label-format unit tests vs. helper implementation when subagent-driven-development is used); T3 has six independent doc edits suitable for parallel dispatch. T2 is essentially sequential. No new HTTP, no JSON output for screen results, no per-language cookbook code — all per spec §3 and §9.

---

## §3 — Task Breakdown

### T1 — Helpers: `attr_to_label` + `list_valid_filters_with_labels`

**Complexity:** LOW

**Spec sections covered:** §5.3, §5.4; §7.5 (label-derivation acceptance); §11 rows 1–2 and row 4 (test file `tests/unit/resource/params/test_label_format.py`).

**Files touched (exhaustive, per spec §11):**
- Create: `fincli/resource/params/_label_format.py`
- Modify: `fincli/resource/params/validators.py` — add `list_valid_filters_with_labels()` plus refactor internals to share a private `_iter_param_entries()` walker with the existing `list_valid_filters()` (per spec §5.4 implementation note). Existing public signature and behavior of `list_valid_filters()` stays unchanged.
- Create: `tests/unit/resource/params/test_label_format.py` (~10 cases, parametrize per spec §8 row 1)
- Modify: `tests/unit/resource/params/test_validators.py` — extend with cases that cover `list_valid_filters_with_labels()` (label keys present, value-map shape, Fundamental-then-Descriptive-then-Technical insertion order). This is not new test file creation; it adds a `class TestListValidFiltersWithLabels` (or function-group) to the existing file because it's a sibling helper to `list_valid_filters()`.

**Acceptance criteria (cite spec §7):**
- §7.5 — all six `attr_to_label` parametrized cases pass.
- §7.4 — `list_valid_filters_with_labels()` returns the §5.2 shape: every entry has `{"label": str, "values": {str: str}}`, the empty-string value-code is preserved, and insertion order is Fundamental → Descriptive → Technical. (Note: §7.4 is also exercised end-to-end by T2's integration test; T1's coverage at the helper layer is the strict unit-test version of the same invariants.)
- §7.1 — `pytest tests/unit/` (and the full suite) stays green; the refactor of `list_valid_filters()` to use `_iter_param_entries()` is behavior-preserving.

**BACKEND scope (priority order):**
1. Create `fincli/resource/params/_label_format.py` with the verbatim docstring, constants, and function body from spec §5.3 (lines 130–202). Do not edit the docstring or the acronym/connector sets — they were spec-approved.
2. Add the parametrized unit-test file `tests/unit/resource/params/test_label_format.py` covering every §7.5 bullet, plus the three extra Examples shown in the spec §5.3 docstring (`PE`, `EPS_GROWTH_NEXT_5_YEARS`, `Twenty_Day_Simple_Moving_Average`). Use `@pytest.mark.parametrize("attr, expected", [...])` for compactness.
3. Refactor `fincli/resource/params/validators.py`: extract a private `_iter_param_entries() -> Iterator[tuple[str, str, dict[str, str]]]` (yielding `(attr_name, query_key, values_dict)`) from the existing `list_valid_filters()` loop, then have both `list_valid_filters()` AND the new `list_valid_filters_with_labels()` consume it. Confirm `list_valid_filters()` output is byte-identical before and after the refactor (existing tests in `test_validators.py` will catch a regression).
4. Add `list_valid_filters_with_labels()` next to `list_valid_filters()`, returning `dict[str, dict[str, object]]` per spec §5.4 signature. Per-entry shape: `{"label": attr_to_label(attr_name), "values": dict(values_dict)}`.
5. Extend `tests/unit/resource/params/test_validators.py` with unit cases for `list_valid_filters_with_labels()` covering the §7.4 invariants at the helper layer.

**Dependencies:** none (this is the foundation task).

**Parallelization opportunity:** YES. See §5 for the two parallel work units inside T1.

**Per-task commit message** (per spec §10.2):
```
feat(params): add attr_to_label + list_valid_filters_with_labels helpers (list-filters-spec)

Pure-Python helpers for the upcoming --list-filters --json CLI flag.
attr_to_label mechanically derives display labels from param attribute
names with acronym preservation and connector lowercasing.
list_valid_filters_with_labels walks the same _PARAM_CLASSES as
list_valid_filters via a new shared _iter_param_entries() generator,
returning the {label, values} shape from spec §5.2. No CLI wiring yet —
that lands in the next commit.

Refs docs/features/list-filters-spec.md §5.3, §5.4, §7.5.
```

---

### T2 — CLI wiring: `--list-filters --json` + mutex + emission

**Complexity:** MEDIUM (Click option plumbing + mutex extension + new tests + integration test against the live module). Bumped from LOW because of the cross-cutting mutex change and the orthogonal-flag-no-op verification matrix.

**Spec sections covered:** §5.1, §5.5; §6 (option table); §7.1 (back-compat), §7.2 (CLI surface), §7.3 (JSON schema), §7.4 (content sampling end-to-end); §11 rows 3, 5–7.

**Files touched (exhaustive, per spec §11):**
- Modify: `fincli/app/cli.py` — add two `@click.option` decorators (`--list-filters`, `--json`), extend the `input_modes_set` counter to include `list_filters`, update `_MUTEX_MSG` to include `--list-filters`, add module constant `_LIST_FILTERS_SCHEMA_VERSION = 1`, add private helper `_emit_filter_inventory()`, branch in `run_main` before `_normalize_filter_input` to short-circuit when `list_filters` is set (after the mutex check; before any banner emission and before `run_stock_screener` import).
- Create: `tests/unit/app/test_cli_list_filters.py` (~8 cases per spec §8 row 2)
- Create: `tests/integration/test_list_filters_output.py` (~5 cases per spec §8 row 3)
- Modify: `tests/unit/app/test_cli_pipeline.py` — extend the mutex test set with `--list-filters` pairings (one per existing input-mode flag), per spec §11 row 7. Existing assertions stay; new cases are added inline with the existing `test_*_mutually_exclusive` cluster.

**Acceptance criteria (cite spec §7):**
- §7.1 (all sub-bullets) — pre-existing 200+ tests still green; interactive picker still launches with no flags; `--history` / `--scrape-link` / `--filter` / `--filters-json` / `--filters-file` unchanged.
- §7.2 (all 8 sub-bullets) — every CLI-surface bullet verified by `test_cli_list_filters.py` and the integration test.
- §7.3 (all 8 sub-bullets) — every JSON-schema bullet verified by `test_list_filters_output.py` (parse stdout as JSON, assert keys/types/insertion-order).
- §7.4 (all 7 sub-bullets) — content sampling (`fa_pe`, `sec`, `ta_rsi` examples) verified end-to-end by the integration test.

**BACKEND scope (priority order):**
1. **Mutex first** (the highest-blast-radius change). Update `_MUTEX_MSG` text to include `--list-filters` per spec §6 "Extended mutex set" block. Extend the `input_modes_set` counter in `run_main` with `bool(list_filters)`. This is one focused edit; verify with the existing `test_filter_and_*_mutually_exclusive` cases in `test_cli_pipeline.py` (they should all still pass — the message text changed but mutex semantics are identical).
2. Add the new `--list-filters` and `--json` options to `run_main` per spec §6. Use the exact option signatures from spec §11 row 3 (`@click.option("--list-filters", is_flag=True)` and `@click.option("--json", "json_format", is_flag=True)`). Add corresponding parameter names to `run_main`'s signature with safe defaults.
3. Add the short-circuit branch in `run_main`: AFTER the mutex check and BEFORE `_normalize_filter_input` (mutex still fires when `--list-filters` is combined with input modes — fail-fast). When `list_filters` is set without `json_format`, raise `click.UsageError("--list-filters requires --json (the only currently supported format).")` — exact wording at BACKEND's discretion within the spec §7.2 bullet ("UsageError message naming `--json` as required"). When both are set, call `_emit_filter_inventory()` and `ctx.exit(0)` (or equivalent). Crucially: this branch fires BEFORE the welcome-banner `click.echo` so stdout stays JSON-only per spec §7.2 bullet 7.
4. Add module constant `_LIST_FILTERS_SCHEMA_VERSION = 1` near `_MUTEX_MSG` so tests can `from fincli.app.cli import _LIST_FILTERS_SCHEMA_VERSION` (mirrors the `JSON_SUMMARY_SCHEMA_VERSION` pattern from `fincli/app/main.py`).
5. Add the `_emit_filter_inventory()` private helper per spec §5.5 (UPDATED post-deep-think). The emitter builds a 3-key payload — `schema_version`, `keys`, `filters` — where `keys = list(inventory.keys())` is the canonical-ordering contract for Go consumers (Go's `encoding/json` decode into `map[string]T` randomizes iteration; consumers iterate `keys` and index into `filters[key]`). Uses local imports of `json` and `list_valid_filters_with_labels`.
6. Extend `tests/unit/app/test_cli_pipeline.py` with five new cases pairing `--list-filters` against each of `--filter`, `--filters-json`, `--filters-file`, `--history`, `--scrape-link` (per spec §7.2 bullets 3–5 plus the two implied by "all input-mode flags"). Use the same `CliRunner` + `_MUTEX_MSG_FRAGMENT` pattern already in the file.
7. Add `tests/unit/app/test_cli_list_filters.py` (~8 cases): `--json`-without-`--list-filters` is silently ignored (spec OQ2 ARCH default); `--list-filters` alone exits 2; `--list-filters --json` exits 0 and stdout is non-empty JSON; mutex with each of the 5 input-mode flags (cross-link with the cases just added to `test_cli_pipeline.py` — duplicate one as a sanity check, leave the rest in `test_cli_pipeline.py`); `--list-filters --json --quiet --debug --json-summary` exits 0 with JSON-only stdout (spec §7.2 bullet 7); `--list-filters --json --output ./foo.csv` exits 0 with no file created (spec §7.2 bullet 6); `--help` output contains `--list-filters` and `--json` substrings (spec §7.2 bullet 8).
8. Add `tests/integration/test_list_filters_output.py` (~6 cases — bumped from 5 to include the keys-list invariant): subprocess `python -m fincli --list-filters --json`, parse stdout as JSON, verify the §7.3 schema (top-level keys `["schema_version", "keys", "filters"]`, `schema_version == 1`, `keys` non-empty list, `set(keys) == set(filters.keys())`, `len(keys) == len(filters)`, `filters` non-empty dict, every entry has `{label, values}`, `keys` order = Fundamental-keys-first-then-Descriptive-then-Technical) and §7.4 content (`fa_pe.label == "PE"`, `fa_pe.values["u20"] == "Under 20"`, `sec.label == "Sector"`, `sec.values["basicmaterials"] == "Basic Materials"`, `ta_rsi.label == "RSI 14"`, plus the cross-class presence check from §7.4 bullet 7).

9. **NEW (per gpt-5.5 deep-think): integrated OQ-B/C/D interaction test.** Add ONE matrix-style test in `tests/unit/app/test_cli_list_filters.py` covering the short-circuit + mutex + orthogonal-flag interaction as a single unit. The test runs `python -m fincli --list-filters --json --quiet --debug --json-summary --output -` and asserts: exit 0, stdout = single JSON line starting with `{"schema_version":` and ending with `}\n`, no welcome banner anywhere, no progress logs, no `OUTPUT_PATH=` discovery line, no JSON summary. This pins the interaction (short-circuit fires BEFORE mutex check fails on `--output`'s orthogonality, BEFORE banner emission, BEFORE `run_stock_screener` import) rather than testing each rule in isolation.

10. **NEW (per gpt-5.5 deep-think): mutex cascade centralization.** Audit existing tests that pattern-match the canonical `_MUTEX_MSG` text (search `tests/` for `mutually exclusive` substring). For each match: if it asserts on a SUBSTRING (`assert "mutually exclusive" in result.output`), leave unchanged — the substring still matches the extended message. If it asserts on the FULL message text, switch to substring matching OR import `_MUTEX_MSG` directly from `fincli.app.cli`. Add a brief comment at the `_MUTEX_MSG` definition in `cli.py`: `# Canonical mutex message — change this and tests/unit/app/test_cli_pipeline.py::_MUTEX_MSG_FRAGMENT may need updating in parallel.`

**Dependencies:** T1 must be merged. Specifically T2 requires `fincli.resource.params.validators.list_valid_filters_with_labels` to exist and return the spec §5.2 shape — without that, `_emit_filter_inventory()` cannot serialize anything. The integration test in T2 also indirectly exercises `_iter_param_entries()` via the same call path.

**Parallelization opportunity:** Limited. The CLI wiring edits are interleaved in one file (`fincli/app/cli.py`) and the new test files import the wired CLI, so they cannot be written before the wiring lands. The mutex-extension test cases inside `test_cli_pipeline.py` can be written in parallel with the CLI wiring if both subagents follow the spec §6 mutex-message text exactly. See §5.

**Per-task commit message** (per spec §10.2):
```
feat(cli): add --list-filters --json flag for non-Python consumers (list-filters-spec)

Adds the metadata-dump CLI entry mode: `fincli --list-filters --json`
emits the filter inventory (schema_version=1, filters={key: {label,
values}}) on a single line of stdout and exits 0. Mutex with all five
input-mode flags so the screener pipeline never runs in this mode.
--list-filters without --json exits 2 with a UsageError; --output /
--quiet / --debug / --json-summary are orthogonal no-ops in this mode.
Welcome banner suppressed so stdout is JSON-only.

CLI option wiring + _emit_filter_inventory helper + extended _MUTEX_MSG.
New unit tests in tests/unit/app/test_cli_list_filters.py; new
integration test in tests/integration/test_list_filters_output.py;
mutex set in tests/unit/app/test_cli_pipeline.py extended with
--list-filters pairings.

Refs docs/features/list-filters-spec.md §5.1, §5.5, §6, §7.1–§7.4.
```

---

### T3 — Doc sweep + spec archive

**Complexity:** LOW per file, MEDIUM in aggregate (six files + one new INTEGRATION.md + spec-status flip + archive move).

**Spec sections covered:** §10.2 commit 3; §11 rows 8–13; §12 (INTEGRATION.md scaffold); §13 (all spec updates); §7.6 (integration-doc acceptance).

**Files touched (exhaustive, per spec §11):**
- Create: `INTEGRATION.md` (repo root) — full structure per spec §12, including the seven sections: Audience & scope, Bootstrap, Per-screen call flow, Exit-code routing (table), OUTPUT_PATH= discovery, Concurrency notes, Caching guidance, Per-language cookbook (placeholder per spec §9 / §12), Reference.
- Modify: `CONTRACTS.md` — three sub-edits per spec §13.1:
  - §1 — add `--list-filters` and `--json` rows to the options table per spec §6.
  - §1 — extend the canonical mutex-message text to include `--list-filters` (verbatim text from spec §6 / §13.1).
  - §1 — add a new behavior-table row per spec §13.1 text.
  - **NEW §5.6** — filter inventory JSON schema sub-section mirroring §5.5 style (document the §5.2 top-level shape, field contract, `schema_version: 1` policy, source-of-truth = `fincli.resource.params.validators.list_valid_filters_with_labels`).
  - §7 — add the stability-policy bullet from spec §13.1.
- Modify: `docs/MODULE_REFERENCE.md` — add new entry for `fincli.resource.params._label_format` (private, `attr_to_label`); extend the existing `validators.py` entry with `list_valid_filters_with_labels` (and mention the internal `_iter_param_entries` helper). Per spec §13.2.
- Modify: `docs/THESIS.md` — add Change Log entry per spec §13.3, dated the merge date.
- Modify: `docs/FEEDBACK-LOG.md` — append a new dated entry per spec §10.3 template. Date = merge date.
- Modify: `README.md` — add a one-line pointer to INTEGRATION.md in the "Pipeline mode" section per spec §13.5.
- Modify: `TESTING.md` — add a one-paragraph note in the "Pipeline mode" subsection per spec §13.6 (lists the three new test files and confirms layout).
- Modify: `docs/features/list-filters-spec.md` — flip status DRAFT → SHIPPED; add the shipped banner at the top (mirrors `pipeline-mode-spec.md` banner format); fill in date-shipped.
- Move: `docs/features/list-filters-spec.md` → `docs/features/archive/list-filters-spec.md` (git mv preserves history).

**Acceptance criteria (cite spec §7):**
- §7.6 (all four bullets):
  - `INTEGRATION.md` exists at repo root with all sections from spec §12.
  - Per-language cookbook section exists with the deferred-placeholder note from spec §9.
  - README's "Pipeline mode" section gains the one-line pointer.
  - Exit-code routing table matches the 0/1/2/3/4 semantics from `fincli/app/exit_codes.py`.
- Spec banner: the SHIPPED banner on `docs/features/archive/list-filters-spec.md` matches the `pipeline-mode-spec.md` banner format (one-paragraph summary + final-commit-SHA reference).
- `git mv` (not delete-and-recreate): commit log shows rename, not add+remove.
- No other tests change behavior (this is a docs-only commit); `pytest` stays green.

**BACKEND scope (priority order):**
1. **CONTRACTS.md first** — the deepest reference target. Add the two new option rows in §1, extend the mutex message, add the new behavior row, write the new §5.6 sub-section (use §5.5 as the structural template), add the §7 stability bullet.
2. Create `INTEGRATION.md` at repo root using spec §12 verbatim as the skeleton. Spec §12 lines 447–501 are intentionally already in publication form — BACKEND fills in the prose where the spec shows section headers only (Audience & scope content, Reference cross-links). Do not invent code examples in the per-language cookbook section; the placeholder text in spec §12 is the final content for that section in this spec.
3. Update `README.md` to add the one-line INTEGRATION.md pointer in the "Pipeline mode" section. Confirm the pointer reads as `For non-Python integrators (Go, Node, etc.), see [INTEGRATION.md](INTEGRATION.md).` per spec §11 row 12.
4. Update `docs/MODULE_REFERENCE.md` with the new module entry (`_label_format`) and the extended `validators.py` entry.
5. Update `docs/THESIS.md` Change Log with the dated entry.
6. Update `docs/FEEDBACK-LOG.md` with the dated entry from spec §10.3 template (lines 386–420). Fill in the actual date.
7. Update `TESTING.md` with the one-paragraph note about the three new test files.
8. Flip the spec's status banner, fill in date shipped + final commit SHA placeholder (use git rev-parse HEAD or leave as `<commit>` for the merge to fill in — but follow whichever convention `pipeline-mode-spec.md` used at archive time; per the existing archive banner, the SHA is the post-merge HEAD that closed the umbrella).
9. `git mv docs/features/list-filters-spec.md docs/features/archive/list-filters-spec.md` to preserve git rename history.

**Dependencies:** T2 must be merged. Specifically T3's CONTRACTS.md §1 options table needs the actual shipped option behavior (mutex message text, exit-code routing) to match T2; T3's INTEGRATION.md exit-code routing table cites `fincli/app/exit_codes.py` which T2 doesn't modify but does depend on; T3's spec-archive flip implies "the code is shipped" so it must come last.

**Parallelization opportunity:** YES — and this is the biggest opportunity in the entire plan. Each of the six modified doc files plus the new INTEGRATION.md and the spec-archive move are independent edits with no cross-file dependencies. See §5.

**Per-task commit message** (per spec §10.2):
```
docs(integration,contracts): add INTEGRATION.md + CONTRACTS §5.6 for filter inventory dump (list-filters-spec)

Closes the polyglot-discoverability gap by documenting the
--list-filters --json output and the broader subprocess integration
pattern for non-Python consumers. New INTEGRATION.md at repo root
covers bootstrap (filter inventory dump), per-screen call flow
(--filters-json + --output - + --json-summary), exit-code routing
(0/1/2/3/4), OUTPUT_PATH= recovery pattern, concurrency notes, and
caching guidance. Per-language cookbook section is a placeholder per
spec §9.

CONTRACTS.md: adds --list-filters and --json options to §1 (table +
mutex message + behavior row); new §5.6 documents the inventory JSON
schema (schema_version=1 policy mirrors §5.5); §7 stability list gains
the inventory-schema bullet. MODULE_REFERENCE, THESIS Change Log,
FEEDBACK-LOG, README, TESTING updated accordingly. Spec moved to
archive with SHIPPED banner.

Refs docs/features/list-filters-spec.md §10.2, §11, §12, §13.
```

---

## §4 — Validation Gates per Task

### T1 gates

**VERIFIER focus areas:**
- `_label_format.py` exists, exports `attr_to_label`, matches spec §5.3 docstring + constants + function body. (Spec is verbatim — diff against §5.3 catches drift.)
- `tests/unit/resource/params/test_label_format.py` exists with parametrized cases covering every §7.5 acceptance bullet AND every Example in the spec §5.3 docstring (`PE`, `EPS_GROWTH_NEXT_5_YEARS`, `Twenty_Day_Simple_Moving_Average`).
- `list_valid_filters_with_labels` is present in `validators.py` with the expected signature.
- The `_iter_param_entries` extraction is real (both `list_valid_filters` AND `list_valid_filters_with_labels` consume it — no copy-paste).
- Behavioral probe: run `pytest tests/unit/resource/params/ -v`; expect all new + existing cases pass.
- Behavioral probe: run `pytest tests/unit/ tests/integration/ tests/e2e/` (full suite); expect 200+ existing cases unaffected.
- Gate replay: `python -c "from fincli.resource.params.validators import list_valid_filters_with_labels; import json; d = list_valid_filters_with_labels(); print(list(d.keys())[:3]); print(d['fa_pe'])"` — sanity-check the inventory shape live (no JSON serialization yet — that's T2).

**REVIEWER focus areas:**
- Is the `_iter_param_entries` extraction clean (single yield site, both consumers identical in their walk pattern)?
- Does the new function's return type annotation (`dict[str, dict[str, object]]`) match the spec §5.4 signature? mypy strict should be silent on the new helpers (T1 raises typing coverage in this slice — see CLAUDE.md "Phase status").
- Are the test cases parametrized (DRY) rather than copy-pasted?
- Is the new module `_label_format.py` truly private (underscore-prefixed file name, no entry in `__init__.py`)?
- Does the new code follow the existing Google-style docstring convention?

**QA focus areas:**
- Spec §7.5 conformance: every label-derivation example produces the documented output.
- Spec §7.4 helper-layer subset: `list_valid_filters_with_labels()["fa_pe"]["label"] == "PE"`, `["values"][""] == "Any"`, `["values"]["u20"] == "Under 20"` — even though §7.4 is end-to-end via CLI in T2, the same invariants are unit-testable at the helper layer here.
- Downstream consumer impact: T1 does not change `validate_filter_pairs` or `list_valid_filters` signatures, so the only "downstream" surface affected is the (not-yet-existing) consumer in T2.
- Refactor regression: the `_iter_param_entries` extraction is behavior-preserving — `list_valid_filters()` returns the same dict before and after. Existing `test_validators.py` cases plus a fresh diff of the function's output against a baseline should both pass.

**HUMAN gate question:** "Do the new helper APIs match the spec, and is the param-class-introspection refactor safe enough to base T2's CLI wiring on?"

---

### T2 gates

**VERIFIER focus areas:**
- `--list-filters` and `--json` options visible in `python -m fincli --help`.
- `python -m fincli --list-filters --json` exits 0; stdout is valid JSON with the §5.2 top-level shape; stderr is empty (or only contains debug output if `--debug` is set elsewhere).
- `python -m fincli --list-filters` (no `--json`) exits 2 with a UsageError mentioning `--json`.
- Each of the 5 mutex pairings (`--list-filters --json --filter ...`, ... `--scrape-link=...`) exits 2 with the extended mutex message.
- `python -m fincli --list-filters --json --output ./should-not-exist.csv` exits 0; no `./should-not-exist.csv` file appears on disk (run from a tmp_path to be safe).
- `python -m fincli --list-filters --json --quiet --debug --json-summary` exits 0; stdout starts with `{` and ends with `}\n` (single JSON line + trailing newline from `click.echo`).
- **NEW (per gpt-5.5 deep-think):** the integrated OQ-B/C/D interaction test (BACKEND scope step 9) passes — short-circuit fires correctly across the full orthogonal-flag matrix.
- **NEW (per gpt-5.5 deep-think):** parsed JSON has top-level keys `["schema_version", "keys", "filters"]` exactly; `set(keys) == set(filters.keys())`; `len(keys) == len(filters)`; `keys` order matches param-class declaration sequence.
- `_LIST_FILTERS_SCHEMA_VERSION` is importable from `fincli.app.cli`.
- Gate replay (one-liner): `python -m fincli --list-filters --json | python -m json.tool | head -20` — should pretty-print the first ~20 lines of the JSON inventory without errors.
- Full test suite: `pytest tests/ -v` — all green; the new test files contribute ~13 new cases (~8 unit + ~5 integration) and the extended mutex set in `test_cli_pipeline.py` adds 5 more.

**REVIEWER focus areas:**
- Is the `_emit_filter_inventory()` short-circuit placed correctly (after mutex check, BEFORE banner emission, BEFORE `run_stock_screener` import)?
- Is `click.echo` used (not `print`)? Does `ensure_ascii=False` appear in the `json.dumps` call?
- Does the new mutex message text exactly match spec §6 (six flags listed, no rewording)?
- Is the `--json` flag truly silently-ignored-when-not-set per spec OQ2 (no error when bare `--json` is passed)?
- Is the CLI option signature (`@click.option("--list-filters", is_flag=True)` and `@click.option("--json", "json_format", is_flag=True)`) consistent with the existing options in `cli.py`?
- Does `_emit_filter_inventory` use a local import for `json` and `list_valid_filters_with_labels` (consistent with the existing local import of `run_stock_screener`)?
- Are integration-test failures clearly attributed to spec sections in their assertion messages?

**QA focus areas:**
- Spec §7.1 conformance: all four back-compat bullets verified manually (interactive picker, `--history`, `--scrape-link`, `--filter`).
- Spec §7.2 conformance: all 8 CLI-surface bullets verified (manual + tests).
- Spec §7.3 conformance: all 8 JSON-schema bullets verified via the integration test.
- Spec §7.4 conformance: all 7 content-sampling bullets verified.
- Downstream consumer impact: simulate a non-Python consumer with a shell one-liner — `python -m fincli --list-filters --json > /tmp/inv.json && wc -c /tmp/inv.json` — confirm the payload is ~20 KB per spec §5.2 size estimate.
- QA-only spec drift check: does the produced stdout under `--list-filters --json` round-trip through `json.loads → json.dumps → json.loads` with no exceptions and an unchanged dict?

**HUMAN gate question:** "Is the CLI surface stable, do all §7.1–§7.4 acceptance bullets pass, and is the JSON payload shape the one we want a Go consumer to lock against?"

---

### T3 gates

**VERIFIER focus areas:**
- `INTEGRATION.md` exists at repo root, contains all sections from spec §12 (Audience & scope, Bootstrap, Per-screen call flow, Exit-code routing, OUTPUT_PATH= discovery, Concurrency notes, Caching guidance, Per-language cookbook with deferred placeholder, Reference).
- `CONTRACTS.md` §1 has both new option rows; mutex message text matches spec §6 verbatim; new §5.6 sub-section exists with the §5.2 shape documented; §7 stability list has the new bullet.
- `docs/MODULE_REFERENCE.md` has the new `_label_format` entry and the extended `validators.py` entry.
- `docs/THESIS.md` Change Log has the new dated entry.
- `docs/FEEDBACK-LOG.md` has the new dated entry from spec §10.3.
- `README.md` "Pipeline mode" section has the one-line INTEGRATION.md pointer.
- `TESTING.md` "Pipeline mode" subsection has the one-paragraph test-files note.
- `docs/features/list-filters-spec.md` no longer exists at the original path; `docs/features/archive/list-filters-spec.md` exists with SHIPPED banner.
- `git log --diff-filter=R --name-status` shows the spec file as renamed (R) not deleted+added.
- Full test suite still green (no code touched in T3, so this is a sanity check only).

**REVIEWER focus areas:**
- Did INTEGRATION.md cite CONTRACTS sections accurately (§1, §3.1, §5.5, §5.6, plus the exit_codes.py reference)?
- Is the exit-code routing table's "Recommended consumer behavior" column consistent with `fincli/app/exit_codes.py` constants (`SUCCESS=0`, `INTERNAL=1`, `USAGE=2`, `UPSTREAM=3`, `DATA=4`)?
- Does the new CONTRACTS §5.6 follow the §5.5 structural template (top-level shape block, field contract table, source-of-truth pointer, stability policy reference)?
- Is the spec-archive banner format consistent with `pipeline-mode-spec.md`'s banner (one-paragraph summary + Status flip + Date shipped + final-commit reference)?
- Did the doc sweep miss any cross-references that point at `docs/features/list-filters-spec.md` (now archived)? Grep for the old path before merging.

**QA focus areas:**
- Spec §7.6 conformance: all four integration-doc bullets verified.
- Cross-doc consistency: does CONTRACTS §1 mutex message match the live `_MUTEX_MSG` constant in T2's `cli.py`? Does INTEGRATION.md's exit-code table match `exit_codes.py` constants?
- Downstream consumer impact: a fresh reader who has never seen the spec can — armed with only `INTEGRATION.md` + `CONTRACTS.md` — call `fincli --list-filters --json` and `fincli --filters-json '{...}' --output - --json-summary` end-to-end. This is a thought experiment, not an automated check, but if the docs fail it the docs are wrong.

**HUMAN gate question:** "Is the documentation surface complete and consistent, and is the spec safely archived so the feature is officially shipped?"

---

## §5 — Subagent-Driven-Development Opportunities

This section identifies GENUINELY INDEPENDENT work units. If BACKEND uses `superpowers:subagent-driven-development`, these are the safe parallel splits. If BACKEND uses single-session execution, ignore this section — sequential execution is fine.

### T1 — TDD-style parallel (tests first while implementation is in progress)

**Honest framing** (per gpt-5.5 deep-think follow-up): `_label_format.attr_to_label()` is imported by `validators.list_valid_filters_with_labels()` — they are NOT fully independent at runtime. What IS genuinely parallelizable is **test authoring vs. implementation authoring**: both work from the same approved spec text, and the test file's import will fail loudly until the implementation lands.

Recommended sequencing inside T1 (3 sub-steps, only step 1+2 parallel):

- **Parallel (steps 1+2 simultaneously):**
  - **Step 1:** Write `tests/unit/resource/params/test_label_format.py` (parametrized cases from §7.5 + §5.3 docstring examples). The test file imports `from fincli.resource.params._label_format import attr_to_label`.
  - **Step 2:** Implement `fincli/resource/params/_label_format.py` per spec §5.3 (verbatim docstring, constants, function body).
- **Sequential after both finish:**
  - **Step 3:** Refactor `validators.py` (extract `_iter_param_entries()`), add `list_valid_filters_with_labels()`, extend `test_validators.py`. This block stays sequential — single file, interleaved edits.

After all three steps, run `pytest tests/unit/resource/params/ -v`; expect all-green.

**Subagent dispatch shape:** if BACKEND uses `superpowers:subagent-driven-development`, dispatch ONE subagent for the parallel step 1+2 pair (two file creates, no dependency) and a SECOND subagent for step 3 (single-file refactor + addition). Do not over-split.

### T2 — Limited parallelism

Almost everything in T2 happens inside `fincli/app/cli.py`, and the new test files import the wired CLI. The one safe split is:

- **Unit A:** Wire the CLI in `cli.py` (options + mutex extension + `_emit_filter_inventory` + short-circuit branch + `_LIST_FILTERS_SCHEMA_VERSION`).
- **Unit B:** Extend `tests/unit/app/test_cli_pipeline.py` with the 5 new `--list-filters` mutex pairings. The mutex message text and the option name are spec-pinned (§6), so this test author can write the cases without waiting for Unit A — the only thing they need is the spec.

The two new test files (`test_cli_list_filters.py` and `test_list_filters_output.py`) cannot meaningfully be written before Unit A finishes — they import the wired CLI and the integration test subprocesses `python -m fincli`. Keep these sequential after Unit A.

### T3 — Six independent doc edits

Each of the following is a self-contained edit to a different file with no cross-dependencies:

- **Unit 1:** `CONTRACTS.md` — §1 options table + mutex message + behavior row + new §5.6 + §7 stability bullet.
- **Unit 2:** `INTEGRATION.md` (new file at repo root) per spec §12.
- **Unit 3:** `docs/MODULE_REFERENCE.md` — `_label_format` entry + extended `validators.py` entry.
- **Unit 4:** `docs/THESIS.md` — Change Log entry.
- **Unit 5:** `docs/FEEDBACK-LOG.md` — dated entry per spec §10.3.
- **Unit 6:** `README.md` (one-line INTEGRATION.md pointer) + `TESTING.md` (one-paragraph test-files note). These two are tiny — bundle into one unit.

After all six units land, do the spec status-flip + `git mv` to archive **sequentially as the final step** (this is a one-line edit + a one-command rename; not worth parallelizing).

Why parallelization is safe: each unit edits a different file; the only cross-references are documentation-text citations (e.g., INTEGRATION.md refers to "CONTRACTS §5.6") which work as long as both sides land before the commit. Concurrent edits to the same file would be unsafe, but no two units in this list overlap on a file.

**Honesty note:** if BACKEND is a single-session execution, T3 will land in 30 minutes of sequential edits with no real risk; parallelism is a nice-to-have here, not a correctness requirement.

---

## §6 — Iteration Limit & Escalation

Per the plan-and-create skill: **each gate (VERIFIER, REVIEWER, QA, HUMAN) gets a maximum of 2–3 round trips with BACKEND before escalating to HUMAN.**

Practical meaning:
- VERIFIER finds an issue → BACKEND fixes → VERIFIER re-checks. If a second re-check still fails, BACKEND has one more attempt. If a third attempt fails, ARCH/HUMAN reviews the spec for ambiguity — the issue may be a spec gap, not an implementation gap.
- REVIEWER blocks merge → BACKEND addresses → REVIEWER re-checks. Same cap.
- QA finds a spec-conformance gap → BACKEND fixes → QA re-validates. Same cap.
- HUMAN gate is binary (approve or block); if blocked, HUMAN provides direction and the cycle returns to whichever agent owns the fix.

If any gate cycle exceeds three round trips, BACKEND must STOP and request HUMAN intervention before continuing. The spec may need amendment, in which case the cycle returns to ARCH (re-spec) → HUMAN-approve → resume execution.

This cap exists because more than three round trips usually means the underlying disagreement is about *what* (a spec question), not *how* (an implementation question), and execution-loop iteration cannot resolve a spec disagreement.

---

## §7 — Spec Updates (during implementation)

The approved spec stays at `docs/features/list-filters-spec.md` during T1 and T2. Status field flips DRAFT → IN_PROGRESS the moment BACKEND opens T1 (small status-only edit BACKEND can make in its first commit, or ARCH can pre-emptively flip when HUMAN approves this plan — see §9 OQ-A).

In T3's final action (after the doc sweep lands), the spec's status flips DRAFT/IN_PROGRESS → SHIPPED with a banner identical in shape to the `pipeline-mode-spec.md` banner. Then `git mv docs/features/list-filters-spec.md docs/features/archive/list-filters-spec.md` to preserve git history. After T3 merges, the spec lives only at `docs/features/archive/list-filters-spec.md`.

No content changes to the spec during implementation. If implementation reveals a spec ambiguity that requires re-design, escalate per §6 — re-spec is a different mode (back to ARCH for an amended spec + HUMAN re-approval), not an inline edit.

---

## §8 — Open Questions / Risks (implementation-level)

These are NEW questions raised by the act of planning. Spec §14 already captured five design-level open questions with HUMAN-approved ARCH defaults; the questions below are different — they cover the implementation-level mechanics that the spec leaves to BACKEND's discretion.

| # | Question | ARCH suggestion | Blocking? |
|---|---|---|---|
| OQ-A | When does the spec status flip from DRAFT → IN_PROGRESS? At the moment HUMAN approves this plan, or in BACKEND's first T1 commit? | **In BACKEND's first T1 commit.** Keeps the status-flip atomic with implementation start; avoids ARCH editing the spec while BACKEND hasn't begun. | No — process question only. |
| OQ-B | Short-circuit in `run_main` for `--list-filters --json` — should it be a brand-new branch BEFORE `_normalize_filter_input` is called, or a branch inside `_normalize_filter_input`? | **Before.** The screener pipeline never runs in this mode (spec §5.1: "No interaction with `run_stock_screener` — the screener pipeline never runs in this mode"). `_normalize_filter_input` is about collapsing input forms for the screener; it has no role in the metadata-dump path. Cleaner separation if the new branch lives directly in `run_main`. | No — design clarification only. |
| OQ-C | If the mutex check is hit while `--list-filters` is set alongside an input mode, does it raise BEFORE or AFTER `_normalize_filter_input`? | **Before.** Fail-fast. The existing `run_main` already does `if input_modes_set > 1: raise click.UsageError(_MUTEX_MSG)` BEFORE calling `_normalize_filter_input`, so this is naturally preserved by adding `bool(list_filters)` to the counter. No reordering needed. | No — confirmed by reading existing code. |
| OQ-D | Should the banner-suppression check (current line 194: `if not quiet and output_path != STDOUT_SENTINEL: click.echo("Welcome...")`) also gate on `list_filters`? | **Yes.** When `list_filters` is set, the short-circuit branch runs BEFORE this line is ever reached, so adding `list_filters` to the gate condition is redundant — but defensive. ARCH suggests the short-circuit branch returning from `run_main` early (via `ctx.exit(0)`) is enough; no need to touch the banner check. BACKEND verifies by integration test §7.2 bullet 7. | No — should be confirmed by behavior of the short-circuit, not by adding redundant guards. |
| OQ-E | The new `--json` flag is silently ignored when `--list-filters` is not set (spec OQ2 ARCH default, HUMAN-approved). Should there be a test that explicitly asserts this silent-ignore behavior, or is the absence of a test enough? | **Add an explicit test in `test_cli_list_filters.py`.** "Silently ignored" is a contract decision, not an accident; future contributors might "fix" it by rejecting bare `--json` and break the contract. A test pins the decision. | No — testability nice-to-have. |
| OQ-F | The integration test in `tests/integration/test_list_filters_output.py` should subprocess `python -m fincli`. Should it use the editable-install entry point (`fincli --list-filters --json`) or the `python -m fincli` form? | **`python -m fincli`.** Matches the pattern already used in `tests/integration/test_pipeline_*.py` (which also subprocess `python -m fincli`). Avoids depending on the installed entry-point shim being present on PATH in CI. | No — convention follow-on. |

None of these are blocking. All have ARCH suggestions. If HUMAN disagrees with any, the resolution lands in this plan via an Edit before T1 starts; if HUMAN agrees, this plan is the final answer.

---

## §9 — Sign-off

This plan is **DRAFT** pending HUMAN approval. The user is being asked: "Is this task breakdown, gate structure, and parallelization split the right way to execute the spec at `docs/features/list-filters-spec.md`?"

After HUMAN approval:
1. ARCH (or BACKEND in T1) flips spec status DRAFT → IN_PROGRESS.
2. BACKEND begins T1 (with or without subagent-driven-development per §5).
3. Each task closes with VERIFIER → REVIEWER → QA → HUMAN gate per §4 before the next task starts.
4. After T3 merges, the spec moves to `docs/features/archive/` with a SHIPPED banner.

HANDOFF_TO: HUMAN
