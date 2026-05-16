# Fin CLI — Finviz stock screener

> A Python command-line tool that scrapes Finviz.com's stock screener, parses the result table, and emits a timestamped CSV.

[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## Overview

Fin CLI is a single-mode command-line application. You pick filter values from the standard Finviz vocabulary (P/E, sector, country, RSI, market cap, etc.); the tool builds the corresponding Finviz URL, fetches every paginated result page through `cfscrape` (Cloudflare bypass), parses the HTML stock table with BeautifulSoup, and writes a timestamped CSV to `workspace_output/`.

There is no server, no database, no broker integration, no REST API. Outputs are CSVs you read in Excel, in pandas, or in any tool that opens CSV.

## Quick Start

### Prerequisites

- Python 3.12 or later
- pip

### Install

```bash
git clone https://github.com/yonatan-levin/fin_cli.git
cd fin_cli
pip install -e ".[dev]"
```

The editable install with the `[dev]` extra pulls runtime deps from `requirements.txt` and dev tooling (`ruff`, `mypy`, `pytest`, `pytest-cov`, `types-beautifulsoup4`, `pip-audit`) from `pyproject.toml`.

If you previously installed this project under its old distribution name `finscrape`, run `pip uninstall finscrape` before reinstalling so pip picks up the rename cleanly.

### Run

```bash
# Interactive filter selection (preferred; bare shell command)
fincli

# Equivalent fallback when the venv's Scripts/ dir is not on PATH
python -m fincli

# Reuse the last filter selection (reads <Config.history_dir>/filter_history.json; see CONTRACTS.md §4 for the path resolution)
fincli --history

# Verbose logging
fincli --debug

# Convenience launchers (install requirements then run python -m fincli)
./run.sh        # Linux / macOS
run.bat         # Windows
```

> If you installed the project before the `[project.scripts]` entry point was added, re-run `pip install -e ".[dev]"` once so the bare `fincli` command lands on PATH. The launchers (`./run.sh`, `run.bat`) keep working unchanged because they invoke `python -m fincli` internally.

### Pipeline mode

`fincli` is also a single-shot building block for downstream automation. Structured filter input, deterministic output destination, stream discipline, and differentiated exit codes (0/1/2/3/4) compose orthogonally; the interactive flow above is unchanged when none of these flags are set.

```bash
# Stream CSV to stdout, pipe to jq via the JSON summary on stderr
fincli --filter fa_pe=u20 --filter sec=energy --output - | head

# Write to an exact path (no timestamp; overwrites if file exists)
fincli --filters-json '{"fa_pe":"u20"}' --output ./out.csv --quiet --json-summary

# Read filters from a JSON file; emit JSON summary on stdout for jq
fincli --filters-file ./filters.json --output ./out.csv --quiet --json-summary | jq '.row_count'

# Override the default workspace_output/ parent via env var
FINCLI_OUTPUT_DIR=/tmp/screener fincli --filter fa_pe=u20

# Recover the destination from stderr without parsing the JSON summary
fincli --filter fa_pe=u20 --output ./out.csv 2> /tmp/log
tail -n1 /tmp/log | cut -d= -f2-     # -> /abs/path/to/out.csv
```

| Surface | Behavior |
|---|---|
| `--filter K=V` (repeatable), `--filters-json`, `--filters-file` | Non-interactive filter input. Mutually exclusive with `--history` / `--scrape-link`. Unknown key/value -> exit 2. |
| `--output PATH` / `-o PATH` | Exact destination; parent dir must exist; no timestamp; overwrites. |
| `--output -` | Stream CSV to stdout. Stdout contains only CSV bytes; banner/progress/errors go to stderr. `Ticker` column is the raw symbol (not `=HYPERLINK(...)`). |
| `FINCLI_OUTPUT_DIR=<dir>` | Parent-dir override for the default timestamped filename. Loses to `--output PATH`. |
| `--quiet` / `-q` | Suppress banner + INFO/DEBUG console lines. Warnings/errors still emit. |
| `--json-summary` | Single-line JSON summary at end of run; schema in CONTRACTS §5.5. |

Exit codes (full table in CONTRACTS §1): `0` SUCCESS, `1` INTERNAL, `2` USAGE, `3` UPSTREAM, `4` DATA. Zero-row results stay exit 0 and write a header-only CSV.

### Output

Results land in `workspace_output/` as a timestamped CSV named by `Config.file_path`:

| Filename | Content |
|---|---|
| `stock_screener_YYYY-MM-DD_HH-MM.csv` | Screener results with Excel-compatible `=HYPERLINK(...)` ticker cells |

The `Ticker` column is wrapped as `=HYPERLINK("https://finviz.com/quote.ashx?t=AAPL", "AAPL")` so each ticker becomes a clickable link to its Finviz quote page when the CSV is opened in Excel or Google Sheets.

### Sample CSV columns

```
No., Ticker, Company, Sector, Industry, Country, Market Cap, P/E, Price, Change, Volume, Symbol
```

The pipeline is synchronous: pages from Finviz are fetched one at a time, in cooperation with the host's anti-bot pacing.

## Configuration

Config lives in `config/config.py` as a Pydantic `Config(SystemSettings)` model. The interesting fields:

- `use_history: bool` — load the last filter selection from `<Config.history_dir>/filter_history.json` (see CONTRACTS.md §4.1 for the default + override).
- `filters: tuple` — parsed filter tuples; populated by the interactive UI or by `--history`.
- `scrape_link: str` — direct Finviz URL override.
- `file_path(name)` — produces a timestamped CSV path under `workspace_output/`.

The full data-shape contract — every Click option, every CSV column, every Pydantic field — is documented in [CONTRACTS.md](CONTRACTS.md).

## Tests

```bash
pytest tests/
pytest tests/unit/
pytest tests/integration/
pytest -k "<pattern>"
pytest --cov=fincli --cov=core --cov=config
```

The Phase-2 test suite seed landed with the pipeline-mode rollout (2026-05-16): 200+ tests under `tests/unit/` (per-function: market_cap, json_to_tuples, validators, output_path, stream routing, CLI option parsing, exit-codes classifier) and `tests/integration/` (CliRunner-driven end-to-end with `fincli.utils.web_scraper.fetch_page_sync` mocked against canned HTML fixtures under `tests/integration/fixtures/`). Coverage is informational in Phase 1; the 90% gate enables in Phase 3 (see `TESTING.md`).

Lint, format, type-check:

```bash
ruff check .
ruff format .
mypy fincli core config logger
```

See [TESTING.md](TESTING.md) for the full testing strategy, fixture conventions, mocking guidance, and the Phase 2 / 3 / 4 follow-up roadmap.

## Project Structure

```
fin_cli/
  fincli/              # Stock screener (cfscrape + BS4 + Click)
  core/                # Pure Python configuration framework
  config/              # Concrete Config(SystemSettings) instance
  logger/              # Singleton logger (typing console + plain console + JSON file)
  tests/               # unit/ domain/ e2e/ — bodies arrive in Phase 2
  workspace_output/    # CSV results (gitignored)
  docs/                # THESIS.md, MODULE_REFERENCE.md, FEEDBACK-LOG.md, specs, features, pendingwork
  agents/              # AI-agent rules + role files
  .claude/             # Claude Code harness (settings + hooks)
  pyproject.toml
  requirements.txt
  ARCHITECTURE.md
  CLAUDE.md
  CONTRACTS.md
  TESTING.md
  TOOLS_REFERENCE.md
  AGENTS.md
```

## Contributing

This repo is harness-aware. **Both AI agents and humans should start with [`AGENTS.md`](AGENTS.md)** — it is the index for everything else: which docs to read for which task, which roles handle which work, the curation rhythm for keeping these docs fresh.

In addition:

- **AI agents** read `AGENTS.md`, then follow `agents/rules/_shared-workflow.md` (auto-injected at SessionStart by `.claude/hooks/load-rules.js`). Subagents pick up their role files from `agents/roles/`. The full skill / slash-command / MCP-tool reference is in [`TOOLS_REFERENCE.md`](TOOLS_REFERENCE.md).
- **Humans** also read [`CLAUDE.md`](CLAUDE.md) (build/run, conventions, gotchas, phase status) and [`ARCHITECTURE.md`](ARCHITECTURE.md) (system overview, module map, data flow, layering).

Pull requests should pass `ruff check .`, `ruff format --check .`, and a clean `pytest tests/` run before review. The `mypy` advisory output is a Phase 1 signal, not a Phase 1 gate (Phase 4 promotes it to gating).

## Documentation

| Document | Audience | Content |
|---|---|---|
| [README.md](README.md) | Everyone | This file — quickstart, overview, doc index |
| [AGENTS.md](AGENTS.md) | AI + humans | Master index. Tier 1–4 reading order. Sub-agent context diet. Curation rhythm. |
| [CLAUDE.md](CLAUDE.md) | Humans + AI assistants | Build/run, conventions, gotchas, phase status, file map |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Anyone touching internals | System overview, module map, data flow, layering, threading |
| [CONTRACTS.md](CONTRACTS.md) | Anyone touching public surfaces | CLI options, Finviz query contract, CSV schema, Pydantic config, logger contract, stability policy |
| [TESTING.md](TESTING.md) | Anyone writing tests | Philosophy, layout, running, mocking, coverage policy, Phase 2/3/4 roadmap |
| [TOOLS_REFERENCE.md](TOOLS_REFERENCE.md) | Anyone using the harness | Build/test/lint/format/type/MCP/hook command reference |
| [docs/THESIS.md](docs/THESIS.md) | Anyone | Project vision, current phase, roadmap, scope boundaries |
| [docs/MODULE_REFERENCE.md](docs/MODULE_REFERENCE.md) | Anyone | Per-module purpose, public surface, data shapes, error modes |

## Authors

- **GoBoldMS** — initial work
- **Yonatan Levin** — continued development

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
