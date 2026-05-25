# INTEGRATION.md — Non-Python Consumers

This document is for **non-Python apps** (Go, Node, Rust, etc.) that want to drive `fincli` from a different language. Python integrators should use the importable surface in `core.configuration.configurator.build_config` + `fincli.app.main.run_stock_screener` instead — see [CONTRACTS.md](CONTRACTS.md) §6.

> Companion docs: [CONTRACTS.md](CONTRACTS.md) (CLI surface, CSV schema, JSON schemas, HTTP API surface, stability policy) and [README.md](README.md) ("Pipeline mode" section for Bash/shell cookbook).

---

## Integration mode selection

Fin CLI offers two integration modes for non-Python consumers:

| Mode | Best for | Latency overhead | Process model |
|---|---|---|---|
| **HTTP API** | Most non-Python consumers (Go/TS/Rust/etc.) | Network round-trip | Long-running server |
| **CLI subprocess** | One-shot pipelines / cron jobs / shell scripts | Per-invocation cold start (~1-2s) | Spawned per call |

**HTTP API mode is often a better fit when** you have a long-running consumer, want typed clients via OpenAPI codegen, or are integrating into an existing service. **Subprocess mode is often a better fit when** you're running cron jobs, one-shot pipelines, or shell scripts where a self-contained command beats a service dependency.

Both modes share the same underlying screener engine, filter inventory, CSV schema, and exit/error semantics — pick the transport that fits your runtime.

---

## Subprocess (CLI) mode

### Audience & scope

You are integrating `fincli` into a downstream automation pipeline written in a language other than Python. Your code spawns `fincli` as a subprocess, reads its CSV output (file path or stdout), parses a JSON summary or `OUTPUT_PATH=` discovery line on stderr, and branches on the exit code.

In scope:

- The subprocess invocation contract — CLI flags, exit codes, stream discipline.
- The two JSON payloads the CLI emits — filter inventory (CONTRACTS §5.6) and per-run summary (CONTRACTS §5.5).
- The `OUTPUT_PATH=` stderr discovery line for recovering the destination path when `--json-summary` is not used.
- Concurrency and caching guidance for production callers.

Out of scope:

- Per-language working code examples (deferred — see "Per-language cookbook" below).
- Running `fincli` inside a long-lived host process via subprocess (no in-process Python bridge today; use HTTP API mode below for long-running scenarios).
- The interactive picker UI (irrelevant for automation; never invoked when any of the structured-input flags is set).

The pipeline-mode umbrella (shipped 2026-05-16) made the CLI deterministic enough to be a single-shot building block; this section describes how to use it as one.

### Bootstrap: discover the filter inventory

Run `fincli --list-filters --json` once at your app's startup to learn the full Finviz filter vocabulary:

```bash
fincli --list-filters --json
```

Output is a single JSON line on stdout; the process exits 0. Schema is documented in CONTRACTS §5.6. Skeleton:

```json
{
  "schema_version": 1,
  "keys": ["fa_pe", "fa_fpe", "sec", "ta_rsi"],
  "filters": {
    "fa_pe":  {"label": "PE",     "values": {"": "Any", "u20": "Under 20"}},
    "sec":    {"label": "Sector", "values": {"": "Any", "energy": "Energy"}},
    "ta_rsi": {"label": "RSI 14", "values": {"": "Any", "ob70": "Overbought (70)"}}
  }
}
```

Use the inventory to:

1. **Validate user input** before invoking the screener. Reject any `query_key` not in `keys`; reject any `value_code` not in `filters[key].values`.
2. **Build dropdowns / autocomplete** for your UI. Display the `label` field; submit the `value_code` to the screener.
3. **Detect Finviz vocabulary drift**. Diff the inventory between fincli upgrades; new keys/values land additively (no `schema_version` bump). A removed or renamed key bumps `schema_version` — treat as breaking.

**Iteration-order gotcha**: do not rely on `filters`-object iteration order. Go's `encoding/json` decodes into `map[string]T` and randomizes iteration; JS object iteration order is engine-defined. Iterate the `keys` array and index into `filters[key]` if you need stable ordering (e.g., for a dropdown grouping). Spec: CONTRACTS §5.6.

### Per-screen call flow

The canonical non-interactive screen invocation:

```bash
fincli --filters-json '{"fa_pe":"u20","sec":"energy"}' --output - --json-summary
```

Breakdown:

| Flag | Purpose |
|---|---|
| `--filters-json '{...}'` | Structured filter input as a flat JSON object. Alternatives: `--filter key=value` (repeatable) or `--filters-file PATH`. Mutually exclusive with `--history` / `--scrape-link` / `--list-filters`. |
| `--output -` | Stream CSV bytes to stdout. Stdout contains **only** CSV bytes — banner / progress / errors / JSON summary all go to stderr. Alternative: `--output PATH` to write a file at an exact path. |
| `--json-summary` | Emit a single-line JSON summary at end of run on the stream not occupied by CSV. Under `--output -`, the summary goes to stderr (after the `OUTPUT_PATH=-` line). |

Consumer recipe:

1. Spawn the subprocess and capture both stdout and stderr separately.
2. Read CSV from stdout (or from the file written when using `--output PATH`).
3. Parse the JSON summary from the **last** stderr line that begins with `{` (the second-to-last line is `OUTPUT_PATH=...`; the last is the JSON summary under `--json-summary`). Schema: CONTRACTS §5.5.
4. Check exit code against the routing table below.

`--filter`, `--filters-json`, and `--filters-file` are interchangeable input shapes for the same canonical flat-object payload. `--filter k=v` is shell-friendly; `--filters-json '{...}'` is API-friendly; `--filters-file ./f.json` is config-file-friendly. Pick whichever fits your wrapper code.

### Exit-code routing

The five exit codes map to consumer behaviors per the table below. Source of truth: `fincli/app/exit_codes.py` (constants `SUCCESS`, `INTERNAL`, `USAGE`, `UPSTREAM`, `DATA`).

| Code | Constant | Meaning | Recommended consumer behavior |
|---|---|---|---|
| `0` | `SUCCESS` | Run completed; CSV written (or streamed). Includes zero-row results — a zero-row run still produces a header-only CSV so every successful invocation is discoverable. | Process the result. Treat zero-row CSVs as a legitimate empty answer, not an error. |
| `1` | `INTERNAL` | Unexpected internal failure. Uncaught exception that didn't match the upstream/data classifier families. Traceback on stderr; written to `logs/error.log` inside the fincli process. | Surface as an error to the operator. **Do not retry** — the failure is likely a bug, not a transient condition. |
| `2` | `USAGE` | CLI input validation error. Mutex violation, unknown filter key or value, malformed JSON in `--filters-json` / `--filters-file`, missing `--json` for `--list-filters`. | Caller bug — fix the input and re-invoke. Validate against the §5.6 inventory before retrying. |
| `3` | `UPSTREAM` | Upstream / network failure. `cfscrape` raised, HTTP error, DNS failure, request timeout. Classified by `requests.exceptions.RequestException`. | **Retry with exponential backoff.** Cloudflare may also throttle — back off generously and consider rate-limiting your downstream invocations. |
| `4` | `DATA` | Data-contract / parse failure. Screener `<table>` element missing, BeautifulSoup couldn't extract a row, columns mismatch. | Surface as an error. **Do not retry** — Finviz HTML layout has likely changed and `fincli` needs an update before the same query will succeed. |

Hardcoding the integer values in your consumer is acceptable as long as you treat the `0` / `1` / `2` / `3` / `4` mapping as contract — CONTRACTS §7 lists exit-code conventions in the stability set. If you have a way to share constants between Python and your language, prefer importing `fincli.app.exit_codes` from a small Python shim.

### OUTPUT_PATH= discovery (when `--json-summary` not used)

The stderr stream always ends with a single line of the form:

```
OUTPUT_PATH=<value>
```

`<value>` is the absolute path the CSV was written to (file mode), or the literal `-` for stdout streaming. Emitted unconditionally — independent of `--quiet`, `--debug`, and `--json-summary` — exactly once, immediately before the process exits.

Extract the path from a shell wrapper without parsing JSON:

```bash
fincli --filter fa_pe=u20 --output ./out.csv 2> /tmp/stderr.log
DEST=$(tail -n1 /tmp/stderr.log | cut -d= -f2-)
echo "CSV is at: $DEST"
```

Under `--json-summary`, the `OUTPUT_PATH=` line still lands on stderr second-to-last (the JSON summary becomes the last line). The format is contract-pinned in CONTRACTS §1 ("Output side effects") and CONTRACTS §7 (stability policy).

### Concurrency notes

- **fincli is stateless per-run.** Safe to spawn multiple subprocesses in parallel from your wrapper. Each invocation builds its own `Config` from CLI flags + env vars and writes only to its declared output destination (`--output PATH`, `--output -`, or the timestamped default).
- **cfscrape's anti-bot pacing is in-process.** Each subprocess gets its own scrape context with its own backoff timers — concurrent invocations do NOT share rate-limit state. This is a feature (no in-process contention) but also a risk (you can collectively overrun Finviz's per-IP throttling if you fan out too aggressively). Rate-limit at YOUR layer, not fincli's.
- **No global state on the filesystem.** The history file (`<Config.history_dir>/filter_history.json`) is overwritten on every successful run that produced a non-empty filter set, but consumer pipelines that always pass `--filter` / `--filters-json` / `--filters-file` don't care about history. If you want to avoid the writeback entirely, set `HISTORY_DIR=` to a per-invocation scratch directory.
- **Logger handlers are per-process.** Each subprocess writes to its own `logs/activity.log` / `logs/error.log`, anchored to the process's CWD. Distinct CWDs per invocation prevent log interleaving across parallel workers.

### Caching guidance

- **Filter inventory (`--list-filters --json`)**: cache aggressively. The inventory rarely changes — typically only when fincli ships a new release that adds Finviz filter coverage. A cache TTL of hours-to-days is reasonable; treat a `schema_version` bump or any vocabulary diff as a cache-invalidation signal. Payload is ~46 KB so memory cost is negligible.
- **Screen results**: cache per filter-set when your access pattern is repeated. fincli scrapes are slow (~0.5–2s per Finviz result page; multi-page screens compound) and Finviz throttles aggressive callers. If your downstream UI re-asks the same question every minute, cache the CSV for at least minutes and prefer a background refresh over a foreground re-scrape.
- **Do NOT cache exit codes.** A previous `0` doesn't predict the next call's outcome under network drift.

### Per-language cookbook

**Deferred.** Working Go / Node / Rust examples will be added in a follow-up commit when the downstream consumer project is further along. This section is a placeholder so contributors know where the canonical examples will live; the language-agnostic patterns above are the spec-pinned shape that every example will follow.

If you write a wrapper for your language and would like it merged here, the minimum acceptable example covers: bootstrap (`--list-filters --json`), one screen invocation (`--filters-json '{...}' --output - --json-summary`), exit-code routing per the table above, and `OUTPUT_PATH=` recovery.

---

## HTTP API mode

The `fincli_api/` package exposes the screener as a FastAPI service. The machine-readable contract is committed at `docs/api/openapi.yaml` (with a JSON companion at `docs/api/openapi.json`). For full endpoint / payload / error-envelope details see [CONTRACTS.md](CONTRACTS.md) §8.

### Quick start

```bash
# Start the API
uvicorn fincli_api.main:app --host 127.0.0.1 --port 8000

# Or via the console script
fincli-api
```

The service binds to `127.0.0.1:8000` by default; pass `--host 0.0.0.0` to listen on all interfaces. Interactive Swagger UI is available at `http://localhost:8000/docs`; ReDoc at `http://localhost:8000/redoc`; the raw OpenAPI schema at `http://localhost:8000/openapi.json`.

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/healthz` | Liveness probe; returns `{"status": "ok"}`. |
| `GET` | `/filters` | Filter inventory (same payload as `fincli --list-filters --json`). |
| `POST` | `/screens` | Run a screen; returns JSON `ScreenResult` with `stocks: Stock[]`. |

Full request/response schemas: [CONTRACTS.md](CONTRACTS.md) §8.

### Sample integration via curl

```bash
# Liveness probe
curl http://localhost:8000/healthz

# List filters (cache aggressively — schema_version bumps invalidate)
curl http://localhost:8000/filters

# Run a screen
curl -X POST http://localhost:8000/screens \
  -H 'Content-Type: application/json' \
  -d '{"filters": {"fa_pe": "u5", "sec": "energy"}}'
```

### Polyglot codegen

The `docs/api/openapi.yaml` snapshot is consumable by every mainstream OpenAPI 3.x toolchain. Common entry points:

- **Go**: [`oapi-codegen`](https://github.com/oapi-codegen/oapi-codegen) — generates typed client + server stubs.
- **TypeScript**: [`openapi-typescript`](https://github.com/openapi-ts/openapi-typescript) for types only, or [`openapi-fetch`](https://github.com/openapi-ts/openapi-fetch) for a typed runtime client.
- **Rust**: `openapi-generator-cli generate -g rust -i docs/api/openapi.yaml -o ./gen`.
- **Java / Kotlin / C# / Ruby / PHP**: any other generator supported by `openapi-generator-cli`.
- **Postman**: Import → Link/File → point at `docs/api/openapi.yaml` (or the live `/openapi.json`) to materialize a collection.
- **Insomnia / Bruno / Hoppscotch**: same OpenAPI-import flow.

Pin your codegen to a specific snapshot commit so you can review API changes deliberately rather than absorbing them silently on the next pull.

### Error handling

All non-2xx responses share a single flat `ErrorResponse` envelope (CONTRACTS §8.4):

```json
{
  "schema_version": 1,
  "error_class": "validation",
  "message": "Unknown filter key 'fa_pee'. Did you mean 'fa_pe'?",
  "details": {"key": "fa_pee", "suggestions": ["fa_pe", "fa_peg", "fa_fpe"]},
  "request_id": null
}
```

`error_class` is the discriminator; consumers `switch` on it rather than parsing `message`. The four values map 1:1 to the CLI exit-code classifier (single source of truth — `fincli/app/exit_codes.py`):

| HTTP status | `error_class` | CLI analog | Recommended consumer behavior |
|---|---|---|---|
| `422` | `validation` | exit 2 (`USAGE`) | Caller bug — fix the request payload. |
| `502` | `upstream` | exit 3 (`UPSTREAM`) | Retry with exponential backoff. |
| `502` | `parsing` | exit 4 (`DATA`) | Surface as error; do NOT retry (Finviz layout drift). |
| `500` | `internal` | exit 1 (`INTERNAL`) | Surface as error with `request_id` for log cross-reference. |

Why `422` (not `400`) for `validation`: `400` is reserved for FastAPI's automatic handling of malformed JSON; `422` is the more precise code for syntactically-valid JSON with a semantically-invalid filter key. `request_id` (UUID4) is populated only on `5xx` paths.

Full per-class `details` payload + plain-text `message` contract: [CONTRACTS.md](CONTRACTS.md) §8.4.

### Drift detection

`python scripts/dump_openapi.py --check` exits non-zero if the committed `docs/api/openapi.{yaml,json}` snapshot diverges from what the live server generates. Suitable as a CI gate, pre-commit hook, or local sanity check before publishing client SDKs — pair it with your codegen step so generated clients can never drift from the running server.

### Concurrency & caching

- The FastAPI app is a long-running process; the screener engine is invoked per request. Same in-process cfscrape pacing notes from the subprocess section apply — Finviz throttles per-IP, so put your rate-limit and per-client cache at the API consumer layer, not inside the service.
- The `/filters` payload is safe to cache aggressively (hours-to-days); a `schema_version` bump or vocabulary diff invalidates the cache. Schema details: CONTRACTS §5.6 (shared with CLI mode).
- `POST /screens` results are scrape-bound and slow (~0.5-2s per Finviz result page; multi-page screens compound). Cache identical requests per filter-set when your access pattern is repeated.

---

## Reference

- **Full CLI surface**: [CONTRACTS.md](CONTRACTS.md) §1 (option table, mutex set, behavior matrix, exit codes, output side effects).
- **HTTP API surface**: [CONTRACTS.md](CONTRACTS.md) §8 (endpoints, request/response schemas, ErrorResponse envelope, stability policy).
- **OpenAPI snapshot**: `docs/api/openapi.yaml` (and `docs/api/openapi.json`) — committed contract; regenerate via `python scripts/dump_openapi.py` and verify via `--check`.
- **CSV schema**: [CONTRACTS.md](CONTRACTS.md) §3.1 (columns, dtypes, sort order, canonical `Symbol` column).
- **JSON summary schema**: [CONTRACTS.md](CONTRACTS.md) §5.5 (`schema_version`, `exit_code`, `output_path`, `row_count`, `query_url`, `filters`, timing).
- **Filter inventory schema**: [CONTRACTS.md](CONTRACTS.md) §5.6 (`schema_version`, `keys`, `filters[].label/values`) — shared between `fincli --list-filters --json` and `GET /filters`.
- **Exit-code classifier source**: `fincli/app/exit_codes.py` (constants + `classify(exc)`); HTTP status mapping follows the same families.
- **Spec archive**: `docs/features/archive/list-filters-spec.md`, `docs/features/archive/pipeline-mode-spec.md` (the umbrella that made the subprocess pattern viable), and `docs/superpowers/specs/archive/2026-05-22-fincli-api-design.md` (HTTP API design + rollout).
