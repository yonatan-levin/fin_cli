# Library Consolidation Proposal: FinCLI + Fundainsight (+ WisdomFruit)

## Executive Summary

- Fit as a library: Yes. The codebase already separates concerns (shared/, fincli/, fundainsight/), has CLI entry points, shared logging and config, and is close to publishable via pip.
- Recommended packaging: A single distribution with subpackages exposing:
  - `finpack.fincli` (screening and scraping helpers)
  - `finpack.fundainsight` (analytics/picking pipeline)
  - `finpack.shared` (config, logging, utils, adapters)
- Backward compatibility: Keep module-level entry points (`-m fincli`, `-m fundainsight`) while offering importable APIs.
- Minimal changes proposed: unify packaging, export stable APIs, add lightweight measurement utility, make key concurrency configurable.

## Observations

- Logging: `shared.infrastructure.logging.LogManager` centralizes formatting and handlers. INFO logging was previously suppressed until configured; WisdomFruit now configures logging at import—consider moving configuration to application entry points to avoid side effects in library usage.
- Config: `shared.infrastructure.config.settings` provides flexible env- and file-based configuration; `build_config` keeps compatibility with existing CLI flows.
- Modularity: fincli fetch + parsing flows are encapsulated; fundainsight offers enhanced domain abstractions.
- Testing: Project has domain and infrastructure tests; we added a micro benchmark harness and a performance test scaffold.

## Proposed Library Layout

```
finpack/
  __init__.py            # exports high-level APIs
  fincli/                # CLI utilities (screening)
  fundainsight/          # analytics pipeline / stock picking
  shared/                # config, logging, utils, adapters
```

- Package name: `finpack` (placeholder; confirm availability on PyPI).
- Entry points (optional):
  - `finpack-cli` -> `fincli.__main__:run_main`
  - `finpack-fundainsight` -> `fundainsight.__main__:run_main`

## Public API Proposal

- `from finpack.fincli.app.main import fetch_urls, build_data_frame`
- `from finpack.fundainsight.app.main import get_opportunities`
- `from finpack.fundainsight.app.stock_picker import picker, StockPicker`
- `from finpack.shared.infrastructure.config import build_config, get_config`
- `from finpack.shared.infrastructure.logging import get_logger, log_manager`

Keep the surface small and stable; treat other modules as internal.

## Packaging Plan (pyproject)

- Update `[project]` metadata with final `name`, `version`, `readme`, `license`.
- Include packages via `setuptools` (or `hatchling`) and add `[project.scripts]` for CLI entry points.
- Ensure `dependencies` match `requirements.txt`.

## TDD + Measurement (example)

Change introduced: `fetch_urls` concurrency becomes configurable and measurable.

We created:
- `shared/infrastructure/utils/measure.py`: lightweight time/memory tracker.
- `fincli/app/main.py`: `fetch_urls(quarry, page_count, max_workers=None, fetch_fn=...)` (injectable fetch function).
- `scripts/bench_fetch_urls.py`: a small benchmark to compare serial vs concurrent behavior with simulated I/O.

Run:
```powershell
$env:PYTHONPATH="."; python scripts/bench_fetch_urls.py
```
Observed measurements (simulated 50ms/page, 20 pages):
- baseline-serial: ~1010.41 ms
- concurrent-8: ~152.16 ms (speedup ~6.64x)

This demonstrates meaningful improvement and provides a repeatable harness to measure future tweaks.

## Risks / Open Questions

-- External providers (yfinance, scraping) are rate-limited; expose config knobs (timeouts, retries, parallelism) consistently.
- SEC EDGAR adapter: keep defensive parsing for possible API format changes.

## Roadmap to Publish

1. Create `finpack/` package root (either rename current roots or set `package_dir` mapping).
2. Normalize imports to `finpack.*`; optionally add thin compatibility shims if needed.
3. Update `pyproject.toml` with scripts and metadata; verify `pip install -e .`.
4. Author a user-facing README with import/CLI examples for fincli and fundainsight.
5. Establish CI for lint, type-check, tests, and a smoke benchmark run.

## Conclusion

The project is a good fit for a single pip-distributed library with clear subpackages. Minimal, non-breaking steps will make it consumable as an importable toolkit while preserving existing CLIs.

