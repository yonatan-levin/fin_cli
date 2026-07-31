# Harness Quality Gates Burndown — Governing Refactor Spec

MODE: PLAN_AND_CREATE  
ROLE: ARCH

**Status:** READY FOR IMPLEMENTATION  
**Branch:** `refactor/harness-spec-burndown`  
**Companion plan:** `docs/refactoring/implementations/harness-quality-gates-burndown-plan.md`  
**Public contract impact:** None

## Summary

This refactor closes the remaining agent-harness quality debt as one coherent stream. It
corrects the project-document roles, raises behavior-validating aggregate coverage across
the complete shipped Python runtime surface to at least 90%, brings strict mypy to zero
errors without suppressing or excluding failures, and then promotes both checks to honest
blocking hook gates. It also gives the four `docs/superpowers` artifacts terminal lifecycle
states and archive locations, sweeps inbound links, and adds negative hook tests proving
that sub-threshold coverage and deliberate type failures block. CLI, HTTP API, CSV, error,
OpenAPI, and malformed-HTML behavior remain unchanged.

## Requirements

### Verified baseline

The implementation starts from the user-verified baseline:

| Gate | Baseline |
|---|---|
| Default pytest suite | 279 passed, 1 skipped, 3 live deselected, 1 xfailed |
| Aggregate runtime coverage | 88%; 979 statements covered, 122 missed |
| Strict mypy over the shipped surface | 49 errors in 13 files |
| Ruff lint and format | Green |
| Live API tests | 3 tests, deselected by the default invocation |
| Deferred defect | Malformed-HTML MAJOR #4 remains represented by a strict xfail plus a current-behavior pin |

The authoritative strict-mypy discovery command is:

```powershell
mypy fincli fincli_api core config logger singleton.py
```

The 13 files currently reporting errors are:

- `singleton.py`
- `core/configuration/config_base.py`
- `config/config.py`
- `logger/handlers.py`
- `logger/formatters.py`
- `logger/logger.py`
- `logger/log_cycle.py`
- `fincli/app/main.py`
- `fincli/cli/cli_stock_screener.py`
- `fincli/stock_screening/content/stock_table.py`
- `fincli/stock_screening/parsers/stock_table.py`
- `fincli/utils/market_cap.py`
- `fincli/utils/web_scraper.py`

`fincli_api/` is already clean under the explicit command, but it is absent from the
configured mypy scope and therefore is not protected by the normal gate.

### Goals

- Establish the shipped Python runtime surface as exactly:
  `fincli`, `fincli_api`, `core`, `config`, `logger`, and `singleton.py`.
- Enforce one aggregate line-coverage threshold of `>=90%` over that entire surface.
- Reach zero strict mypy errors over that same surface without weakening strict mode,
  omitting modules, adding broad ignores, or hiding errors.
- Use behavior-validating tests to close the coverage gap; do not add import-only,
  assertion-free, private-call-count, or line-execution padding tests.
- Make repo-wide Stop checks block on Ruff lint, Ruff format, strict mypy, pytest, or
  aggregate coverage failure.
- Make PostToolUse per-Python-file checks return a blocking failure when the final Ruff,
  format, or mypy check is non-zero. The saved edit is not rolled back; the block prevents
  the agent from treating the edit as accepted and continuing silently.
- Add hook-level negative tests proving:
  - aggregate coverage below 90% blocks Stop;
  - a deliberate strict-mypy error blocks Stop;
  - a deliberate per-file type error blocks PostToolUse;
  - clean required gates still permit completion.
- Correct document responsibilities using the Midas precedent:
  - `CLAUDE.md`: identity, commands, active conventions, and still-active traps;
  - `docs/THESIS.md`: canonical phase and milestone history;
  - `docs/CHANGELOG.md`: thin newest-first shipped-work index;
  - `docs/FEEDBACK-LOG.md`: append-only corrections and validated choices.
- Reconcile all four current `docs/superpowers` artifacts to terminal, accurate states and
  archive locations, then update every inbound path reference.
- Preserve all public behavior and contracts.
- Complete the validation sequence `BACKEND -> VERIFIER -> REVIEWER -> QA -> HUMAN`, with
  no more than three validation cycles.

### Non-goals

- No CLI option, exit-code, stream, CSV schema, filter-inventory, or importable service
  contract change.
- No HTTP endpoint, request/response model, status mapping, error envelope, OpenAPI, host,
  authentication, or deployment change.
- No fix for malformed-HTML MAJOR #4. Its strict xfail and current-behavior pin remain.
- No new runtime feature, parser behavior, retry policy, logger behavior, or output format.
- No per-module coverage thresholds or exemptions. The gate is aggregate.
- No broad mypy suppression such as `ignore_errors`, global
  `ignore_missing_imports`, `follow_imports = "skip"`, new excluded paths, disabled error
  codes, or blanket `# type: ignore` comments.
- No Ruff `D` rule enablement. Docstring enforcement is unrelated to the coverage/type-gate
  burndown, and Ruff is already green. A separate evidence-backed spec may consider it.
- No CI/GitHub Actions work and no GitHub issue mutation.
- No commit, push, PR, merge, or worktree removal without explicit HUMAN instruction.

### Constraints

- Python remains 3.12+ and the existing package/module layout remains intact.
- `pytest.ini` remains the canonical pytest runner configuration.
- The aggregate threshold is line coverage, matching the verified baseline; this stream
  does not silently switch to branch coverage.
- `singleton.py` is included because `[tool.setuptools] py-modules = ["singleton"]` ships
  it and `logger` consumes it.
- The only permissible missing-import accommodation is a narrow, documented override for
  a third-party package that genuinely has no usable type information. Existing typed
  dependencies must use real stubs instead.
- Live-Finviz validation is mandatory before HUMAN because typing work touches
  `fincli/stock_screening/` and the API depends on that path.
- Historical prose may describe former decisions, but every artifact's top-level status,
  location, and inbound links must be current and unambiguous.

## Architecture

### Major decisions and trade-offs

#### 1. One shipped-surface definition

`pyproject.toml` becomes the canonical source for both strict-mypy scope and coverage
source scope:

| Concern | Canonical scope |
|---|---|
| mypy `files` | `fincli`, `fincli_api`, `core`, `config`, `logger`, `singleton.py` |
| coverage `source` | `fincli`, `fincli_api`, `core`, `config`, `logger`, `singleton` |

The filename form is correct for mypy; the importable module name is correct for coverage.
The Stop hook runs bare `mypy` and a coverage-config-driven pytest command so package lists
are not copied into JavaScript and allowed to drift.

Trade-off: the scope is coupled to the current setuptools package list. That is desirable:
adding a future shipped package requires changing packaging and quality scope together.
The docs and review checklist make that coupling explicit.

#### 2. One full-suite test-and-coverage execution

The Stop hook uses one pytest-cov invocation for both default tests and aggregate coverage:

```text
pytest tests/ --cov --cov-report=term-missing
```

`[tool.coverage.run]` supplies the source set and `[tool.coverage.report]` supplies
`fail_under = 90` and missing-line display. `pytest.ini` continues to exclude `live` tests
from this offline gate.

This replaces the separate plain-pytest check plus stubbed coverage step, avoiding a
duplicate full-suite run. A non-zero result means either tests failed or aggregate coverage
fell below 90%, and is blocking in either case.

#### 3. Type correctness before enforcement

The stream first makes the strict command green, then flips hook policy. Third-party type
information is supplied through dev dependencies such as `pandas-stubs`,
`types-colorama`, and `types-requests`; the exact resolved versions must be compatible with
the installed runtime packages. The existing broad `requests` missing-import override is
removed once real stubs are installed. Any `cfscrape` override must be narrowed to the
actually imported untyped module and documented as an external boundary.

Type-only edits must preserve runtime semantics. Where typing reveals a genuinely invalid
import or unsafe contract, the implementation must choose the smallest runtime-neutral
correction and run the existing behavior tests around that module.

#### 4. Blocking means honest process control

Required checks produce only two terminal states:

| Hook result | Process behavior |
|---|---|
| All required checks pass | exit `0` with an accurate success message |
| Any required check fails, times out, or is unavailable | exit `2` with the check name, command, and bounded diagnostic on stderr |

Dependency audit and documentation reminders remain outside the required quality-gate set.
They may be advisory or explicitly reported as skipped, but they cannot cause a false
“all gates passed” message.

PostToolUse occurs after the file is saved. Therefore “blocking PostToolUse” means the
hook exits `2` and returns actionable feedback; it cannot undo the edit. The next agent
action is to repair the file and rerun the check.

#### 5. Test hook behavior at the process boundary

Hook tests use pytest to copy `.claude/hooks/` into an isolated `tmp_path` project, seed the
session file, provide controlled command executables on `PATH`, invoke Node with realistic
stdin JSON, and assert exit code/stdout/stderr. This tests the actual hook entry point and
response protocol without modifying the real session file or relying on current repo
failures.

Command shims simulate sub-90 coverage and repo-wide mypy failure. A temporary Python file
containing a deliberate assignment type error exercises the real PostToolUse per-file path.

#### 6. Documentation lifecycle is a boundary, not a prose cleanup

Live operational docs describe only current state. Detailed completed work moves to
archives. `docs/CHANGELOG.md` points to those authoritative artifacts without duplicating
their narratives. Path-only changes are applied even in historical inbound references so
links remain resolvable; historical assertions are otherwise preserved.

### Data flow

```text
Python edit
   |
   v
PostToolUse post-edit.js
   |-- secret/security scans
   |-- Ruff fix + final Ruff check
   |-- Ruff format + final format check
   `-- strict mypy for edited file
          |
          +-- all green ----------> exit 0
          `-- any required fail --> exit 2 + diagnostic

Session Stop
   |
   v
on-stop.js
   |-- ruff check .
   |-- ruff format --check .
   |-- mypy                 (scope from pyproject.toml)
   `-- pytest --cov         (scope + >=90 from pyproject.toml)
          |
          +-- all green ----------> exit 0
          `-- any required fail --> exit 2 + diagnostic
```

### Boundaries and dependency direction

- `pyproject.toml` owns quality policy values and shipped-surface scope.
- `.claude/hooks/*.js` orchestrate tools and map results to the Claude hook protocol; they
  do not own duplicate package lists or thresholds.
- `tests/integration/hooks/` validates hook process behavior and may not depend on product
  network access.
- `tests/unit/` and existing product integration tests validate behavior and raise
  aggregate Python coverage.
- Product packages remain unaware of hooks, coverage, and documentation lifecycle.
- Documentation consumes verified gate state; hooks never parse documentation to decide
  whether code passes.

### Folder structure

Only the affected or newly organized paths are shown:

```text
algo_beta/
├── pyproject.toml                           # mypy scope, coverage source + >=90 policy, dev stubs
├── AGENTS.md                                # loading contract + corrected document roles
├── CLAUDE.md                                # identity, commands, current conventions/traps only
├── TESTING.md                               # enforced gate commands and test strategy
├── TOOLS_REFERENCE.md                       # operator command reference
├── .claude/
│   └── hooks/
│       ├── utils.js                         # shipped-module detection, shared hook helpers
│       ├── post-edit.js                     # blocking per-file quality checks
│       └── on-stop.js                       # blocking repo-wide gates
├── tests/
│   ├── integration/
│   │   └── hooks/
│   │       ├── conftest.py                  # isolated hook sandbox + command shims
│   │       └── test_quality_gate_hooks.py   # positive and negative process tests
│   └── unit/
│       ├── stock_screening/parsers/
│       │   └── test_stock_table.py          # row/link/malformed behavior
│       ├── utils/test_web_scraper.py         # HTTP-boundary behavior
│       └── test_singleton.py                 # metaclass instance behavior
├── agents/
│   ├── rules/                               # current blocking-gate workflow language
│   └── roles/                               # current BACKEND/VERIFIER/REVIEWER/QA expectations
└── docs/
    ├── THESIS.md                            # canonical phase/milestone history
    ├── CHANGELOG.md                         # thin shipped-stream index
    ├── FEEDBACK-LOG.md                      # append-only document-role correction
    ├── refactoring/
    │   ├── README.md                        # spec/implementation/archive lifecycle convention
    │   ├── spec/
    │   │   └── harness-quality-gates-burndown-spec.md
    │   └── implementations/
    │       └── harness-quality-gates-burndown-plan.md
    └── superpowers/
        ├── specs/
        │   └── archive/
        │       ├── 2026-05-02-agent-harness-replication-design.md
        │       ├── 2026-05-04-fincli-only-refactor-design.md
        │       └── 2026-05-22-fincli-api-design.md
        └── plans/
            └── archive/
                └── 2026-05-02-agent-harness-replication.md
```

## API Contracts

### Public CLI and HTTP contracts

There are no public API changes:

- `CONTRACTS.md` is not changed.
- `docs/api/openapi.yaml`, `docs/api/openapi.json`, and
  `docs/api/postman_collection.json` are not changed.
- CLI commands/options, exit codes, CSV schema, JSON summary, filter inventory, API
  endpoints, request/response models, and error mappings remain byte/behavior compatible.
- `scripts/dump_openapi.py --check` must remain green.

### Internal hook contracts

#### Stop hook

- Input: Claude Stop-hook JSON on stdin.
- Success: exit `0`; stdout JSON may contain `systemMessage`.
- Required-gate failure: exit `2`; stderr identifies every failed required gate and gives
  bounded diagnostic output.
- `stop_hook_active = true`: exit `0` immediately to prevent loops.

#### PostToolUse hook

- Input: Claude PostToolUse JSON containing `tool_input.file_path`.
- Non-Python/non-testable file: exit `0`.
- Clean Python file: exit `0`.
- Failed final Ruff, format, or strict-mypy check: exit `2` with file and check details.
- The hook never claims the file was reverted.

### Error model

Hook diagnostics distinguish:

- tool returned non-zero;
- tool executable unavailable;
- tool timed out;
- hook infrastructure exception.

Each required case is blocking. Diagnostics are truncated to a bounded size to avoid
flooding agent context, while preserving the check name and actionable tail/head.

## File Categories

### Quality configuration

- Modify `pyproject.toml`.
- Do not modify `pytest.ini` except if implementation evidence proves the existing
  default-live exclusion conflicts with the canonical command; no such conflict is
  currently known.

### Hook implementation

- Modify `.claude/hooks/on-stop.js`.
- Modify `.claude/hooks/post-edit.js`.
- Modify `.claude/hooks/utils.js` only for shared execution helpers and complete
  `fincli_api`/`singleton.py` service detection.

### Behavior and gate tests

- Create `tests/integration/hooks/conftest.py`.
- Create `tests/integration/hooks/test_quality_gate_hooks.py`.
- Create `tests/unit/stock_screening/parsers/test_stock_table.py`.
- Create `tests/unit/utils/test_web_scraper.py`.
- Create `tests/unit/test_singleton.py`.
- Extend an existing test file instead of creating another only when the module already
  has the same behavioral responsibility.

### Strict typing

Modify only the 13 baseline-error files listed under Requirements unless adding real
stubs reveals a strict error in another shipped file. Any newly revealed file is in scope
only for the smallest typing correction needed to reach zero.

### Live operational documentation

- Modify `AGENTS.md`, `CLAUDE.md`, `TESTING.md`, `TOOLS_REFERENCE.md`.
- Modify `docs/THESIS.md`.
- Create `docs/CHANGELOG.md`.
- Append one correction to `docs/FEEDBACK-LOG.md`; do not edit prior entries.
- Modify `docs/refactoring/README.md`.
- Update stale gate language in:
  - `agents/rules/_shared-workflow.md`
  - `agents/rules/preflight.md`
  - `agents/rules/orchestrator.md`
  - `agents/roles/backend-architect.md`
  - `agents/roles/code-architect.md`
  - `agents/roles/code-reviewer.md`
  - `agents/roles/frontend-developer.md`
  - `agents/roles/qa-debugger.md`
  - `agents/roles/verifier.md`

### Lifecycle moves and inbound-link updates

- Move and minimally amend the three completed active `docs/superpowers` artifacts.
- Normalize the already archived API design metadata.
- Apply path-only inbound-link updates repo-wide, including historical text artifacts and
  archived docs, so no old live path remains unresolved.

## Module Descriptions

### `pyproject.toml`

Owns strict-mypy file discovery, aggregate coverage source discovery, the 90% threshold,
and typing-only dev dependencies. It is the single quality-policy source consumed by local
commands and hooks.

### `.claude/hooks/on-stop.js`

Runs the repo-wide required gate set and translates any failure into Stop-hook exit `2`.
It preserves the loop guard and keeps dependency audit/document reminders separate from
required gates.

### `.claude/hooks/post-edit.js`

Runs lightweight final checks for the edited Python file. Ruff may continue to apply its
existing safe auto-fixes/formatting, but a final verification pass must determine the hook
result. Failures cannot be swallowed.

### `.claude/hooks/utils.js`

Holds shared process execution/response helpers and module detection. It must recognize
all shipped Python surfaces, including `fincli_api/` and root `singleton.py`.

### `tests/integration/hooks/`

Provides OS-aware, isolated process tests for the real hook scripts. Tests copy hooks into
a temporary project and never mutate `.claude/hooks/.session-edits.json` in the worktree.

### Product typing/test slices

The typing files retain their current runtime responsibilities. New unit tests target
observable parser, scraper-boundary, and Singleton behavior that is currently under-tested;
they are not allowed to assert annotations or private implementation details.

### Documentation set

The four document roles are mutually exclusive enough to prevent future history walls:

| Document | Owns | Must not become |
|---|---|---|
| `CLAUDE.md` | Identity, commands, active conventions, current traps | changelog, phase diary, corrections log |
| `docs/THESIS.md` | Direction plus canonical phase/milestone history | command reference |
| `docs/CHANGELOG.md` | One-line shipped-stream index with links | narrative closeout |
| `docs/FEEDBACK-LOG.md` | Append-only corrections/validated choices | rewritten history |

## Tasks by Agent

### BACKEND

- Add RED hook-process tests before hook edits.
- Add centralized coverage/mypy policy and real typing stubs.
- Add behavior-validating tests until aggregate runtime coverage is at least 90%.
- Eliminate every strict-mypy error over the configured shipped surface.
- Promote Stop and PostToolUse checks to blocking and make hook tests green.
- Perform the live-doc role correction, phase reconciliation, lifecycle moves, and link
  sweep.
- Run the complete local gate set and hand off evidence to VERIFIER.

### FRONTEND

- Not applicable. No frontend surface changes.

### UX_UI

- Not applicable. No CLI UX or copy behavior changes.

### VERIFIER

- Independently run strict mypy, aggregate coverage, default suite, hook negative tests,
  Ruff, OpenAPI drift, malformed-HTML pair, and live-Finviz tests.
- Confirm no required gate can fail while the hook exits `0`.
- Confirm no public contract file or OpenAPI artifact changed.

### REVIEWER

- Reject coverage padding, suppressions, scope omissions, duplicated policy lists, false
  success messages, or behavior changes disguised as typing fixes.
- Verify the document roles and lifecycle/link sweep.
- Confirm optional Ruff `D` rules were not introduced.

### QA

- Validate CLI/API regression behavior using existing automated suites.
- Confirm the malformed-HTML desired-behavior test remains xfailed and its current-behavior
  companion remains passing.
- Confirm all acceptance criteria and doc navigation work from the final tree.

## Spec Updates

Implementation updates are intentionally small and concrete:

- `AGENTS.md`: add `docs/CHANGELOG.md` to the loading/file-role contract; state that
  `CLAUDE.md` is not project history and `THESIS.md` is canonical for phases.
- `CLAUDE.md`: remove stale Phase 1–4 history/status wall; retain current gate commands and
  active traps only.
- `docs/THESIS.md`: record Phase 1 and 2 as shipped; record this stream as the Phase 3/4
  closure when verified.
- `docs/CHANGELOG.md`: create a thin newest-first index pointing to authoritative archived
  artifacts and this refactor.
- `docs/FEEDBACK-LOG.md`: append the document-role correction with What/Why/How to apply.
- `TESTING.md`: replace deferred language with the exact enforced commands, scope, and
  hook-negative-test strategy.
- `TOOLS_REFERENCE.md` and agent role/rule docs: replace advisory/deferred language with
  current blocking policy.
- `docs/refactoring/README.md`: document `spec/`, `implementations/`, and archive lifecycle.
- `ARCHITECTURE.md` and `CONTRACTS.md`: no update; runtime architecture and public
  contracts do not change.

## Tests

### Unit

- Stock-table parser: valid row extraction, ticker URL construction, empty rows, malformed
  anchor behavior.
- Web scraper boundary: successful byte return, timeout/header call shape where already
  contractual, and exception propagation/wrapping without live network.
- Singleton metaclass: same class returns the same instance; different classes do not
  share an instance; test isolation clears only test-owned instances.

### Integration

- Stop hook blocks on an 89% simulated aggregate result.
- Stop hook blocks on a simulated strict-mypy failure.
- PostToolUse blocks on a temporary Python file with a deliberate type mismatch.
- Clean Stop and PostToolUse paths exit `0`.
- Stop-loop guard still exits `0`.

### Regression

- Existing default suite remains green; new tests increase the pass count while the
  existing skip/live-deselection/xfail semantics remain.
- `scripts/dump_openapi.py --check` remains green.
- The MAJOR #4 no-table pair remains one pass plus one strict xfail.
- The three opt-in live-Finviz tests pass before HUMAN review.

### Coverage quality rules

- Test assertions must target returned values, emitted output, filesystem effects, process
  exit status, or documented exceptions.
- No test may exist solely to execute lines.
- No new `coverage omit`, `exclude_lines`, `pragma: no cover`, or per-package threshold is
  introduced to reach 90%.

## Implementation Roadmap

1. Add hook-level negative tests and confirm RED.
2. Add centralized aggregate coverage policy and behavior tests; reach `>=90%`.
3. Expand strict-mypy scope and install real stubs; capture the post-stub RED baseline.
4. Burn down foundational/config/logger typing errors.
5. Burn down fincli parser/I/O/orchestrator typing errors and reach zero.
6. Flip hooks to blocking and make hook tests GREEN.
7. Correct live document roles and gate language.
8. Archive/reconcile `docs/superpowers` artifacts and sweep inbound links.
9. Run BACKEND final validation, then hand off through VERIFIER, REVIEWER, QA, HUMAN.

## Potential Challenges

| Challenge | Risk | Mitigation |
|---|---|---|
| Real pandas/colorama/request stubs reveal more errors than the current 49 | Medium | Treat newly revealed shipped-surface errors as part of the same strict-zero criterion; do not restore broad overrides |
| Typing BeautifulSoup/cfscrape boundaries encourages `Any` spread | Medium | Type concrete local inputs/outputs; keep any unavoidable external untyped boundary narrow and documented |
| PostToolUse cannot undo an edit | Low | State the semantics honestly; exit `2`, preserve diagnostics, require repair before proceeding |
| Full coverage and test commands drift | High | Keep source list/threshold in `pyproject.toml`; hooks consume config-driven commands |
| Hook tests mutate real session state | High | Copy hooks and session file into `tmp_path`; never invoke negative fixtures against the live hook directory |
| Historical links break after moves | Medium | Repo-wide fixed-string checks for every old path; update path text even in historical inbound artifacts |
| Type edits accidentally close MAJOR #4 | High | Run the strict-xfail/current-pin pair after every parser slice and at final QA |
| Gate activation blocks before debt is green | High | Enable blocking only after coverage and mypy are green on the implementation branch |

## Migration and Rollback

### Migration

1. Land behavior tests and quality configuration while hooks still use their old policy.
2. Reach aggregate coverage `>=90%` and strict mypy `0`.
3. Run the new hook negative tests in RED against old hooks.
4. Flip hook behavior and make the hook suite GREEN.
5. Reconcile docs only after final commands are stable, so live docs describe observed
   behavior.

There is no user-data, API, CSV, or configuration migration.

### Rollback

- If hook protocol behavior prevents normal agent operation, revert the hook enforcement
  files as one unit while retaining tests and the green source state for diagnosis. Do not
  lower thresholds or reintroduce ignores as a “rollback.”
- If typing changes alter runtime behavior, revert only the offending typed module and its
  paired tests, restore the RED mypy evidence, and return to BACKEND.
- If lifecycle moves break links, restore the files to their prior locations and revert the
  matching inbound-link sweep together.
- Any repository rollback uses a normal revert/explicit file restoration only after HUMAN
  instruction; no destructive reset is part of this plan.

## Lifecycle Closure

The completed historical artifacts end in these locations:

| Current artifact | Terminal location | Terminal state |
|---|---|---|
| `docs/superpowers/specs/2026-05-02-agent-harness-replication-design.md` | `docs/superpowers/specs/archive/2026-05-02-agent-harness-replication-design.md` | SHIPPED for Phase 1/2; Phase 3/4 authority superseded by this spec |
| `docs/superpowers/plans/2026-05-02-agent-harness-replication.md` | `docs/superpowers/plans/archive/2026-05-02-agent-harness-replication.md` | EXECUTED; historical implementation record |
| `docs/superpowers/specs/2026-05-04-fincli-only-refactor-design.md` | `docs/superpowers/specs/archive/2026-05-04-fincli-only-refactor-design.md` | SHIPPED; historical scope-reduction record |
| `docs/superpowers/specs/archive/2026-05-22-fincli-api-design.md` | unchanged | SHIPPED; remove contradictory DRAFT metadata |

After HUMAN accepts the implementation, this spec and its companion plan become eligible
for archive under `docs/refactoring/archive/`; they are not moved during BACKEND work
unless HUMAN explicitly closes the stream.

## GitHub Issue Update

- Issue: N/A
- Status: not updated
- Actions taken:
  - No GitHub mutation was requested or performed.
- Proposed update:
  - None. HUMAN may choose issue/PR tracking after implementation.

## Acceptance Criteria

- [ ] `pyproject.toml` defines the complete shipped surface for strict mypy and aggregate
  coverage, including `fincli_api` and `singleton`.
- [ ] `mypy` exits `0` with zero errors over all configured files.
- [ ] Strict mode remains enabled and no broad ignore/exclude/error-code suppression is
  added.
- [ ] Real stubs replace the `requests` missing-import override; any retained cfscrape
  exception is narrow and justified.
- [ ] `pytest tests/ --cov --cov-report=term-missing` exits `0` with aggregate line
  coverage `>=90%`.
- [ ] Coverage includes `fincli`, `fincli_api`, `core`, `config`, `logger`, and
  `singleton.py`; no package is omitted or given a lower threshold.
- [ ] Added coverage tests validate observable behavior and pass REVIEWER's no-padding
  review.
- [ ] `on-stop.js` exits `2` when Ruff, format, strict mypy, tests, or coverage fails.
- [ ] `post-edit.js` exits `2` when a final per-file Ruff, format, or strict-mypy check
  fails, while accurately stating that the saved edit remains.
- [ ] Hook integration tests prove sub-90 coverage and deliberate type failures block.
- [ ] Clean hook-path tests and the Stop loop guard exit `0`.
- [ ] Ruff lint and format remain green; Ruff `D` is not enabled.
- [ ] The default suite is green, existing live tests remain default-deselected, the
  existing skip remains justified, and MAJOR #4 remains one strict xfail plus one current
  behavior pass.
- [ ] All three live-Finviz API tests pass in the final VERIFIER cycle.
- [ ] `scripts/dump_openapi.py --check` passes and public contract/OpenAPI files are
  unchanged.
- [ ] `CLAUDE.md`, `THESIS.md`, `CHANGELOG.md`, and `FEEDBACK-LOG.md` obey their defined
  roles; the correction is appended to FEEDBACK-LOG.
- [ ] Phase 1/2 are recorded shipped and Phase 3/4 are recorded closed by this stream in
  `docs/THESIS.md`.
- [ ] All four `docs/superpowers` artifacts have terminal metadata and correct archive
  locations.
- [ ] Fixed-string searches find no inbound links to the three old active paths.
- [ ] BACKEND, VERIFIER, REVIEWER, and QA all produce passing/approving evidence before
  HUMAN acceptance.
- [ ] No more than three complete validation cycles occur; a third failed cycle escalates
  to HUMAN rather than starting a fourth.

## Assumptions and Open Questions

### Assumptions

- The supplied test/coverage baseline is authoritative; this ARCH turn does not reinstall
  the project or regenerate coverage artifacts.
- The 49-error mypy result reproduced from the existing shared development environment is
  representative of this worktree.
- Current public behavior is represented by `CONTRACTS.md`, the OpenAPI snapshots, and the
  existing test suite.
- Node.js remains available because the current hook harness already depends on it.

### Blocking questions

- None. The user supplied the threshold, scope, lifecycle policy, non-goals, and handoff
  order.

### Non-blocking questions

- If a newly installed third-party stub package is incompatible with the runtime version,
  BACKEND may pin a compatible dev-only version, documenting the reason in `pyproject.toml`
  and the handoff.
- If aggregate coverage is already at least 90% after adding the three specified behavior
  slices, no additional coverage-only test files should be created.

## Next Steps

1. BACKEND executes the companion plan task-by-task with RED→GREEN evidence.
2. VERIFIER independently reruns every required gate and negative hook test.
3. REVIEWER evaluates architecture, suppression risk, test quality, and doc lifecycle.
4. QA validates behavior/contracts and the deferred MAJOR #4 pair.
5. HUMAN decides acceptance and any commit/integration action.

HANDOFF_TO: BACKEND
