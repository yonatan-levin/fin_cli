# TESTING.md - Fin CLI Testing Strategy

This document defines the testing strategy, conventions, and follow-up roadmap for Fin CLI.

## Philosophy

Tests verify **behavior**, not implementation. A test that locks in the current implementation of a function (mocking out internals, asserting call counts on private helpers) becomes a tax to pay every time the function is refactored, even when behavior is unchanged. A test that asserts what the function *does* — input goes in, output comes out, side effect happens — survives refactors and earns its keep.

The test suite uses a three-tier pyramid: `tests/unit/` (mocked at boundaries), `tests/integration/` (real fincli + mocked Finviz HTML fixtures), `tests/e2e/` (live Finviz HTTP, opt-in via `pytest -m live`). Each tier has a `tests/<tier>/api/` sub-directory mirroring the layout for `fincli_api/`. Current state: 302 passed / 3 deselected (live tier) / 1 xfailed (MAJOR #4 deferred) on the default `pytest tests/` invocation. The config-driven aggregate run reports 94% coverage. `pytest -m live tests/e2e/api/` runs the 3 live-Finviz API smoke tests (~3s, network-dependent).

When tests do land, they should:

1. **Validate behavior at module boundaries.** A test for `convert_market_cap_to_numeric` checks that the right numeric value comes out for a given Finviz string input — not which intermediate variables get assigned in what order.
2. **Use mocks only at the system boundary.** Mock `cfscrape.create_scraper()`, mock the filesystem when verifying CSV writes. Do not mock pandas, do not mock Pydantic, do not mock the Singleton logger.
3. **Run fast.** Unit tests should complete in well under a second each; the full suite (when it exists) should sit comfortably in a CI step.

## Layout

Actual layout as of the 2026-05-16 pipeline-mode shipping cycle:

```
tests/
  unit/                                # function-level: per-function in isolation
    app/
      test_cli.py                      # back-compat regression seed (Task 1)
      test_cli_output.py               # --output / -o option parsing
      test_cli_pipeline.py             # structured input options (Pillar 1)
      test_exit_codes.py               # classify() per exception family
    cli/
      test_cli_stock_screener.py       # interactive picker + writeback fix
    configuration/
      test_configurator_filters.py     # build_config(filters=...) wiring
      test_output_path.py              # Config.file_path precedence + env var
    converters/
      test_json_to_tuples.py           # strict dict-only schema
    logger/
      test_stream_routing.py           # set_console_stream / set_quiet
    resource/params/
      test_validators.py               # unknown key/value rejection
    utils/
      test_market_cap.py               # convert_market_cap_to_numeric contract
  integration/                         # CLI-level: invoke run_main with mocked fetch
    _fixtures_loader.py                # shared loader for canned HTML
    fixtures/
      finviz_happy.html                # one valid row
      finviz_empty.html                # table present, no rows
      finviz_no_table.html             # missing table element
      finviz_malformed_row.html        # row without link anchor (-> DATA exit 4)
    test_pipeline_streaming.py         # --output - stream discipline
    test_pipeline_summary.py           # --json-summary schema
    test_pipeline_ticker_carveout.py   # Ticker/Symbol carve-out (spec §5.6)
    test_pipeline_exit_codes.py        # end-to-end classifier (exit 3, 4, 1)
    test_zero_row_success.py           # header-only CSV on zero-row result
```

No `__init__.py` files anywhere under `tests/` (deliberate — keeps pytest's
rootdir-based test collection working). The integration suite's shared
helper module is `tests/integration/_fixtures_loader.py` (leading
underscore so pytest does not collect it as a test module). Tests import
it directly as `from _fixtures_loader import finviz_happy_html` —
relies on pytest putting each test file's parent directory on
`sys.path` when no package marker is present.

The Phase-2-era three-layer plan (unit / domain / e2e) collapsed during
the pipeline-mode rollout into the two-layer **unit + integration**
shape above:

- **Unit** — one function or one module's public surface in isolation. No
  HTTP, no real CSV writes (use `tmp_path` when filesystem assertions
  are required). Real pandas, real Pydantic, real Singleton logger.
- **Integration** — drives the full Click entry point via Click's
  `CliRunner`. ``fincli.utils.web_scraper.fetch_page_sync`` is mocked at
  the orchestrator boundary so no real HTTP fires. CSV writes go to
  `tmp_path`-provided directories; stdout streaming is captured via
  `CliRunner`'s `Result.stdout` / `result.stderr` separation (Click 8.2+).

## Running Tests

```bash
# Everything
pytest tests/

# Layer-scoped
pytest tests/unit/
pytest tests/integration/
pytest tests/e2e/

# Pattern match by name
pytest -k "market_cap"
pytest -k "build_query and not e2e"

# Stop at first failure (handy when iterating)
pytest -x

# Verbose
pytest -v

# Blocking aggregate coverage gate (same command used by the Stop hook)
pytest tests/ --cov --cov-report=term-missing
```

The `-ra` default in `pytest.ini` ensures a short summary of skipped, xfailed,
and errored tests prints at the end of every run.

## Fixture Conventions

Each test layer has its own `conftest.py`. Shared cross-layer fixtures live in the top-level `tests/conftest.py`.

**Recommended fixtures:**

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

- **`fincli.utils.web_scraper.fetch_page_sync`** — the seam for the integration suite. Patch with `unittest.mock.patch("fincli.app.main.fetch_page_sync", ...)` (patch the import site, since the orchestrator imports `fetch_page_sync` at module-load time). Either `side_effect=` for raising-exception scenarios (UPSTREAM tests) or `return_value=<canned-html-bytes>` for happy/zero-row/parse-failure scenarios. `cfscrape.create_scraper()` is **never** invoked in tests as a consequence — the seam is one layer up.
- **Filesystem writes for CSV** — use the `tmp_path` fixture (built into pytest) so each test gets an isolated temp directory.

### Pipeline mode tests

The pipeline-mode shipping cycle introduced the `tests/integration/` directory and a shared canned-HTML fixture set under `tests/integration/fixtures/`. The integration tests are CliRunner-driven end-to-end runs through the full Click entry point with `fetch_page_sync` mocked at the orchestrator boundary; assertions target `result.stdout` / `result.stderr` / `result.exit_code` / the contents of the file written under `tmp_path`.

Four canned HTML fixtures exist (loaded via `tests/integration/_fixtures_loader.py`):

| Fixture | Purpose |
|---|---|
| `finviz_happy.html` | One valid row with a working link anchor — drives the happy-path tests. |
| `finviz_empty.html` | Table present, empty `<tbody>` — drives the zero-row success branch (header-only CSV, exit 0). |
| `finviz_no_table.html` | Page without the screener table element — `all_table_content` returns empty list. |
| `finviz_malformed_row.html` | Row with a non-anchor cell where the parser expects `<a href=...>` — drives the DATA classifier (exit 4 via `AttributeError`). |

To add a new pipeline-mode integration test:

1. Add the fixture file under `tests/integration/fixtures/` if a new HTML shape is needed.
2. Add a loader function in `tests/integration/_fixtures_loader.py` matching the existing pattern.
3. Write the test in a new or existing `test_pipeline_*.py` file under `tests/integration/`. Use `CliRunner().invoke(run_main, [...], catch_exceptions=False)`.
4. Assert on `result.exit_code` (using constants from `fincli.app.exit_codes`, not hardcoded integers), `result.stdout`, `result.stderr`, and `tmp_path` contents.

### List-filters tests

The list-filters feature (shipped 2026-05-21; spec at `docs/features/archive/list-filters-spec.md`) added three new test files that follow the existing layout convention: `tests/unit/resource/params/test_label_format.py` parametrizes the `attr_to_label` mechanical-label-derivation algorithm; `tests/unit/app/test_cli_list_filters.py` pins the Click surface for `--list-filters` / `--json` (option-presence, the `--json`-required usage error, the silent-ignore behavior of bare `--json` per spec OQ2, mutex with each input mode, orthogonal-flag no-ops, and the integrated OQ-B/C/D matrix test that locks the short-circuit ordering); `tests/integration/test_list_filters_output.py` subprocess-invokes `python -m fincli --list-filters --json` and validates the JSON-inventory schema (CONTRACTS §5.6) end-to-end. The inventory dump short-circuits the screener pipeline, so no `fetch_page_sync` mock or HTML fixture is needed — the unit tests use `CliRunner` directly and the integration test uses `subprocess.run`.

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

## API tests (fincli_api/)

The API has a 3-tier test pyramid mirroring the spec §6 structure (`docs/superpowers/specs/archive/2026-05-22-fincli-api-design.md`):

| Tier | Path | What's mocked | What's real | Target speed |
|---|---|---|---|---|
| Unit | `tests/unit/api/` | adapter (`fincli_api.adapters.fincli` functions) | FastAPI routes, Pydantic validation, error envelope | <500ms |
| Integration | `tests/integration/api/` | `fincli.app.main.fetch_page_sync` (HTTP boundary) | Adapter, fincli orchestrator, BS4 parsing | <3s |
| E2E | `tests/e2e/api/` | nothing | Full stack: API -> fincli -> live Finviz | <30s |

### Default invocation excludes live tier

`pytest tests/` skips the live tier via `pytest.ini`'s `addopts = -q -ra -m "not live"`. Explicit `pytest -m live tests/e2e/api/` runs the 3 live-Finviz smoke tests.

### Conftest patterns

**Both unit and integration conftests use `TestClient(app, raise_server_exceptions=False)`**. Starlette's default re-raises exceptions through middleware in tests, which bypasses our `@app.exception_handler(Exception)`. Without the override, every test that triggers a handler-mapped exception sees the raw exception instead of the JSONResponse envelope.

**Mock target rule** (T3 BACKEND surprise): integration tier patches `fincli.app.main.fetch_page_sync`, NOT `fincli.utils.web_scraper.fetch_page_sync`. The former is the local-name binding via `from ... import fetch_page_sync` in `main.py`; patching the original location doesn't affect what `main.py` already imported. (Same rule as the pipeline-mode integration suite — see "Mocking Strategy" above.)

### MAJOR #4 deferred limitation

`tests/integration/api/test_screens_integration.py` pairs a `@pytest.mark.xfail(strict=True)` test (spec-intent: 502 parsing) with a current-behavior pin test (actual: 200 empty) for the `finviz_no_table.html` fixture. Closing MAJOR #4 (malformed HTML -> 502) will mechanically trip both tests in the same commit — forcing a coordinated code + test + docs update. See `fincli_api/exception_handlers.py` module docstring for the deferred rationale.

### Pre-PR live-Finviz gate

Per FEEDBACK-LOG.md 2026-05-22 + 2026-05-24 entries, `pytest -m live tests/e2e/api/` is MANDATORY before HUMAN approval on any change to `fincli_api/` or `fincli/stock_screening/`. The umbrella's near-miss (1-page IndexError that shipped because mocked tests didn't exercise the live path) is the durable rationale.

## Blocking quality gates

The Stop hook enforces all four code-quality gates:

| Gate | Command / policy |
|---|---|
| Lint | `ruff check .` |
| Format | `ruff format --check .` |
| Types | Bare `mypy`, with the complete shipped scope configured in `pyproject.toml` and `strict = true` |
| Coverage | Aggregate runtime coverage at least 90% across `fincli`, `fincli_api`, `core`, `config`, `logger`, and `singleton` |

The default pytest suite is also blocking. Coverage runs separately so a test
failure and a threshold regression remain distinguishable in hook output.

### Coverage

Coverage is aggregate, not per-package. Every shipped runtime module is named in
the command; no low-coverage package is silently excluded. Tests must validate
behavior at a boundary—adding execution-only padding to satisfy the percentage
is not acceptable.

### Type checking

Mypy is strict and blocking. The `cfscrape` override remains because that
library publishes no usable type information; BeautifulSoup, pandas, and
colorama use installed stubs. `fincli_api` is part of the same gate as the CLI.

The post-edit hook surfaces a per-file mypy failure immediately. Because
PostToolUse runs after an edit, the Stop hook is the authoritative blocker that
prevents an unresolved type regression from completing the session.

### Lint and format

```bash
ruff check .
ruff check --fix .
ruff format .
ruff format --check .
```

The lint family remains `["E", "F", "W", "I", "B", "UP", "N", "SIM"]`.
Pydocstyle (`D`) is deliberately not enabled by the quality-gate burn-down; it
would require a separate migration decision.

## Test authoring conventions

- Name tests `test_<unit_under_test>_<scenario>`.
- Use classes only when cases genuinely share setup.
- Prefer plain `assert`; use `pytest.approx` for floating-point behavior.
- Use `pytest.mark.parametrize` for table-shaped behavior with readable IDs.
- Keep mocks at I/O boundaries; do not mock pandas or Pydantic.

## Known limitations

- Finviz HTML can change without notice. Recorded fixtures isolate the default
  suite; refresh them deliberately when the upstream contract changes.
- The malformed-HTML no-table case remains the documented MAJOR #4 xfail pair.
- The Singleton logger can leak handler state if future parallel tests stop
  restoring it; add a reset fixture only if that failure materializes.
