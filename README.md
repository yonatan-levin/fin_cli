# Fin CLI — Stock screener + fundamental analysis

> A Python command-line tool for screening stocks from Finviz.com and running price-to-asset fundamental analysis on the screening results using Yahoo Finance data.

[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## Overview

Fin CLI ships two operating modes that share one configuration framework, one Singleton logger, and one CSV output convention:

- **`fincli`** — interactive Finviz screener. Pick filter values from the standard Finviz vocabulary (P/E, sector, country, RSI, market cap, etc.); the tool builds the corresponding URL, fetches every paginated result page through `cfscrape` (Cloudflare bypass), parses the HTML stock table with BeautifulSoup, and writes a timestamped CSV to `workspace_output/`.
- **`fundainsight`** — fundamental-analysis pipeline. Runs the screener, then for each candidate ticker fetches quarterly balance sheet, market cap, shares outstanding, and 30-day price history from Yahoo Finance via `yahooquery`. Computes price-to-asset and price-to-current-asset ratios, applies country / sector / price-threshold filters, and writes a second timestamped CSV. The intent is to surface stocks trading below their adjusted book value of current assets.

The tool is single-process, single-machine. There is no server, no database, no broker integration, no REST API. Outputs are CSVs you read in Excel, in pandas, or in any tool that opens CSV.

## Quick Start

### Prerequisites

- Python 3.12 or later
- pip

### Install

```bash
git clone https://github.com/yonatan-levin/algo_beta.git
cd algo_beta
pip install -e ".[dev]"
```

The editable install with the `[dev]` extra pulls runtime deps from `requirements.txt` and dev tooling (`ruff`, `mypy`, `pytest`, `pytest-cov`, `types-beautifulsoup4`) from `pyproject.toml`.

### Run

```bash
# Stock screener — interactive
python -m fincli

# Stock screener — reuse last filter selection
python -m fincli --history

# Fundamental analysis (one of --history / --set-filters / --scrape-link is required)
python -m fundainsight --history
python -m fundainsight --set-filters '{"fa_pe":"u20","sec":"energy"}'
python -m fundainsight --scrape-link 'https://finviz.com/screener.ashx?v=111&f=fa_pe_u20&ft=2'

# Convenience launchers
./run.sh        # Linux / macOS — interactive menu
run.bat         # Windows
```

### Output

All results land in `workspace_output/` as timestamped CSVs:

| Filename | Producer | Content |
|---|---|---|
| `stock_screener_YYYY-MM-DD_HH-MM.csv` | `fincli` | Screening results with Excel-compatible `=HYPERLINK(...)` ticker cells |
| `funda_insight_result_unfiltered_YYYY-MM-DD_HH-MM.csv` | `fundainsight` | Pre-filter analysis with all ratios |
| `funda_insight_result_YYYY-MM-DD_HH-MM.csv` | `fundainsight` | After country / sector / price-threshold filters |

## Two CLI Modes

**`fincli`** scrapes Finviz: build a query URL from your filter selection, fetch all pages with `cfscrape`, parse the HTML stock table with BeautifulSoup, and emit a CSV. Synchronous; one HTTP request at a time.

**`fundainsight`** enriches: take the screener's symbol list, fan out across `ThreadPoolExecutor` workers to call `yahooquery.Ticker(symbol)` for balance sheet + market data, compute ratios, apply filters, and emit a CSV.

### Sample CSV columns

Screener CSV (`stock_screener_*.csv`):

```
No., Ticker, Company, Sector, Industry, Country, Market Cap, P/E, Price, Change, Volume, Symbol
```

Fundamental analysis CSV (`funda_insight_result_*.csv`):

```
Symbol, Sector, Country, Market Cap, Shares Outstanding,
Total Assets, Adjusted Total Assets, Adjusted Total Current Assets,
Total Equity, Average Price in Last 30 Days,
price_by_assets, price_by_current_assets,
price/price_to_assets_ratio, price/price_to_current_assets_ratio
```

The `Ticker` column in the screener CSV is wrapped as `=HYPERLINK("https://finviz.com/quote.ashx?t=AAPL", "AAPL")` so that opening the CSV in Excel or Google Sheets makes each ticker a clickable link to its Finviz quote page.

## Configuration

Config lives in `config/config.py` as a Pydantic `Config(SystemSettings)` model. The interesting fields:

- `use_history: bool` — load the last filter selection from `<module>/local_history/filter_history.json`.
- `filters: tuple` — parsed filter tuples; populated by the interactive UI, by `--set-filters`, or by `--history`.
- `scrape_link: str` — direct Finviz URL override.
- `file_path(name)` — produces a timestamped CSV path under `workspace_output/`.

The full data-shape contract — every Click option, every CSV column, every Yahoo field, every Pydantic field — is documented in [CONTRACTS.md](CONTRACTS.md).

## Tests

```bash
pytest tests/
pytest tests/unit/
pytest -k "<pattern>"
pytest --cov=fundainsight --cov=fincli --cov=core --cov=config
```

> **Note**: the `tests/` folder structure exists, but test bodies are introduced in **Phase 2** of the agent-harness rollout (`docs/superpowers/specs/2026-05-02-agent-harness-replication-design.md`, §8.1). As of this commit there are no tests. The `pytest` command above runs cleanly because there is nothing to fail — adding behavior validation is queued and intentional.

Lint, format, type-check:

```bash
ruff check .
ruff format .
mypy fundainsight fincli core config logger
```

See [TESTING.md](TESTING.md) for the full testing strategy, fixture conventions, mocking guidance, and the Phase 2 / 3 / 4 follow-up roadmap.

## Project Structure

```
algo_beta/
  fincli/              # Stock screener (cfscrape + BS4 + Click)
  fundainsight/        # Fundamental analysis (yahooquery + ThreadPool + Click)
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
  AGENTS.md            # (lands in the final commit of harness Phase 1)
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
| [CONTRACTS.md](CONTRACTS.md) | Anyone touching public surfaces | CLI options, Finviz query contract, Yahoo data shape, CSV schema, Pydantic config, logger contract, stability policy |
| [TESTING.md](TESTING.md) | Anyone writing tests | Philosophy, layout, running, mocking, coverage policy, Phase 2/3/4 roadmap |
| [TOOLS_REFERENCE.md](TOOLS_REFERENCE.md) | Anyone using the harness | Build/test/lint/format/type/MCP/hook command reference |
| [docs/THESIS.md](docs/THESIS.md) | Anyone | Project vision, current phase, roadmap, scope boundaries |
| [docs/MODULE_REFERENCE.md](docs/MODULE_REFERENCE.md) | Anyone | Per-module purpose, public surface, data shapes, error modes |

## Authors

- **GoBoldMS** — initial work
- **Yonatan Levin** — continued development

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
