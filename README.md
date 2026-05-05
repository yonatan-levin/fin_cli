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
# Interactive filter selection
python -m fincli

# Reuse the last filter selection (reads fincli/local_history/filter_history.json)
python -m fincli --history

# Verbose logging
python -m fincli --debug

# Convenience launchers (install requirements then run python -m fincli)
./run.sh        # Linux / macOS
run.bat         # Windows
```

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

- `use_history: bool` — load the last filter selection from `fincli/local_history/filter_history.json`.
- `filters: tuple` — parsed filter tuples; populated by the interactive UI or by `--history`.
- `scrape_link: str` — direct Finviz URL override.
- `file_path(name)` — produces a timestamped CSV path under `workspace_output/`.

The full data-shape contract — every Click option, every CSV column, every Pydantic field — is documented in [CONTRACTS.md](CONTRACTS.md).

## Tests

```bash
pytest tests/
pytest tests/unit/
pytest -k "<pattern>"
pytest --cov=fincli --cov=core --cov=config
```

> **Note:** the `tests/` folder structure exists, but test bodies are introduced in **Phase 2** of the agent-harness rollout. As of this commit there are no tests. The `pytest` command above runs cleanly because there is nothing to fail — adding behavior validation is queued and intentional.

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
  docs/                # THESIS.md, MODULE_REFERENCE.md, FEEDBACK-LOG.md, specs
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
