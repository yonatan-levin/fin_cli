# Harness Quality Gates Burndown Implementation Plan

> **Status: EXECUTED — SHIPPED and archived 2026-08-11.** The work landed via
> commits `0d90ef8`, `7c59fb6`, `db93430` (merged `d46afda`, follow-up `05a1536`);
> end state verified 2026-08-11 (strict-mypy zero, 94.13% aggregate coverage,
> blocking hooks). Checkboxes below were not ticked during execution and are
> preserved as-is; the governing spec's banner
> (`docs/refactoring/archive/harness-quality-gates-burndown-spec.md`) is the
> closure record.

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox
> (`- [ ]`) syntax for tracking.

MODE: PLAN_AND_CREATE  
ROLE: ARCH

**Goal:** Close the shipped-runtime coverage and strict-mypy debt, promote the local hooks
to tested blocking gates, and reconcile document roles/lifecycle without changing public
behavior.

**Architecture:** `pyproject.toml` is the single source for shipped-surface mypy and
coverage policy. Product behavior tests raise aggregate line coverage; type corrections
make bare `mypy` green; only then do `post-edit.js` and `on-stop.js` switch to exit-2
blocking behavior. Live docs are reconciled after the commands are stable, and completed
historical artifacts move to archive with a repo-wide inbound-link sweep.

**Tech Stack:** Python 3.12+, pytest, pytest-cov/coverage.py, mypy strict, Ruff, Node.js
Claude Code hooks, Markdown.

**Governing spec:**
`docs/refactoring/archive/harness-quality-gates-burndown-spec.md`

## Global Constraints

- Work only in
  `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\algo_beta-harness-burndown`
  on `refactor/harness-spec-burndown`.
- Do not commit, push, open a PR, merge, or remove the worktree without explicit HUMAN
  instruction.
- Preserve CLI/API/CSV/OpenAPI behavior and `CONTRACTS.md`.
- Leave malformed-HTML MAJOR #4 out of scope; preserve its strict xfail/current-pin pair.
- Coverage is one aggregate line-coverage gate at `>=90%` over `fincli`, `fincli_api`,
  `core`, `config`, `logger`, and `singleton.py`.
- Strict mypy must reach zero over the same shipped surface without weakening or hiding
  errors.
- Do not add global ignores, excluded shipped paths, disabled mypy codes, coverage omits,
  `pragma: no cover`, per-module threshold easing, or coverage-padding tests.
- Do not enable optional Ruff `D` rules.
- `pytest.ini` remains canonical for pytest runner options.
- Required handoff order is `BACKEND -> VERIFIER -> REVIEWER -> QA -> HUMAN`.
- A failed validation stage returns to BACKEND and restarts at VERIFIER. Stop after at most
  three complete validation cycles and escalate to HUMAN.

---

## Baseline and File Map

### Baseline commands

Run from the worktree after installing its editable dev environment:

```powershell
pytest tests/
pytest tests/ --cov=fincli --cov=fincli_api --cov=core --cov=config --cov=logger --cov=singleton --cov-report=term-missing
mypy fincli fincli_api core config logger singleton.py
ruff check .
ruff format --check .
```

Expected initial evidence:

- pytest: `279 passed, 1 skipped, 3 deselected, 1 xfailed`;
- coverage: aggregate 88%, 979 covered / 122 missed;
- mypy: 49 errors in 13 files;
- Ruff: green.

### Planned file responsibilities

| Path | Responsibility in this stream |
|---|---|
| `pyproject.toml` | Canonical mypy scope, coverage source/threshold, real typing-stub dev dependencies |
| `.claude/hooks/on-stop.js` | Blocking repo-wide gate orchestration |
| `.claude/hooks/post-edit.js` | Blocking final per-file checks |
| `.claude/hooks/utils.js` | Shared process/response helpers and full shipped-module detection |
| `tests/integration/hooks/conftest.py` | Isolated copied-hook sandbox, session seed, OS-aware command shims |
| `tests/integration/hooks/test_quality_gate_hooks.py` | Hook positive/negative process contracts |
| `tests/unit/stock_screening/parsers/test_stock_table.py` | Parser behavior coverage |
| `tests/unit/utils/test_web_scraper.py` | HTTP-boundary behavior coverage |
| `tests/unit/test_singleton.py` | Singleton metaclass behavior coverage |
| 13 baseline-error Python files | Runtime-neutral strict typing corrections |
| `AGENTS.md`, `CLAUDE.md`, `TESTING.md`, `TOOLS_REFERENCE.md` | Current document roles and gate commands |
| `docs/THESIS.md`, `docs/CHANGELOG.md`, `docs/FEEDBACK-LOG.md` | Phase history, thin index, append-only correction |
| `agents/rules/*.md`, selected `agents/roles/*.md` | Current blocking-gate workflow |
| `docs/superpowers/**` | Terminal statuses, archive moves, inbound-link closure |

---

### Task 1: Establish RED hook-process tests

**Owner:** BACKEND

**Files:**

- Create: `tests/integration/hooks/conftest.py`
- Create: `tests/integration/hooks/test_quality_gate_hooks.py`
- Read: `.claude/hooks/utils.js`
- Read: `.claude/hooks/on-stop.js`
- Read: `.claude/hooks/post-edit.js`

**Interfaces:**

- Consumes: Claude hook stdin JSON; hook exit `0`/`2`; `.session-edits.json` shape from
  `utils.js`.
- Produces: an isolated subprocess harness that later hook tasks must satisfy.

- [ ] **Step 1: Build the isolated hook sandbox fixture**

In `tests/integration/hooks/conftest.py`, define fixtures/helpers with these observable
contracts:

- copy `.claude/hooks/{utils,on-stop,post-edit}.js` into
  `tmp_path/.claude/hooks/`;
- create minimal `fincli/`, `fincli_api/`, `core/`, `config/`, `logger/`, `tests/`, and
  root `singleton.py` paths only when a test needs them;
- set `CLAUDE_PROJECT_DIR` to the temporary project;
- seed copied `.session-edits.json` with:
  `editedFiles`, `affectedServices`, `hasTestableChanges`, `docsToUpdate`, and security
  fields matching `utils.loadSession`;
- invoke Node with JSON stdin and return `CompletedProcess`;
- create command shims in a temporary `bin` directory. On Windows create `.cmd` shims; on
  POSIX create executable scripts. Prepend, never replace, the inherited `PATH`.

- [ ] **Step 2: Write the future Stop-hook failure tests**

In `test_quality_gate_hooks.py`, add:

- `test_on_stop_blocks_when_aggregate_coverage_is_below_90`
  - Ruff/format/mypy shims exit `0`.
  - The pytest shim exits `1` when invoked with `--cov` and emits a `TOTAL ... 89%`
    diagnostic.
  - Assert hook exit `2` and stderr names aggregate coverage.
- `test_on_stop_blocks_when_strict_mypy_fails`
  - mypy shim exits `1` with a deliberate assignment-error diagnostic.
  - Other required checks exit `0`.
  - Assert exit `2` and stderr names strict mypy.
- `test_on_stop_all_required_gates_green_exits_zero`
  - all required shims exit `0`;
  - assert exit `0` and an accurate success message.
- `test_on_stop_loop_guard_exits_zero_without_running_commands`
  - invoke with `{"stop_hook_active": true}`;
  - command shims fail if called;
  - assert exit `0`.

- [ ] **Step 3: Write the future PostToolUse failure tests**

Add:

- `test_post_edit_blocks_on_deliberate_type_error`
  - create `fincli/deliberate_type_error.py` containing an annotated integer assigned a
    string;
  - invoke copied `post-edit.js` with that path;
  - assert exit `2`, stderr identifies mypy, and the file still exists unchanged.
- `test_post_edit_clean_python_file_exits_zero`
  - create a fully typed clean Python file;
  - assert exit `0`.
- `test_post_edit_markdown_skips_code_gates`
  - create a Markdown file;
  - shims fail if called;
  - assert exit `0`.

- [ ] **Step 4: Run the hook tests and verify RED**

```powershell
pytest tests/integration/hooks/test_quality_gate_hooks.py -q
```

Expected before hook edits: negative tests fail because coverage is stubbed, mypy is
advisory/swallowed, and accumulated Stop issues still use the success response.

- [ ] **Step 5: Preserve RED evidence**

Record failing test names and current exit-code mismatches in the BACKEND handoff notes.
Do not weaken assertions to fit current hooks.

**Checkpoint:** No hook implementation changes yet; the failure contract is executable.

---

### Task 2: Define aggregate coverage policy and close the behavior gap

**Owner:** BACKEND

**Files:**

- Modify: `pyproject.toml`
- Create: `tests/unit/stock_screening/parsers/test_stock_table.py`
- Create: `tests/unit/utils/test_web_scraper.py`
- Create: `tests/unit/test_singleton.py`
- Read: `fincli/stock_screening/parsers/stock_table.py`
- Read: `fincli/utils/web_scraper.py`
- Read: `singleton.py`

**Interfaces:**

- Consumes: shipped setuptools surface and existing public module behavior.
- Produces: config-driven `pytest tests/ --cov --cov-report=term-missing` gate at
  aggregate `>=90%`.

- [ ] **Step 1: Add the centralized coverage configuration**

In `pyproject.toml`:

- `[tool.coverage.run]` uses source entries `fincli`, `fincli_api`, `core`, `config`,
  `logger`, `singleton`;
- `[tool.coverage.report]` sets `fail_under = 90` and displays missing lines;
- do not add omit/exclude lists or branch-coverage policy.

- [ ] **Step 2: Run the config-driven aggregate command and verify RED**

```powershell
pytest tests/ --cov --cov-report=term-missing
```

Expected: tests pass, but the process exits non-zero because aggregate coverage is below
90%. Capture the term-missing table.

- [ ] **Step 3: Add parser behavior tests**

In `tests/unit/stock_screening/parsers/test_stock_table.py`, test:

- `repr()` identifies the parser and underlying content;
- a valid `tr[valign="top"]` row produces stripped cell text plus the absolute Finviz
  ticker link;
- no matching rows produces an empty list;
- a row missing the expected ticker anchor raises the same exception family used by the
  current DATA/parsing classifier path.

Assertions target returned rows/links/exceptions, not helper call counts.

- [ ] **Step 4: Run parser tests**

```powershell
pytest tests/unit/stock_screening/parsers/test_stock_table.py -q
```

Expected: PASS without changing parser behavior.

- [ ] **Step 5: Add scraper-boundary behavior tests**

In `tests/unit/utils/test_web_scraper.py`, test without network:

- `scrape(url)` returns response bytes and supplies a 10-second timeout plus one allowed
  user-agent;
- a `requests.exceptions.HTTPError` from the session is re-raised through the existing
  wrapped exception behavior;
- `fetch_page_sync(url)` returns scraper response bytes and emits the existing success log
  call, with time/randomness mocked only at their external boundaries.

- [ ] **Step 6: Run scraper tests**

```powershell
pytest tests/unit/utils/test_web_scraper.py -q
```

Expected: PASS; no live HTTP.

- [ ] **Step 7: Add Singleton behavior tests**

In `tests/unit/test_singleton.py`, define test-local classes and verify:

- repeated construction of one class returns the identical object;
- distinct classes receive distinct objects;
- constructor state from the first construction is retained on the repeated call.

Isolate cleanup to test-local class keys in `Singleton._instances`; do not clear logger's
live Singleton entry globally.

- [ ] **Step 8: Run Singleton tests**

```powershell
pytest tests/unit/test_singleton.py -q
```

Expected: PASS.

- [ ] **Step 9: Run aggregate coverage and verify GREEN**

```powershell
pytest tests/ --cov --cov-report=term-missing
```

Expected: all default tests pass and aggregate line coverage is at least 90%.

If the three specified behavior slices do not reach 90%, use the captured term-missing
table to add the smallest additional observable-behavior cases to the existing test file
that mirrors the uncovered module. REVIEWER must approve each additional case as behavior
coverage, not line execution.

**Checkpoint:** Coverage policy and product tests are green; hooks are still unchanged.

---

### Task 3: Expand strict-mypy scope and expose the final RED baseline

**Owner:** BACKEND

**Files:**

- Modify: `pyproject.toml`

**Interfaces:**

- Consumes: setuptools shipped surface.
- Produces: bare `mypy` as the canonical complete strict check.

- [ ] **Step 1: Expand configured mypy scope**

Set `[tool.mypy].files` to:

- `fincli`
- `fincli_api`
- `core`
- `config`
- `logger`
- `singleton.py`

Do not change `strict = true`, weaken diagnostics, or add exclusions.

- [ ] **Step 2: Replace typed-dependency hiding with real stubs**

Add dev-only dependencies for:

- pandas;
- colorama;
- requests.

Use the ecosystem stub distributions compatible with the installed runtime versions.
Remove `requests` from the missing-import override. Narrow the remaining cfscrape override
to only the actually imported untyped module(s), with a comment that it is an external
untyped boundary.

- [ ] **Step 3: Install the worktree dev environment**

```powershell
pip install -e ".[dev]"
```

Expected: editable install succeeds and the added stub distributions resolve.

- [ ] **Step 4: Run bare mypy and verify RED**

```powershell
mypy
```

Expected: non-zero. The known 49 errors are visible, and real stubs may reveal additional
specific errors. No shipped file is silently omitted.

- [ ] **Step 5: Record the post-stub error inventory**

Group errors by the two implementation slices in Tasks 4 and 5. If a new error appears in
another shipped file, add that exact path to the applicable slice; do not add an ignore.

**Checkpoint:** The configured command is complete and honestly red.

---

### Task 4: Burn down foundational, config, and logger typing

**Owner:** BACKEND

**Files:**

- Modify: `singleton.py`
- Modify: `core/configuration/config_base.py`
- Modify: `config/config.py`
- Modify: `logger/handlers.py`
- Modify: `logger/formatters.py`
- Modify: `logger/logger.py`
- Modify: `logger/log_cycle.py`
- Test: `tests/unit/test_singleton.py`
- Test: `tests/unit/configuration/test_configurator_filters.py`
- Test: `tests/unit/configuration/test_output_path.py`
- Test: `tests/unit/logger/test_stream_routing.py`

**Interfaces:**

- Consumes: current Singleton, Pydantic config, and logger runtime contracts.
- Produces: zero strict errors in this slice with no runtime behavior change.

- [ ] **Step 1: Type the Singleton boundary**

Add precise annotations for the metaclass instance registry and `__call__` arguments/return.
Use explicit boundary typing appropriate for a metaclass; do not suppress
`var-annotated`/`no-untyped-def`.

- [ ] **Step 2: Verify Singleton behavior**

```powershell
pytest tests/unit/test_singleton.py -q
mypy singleton.py
```

Expected: both commands PASS.

- [ ] **Step 3: Correct the generic configuration typing**

Resolve `ClassVar`/type-variable and `Any` return errors in
`core/configuration/config_base.py` without changing Pydantic field/default behavior.
Type `Config.filters` in `config/config.py` as the existing tuple-of-string-pairs shape.

- [ ] **Step 4: Verify configuration behavior**

```powershell
pytest tests/unit/configuration/test_configurator_filters.py tests/unit/configuration/test_output_path.py -q
mypy core config
```

Expected: tests pass and mypy reports zero errors for `core` and `config`.

- [ ] **Step 5: Type logger handlers and formatters**

Supply the concrete stream generic parameters, formatter return types, and JSON values
without changing output, quiet filtering, typing delay, file mode, or formatting.

- [ ] **Step 6: Correct the logger type-only import**

In `logger/logger.py`, replace the invalid type-checking-only relative import with the
actual project config import path. Add missing method/constructor return annotations.
Preserve the public logger method names, parameter order, streams, files, and Singleton.

- [ ] **Step 7: Type `LogCycleHandler`**

Add constructor and public method annotations while preserving path names, overwrite
behavior, log counters, and JSON payload behavior.

- [ ] **Step 8: Verify logger behavior**

```powershell
pytest tests/unit/logger/test_stream_routing.py -q
mypy logger
```

Expected: tests pass and logger mypy is clean.

- [ ] **Step 9: Run the full default regression suite**

```powershell
pytest tests/
```

Expected: PASS with MAJOR #4 still xfailed.

**Checkpoint:** Foundation/config/logger/singleton are strict-clean.

---

### Task 5: Burn down fincli parser, I/O, CLI, and orchestrator typing

**Owner:** BACKEND

**Files:**

- Modify: `fincli/stock_screening/parsers/stock_table.py`
- Modify: `fincli/stock_screening/content/stock_table.py`
- Modify: `fincli/utils/web_scraper.py`
- Modify: `fincli/utils/market_cap.py`
- Modify: `fincli/cli/cli_stock_screener.py`
- Modify: `fincli/app/main.py`
- Test: `tests/unit/stock_screening/parsers/test_stock_table.py`
- Test: `tests/unit/stock_screening/content/test_stock_table.py`
- Test: `tests/unit/utils/test_web_scraper.py`
- Test: `tests/unit/utils/test_market_cap.py`
- Test: `tests/unit/cli/test_cli_stock_screener.py`
- Test: existing `tests/integration/test_pipeline_*.py`
- Test: `tests/integration/api/test_screens_integration.py`

**Interfaces:**

- Consumes: CLI/CSV/API behavior fixed by `CONTRACTS.md`.
- Produces: zero strict errors across `fincli` while leaving `fincli_api` clean and behavior
  unchanged.

- [ ] **Step 1: Type the BeautifulSoup parser/content boundary**

Annotate parser constructor, properties, row/cell collection, ticker link, content wrapper,
and page-count interfaces using the installed BeautifulSoup stubs. Remove the now-unused
type-ignore only after the expression is genuinely typed.

- [ ] **Step 2: Run parser/content tests**

```powershell
pytest tests/unit/stock_screening/parsers/test_stock_table.py tests/unit/stock_screening/content/test_stock_table.py -q
mypy fincli/stock_screening
```

Expected: PASS and strict-clean.

- [ ] **Step 3: Type web scraper and market-cap boundaries**

Annotate URL inputs, byte outputs, sessions/scrapers, and timing values. Keep cfscrape's
untyped edge localized. Do not change request order, headers, timeout behavior, exception
families, logging, or numeric coercion.

- [ ] **Step 4: Run utility tests**

```powershell
pytest tests/unit/utils/test_web_scraper.py tests/unit/utils/test_market_cap.py -q
mypy fincli/utils
```

Expected: PASS and strict-clean.

- [ ] **Step 5: Type interactive CLI helpers**

Annotate section options, selected indices/pairs, prompts, history writes, and return
values. Preserve Fundamental -> Descriptive -> Technical order, local 1-based numbering,
blank-skip behavior, and reprompt behavior.

- [ ] **Step 6: Run CLI tests**

```powershell
pytest tests/unit/cli/test_cli_stock_screener.py tests/unit/app -q
mypy fincli/cli fincli/app
```

Expected: PASS. If `fincli/app/main.py` remains red, continue with Step 7 before evaluating
the slice.

- [ ] **Step 7: Type the orchestrator/DataFrame boundary**

Annotate fetch/page/row collections, DataFrame construction, output/summary helpers, and
tuple shapes. Use pandas stubs and preserve:

- DataFrame columns/order/dtypes;
- nullable `Float64` market cap behavior;
- `Ticker`/`Symbol` carve-out;
- stream routing and exit classification;
- API adapter's in-memory DataFrame path.

- [ ] **Step 8: Run pipeline and API integration regression tests**

```powershell
pytest tests/integration/test_pipeline_exit_codes.py tests/integration/test_pipeline_streaming.py tests/integration/test_pipeline_summary.py tests/integration/test_pipeline_ticker_carveout.py tests/integration/test_zero_row_success.py tests/integration/api/test_screens_integration.py -q -ra
```

Expected: all selected current-behavior tests pass and the no-table desired-behavior case
remains xfailed.

- [ ] **Step 9: Verify the complete strict scope is GREEN**

```powershell
mypy
```

Expected: `Success: no issues found` across the configured shipped surface, including
`fincli_api` and `singleton.py`.

- [ ] **Step 10: Re-run aggregate coverage**

```powershell
pytest tests/ --cov --cov-report=term-missing
```

Expected: default suite PASS and aggregate coverage `>=90%`.

**Checkpoint:** Phase 3 and 4 preconditions are green before hook enforcement.

---

### Task 6: Promote Stop and PostToolUse to blocking gates

**Owner:** BACKEND

**Files:**

- Modify: `.claude/hooks/utils.js`
- Modify: `.claude/hooks/post-edit.js`
- Modify: `.claude/hooks/on-stop.js`
- Test: `tests/integration/hooks/conftest.py`
- Test: `tests/integration/hooks/test_quality_gate_hooks.py`

**Interfaces:**

- Consumes: green `mypy` and config-driven pytest-cov commands.
- Produces: exit-2 blocking semantics for every required gate.

- [ ] **Step 1: Centralize safe command-result handling**

In `utils.js`, expose one shared command-result abstraction used by both hooks. It must
distinguish success, non-zero exit, missing executable, timeout, and infrastructure error;
include check name/command/bounded output; and avoid interpolating untrusted file paths
into an unsafe shell command where an argument-array API is available.

Extend service detection for:

- `fincli_api/`;
- root `singleton.py`.

Update dependency expansion so changes to shared `core`, `config`, `logger`, or Singleton
correctly identify both CLI/API dependents for reporting. Required gates remain repo-wide.

- [ ] **Step 2: Make PostToolUse verify after auto-fix**

For edited Python files:

1. retain the existing safe Ruff auto-fix and format actions;
2. run final non-mutating Ruff check;
3. run final Ruff format check;
4. run strict mypy on the file;
5. exit `2` through the blocking response when any final check fails.

Do not catch-and-discard required-check output. Keep secret/security diagnostics visible.
State in the diagnostic that the saved edit remains and must be repaired.

- [ ] **Step 3: Replace Stop's advisory/stubbed gate set**

The required Stop checks are exactly:

```text
ruff check .
ruff format --check .
mypy
pytest tests/ --cov --cov-report=term-missing
```

Remove the duplicate plain pytest run and the coverage stub. On any required failure,
aggregate diagnostics and call the blocking response (exit `2`). On success, exit `0`.
Preserve `stop_hook_active` loop prevention.

Dependency audit and doc/skill reminders may remain advisory, but skipped/advisory items
must not be described as passed required gates.

- [ ] **Step 4: Validate JavaScript syntax**

```powershell
node --check .claude/hooks/utils.js
node --check .claude/hooks/post-edit.js
node --check .claude/hooks/on-stop.js
```

Expected: all exit `0`.

- [ ] **Step 5: Run the hook test suite and verify GREEN**

```powershell
pytest tests/integration/hooks/test_quality_gate_hooks.py -q
```

Expected: all positive/negative process tests PASS.

- [ ] **Step 6: Run real required commands**

```powershell
ruff check .
ruff format --check .
mypy
pytest tests/ --cov --cov-report=term-missing
```

Expected: all exit `0`.

**Checkpoint:** Hook enforcement is active only after debt is green.

---

### Task 7: Correct document roles and current gate policy

**Owner:** BACKEND

**Files:**

- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `TESTING.md`
- Modify: `TOOLS_REFERENCE.md`
- Modify: `docs/THESIS.md`
- Create: `docs/CHANGELOG.md`
- Modify append-only: `docs/FEEDBACK-LOG.md`
- Modify: `docs/refactoring/README.md`
- Modify: `agents/rules/_shared-workflow.md`
- Modify: `agents/rules/preflight.md`
- Modify: `agents/rules/orchestrator.md`
- Modify: `agents/roles/backend-architect.md`
- Modify: `agents/roles/code-architect.md`
- Modify: `agents/roles/code-reviewer.md`
- Modify: `agents/roles/frontend-developer.md`
- Modify: `agents/roles/qa-debugger.md`
- Modify: `agents/roles/verifier.md`

**Interfaces:**

- Consumes: observed final hook commands/results from Tasks 2–6.
- Produces: one current operational story and one canonical history story.

- [ ] **Step 1: Update the loading/document-role contract**

In `AGENTS.md`:

- define `CLAUDE.md` as identity, commands, active conventions, and active traps;
- define `docs/THESIS.md` as canonical phase/milestone history;
- add `docs/CHANGELOG.md` as a thin shipped-stream index not normally loaded;
- retain `docs/FEEDBACK-LOG.md` as append-only corrections;
- state that AGENTS itself is a loading contract, not a phase history.

- [ ] **Step 2: Make CLAUDE current, not historical**

Remove the stale Phase 1–4 history/status wall. Keep:

- current project identity and run commands;
- exact required gate commands;
- current pytest.ini/local-binding/live-e2e/MAJOR #4 traps;
- current worktree/integration rules.

Link to THESIS/CHANGELOG for history instead of repeating it.

- [ ] **Step 3: Make THESIS the canonical phase record**

Record:

- Phase 1 harness shipped;
- Phase 2 meaningful test suite shipped;
- Phase 3 aggregate coverage gate closed by this stream;
- Phase 4 strict-mypy hard gate closed by this stream;
- Phase 5 API shipped;
- current next-direction material without copying command details.

Use the actual implementation/verification date when recording closure.

- [ ] **Step 4: Create the thin shipped-work index**

Create `docs/CHANGELOG.md` with:

- a short “index, not narrative” policy;
- newest-first one-line entries;
- links to authoritative archived spec/plan/closeout artifacts;
- an entry for this harness-quality-gates burndown after it is verified.

Do not copy THESIS narratives or commit ladders into this file.

- [ ] **Step 5: Append the user correction**

Append one dated entry to `docs/FEEDBACK-LOG.md`:

- **What:** CLAUDE is identity/commands/current conventions/active traps; THESIS owns phase
  history; CHANGELOG is a thin shipped index; FEEDBACK records corrections.
- **Why:** duplicated history drifts and hides active operating guidance.
- **How to apply:** move phase narratives out of CLAUDE, link instead of copy, and never
  rewrite prior FEEDBACK entries.

Do not alter any previous entry.

- [ ] **Step 6: Update testing/tool references**

In `TESTING.md`, document:

- complete shipped surface;
- exact aggregate coverage command and `>=90%` enforcement;
- bare strict `mypy` hard gate;
- hook negative tests;
- default/live test split;
- no coverage padding/suppression policy.

In `TOOLS_REFERENCE.md`, replace deferred/advisory commands with the same canonical
commands.

- [ ] **Step 7: Update agent workflow docs**

Replace every active “Phase 1 advisory,” “Phase 3 deferred,” or “Phase 4 promotes later”
statement in the listed rule/role files with the current blocking policy. VERIFIER,
REVIEWER, and QA must require aggregate coverage and strict zero mypy.

Keep FRONTEND/UX_UI hedge semantics otherwise unchanged.

- [ ] **Step 8: Document refactoring artifact lifecycle**

In `docs/refactoring/README.md`, define:

- `spec/` for governing designs;
- `implementations/` for active execution plans/handoffs;
- `archive/` for HUMAN-closed artifacts.

- [ ] **Step 9: Run active-doc stale-state checks**

```powershell
rg -n -i "Phase 1.*advisory|Phase 3.*deferred|Phase 4.*promotes|coverage.*deferred|mypy.*advisory" AGENTS.md CLAUDE.md TESTING.md TOOLS_REFERENCE.md agents
```

Expected: no stale active-policy matches. Historical archive prose is excluded from this
check.

**Checkpoint:** Live docs describe the implemented gates and obey the four document roles.

---

### Task 8: Close `docs/superpowers` lifecycle and sweep inbound links

**Owner:** BACKEND

**Files:**

- Move:
  `docs/superpowers/specs/2026-05-02-agent-harness-replication-design.md`
  -> `docs/superpowers/specs/archive/2026-05-02-agent-harness-replication-design.md`
- Move:
  `docs/superpowers/plans/2026-05-02-agent-harness-replication.md`
  -> `docs/superpowers/plans/archive/2026-05-02-agent-harness-replication.md`
- Move:
  `docs/superpowers/specs/2026-05-04-fincli-only-refactor-design.md`
  -> `docs/superpowers/specs/archive/2026-05-04-fincli-only-refactor-design.md`
- Modify:
  `docs/superpowers/specs/archive/2026-05-22-fincli-api-design.md`
- Modify: every tracked inbound text reference found by fixed-string search

**Interfaces:**

- Consumes: terminal phase record from Task 7.
- Produces: no completed artifact presented as active and no broken old path.

- [ ] **Step 1: Create the plans archive directory**

Create `docs/superpowers/plans/archive/` if absent.

- [ ] **Step 2: Move the three completed active artifacts**

Use `git mv` only if HUMAN has authorized repository staging/commit workflow; otherwise
perform ordinary filesystem moves that preserve content and let Git detect renames.

- [ ] **Step 3: Add minimal terminal banners/metadata**

- Harness design: SHIPPED for Phase 1/2; Phase 3/4 authority superseded by the governing
  refactor spec.
- Harness plan: EXECUTED; historical plan.
- Fincli-only design: SHIPPED; historical removal of `fundainsight`, predating the API
  transport.
- API design: remove contradictory `DRAFT` version metadata and append a shipped lifecycle
  entry without rewriting historical design content.

- [ ] **Step 4: Sweep every inbound old path**

Update all tracked text references, including active docs, archived docs, source docstrings,
and `arch-conversation-fincli-only-refactor.txt`, from the old active locations to the new
archive locations. These are path-only repairs; preserve historical assertions.

- [ ] **Step 5: Prove old paths have no inbound references**

```powershell
rg -n -F "docs/superpowers/specs/2026-05-02-agent-harness-replication-design.md" .
rg -n -F "docs/superpowers/plans/2026-05-02-agent-harness-replication.md" .
rg -n -F "docs/superpowers/specs/2026-05-04-fincli-only-refactor-design.md" .
```

Expected: no matches.

- [ ] **Step 6: Prove terminal locations and top statuses**

```powershell
Get-ChildItem -Recurse -File docs/superpowers | Select-Object -ExpandProperty FullName
rg -n "Status:|SHIPPED|EXECUTED|superseded" docs/superpowers/specs/archive docs/superpowers/plans/archive
```

Expected: all four artifacts are in terminal locations with unambiguous top metadata.

- [ ] **Step 7: Validate Markdown links by repository search**

For every moved path, confirm all references resolve to an existing file. Spot-check links
from `AGENTS.md`, `CLAUDE.md`, `TESTING.md`, `docs/THESIS.md`, `docs/CHANGELOG.md`,
`docs/FEEDBACK-LOG.md`, and archived companion specs.

**Checkpoint:** All `docs/superpowers` work is terminal and navigable.

---

### Task 9: BACKEND final validation and evidence handoff

**Owner:** BACKEND

**Files:**

- No new files unless a failing required test reveals an in-scope correction.

- [ ] **Step 1: Run syntax, lint, and format**

```powershell
node --check .claude/hooks/utils.js
node --check .claude/hooks/post-edit.js
node --check .claude/hooks/on-stop.js
ruff check .
ruff format --check .
```

Expected: all exit `0`.

- [ ] **Step 2: Run strict typing**

```powershell
mypy
```

Expected: zero errors over 55 or more shipped source files, including `fincli_api` and
`singleton.py`.

- [ ] **Step 3: Run hook positive/negative tests**

```powershell
pytest tests/integration/hooks/test_quality_gate_hooks.py -q
```

Expected: PASS, including sub-90 and deliberate-type-error blocking cases.

- [ ] **Step 4: Run the default suite and aggregate gate**

```powershell
pytest tests/
pytest tests/ --cov --cov-report=term-missing
```

Expected:

- all tests pass;
- the existing skip remains justified;
- live tests remain default-deselected;
- MAJOR #4 remains xfailed;
- aggregate line coverage is at least 90%.

- [ ] **Step 5: Pin MAJOR #4 unchanged**

```powershell
pytest tests/integration/api/test_screens_integration.py -q -ra -k "no_table"
```

Expected: current-behavior test PASS and desired 502-parsing test XFAIL, not XPASS.

- [ ] **Step 6: Check OpenAPI and contracts**

```powershell
python scripts/dump_openapi.py --check
git diff -- CONTRACTS.md docs/api/openapi.yaml docs/api/openapi.json docs/api/postman_collection.json
```

Expected: OpenAPI check exits `0`; diff command has no output.

- [ ] **Step 7: Run live-Finviz gate**

```powershell
pytest -m live tests/e2e/api/ -q -ra
```

Expected: 3 passed. If the sanctioned live provider is unavailable, report the exact
external failure to VERIFIER/HUMAN; do not substitute another provider or waive the gate.

- [ ] **Step 8: Verify Ruff D remains declined**

```powershell
rg -n 'select = .*"D"|extend-select = .*"D"' pyproject.toml
```

Expected: no matches enabling Ruff `D`.

- [ ] **Step 9: Verify diff scope**

```powershell
git status --short
git diff --name-only
```

Expected: only files authorized by the governing spec. No contract/OpenAPI artifact
changes.

- [ ] **Step 10: Hand off to VERIFIER**

Provide:

- baseline and final test/coverage/mypy totals;
- exact commands and exit codes;
- list of source/type/test/hook/doc changes;
- hook-negative-test evidence;
- MAJOR #4 pair evidence;
- live-Finviz result;
- lifecycle move/link-sweep evidence;
- explicit statement that no commit/push/PR occurred.

HANDOFF_TO: VERIFIER

---

### Task 10: Independent verification

**Owner:** VERIFIER

**Files:**

- Read governing spec, plan, full diff, and affected role.
- Do not modify implementation.

- [ ] **Step 1: Re-run all required local gates independently**

Run:

```powershell
ruff check .
ruff format --check .
mypy
pytest tests/ --cov --cov-report=term-missing
pytest tests/integration/hooks/test_quality_gate_hooks.py -q
python scripts/dump_openapi.py --check
pytest tests/integration/api/test_screens_integration.py -q -ra -k "no_table"
pytest -m live tests/e2e/api/ -q -ra
```

- [ ] **Step 2: Inspect scope and policy**

Confirm:

- coverage and mypy scopes match setuptools shipped surface;
- threshold is aggregate 90%;
- no suppression/exclusion/padding;
- failed required checks reach exit `2`;
- no false “all passed” path remains;
- public contracts are untouched.

- [ ] **Step 3: Inspect lifecycle/doc roles**

Confirm terminal archive locations, no old inbound paths, FEEDBACK append-only behavior,
and CLAUDE/THESIS/CHANGELOG separation.

- [ ] **Step 4: Issue verdict**

Return `VERIFIED` only if every acceptance criterion is evidenced. Otherwise return
`NOT VERIFIED` to BACKEND with exact failures.

HANDOFF_TO: REVIEWER

---

### Task 11: Architecture, quality, and suppression review

**Owner:** REVIEWER

**Files:**

- Review full diff plus VERIFIER evidence.

- [ ] **Step 1: Review type changes**

Reject runtime behavior drift, unjustified `Any`, broad ignores, disabled diagnostics,
false casts, or external-stub workarounds that conceal project errors.

- [ ] **Step 2: Review coverage tests**

Reject tests that assert private call counts, merely import modules, lack meaningful
assertions, or exist only to execute lines.

- [ ] **Step 3: Review hook architecture**

Confirm policy centralization, safe process invocation, bounded diagnostics, loop safety,
positive/negative process tests, and exit-2 behavior.

- [ ] **Step 4: Review docs/lifecycle**

Confirm document roles, terminal metadata, archive paths, inbound links, and explicit Ruff
`D` decline.

- [ ] **Step 5: Issue verdict**

Return `APPROVE`/`APPROVE_WITH_NITS` only with no MAJOR/BLOCKER. A rejection returns to
BACKEND and restarts validation at VERIFIER.

HANDOFF_TO: QA

---

### Task 12: QA and HUMAN closure

**Owner:** QA, then HUMAN

- [ ] **Step 1: QA validates observable behavior**

Validate:

- existing CLI/API suites and OpenAPI drift;
- no-table MAJOR #4 pair unchanged;
- aggregate coverage and strict typing gates;
- hook block/pass behavior;
- docs navigation and lifecycle acceptance criteria.

- [ ] **Step 2: QA issues PASS/FAIL**

`FAIL` returns to BACKEND and restarts at VERIFIER. Do not exceed three complete validation
cycles.

- [ ] **Step 3: HUMAN decides acceptance**

Only HUMAN may:

- accept the stream;
- authorize commits/integration;
- close/archive the governing spec and plan;
- accept an externally blocked live test with explicit rationale.

HANDOFF_TO: HUMAN

---

## Self-Review

### Spec coverage

- Document roles/correction: Tasks 7–8.
- Aggregate full-surface coverage `>=90%`: Task 2 and Tasks 6/9.
- Strict zero mypy including API/Singleton: Tasks 3–5.
- Blocking Stop/PostToolUse: Tasks 1 and 6.
- Negative hook tests: Task 1, green in Task 6.
- Public behavior and MAJOR #4 preservation: Tasks 5, 9–12.
- `docs/superpowers` terminal lifecycle/link sweep: Task 8.
- Ruff `D` explicit decline: Global Constraints and Task 9.
- Required handoff/loop cap: Tasks 9–12.

### Placeholder scan

No implementation decision is deferred. Additional coverage cases are allowed only when
the term-missing report proves the specified behavior slices are insufficient, and the
selection rule and acceptance test are explicit.

### Contract consistency

- Mypy source names use filesystem targets, including `singleton.py`.
- Coverage source names use importable modules, including `singleton`.
- Hooks consume bare/config-driven commands and do not duplicate package lists or the 90%
  threshold.
- Default pytest remains offline; live tests remain a separate mandatory final gate.

HANDOFF_TO: BACKEND
