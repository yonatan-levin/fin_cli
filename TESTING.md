# TESTING.md - Fin CLI Testing Strategy

This document defines the testing strategy, conventions, and follow-up roadmap for Fin CLI.

## Philosophy

Tests verify **behavior**, not implementation. A test that locks in the current implementation of a function (mocking out internals, asserting call counts on private helpers) becomes a tax to pay every time the function is refactored, even when behavior is unchanged. A test that asserts what the function *does* — input goes in, output comes out, side effect happens — survives refactors and earns its keep.

This codebase currently has **zero test bodies**. The `tests/` folder structure (`tests/unit/`, `tests/domain/`, `tests/e2e/`) exists from a prior reorganization, but `__pycache__` is the only surviving artifact of the old test files. **Phase 2** of the agent-harness rollout (`docs/superpowers/specs/2026-05-02-agent-harness-replication-design.md`, §8.1) is the work item that introduces real tests. Until that ships, `pytest tests/` runs cleanly because there is nothing to fail — and that is the intentional starting state, not a gap to backfill in Phase 1.

When tests do land, they should:

1. **Validate behavior at module boundaries.** A test for `equity_calc.adjust_assets` checks that the right dollar amount comes out for a given balance-sheet input — not which intermediate variables get assigned in what order.
2. **Use mocks only at the system boundary.** Mock `cfscrape.create_scraper()`, mock `yahooquery.Ticker(...)`, mock the filesystem when verifying CSV writes. Do not mock pandas, do not mock Pydantic, do not mock the Singleton logger.
3. **Run fast.** Unit tests should complete in well under a second each; the full suite (when it exists) should sit comfortably in a CI step.

## Layout

```
tests/
  conftest.py                          # shared pytest fixtures (Phase 2)
  unit/                                # function-level: per-function in isolation
    conftest.py
    test_market_cap_conversion.py      # convert_market_cap_to_numeric
    test_query_builder.py              # build_stock_screener_query
    test_equity_calc.py                # adjust_assets, calculate_price_to_data, ratio_between_two_values
    test_filters.py                    # Filters fluent chain
    test_json_to_tuples.py             # json_to_tuples
    test_config.py                     # Config + build_config
  domain/                              # module-level: per-module behavior
    conftest.py
    test_screening_pipeline.py         # fincli main: query -> fetch (mocked) -> parse -> DataFrame
    test_picker_pipeline.py            # fundainsight picker: enrich (mocked) -> ratios -> filters
    test_configurator_history.py       # filter_history.json round-trip
  e2e/                                 # CLI-level: invoke `python -m <mode>` with fixtures
    conftest.py
    fixtures/
      finviz_sample.html               # recorded Finviz HTML
      yahoo_balance_sheet.json         # recorded yahooquery balance sheet
      yahoo_summary_detail.json
      yahoo_key_stats.json
      yahoo_history_1mo.csv
    test_fincli_invocation.py
    test_fundainsight_invocation.py
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
pytest -k "filter_countries and not e2e"

# Stop at first failure (handy when iterating)
pytest -x

# Verbose
pytest -v

# Coverage (informational — not enforced in Phase 1)
pytest --cov=fundainsight --cov=fincli --cov=core --cov=config --cov-report=term-missing
```

The `-ra` default in `[tool.pytest.ini_options]` (see `pyproject.toml`) ensures a short summary of skipped, xfailed, and errored tests prints at the end of every run.

## Fixture Conventions

Each test layer has its own `conftest.py`. Shared cross-layer fixtures live in the top-level `tests/conftest.py`.

**Recommended fixtures (Phase 2 scope):**

```python
# tests/conftest.py

@pytest.fixture
def sample_screening_df():
    """DataFrame mimicking fincli stock screening output."""
    return pd.DataFrame({
        "Symbol":      ["AAPL", "MSFT", "GOOGL"],
        "Ticker":      ["AAPL", "MSFT", "GOOGL"],
        "Sector":      ["Technology"] * 3,
        "Country":     ["USA"] * 3,
        "Market Cap":  [2_890_000_000_000, 2_800_000_000_000, 1_700_000_000_000],
    })

@pytest.fixture
def sample_financial_data():
    """Dict matching get_financial_data()'s return schema (CONTRACTS.md §3)."""
    return {
        "Symbol": "AAPL",
        "Market Cap": 2_890_000_000_000,
        "Shares Outstanding": 15_800_000_000,
        "Total Assets": 352_583_000_000,
        "Adjusted Total Assets": 300_000_000_000,
        "Adjusted Total Current Assets": 100_000_000_000,
        "Total Equity": 62_146_000_000,
        "Average Price in Last 30 Days": 182.50,
    }

@pytest.fixture
def finviz_sample_html():
    """Recorded Finviz HTML fixture for the screener parser."""
    return Path("tests/e2e/fixtures/finviz_sample.html").read_bytes()

@pytest.fixture
def yahoo_balance_sheet_df():
    """Recorded yahooquery balance_sheet DataFrame."""
    return pd.read_json("tests/e2e/fixtures/yahoo_balance_sheet.json")
```

Fixture rules of thumb:

- **JSON / HTML fixture files** live under `tests/e2e/fixtures/`. They are real recorded responses, redacted of any secrets (there are no secrets in Finviz / Yahoo public data, but the convention applies anyway).
- **One fixture, one fact.** A fixture that builds an entire 200-row DataFrame is doing too much; split into smaller, named fixtures composed via `@pytest.mark.parametrize`.

## Mocking Strategy

### What to mock

- **`cfscrape.create_scraper()`** — never make real HTTP calls in unit/domain tests. Use the [`responses`](https://github.com/getsentry/responses) library or [`vcrpy`](https://vcrpy.readthedocs.io) (recorded interactions) at the I/O boundary. Both are well-suited; pick one in Phase 2 and use it consistently.
- **`yahooquery.Ticker`** — patch at the import site (`fundainsight.calculators.equity_calc.yq.Ticker`) with `unittest.mock.patch`. Return a `MagicMock` configured to mirror the four shapes documented in `CONTRACTS.md` §3 (balance_sheet, summary_detail, key_stats, history).
- **Filesystem writes for CSV** — use the `tmp_path` fixture (built into pytest) so each test gets an isolated temp directory.

### What NOT to mock

- **pandas DataFrame operations.** pandas is fast and deterministic; mocking it produces tests that no longer test anything real.
- **Pydantic validation.** Pydantic *is* the validation contract. If a test wants to verify "this config is invalid", it should construct an invalid `Config` and let Pydantic raise.
- **Filter chain logic in `fundainsight/calculators/filters.py`.** The whole point of the chain is the chained behavior; mocking link-by-link defeats the test.
- **The Singleton logger.** Let it write into the test's temp directory or a `caplog` fixture. Resetting the Singleton between tests is best handled via a fixture in `tests/conftest.py` if test pollution turns out to be an issue (likely once Phase 2 expands).

### Example

```python
from unittest.mock import patch, MagicMock
import pandas as pd
import pytest

@patch("fundainsight.calculators.equity_calc.yq.Ticker")
def test_get_financial_data_happy_path(mock_ticker_class, sample_financial_data):
    mock_ticker = MagicMock()
    mock_ticker_class.return_value = mock_ticker

    mock_ticker.balance_sheet.return_value = pd.DataFrame({
        "TotalAssets":          [None, 352_583_000_000],
        "CurrentAssets":        [None, 143_566_000_000],
        "OtherCurrentAssets":   [None, 14_695_000_000],
        "Goodwill":             [None, 0],
        "OtherNonCurrentAssets":[None, 52_583_000_000],
        "Inventory":            [None, 6_511_000_000],
        "StockholdersEquity":   [None, 62_146_000_000],
    })
    mock_ticker.summary_detail = {"AAPL": {"marketCap": 2_890_000_000_000}}
    mock_ticker.key_stats      = {"AAPL": {"sharesOutstanding": 15_800_000_000}}
    mock_ticker.history.return_value = pd.DataFrame({"close": [180.0, 185.0, 182.5]})

    from fundainsight.calculators.equity_calc import get_financial_data
    result = get_financial_data("AAPL")
    assert result is not None
    assert result["Symbol"] == "AAPL"
    assert result["Market Cap"] == 2_890_000_000_000
```

## Coverage

**Coverage is deferred to Phase 3** of the harness rollout (`docs/superpowers/specs/2026-05-02-agent-harness-replication-design.md`, §8.2).

In Phase 1 (now):

- `pytest-cov` is installed in dev dependencies so the tooling is ready.
- `pytest --cov=fundainsight --cov=fincli ...` runs and produces a report — but the value is informational only. There is no threshold, and `.claude/hooks/on-stop.js` does not enforce one.

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
files = ["fundainsight", "fincli", "core", "config", "logger"]
strict = true

[[tool.mypy.overrides]]
module = ["cfscrape", "cfscrape.*", "yahooquery", "yahooquery.*"]
ignore_missing_imports = true
```

`bs4` is typed via the `types-beautifulsoup4` dev dep, which is cleaner than an override.

The codebase has very few type hints today, so `strict = true` produces hundreds of errors. **In Phase 1, mypy results surface through the `warnings` channel of `on-stop.js`, NOT the `issues` channel.** That means:

- The user sees the running error count after every Stop event.
- The user is not blocked from finishing a session by mypy errors.
- The advisory pressure encourages adding type hints to whatever module is being touched, without forcing a giant up-front type-hint sprint.

**Phase 4** of the harness rollout (`docs/superpowers/specs/2026-05-02-agent-harness-replication-design.md`, §8.3) flips mypy from advisory `warnings` to a hard `issues` gate once `mypy fundainsight fincli core config logger` reports zero errors. The trigger condition is concrete: zero errors. Until then, the gap is visible but does not block work.

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

## Phased Roadmap

This section is the source of truth for *when* the deferred test work happens. All three phases are tracked, not informal — this is by design (the user explicitly flagged the risk of "deferred test work" silently disappearing).

### Phase 2 — Introduce pytest test suite

**Trigger:** after Phase 1 (this commit's harness) ships and stabilizes.

**Scope:**

- Real `pytest` tests under `tests/unit/`, `tests/domain/`, `tests/e2e/`.
- One test file per module listed in `tests/` layout above.
- HTML fixture for the Finviz parser.
- `yahooquery.Ticker` mock fixtures for the picker pipeline.
- Add type hints incrementally to the modules being tested — this is the natural moment to drive the mypy advisory count down.
- **Fix the `equity_calc.adjust_assets` `not int` bug** as part of writing its test (write the regression test that pins current behavior, then fix the bug, then update the test to pin corrected behavior).

**Out of scope for Phase 2:**

- `wisdom_fruit/` (experimental).
- `logger/` (Singleton plumbing; low value, hard to test).
- Live E2E tests against real Finviz / Yahoo (gated behind an env var when added).

**Definition of Done:**

- `pytest tests/` passes locally and inside `on-stop.js`.
- At least one test exists per module listed in the layout.
- The `adjust_assets` bug is fixed and pinned by a regression test.
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

**Trigger:** when `mypy fundainsight fincli core config logger` returns zero errors.

**Scope:**

- In `.claude/hooks/on-stop.js`, move the mypy result from the `warnings` channel to the `issues` channel.
- In `.claude/hooks/post-edit.js`, treat mypy errors on the just-edited file as blocking, not advisory.
- Update `agents/roles/verifier.md` to list mypy as a hard gate.
- Update `agents/rules/_shared-workflow.md` VERIFIER block similarly.
- Update `TESTING.md` to document the new policy.
- Decide whether to enable ruff `D` rules (Google docstring enforcement) at the same time.

**Definition of Done:**

- `mypy fundainsight fincli core config logger` returns zero errors.
- `on-stop.js` and `post-edit.js` treat mypy as blocking.
- A new session running `on-stop.js` against a deliberately-mistyped local edit fails the gate.
- Tracking spec at `docs/superpowers/specs/<future-date>-mypy-promote-to-gate-spec.md`.

The phases are sequenced because Phase 4's trigger condition (zero mypy errors) is achieved naturally by the type-hint adoption that Phase 2 produces; promoting mypy to a gate on its own merit is cleaner than smuggling the flip into a test-introduction PR.

## When Tests Land — Useful Conventions

When Phase 2 starts, the following conventions are recommended (matching the broader "tests verify behavior, not implementation" stance above):

- **Test name pattern**: `test_<unit_under_test>_<scenario>` — e.g., `test_convert_market_cap_billions_returns_float`, `test_filter_countries_excludes_all_listed`, `test_get_financial_data_returns_none_when_balance_sheet_missing`.
- **Class grouping**: optional. Use `class TestConvertMarketCap:` only when several tests share fixtures or setup, not as default.
- **Assertions**: prefer plain `assert` over an assertion library. Use `pytest.approx` for floating-point comparisons. Default tolerance for ratio math: `rel=1e-6`.
- **Parametrization**: `@pytest.mark.parametrize` for table-style cases. Each row is a `pytest.param(input, expected, id="<short label>")` so the test ID is human-readable.

## Known Gaps

- **No tests today.** Phase 2 lands them. Don't write tests in Phase 1 unless you are also writing the test infrastructure (fixtures, conftest, recorded HTML/JSON) — half a test suite is worse than none.
- **`equity_calc.adjust_assets` has a known bug** (`not int` is always `False`; the second branch always runs). Phase 2 captures this in a regression test, then fixes it.
- **External services drift.** Finviz HTML and Yahoo Finance JSON shapes can change without notice. The mocking strategy isolates unit/domain tests from drift, but E2E tests against recorded fixtures will need refreshing periodically. When a fixture goes stale, replace it with a fresh recording.
- **Singleton logger pollution.** When tests start running in parallel, the Singleton may leak handlers between tests. The fix is a `tests/conftest.py` autouse fixture that resets the Singleton between tests; add this when it actually causes a flake, not preemptively.
