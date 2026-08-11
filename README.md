# Fin CLI

> Turn Finviz stock screens into reproducible data — one filter set in, a clean CSV or typed JSON out.

[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Fin CLI (`fincli`) is the stock-screener tool of the **Strade** multi-tool finance workspace, alongside its siblings **midas** (DCF valuation), **swinger** (technical snapshots), **borker** (Interactive Brokers trading), and the **orchestrator** that composes them.

## What is it?

Fin CLI turns [Finviz.com](https://finviz.com)'s stock screener into a scriptable, contract-stable data source. You express a filter set once — using Finviz's own filter vocabulary — and get the matching ticker table back as a timestamped CSV (for humans and Excel) or typed JSON (for programs), through one shared engine behind both a CLI and a FastAPI service.

Under the hood it builds the Finviz screener URL from your filters, fetches every paginated result page, parses the result table, and hands you the screen as rows. That's it — no database, no broker, no web UI. It's for the personal or technical investor (and their downstream automation) who wants Finviz screens as reproducible data rather than a web page.

## Why it's interesting

- **66 filter keys, three families.** Fundamental (P/E, forward P/E, PEG, P/S, P/B, EPS/sales growth, ROA/ROE/ROI, ratios, debt/equity, margins, ownership), Descriptive (exchange, index, sector, industry, country, market cap, dividend yield, analyst recommendation, earnings date, volume, price, IPO date), and Technical (performance, volatility, RSI(14), gap, SMA 20/50/200, change, highs/lows, chart pattern, candlestick, beta, ATR).
- **Two co-equal entry points, one engine.** The CLI and the HTTP API share a single orchestrator and validator, so the filter vocabulary, error classification, and behavior can't drift between surfaces. A filter that's valid on the command line is valid — identically — over HTTP.
- **Contract-first by design.** [CONTRACTS.md](CONTRACTS.md) pins every CLI flag, CSV column, exit code, JSON schema, and API shape. A committed OpenAPI 3.1.0 snapshot ([`docs/api/openapi.yaml`](docs/api/openapi.yaml)) plus a Postman collection let Go/TypeScript/Rust consumers codegen typed clients.
- **Pipeline-grade CLI ergonomics.** Differentiated exit codes, a `--json-summary` line, CSV streaming to stdout (CSV bytes on stdout, all chatter on stderr), and an always-emitted `OUTPUT_PATH=` line — built to be a well-behaved building block in scripts and cron jobs.
- **Correctness-first ethic.** Silent corruption — a row that fails to parse and quietly vanishes — is treated as the worst possible failure mode. Market Cap is a nullable float (an empty cell for N/A, never `"nan"`), and parse failures are classified loudly rather than swallowed.
- **Human-friendly output too.** The CSV's Ticker cells are Excel `HYPERLINK` formulas, so every ticker is a clickable link to its Finviz quote page when opened in Excel or Google Sheets — with a raw `Symbol` column alongside for machines.

## Quick Start

Requires Python 3.12+.

```bash
git clone https://github.com/yonatan-levin/fin_cli.git
cd fin_cli
pip install -e ".[dev]"
```

### Run the CLI

```bash
fincli                                   # interactive filter picker
python -m fincli                         # portable equivalent

# Non-interactive: filters as flags, stream CSV to stdout
fincli --filter fa_pe=u20 --filter sec=energy --output - | head

# Filters as inline JSON, exact output path, machine-readable summary
fincli --filters-json '{"fa_pe":"u20"}' --output ./out.csv --quiet --json-summary
```

By default results land as a timestamped CSV at `workspace_output/stock_screener_YYYY-MM-DD_HH-MM.csv` with columns:

```
No., Ticker, Company, Sector, Industry, Country, Market Cap, P/E, Price, Change, Volume, Symbol
```

### Run the HTTP API

```bash
uvicorn fincli_api.main:app --reload     # dev mode with auto-reload (localhost:8000)
fincli-api                               # or the console script (binds 0.0.0.0:8000)
```

Then run a screen:

```bash
curl -X POST http://localhost:8000/screens \
  -H 'Content-Type: application/json' \
  -d '{"filters": {"fa_pe": "u5", "sec": "energy"}}'
# -> {"schema_version":1,"row_count":N,"duration_ms":...,
#     "stocks":[{"ticker":"CNX","sector":"Energy","market_cap":5.2e9,
#                "pe":"4.2","price":"$34.55","rank":1,
#                "finviz_url":"https://finviz.com/quote.ashx?t=CNX"}, ...]}
```

An empty `{}` body runs a full dump; zero matches returns `200` with `stocks: []`. Interactive docs live at the Swagger UI: `http://localhost:8000/docs`.

## Usage at a glance

### CLI

| Flag | What it does |
|---|---|
| `--list-filters` (+ `--json`) | Dump the full 67-key filter inventory and exit 0 (no screen runs) |
| `--filter K=V` (repeatable) | Add a filter, e.g. `--filter fa_pe=u20 --filter sec=energy` |
| `--filters-json '{...}'` / `--filters-file PATH` | Filters as inline JSON or a JSON file |
| `--output PATH` / `-o` | Exact CSV destination; `--output -` streams CSV to stdout |
| `--history` | Re-run the last filter selection |
| `--scrape-link URL` | Screen from a direct Finviz URL |
| `--quiet` / `-q`, `--debug` | Less / more console chatter (never on stdout) |
| `--json-summary` | Single-line JSON run summary for `jq` and friends |

The filter-input flags (`--filter`, `--filters-json`, `--filters-file`, `--history`, `--scrape-link`, `--list-filters`) are mutually exclusive — at most one, else exit 2.

**Exit codes:** `0` success (zero rows still exits 0 with a header-only CSV) · `1` internal · `2` usage · `3` upstream (Finviz/network) · `4` data (parse/contract failure).

### HTTP API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/filters` | Full filter inventory (byte-equivalent to `fincli --list-filters --json`) |
| `POST` | `/screens` | Run a screen; returns a typed `ScreenResult` envelope |
| `GET` | `/healthz` | Liveness — `{"status":"ok"}` |
| `GET` | `/docs` · `/redoc` · `/openapi.json` | Swagger UI, Redoc, OpenAPI spec |

Errors map 1:1 to the CLI exit codes: validation → `422`, upstream → `502`, parsing → `502`, internal → `500` (with a `request_id`).

## Status & non-goals

Fin CLI (v0.1.0) is **functional and used for real investment research**. The CLI is the original surface; the HTTP API shipped 2026-05-24. The suite ships with 200+ tests.

Honest edges to know about:

- **Source-only** — no PyPI release yet; install from the repo.
- **Localhost, single-user API by design** — no auth, no rate limiting, no persistence. Don't put it on the open internet as-is.
- **Known limitation (tracked):** malformed Finviz HTML that lacks the screener table currently returns `200` with empty `stocks` instead of a `502` parsing error.

Explicit **non-goals** — Fin CLI is *not* a backtester, a portfolio optimizer, a trading bot, or a fundamental-analysis pipeline. It does one thing: turn a Finviz screen into data you can trust and build on.

## Contributing

Contributions are very welcome — new filter coverage, output formats, hardening the parsing contract, or just better docs. Start with [AGENTS.md](AGENTS.md) (the doc index for humans and AI agents alike), then [CONTRACTS.md](CONTRACTS.md) for the public surfaces and [TESTING.md](TESTING.md) for how the suite is organized. Please make sure `ruff check .`, `ruff format --check .`, and `pytest tests/` are green before opening a PR.

## Authors & License

- **GoBoldMS** — initial work
- **Yonatan Levin** — continued development

Licensed under the MIT License — see [LICENSE](LICENSE) for details.
