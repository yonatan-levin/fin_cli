> **SHIPPED 2026-05-11** — Feature restored. CLI plumbing landed in `fincli/app/cli.py`, configurator threads `scrape_link` through `build_config`, `run_stock_screener` short-circuits the interactive picker when the URL is set, `--history` + `--scrape-link` are rejected as mutually exclusive, CONTRACTS §1 + §6 re-document the surface, and `tests/unit/app/test_cli.py` pins both regression cases. See the 2026-05-11 entry in `docs/FEEDBACK-LOG.md` for the lasting decision record.

---

# Restore `--scrape-link` CLI option — Feature Spec

**Status:** SHIPPED — archived 2026-05-11
**Date opened:** 2026-05-11
**Severity:** HIGH (sole user; bypass-the-interactive-flow is a major productivity feature; documented in 5 doc surfaces but CLI plumbing missing)
**Related QA triage:** in-session 2026-05-11 (root cause: commit `a840a1c` incidental loss)
**Sets convention for:** `docs/features/` directory — first entry; follows the `<topic>-spec.md` naming used by `docs/refactoring/`. Ships → moves to `docs/features/archive/` with a Shipped banner.

---

## Goal

Restore the `--scrape-link=<url>` Click option that was incidentally removed during the 2026-05-04 single-mode refactor. The option lets the user pass a Finviz screener URL directly and bypass the three-section interactive filter UI. Today, `Config.scrape_link: str = ""` field exists and is documented as part of the Config contract, but no CLI plumbing populates it — running `./run.bat --scrape-link=<url>` gives `Error: No such option: --scrape-link`.

**Goals:**
- Add `--scrape-link` as a Click option on `fincli/app/cli.py:run_main` with the historical semantics (non-empty URL → use verbatim; empty/default → current interactive flow).
- Thread the value from CLI → `build_config(scrape_link=...)` → `Config.scrape_link` → screener pipeline.
- Make `--scrape-link` and `--history` mutually exclusive (alternative input modes; using both is undefined).
- Update `CONTRACTS.md` §1 to re-document the option.
- Append a `docs/FEEDBACK-LOG.md` entry recording the restoration.
- Add a minimal regression test (Phase 2 scaffolding seed — section-scoped Click `CliRunner` test).

**Non-goals:**
- Restoring the sibling `--set-filters` JSON-input option (also lost in `a840a1c`). Tracked separately in `docs/reviewer/` if the user wants it.
- Fixing the unrelated `scripts/check_requirements.py` `pkg_resources` AttributeError on Python 3.12+. Separate bug.
- Adding full Phase 2 test infrastructure (fixtures, conftest, HTTP cassettes). Only the one regression test for this fix lands here.

---

## Background (from QA triage)

The historical Click decorator lived on `fundainsight/app/cli.py` (commit `3eb9228`, Oct 2023):

```python
@click.option('--scrape-link', default="", help='Set the scrape link to be used.')
def run_main(ctx, history=False, debug=False, set_filters="", scrape_link=""):
    if ctx.invoked_subcommand is None:
        get_opportunities(history=history, debug=debug, set_filters=set_filters, scrape_link=scrape_link)
```

And the consumer in `fundainsight/app/fincli.py`:

```python
def get_recommended_stocks(filters: tuple, scrape_link: str = ""):
    if scrape_link == "":
        quarry = build_stock_screener_query(filters)
    else:
        quarry = scrape_link
```

Commit `a840a1c` ("refactor: remove fundainsight package and yahooquery dependency", 2026-05-05) deleted the entire `fundainsight/` package, taking the decorator with it. The fincli-side `fincli/app/cli.py` never carried `--scrape-link` — so this is feature *restoration on a different entry point*, not a true revert. The May-4 reduction spec and FEEDBACK-LOG say nothing about removing the feature deliberately — strong evidence it was incidental, supported by:
- `Config.scrape_link: str = ""` field still exists (`config/config.py:20`)
- `CONTRACTS.md` §4, `ARCHITECTURE.md`, `README.md`, `docs/MODULE_REFERENCE.md` all describe the field
- No commit removed `Config.scrape_link` deliberately

---

## Resolved decisions (defaults — push back if you disagree)

| # | Question | Decision | Reason |
|---|---|---|---|
| 1 | Restore the historical semantics? | **Yes** — non-empty URL → use verbatim, skip query-builder + interactive UI | Matches documented `Config.scrape_link` contract and the historical fundainsight implementation |
| 2 | Mutual exclusion with `--history`? | **Yes** — emit a Click error if both are set | Alternative input modes; using both is undefined. Historical fundainsight didn't enforce this; new code should. Implementation: Click `callback` on `--scrape-link` that checks `ctx.params['history']` (or a wrapper validation in `run_main`) |
| 3 | Restore sibling `--set-filters`? | **No** — defer to a follow-up reviewer note | User didn't report it; strict scope adherence. Open `docs/reviewer/set-filters-restoration.md` documenting the parallel loss. Decide separately. |
| 4 | Add a regression test? | **Yes** — minimal single-file `tests/unit/app/test_cli.py` using Click `CliRunner` | The /debug skill mandates regression tests. This is the smallest possible test; doubles as the first seed of Phase 2's adaptive-e2e test scaffolding ("section-scoped e2e" on the CLI option-parsing layer, matching the Phase 2 strategy you approved). No fixture infrastructure needed — `CliRunner` is built into Click. |
| 5 | Commit shape | Single atomic commit: code + CONTRACTS doc + FEEDBACK-LOG entry + the one test file + spec → archive | Mirrors the prior cycle pattern; preserves audit trail in one place |
| 6 | URL validation? | **No** — accept any string; let cfscrape report HTTP failures downstream | Pre-validating the URL adds surface for no real benefit; the user can already pass garbage interactively. Trust at the boundary. |
| 7 | Help text content | `Direct Finviz screener URL; bypasses interactive filter selection. Mutually exclusive with --history.` | Discoverable via `--help`; documents both the semantics and the mutual-exclusion constraint |

---

## Architecture

### File touches

| File | Change |
|---|---|
| `fincli/app/cli.py` | Add `@click.option('--scrape-link', default="", help='...')` decorator on `run_main`. Add `scrape_link: str = ""` parameter. Add mutual-exclusion check (if both `history` and `scrape_link` are set → `raise click.UsageError(...)`). Forward to `run_stock_screener(scrape_link=scrape_link)`. |
| `fincli/app/main.py` | `run_stock_screener(history, debug)` signature gains `scrape_link: str = ""`. Pass to `build_config(use_history=history, scrape_link=scrape_link)`. When `config.scrape_link` is non-empty, short-circuit: use it as the query directly, skip `select_filters_and_values(config)`. |
| `core/configuration/configurator.py` | `build_config(use_history, filters)` signature gains `scrape_link: str = ""`. Assign to `config.scrape_link` if non-empty. |
| `config/config.py` | **No change.** `Config.scrape_link` field already exists. |
| `CONTRACTS.md` §1 | Add `--scrape-link` row to the Options table. Add a Behavior table row describing the bypass semantics + mutual-exclusion constraint. |
| `docs/FEEDBACK-LOG.md` | Append `### 2026-05-11 — Restore --scrape-link CLI option` entry. Captures: incidental loss in `a840a1c`; restoration mechanism; mutual-exclusion decision; sibling `--set-filters` still pending. |
| `tests/unit/app/test_cli.py` | NEW. Single `CliRunner` test asserting `--scrape-link=<url>` is accepted and `Config.scrape_link` is populated. Also a test for the mutual-exclusion `UsageError` when both `--history` and `--scrape-link` are passed. (Plus possibly `tests/unit/app/__init__.py` if needed for collection.) |
| `docs/features/scrape-link-restoration-spec.md` (this file) | Will move to `docs/features/archive/` with Shipped banner once cycle completes. |

### Exact code shape (illustrative)

`fincli/app/cli.py`:
```python
import click


@click.group(invoke_without_command=True)
@click.option('--history', '--hist', is_flag=True, help='Use filters of recent search.')
@click.option('--debug', is_flag=True, help='Display details logging.')
@click.option('--scrape-link', default="", help='Direct Finviz screener URL; bypasses interactive filter selection. Mutually exclusive with --history.')
@click.pass_context
def run_main(ctx: click.Context,
             history: bool = False,
             debug: bool = False,
             scrape_link: str = ""
             ) -> None:
    """
    Welcome to the Stock Screener CLI!
    """
    if history and scrape_link:
        raise click.UsageError("--history and --scrape-link are mutually exclusive; pick one input mode.")
    click.echo("Welcome to the Stock Screener CLI!")
    from .main import run_stock_screener

    if ctx.invoked_subcommand is None:
        run_stock_screener(history=history, debug=debug, scrape_link=scrape_link)
```

`core/configuration/configurator.py`:
```python
def build_config(
    use_history: bool = False,
    filters: str = "",
    scrape_link: str = ""
) -> Config:
    """Create the configuration."""
    config = Config()

    history_dir_env = os.getenv("HISTORY_DIR")
    if history_dir_env:
        config.history_dir = Path(history_dir_env)

    if scrape_link:
        config.scrape_link = scrape_link

    if use_history:
        config.use_history = use_history
        filepath = config.history_dir / 'filter_history.json'
        with open(filepath, 'r') as f:
            filters_data = json.load(f)
            config.filters = tuple(filters_data.items())

    if filters != "" and not use_history:
        config.filters = json_to_tuples(filters)

    return config
```

`fincli/app/main.py` — short-circuit at the query-construction step. The exact insertion point depends on the current structure; BACKEND will inspect and place it correctly. The principle: when `config.scrape_link` is truthy, use it as the URL directly (skip `build_stock_screener_query` and the interactive UI).

`tests/unit/app/test_cli.py`:
```python
from click.testing import CliRunner

from fincli.app.cli import run_main


def test_scrape_link_option_accepted():
    """--scrape-link=<url> is parsed and forwarded; CLI exits 0 if downstream succeeds."""
    runner = CliRunner()
    # Use --help to short-circuit the screener call but prove the option parses.
    result = runner.invoke(run_main, ['--scrape-link=https://finviz.com/test', '--help'])
    assert result.exit_code == 0
    assert '--scrape-link' in result.output


def test_scrape_link_and_history_mutually_exclusive():
    """Passing both --history and --scrape-link raises UsageError."""
    runner = CliRunner()
    result = runner.invoke(run_main, ['--history', '--scrape-link=https://finviz.com/test'])
    assert result.exit_code != 0
    assert 'mutually exclusive' in result.output.lower()
```

---

## Tasks by Agent

**BACKEND** (single agent — CLI + config plumbing + minimal test):

1. Edit `fincli/app/cli.py`: add the Click option, the mutual-exclusion check, the `scrape_link` parameter, and the forward to `run_stock_screener`.
2. Edit `core/configuration/configurator.py`: add `scrape_link` parameter and populate `config.scrape_link` if non-empty.
3. Edit `fincli/app/main.py`: add `scrape_link` parameter to `run_stock_screener`, pass to `build_config`, and short-circuit the query-construction when `config.scrape_link` is truthy.
4. Create `tests/unit/app/__init__.py` if needed for pytest collection (or confirm not needed for the current pytest config).
5. Create `tests/unit/app/test_cli.py` with the two tests above.
6. Edit `CONTRACTS.md` §1: add `--scrape-link` row to Options table, add Behavior table row, add mutual-exclusion note.
7. Append the 2026-05-11 entry to `docs/FEEDBACK-LOG.md`.
8. Move this spec from `docs/features/scrape-link-restoration-spec.md` to `docs/features/archive/scrape-link-restoration-spec.md` (create the `archive/` subdirectory) with a Shipped banner.
9. Run verification (lint, format, mypy, pytest the new test, fincli --help).

**No FRONTEND, no UX_UI** — CLI plumbing only.

---

## Verification (BACKEND runs these)

```bash
.venv/Scripts/python.exe -m ruff check .                            # expect 199 baseline (may shift slightly if new code adds/removes lint)
.venv/Scripts/python.exe -m ruff format --check .                   # expect 21 baseline
.venv/Scripts/python.exe -m mypy fincli core config logger          # expect 60 baseline or lower
.venv/Scripts/python.exe -m pytest tests/unit/app/test_cli.py -v    # expect 2 passing tests
.venv/Scripts/python.exe -m pytest tests/ --collect-only            # expect 2 tests collected (the new file), 0 errors
.venv/Scripts/fincli.exe --help                                     # expect exit 0; --scrape-link visible in help
.venv/Scripts/fincli.exe --scrape-link=https://finviz.com/test --help
                                                                     # expect exit 0; --help short-circuits the actual run
.venv/Scripts/python.exe -c "from core.configuration.configurator import build_config; c = build_config(scrape_link='https://example.com/x'); print(c.scrape_link)"
                                                                     # expect: https://example.com/x
```

**Do NOT run** `fincli --scrape-link=<real-url>` without `--help` — would trigger an actual Finviz scrape.

---

## Acceptance criteria

- [ ] `fincli --help` shows `--scrape-link` option with the documented help text
- [ ] `fincli --scrape-link=<url>` does not error with "No such option"
- [ ] `fincli --history --scrape-link=<url>` errors with a clear "mutually exclusive" message and non-zero exit code
- [ ] `Config().scrape_link` defaults to `""`; `build_config(scrape_link='https://...').scrape_link` returns the URL
- [ ] Pytest collects and passes the two new tests (`tests/unit/app/test_cli.py::test_scrape_link_option_accepted`, `test_scrape_link_and_history_mutually_exclusive`)
- [ ] Ruff / format / mypy do not regress
- [ ] CONTRACTS.md §1 documents the option + mutual-exclusion behavior
- [ ] FEEDBACK-LOG has the 2026-05-11 restoration entry
- [ ] This spec moves to `docs/features/archive/` with Shipped banner

---

## Risks / Watch-outs

- **Mutual-exclusion check timing.** Click's `@click.pass_context` passes `ctx` after option parsing. The simplest check is inline in `run_main` body (as drafted above). A more Click-idiomatic approach is a `callback` on `--scrape-link` that checks `ctx.params`, but at callback time the other option may not have been parsed yet (depends on declaration order). Inline check is more robust; BACKEND should keep it inline.
- **Empty-string vs None semantics.** `click.option(default="")` means an unpassed flag yields `""` (truthy-check-safe). Don't change to `default=None` without updating the downstream `if scrape_link:` check.
- **Pytest collection.** The new `tests/unit/app/test_cli.py` will be the *first* real test file in the repo. `pytest.ini` / `pyproject.toml [tool.pytest.ini_options]` already declare `testpaths = ["tests"]`, so collection should just work. Confirm during verification.
- **Mypy on the new test file.** Click's `CliRunner` is typed (Click ships type info). Mypy may or may not include the test file in its scan depending on `[tool.mypy] files`. Today's config is `files = ["fincli", "core", "config", "logger"]` — does NOT include `tests/`. So no new mypy delta expected from the test file.
- **`fincli/app/main.py` short-circuit location.** BACKEND must inspect the current `run_stock_screener` body to find the right place to gate the interactive UI. The principle: when `config.scrape_link` is truthy, skip filter selection + query construction; use the URL as `quarry` directly.

---

## Spec / doc updates bundled with the change

- `docs/features/archive/scrape-link-restoration-spec.md` — this file, moved + banner-prepended
- `docs/FEEDBACK-LOG.md` — new entry
- `CONTRACTS.md` §1 — re-documented surface
- (Optional, separate cycle) `docs/reviewer/set-filters-restoration.md` — tracking the sibling deferred work
