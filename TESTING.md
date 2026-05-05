# TESTING.md - Fin CLI Testing Strategy

This document defines the testing strategy, conventions, and follow-up roadmap for Fin CLI.

## Philosophy

Tests verify **behavior**, not implementation. A test that locks in the current implementation of a function (mocking out internals, asserting call counts on private helpers) becomes a tax to pay every time the function is refactored, even when behavior is unchanged. A test that asserts what the function *does* — input goes in, output comes out, side effect happens — survives refactors and earns its keep.

This codebase currently has **zero test bodies**. The `tests/` folder structure (`tests/unit/`, `tests/domain/`, `tests/e2e/`) exists from a prior reorganization, but `__pycache__` is the only surviving artifact of the old test files. **Phase 2** of the agent-harness rollout (`docs/superpowers/specs/2026-05-02-agent-harness-replication-design.md`, §8.1) is the work item that introduces real tests. Until that ships, `pytest tests/` runs cleanly because there is nothing to fail — and that is the intentional starting state, not a gap to backfill in Phase 1.

When tests do land, they should:

1. **Validate behavior at module boundaries.** A test for `convert_market_cap_to_numeric` checks that the right numeric value comes out for a given Finviz string input — not which intermediate variables get assigned in what order.
2. **Use mocks only at the system boundary.** Mock `cfscrape.create_scraper()`, mock the filesystem when verifying CSV writes. Do not mock pandas, do not mock Pydantic, do not mock the Singleton logger.
3. **Run fast.** Unit tests should complete in well under a second each; the full suite (when it exists) should sit comfortably in a CI step.

## Layout

```
tests/
  conftest.py                          # shared pytest fixtures (Phase 2)
  unit/                                # function-level: per-function in isolation
    conftest.py
    test_market_cap_conversion.py      # convert_market_cap_to_numeric
    test_query_builder.py              # build_stock_screener_query
    test_json_to_tuples.py             # json_to_tuples
    test_config.py                     # Config + build_config
  domain/                              # module-level: per-module behavior
    conftest.py
    test_screening_pipeline.py         # fincli main: query -> fetch (mocked) -> parse -> DataFrame
    test_configurator_history.py       # filter_history.json round-trip
  e2e/                                 # CLI-level: invoke `python -m fincli` with fixtures
    conftest.py
    fixtures/
      finviz_sample.html               # recorded Finviz HTML
    test_fincli_invocation.py
```

The three layers map to scope, not to "more important / less important":

- **Unit** — one function, no I/O, no DataFrame fan-out unless the function itself manipulates DataFrames.
- **Domain** — one module's pipeline, with external services mocked at their I/O boundary. Real pandas, real Pydantic, real logger.
- **E2E** — the CLI as a black box. `python -m fincli` runs against fixture files served by a stand-in HTTP layer; assertions are made against the produced CSV.

## Running Tests

```bash
# Everything
pytest tests/

# Layer-scoped
pytest tests/unit/
pytest tests/domain/
pytest tests/e2e/

# Pattern match by name
pytest -k "market_cap"
pytest -k "build_query and not e2e"

# Stop at first failure (handy when iterating)
pytest -x

# Verbose
pytest -v

# Coverage (informational — not enforced in Phase 1)
pytest --cov=fincli --cov=core --cov=config --cov-report=term-missing
```

The `-ra` default in `[tool.pytest.ini_options]` (see `pyproject.toml`) ensures a short summary of skipped, xfailed, and errored tests prints at the end of every run.

## Fixture Conventions

Each test layer has its own `conftest.py`. Shared cross-layer fixtures live in the top-level `tests/conftest.py`.

**Recommended fixtures (Phase 2 scope):**

```python
# tests/conftest.py

@pytest.fixture
def sample_screening_df():
    """DataFrame mimicking the output of build_data_frame."""
    return pd.DataFrame({
        "Symbol":      ["AAPL", "MSFT", "GOOGL"],
        "Ticker":      ["AAPL", "MSFT", "GOOGL"],
        "Sector":      ["Technology"] * 3,
        "Country":     ["USA"] * 3,
        "Market Cap":  [2_890_000_000_000, 2_800_000_000_000, 1_700_000_000_000],
    })

@pytest.fixture
def finviz_sample_html():
    """Recorded Finviz HTML fixture for the screener parser."""
    return Path("tests/e2e/fixtures/finviz_sample.html").read_bytes()
```

Fixture rules of thumb:

- **HTML fixture files** live under `tests/e2e/fixtures/`. They are real recorded responses, redacted of any secrets (there are no secrets in Finviz public data, but the convention applies anyway).
- **One fixture, one fact.** A fixture that builds an entire 200-row DataFrame is doing too much; split into smaller, named fixtures composed via `@pytest.mark.parametrize`.

## Mocking Strategy

### What to mock

- **`cfscrape.create_scraper()`** — never make real HTTP calls in unit/domain tests. Use the [`responses`](https://github.com/getsentry/responses) library or [`vcrpy`](https://vcrpy.readthedocs.io) (recorded interactions) at the I/O boundary. Both are well-suited; pick one in Phase 2 and use it consistently.
- **Filesystem writes for CSV** — use the `tmp_path` fixture (built into pytest) so each test gets an isolated temp directory.

### What NOT to mock

- **pandas DataFrame operations.** pandas is fast and deterministic; mocking it produces tests that no longer test anything real.
- **Pydantic validation.** Pydantic *is* the validation contract. If a test wants to verify "this config is invalid", it should construct an invalid `Config` and let Pydantic raise.
- **The Singleton logger.** Let it write into the test's temp directory or a `caplog` fixture. Resetting the Singleton between tests is best handled via a fixture in `tests/conftest.py` if test pollution turns out to be an issue (likely once Phase 2 expands).

### Example

```python
from unittest.mock import patch, MagicMock
import pandas as pd
import pytest

@patch("fincli.utils.web_scraper.cfscrape.create_scraper")
def test_fetch_urls_returns_one_blob_per_page(mock_create_scraper, finviz_sample_html):
    mock_scraper = MagicMock()
    mock_scraper.get.return_value.content = finviz_sample_html
    mock_create_scraper.return_value = mock_scraper

    from fincli.app.main import fetch_urls
    pages = fetch_urls("https://finviz.com/screener.ashx?v=111&f=fa_pe_u20&ft=2", page_count=3)
    assert len(pages) == 3
    assert all(isinstance(p, bytes) for p in pages)
```

## Coverage

**Coverage is deferred to Phase 3** of the harness rollout (`docs/superpowers/specs/2026-05-02-agent-harness-replication-design.md`, §8.2).

In Phase 1 (now):

- `pytest-cov` is installed in dev dependencies so the tooling is ready.
- `pytest --cov=fincli ...` runs and produces a report — but the value is informational only. There is no threshold, and `.claude/hooks/on-stop.js` does not enforce one.

In Phase 3 (after Phase 2 establishes a real test suite):

- The target coverage threshold is **90%**, matching the Midas reference harness.
- `.claude/hooks/on-stop.js` will block the `Stop` event when coverage drops below 90%.
- Per-module thresholds may be tuned during ramp-up (e.g., `logger/` is hard to test usefully, so a lower per-module threshold is plausible there).

The reason Phase 3 is its own work item, not folded into Phase 2, is straightforward: a coverage gate against zero tests is meaningless, and a coverage gate enabled before tests have substance creates pressure to write low-quality tests just to hit the metric. The correct sequence is: **write tests first, enable coverage gate second**.

## Type Checking

`mypy` runs on every save (via `.claude/hooks/post-edit.js`) and on every `Stop` event (via `.claude/hooks/on-stop.js`). The `pyproject.toml` config is **`strict = true` from day one**, deliberately:

```toml
[tool.mypy]
python_version = "3.12"
files = ["fincli", "core", "config", "logger"]
strict = true

[[tool.mypy.overrides]]
module = ["cfscrape", "cfscrape.*"]
ignore_missing_imports = true
```

`bs4` is typed via the `types-beautifulsoup4` dev dep, which is cleaner than an override.

The codebase has very few type hints today, so `strict = true` produces dozens of errors. **In Phase 1, mypy results surface through the `warnings` channel of `on-stop.js`, NOT the `issues` channel.** That means:

- The user sees the running error count after every Stop event.
- The user is not blocked from finishing a session by mypy errors.
- The advisory pressure encourages adding type hints to whatever module is being touched, without forcing a giant up-front type-hint sprint.

**Phase 4** of the harness rollout (`docs/superpowers/specs/2026-05-02-agent-harness-replication-design.md`, §8.3) flips mypy from advisory `warnings` to a hard `issues` gate once `mypy fincli core config logger` reports zero errors. The trigger condition is concrete: zero errors. Until then, the gap is visible but does not block work.

This phased approach exists because:

- A blocking mypy gate against an unannotated codebase forces an immediate massive type-hint sprint, which is out of Phase 1 scope.
- An optional or weakened mypy config (e.g., `strict = false`) hides the actual gap behind a friendlier number.
- The `warnings` channel is the honest middle ground: real numbers, advisory pressure, no blocked sessions.

## Lint and Format

```bash
ruff check .          # lint (pyflakes + pycodestyle + isort + bugbear + pyupgrade + naming + simplify)
ruff check --fix .    # auto-fix the mechanical issues
ruff format .         # format (black-compatible)
ruff format --check . # verify formatting without writing
```

Both are run automatically by `.claude/hooks/post-edit.js` on every saved `.py` file. The Stop hook also runs `ruff check .` and `ruff format --check .` against the whole repo. Configuration sits in `pyproject.toml` under `[tool.ruff]`, `[tool.ruff.lint]`, and `[tool.ruff.format]`.

The lint rule set is the conservative `["E", "F", "W", "I", "B", "UP", "N", "SIM"]`. The `D` (pydocstyle / Google docstrings) rule family is **not** enabled in Phase 1 to avoid drowning in style violations before type-hint adoption stabilizes; Phase 4 may enable `D` rules at the same time mypy promotes to a hard gate.

### First-run ruff baseline

The Phase 1 harness lands against pre-existing source code that has not been linted before. The first `on-stop.js` run will surface a backlog of ruff findings and mypy errors across `fincli/`, `core/`, `config/`, `logger/`. Both totals will appear in the Stop hook's `systemMessage` — ruff under `issues`, mypy under `warnings` (advisory until Phase 4). This is expected and is the calibration baseline for Phase 2 cleanup; it does not block work. Sweeping the backlog down is opportunistic — fix what you touch, defer the rest.

## Phased Roadmap

This section is the source of truth for *when* the deferred test work happens. All three phases are tracked, not informal — this is by design (the user explicitly flagged the risk of "deferred test work" silently disappearing).

### Phase 2 — Introduce pytest test suite

**Trigger:** after Phase 1 (this commit's harness) ships and stabilizes.

**Scope:**

- Real `pytest` tests under `tests/unit/`, `tests/domain/`, `tests/e2e/`.
- One test file per module listed in `tests/` layout above.
- HTML fixture for the Finviz parser.
- Add type hints incrementally to the modules being tested — this is the natural moment to drive the mypy advisory count down.

**Out of scope for Phase 2:**

- `logger/` (Singleton plumbing; low value, hard to test).
- Live E2E tests against real Finviz (gated behind an env var when added).

**Definition of Done:**

- `pytest tests/` passes locally and inside `on-stop.js`.
- At least one test exists per module listed in the layout.
- Tracking issue or follow-up spec at `docs/superpowers/specs/<future-date>-pytest-suite-bootstrap-spec.md`.

### Phase 3 — Enable coverage gate

**Trigger:** after Phase 2 establishes a meaningful baseline test suite.

**Scope:**

- In `.claude/hooks/on-stop.js`, change `runCoverageCheck` from the Phase 1 stub (`{skipped: true, reason: "Phase 3 deferred — no coverage threshold yet"}`) to an actual `pytest --cov=...` invocation that compares the result to the 90% threshold.
- Update `TESTING.md` (this file's "Coverage" section) to document the enforced threshold.
- Update `agents/roles/verifier.md` to flip the coverage row from "deferred" to **90%**.
- Update `agents/rules/_shared-workflow.md` VERIFIER block similarly.

**Definition of Done:**

- `on-stop.js` blocks Stop when coverage drops below 90%.
- `TESTING.md` lists the enforced threshold and rationale.
- Tracking spec at `docs/superpowers/specs/<future-date>-coverage-gate-enable-spec.md`.

### Phase 4 — Promote mypy from warning to gate

**Trigger:** when `mypy fincli core config logger` returns zero errors.

**Scope:**

- In `.claude/hooks/on-stop.js`, move the mypy result from the `warnings` channel to the `issues` channel.
- In `.claude/hooks/post-edit.js`, treat mypy errors on the just-edited file as blocking, not advisory.
- Update `agents/roles/verifier.md` to list mypy as a hard gate.
- Update `agents/rules/_shared-workflow.md` VERIFIER block similarly.
- Update `TESTING.md` to document the new policy.
- Decide whether to enable ruff `D` rules (Google docstring enforcement) at the same time.

**Definition of Done:**

- `mypy fincli core config logger` returns zero errors.
- `on-stop.js` and `post-edit.js` treat mypy as blocking.
- A new session running `on-stop.js` against a deliberately-mistyped local edit fails the gate.
- Tracking spec at `docs/superpowers/specs/<future-date>-mypy-promote-to-gate-spec.md`.

The phases are sequenced because Phase 4's trigger condition (zero mypy errors) is achieved naturally by the type-hint adoption that Phase 2 produces; promoting mypy to a gate on its own merit is cleaner than smuggling the flip into a test-introduction PR.

## When Tests Land — Useful Conventions

When Phase 2 starts, the following conventions are recommended (matching the broader "tests verify behavior, not implementation" stance above):

- **Test name pattern**: `test_<unit_under_test>_<scenario>` — e.g., `test_convert_market_cap_billions_returns_float`, `test_build_query_handles_empty_filter_tuple`, `test_json_to_tuples_raises_on_malformed_input`.
- **Class grouping**: optional. Use `class TestConvertMarketCap:` only when several tests share fixtures or setup, not as default.
- **Assertions**: prefer plain `assert` over an assertion library. Use `pytest.approx` for floating-point comparisons. Default tolerance for ratio math: `rel=1e-6`.
- **Parametrization**: `@pytest.mark.parametrize` for table-style cases. Each row is a `pytest.param(input, expected, id="<short label>")` so the test ID is human-readable.

## Known Gaps

- **No tests today.** Phase 2 lands them. Don't write tests in Phase 1 unless you are also writing the test infrastructure (fixtures, conftest, recorded HTML) — half a test suite is worse than none.
- **External services drift.** Finviz HTML can change without notice. The mocking strategy isolates unit/domain tests from drift, but E2E tests against recorded fixtures will need refreshing periodically. When a fixture goes stale, replace it with a fresh recording.
- **Singleton logger pollution.** When tests start running in parallel, the Singleton may leak handlers between tests. The fix is a `tests/conftest.py` autouse fixture that resets the Singleton between tests; add this when it actually causes a flake, not preemptively.
