# Pipeline Mode — Feature Spec

> **SHIPPED — 2026-05-16.** All four pillars + two adjacent fixes landed across commits `f775b7e..HEAD` on the `refactor/fincli-only` branch (six BACKEND tasks, each its own commit, with VERIFIER + REVIEWER + QA + HUMAN gates between). Final umbrella-closer commits: Pillar-4 exit codes + zero-row success + Ticker stdout carve-out, then the full doc sweep across `CONTRACTS.md` / `ARCHITECTURE.md` / `docs/MODULE_REFERENCE.md` / `docs/THESIS.md` / `docs/FEEDBACK-LOG.md` / `README.md` / `TESTING.md` / `CLAUDE.md` + agent role files, then this spec moved to `archive/` with this banner. `fincli` is now consumable by another program — see `README.md`'s "Pipeline mode" section for cookbook examples and `CONTRACTS.md` §1 / §5.5 for the contract surface (option table, behavior matrix, exit-code table, JSON summary schema). Field decisions captured in `docs/FEEDBACK-LOG.md` (2026-05-16 entry).

**Status:** SHIPPED (was DRAFT)
**Spec ID:** `pipeline-mode-spec`
**Date drafted:** 2026-05-15
**Date shipped:** 2026-05-16
**Author:** ARCH (plan-and-create, Phase 1)
**Severity:** HIGH — unblocks fincli as a building block for a downstream automation pipeline (the user's broader trading workflow). All four pillars are co-dependent; shipping in isolation produces only partial automation.
**Related:**
- `CONTRACTS.md` §7 (stability policy — every change here is additive per §7)
- `docs/THESIS.md` Design Principle #1 ("Composability over orchestration") and Principle #2 ("Fail loudly, never silently")
- `docs/features/archive/scrape-link-restoration-spec.md` (precedent for input-mode bypass; mutual-exclusion machinery)
- `docs/refactoring/archive/history-path-config-spec.md` (precedent for env-var-overridable Config paths via `platformdirs`)

---

## 1. Status / Metadata

| Field | Value |
|---|---|
| Spec | `docs/features/pipeline-mode-spec.md` |
| Status | DRAFT (Phase 1 Planning) |
| Cycle | plan-and-create |
| Owner agents | ARCH (this file) → BACKEND → VERIFIER → REVIEWER → QA → HUMAN |
| Implementation strategy | Single multi-step BACKEND cycle, six tasks landing in the order in §12 (back-compat first, market-cap fix early, then the four pillars). Each task is a separate commit. |
| Breaking changes | **None.** Every change is additive per CONTRACTS §7. The current human-interactive flow is preserved bit-for-bit when no new flags are set. |
| Out-of-scope (explicit) | See §9 |

---

## 2. Goal

Make `fincli` consumable by another program. Today the screener is interactive-first and the only programmatic affordance is reading a freshly written timestamped CSV out of a hardcoded `workspace_output/` directory. A downstream automation script that wants to invoke `fincli`, get back a deterministic file path, and act on the rows must scrape stdout, guess the timestamp, and rely on undocumented dtype behavior. This spec adds four pillars — structured filter input, deterministic output destination, stream discipline (stdout vs. stderr), and differentiated exit codes — plus two adjacent fixes (the buggy `convert_market_cap_to_numeric` function and the canonical-status of the `Symbol` column) so that fincli becomes a stable, single-shot building block in a larger pipeline.

---

## 3. Non-Goals

This spec deliberately does **not** ship:

- Changing the no-flag default output path. `Config.file_path` (`config/config.py:22-26`) still resolves to `os.path.join(os.getcwd(), 'workspace_output/...')`. Making that portable (e.g., via `platformdirs.user_cache_dir`) is a behavioral change for existing human users; defer to a separate refactor spec, harmonized with the `HISTORY_DIR` rename in §9.
- A `--fail-on-empty` flag. Zero-row results stay exit code 0; a future opt-in flag is fine but not in this spec.
- Async / parallel page fetch. The existing synchronous pacing cooperates with Finviz's anti-bot throttle; do not touch it.
- A TUI / dashboard / web UI.
- A subcommand restructure (e.g., `fincli screen ...`, `fincli pipeline ...`). The single-command surface is preserved; new flags layer onto `run_main`.
- Renaming `HISTORY_DIR` → `FINCLI_HISTORY_DIR`. Tracked as a follow-up harmonization with the new `FINCLI_OUTPUT_DIR` (see §9).
- Validation of the `--scrape-link` URL shape. Per THESIS Principle #2 the caller knows best at this boundary; the new validator helper in Pillar 1 only inspects structured filter input.
- Any change to `cfscrape`, the User-Agent rotator, or the Finviz HTML parser.
- Replacing the existing Singleton `Logger`. The fix is reconfiguring its handler stream destinations under specific flags, not swapping it out.

---

## 4. Background

### 4.1 What is already half-built

Several pieces of the pipeline-mode story are already shipped but not wired:

- **Configurator accepts a JSON filters payload it never receives.** `core/configuration/configurator.py:9-37` declares `build_config(use_history=False, filters="", scrape_link="")`. The `filters` parameter feeds through `core/converters/json.py:json_to_tuples` into `config.filters`, but **no `@click.option` exposes it** in `fincli/app/cli.py:1-40` — so `config.filters` is always empty when called from the CLI. Dead code.
- **`select_filters_and_values` ignores `config.filters`.** Even if the configurator did receive filters, `fincli/cli/cli_stock_screener.py:11-46` only honors `config.use_history` and the interactive picker; `config.filters` is never read.
- **`history_dir` is portable but `file_path` is not.** `Config.history_dir` (`config/config.py:21`) was made portable on 2026-05-10 via `platformdirs.user_data_dir(...)` plus a `HISTORY_DIR` env override. `Config.file_path` (lines 22-26) was left CWD-relative for compatibility — that's the gap this spec fills with `--output` and `FINCLI_OUTPUT_DIR`, without touching the CWD-relative default.
- **`--scrape-link` already exists** as the precedent for an input-mode bypass with mutual-exclusion (`fincli/app/cli.py:7-30`). New input modes follow the same machinery.

### 4.2 What is broken

- **stdout has three concerns mixed together.** The Singleton logger's `TypingConsoleHandler` (`logger/handlers.py:17-38`, via `print(...)`) and `ConsoleHandler` (`logger/handlers.py:8-14`, also `print(...)`) both write to **stdout**. The `click.echo("Welcome to the Stock Screener CLI!")` banner at `fincli/app/cli.py:32` writes to stdout. The only result signal is `logger.info(f"File saved to {file_path}", ...)` at `fincli/app/main.py:81`, also stdout, also wrapped in typing-effect ANSI codes. A pipeline that wants to capture the CSV path has nowhere clean to look.
- **No machine-readable result handle.** Today's `OUTPUT_PATH` is buried in a typing-animated log line whose format is `{title_color}` + space + `{message}` (per `logger.py:36`). Parseable only by humans.
- **Ticker column is poisoned for non-Excel consumers.** `main.py:29` rewrites `Ticker` to `=HYPERLINK("https://finviz.com/quote.ashx?t=AAPL", "AAPL")`. The raw symbol is preserved as `Symbol` (line 28) — but the column is appended last and undocumented as the canonical automation column, and the Excel formula breaks `pandas.read_csv` typing for the column.
- **Exit codes are undifferentiated.** `main.py:71-74` returns silently with no CSV when zero rows are found; everything else either succeeds with exit 0 or bubbles to Click's default exit 1 with a traceback. CONTRACTS §1 declares "0 = run completed; CSV written" — the zero-row case violates that contract today (no CSV is written).
- **Latent `convert_market_cap_to_numeric` bug.** `main.py:33-46`:
  - Line 34: `market_cap.replace("'","")` is unassigned (no-op).
  - Lines 41-44: the `_` and `-` branches return strings, mixing the column dtype with the numeric branches above. CONTRACTS §3.1 declares the column as `float`.
  - Line 46: a bare `"-"` (no abbreviation suffix) skips all branches and crashes `float("-")` with `ValueError`.
- **Silent-corruption hazard in `build_stock_screener_query`.** `fincli/utils/quary_builders.py:18-22` only appends a filter when `key in attr_value` — which is `key in <a list>` — so an unknown key is silently dropped, and Finviz returns the unfiltered universe. Direct violation of THESIS Principle #2 and a pipeline correctness disaster.
- **`filter_history.json` writeback is dead.** `fincli/cli/cli_stock_screener.py:40-42` writes the history file *inside* `if config.use_history:` — but `use_history` is the *read* path, not the write path. Writeback never executes. Pre-existing bug, in scope to fix as part of Pillar 1.

These six issues form a single coherent unit of work because shipping any one of them in isolation still leaves the pipeline use case broken.

---

## 5. Design

The four pillars + two adjacent fixes share a single guiding principle: **the human-interactive flow is the default and is unchanged**. New flags compose; absence of all new flags = today's behavior bit-for-bit.

### 5.1 Pillar 1 — Structured Filter Input

Three new mutually-exclusive Click options that together populate `Config.filters` non-interactively. All three feed into the existing `core.converters.json.json_to_tuples` path.

| Flag | Type | Default | Description |
|---|---|---|---|
| `--filter KEY=VALUE` | repeatable string | `[]` | Single filter as a `key=value` pair. Repeatable: `--filter fa_pe=u20 --filter sec=energy`. |
| `--filters-json STR` | string | `""` | A single JSON document as a literal CLI argument. Canonical shape: a flat object — `'{"fa_pe":"u20","sec":"energy"}'`. |
| `--filters-file PATH` | `click.Path(exists=True, dir_okay=False, readable=True)` | `None` | Path to a JSON file containing the same flat-object payload. |

**Mutual-exclusion set:** `--filter`, `--filters-json`, `--filters-file`, `--history`, `--scrape-link`. Pick exactly one (or none = interactive). Implementation: extend the existing inline check at `fincli/app/cli.py:27-30` to count "input modes set" and raise `click.UsageError` when count > 1 (see §6 for the exact error message).

**Wiring (the choke point fix):**

1. **CLI → configurator.** New options collected in `run_main`, normalized into a JSON string (the natural shape for the existing `build_config(filters=...)` parameter):
   - `--filter fa_pe=u20 --filter sec=energy` → `'{"fa_pe":"u20","sec":"energy"}'`
   - `--filters-json '{"fa_pe":"u20"}'` → passed through verbatim.
   - `--filters-file path/to/x.json` → file content read and passed as the string.
   The CLI does this *normalization* (collapsing the three forms into one) so the configurator stays single-shape.
2. **Configurator** (already correct; just gets a non-empty `filters` argument now). Lines 34-35: `if filters != "" and not use_history: config.filters = json_to_tuples(filters)`.
3. **`json_to_tuples` schema lockdown.** Today (`core/converters/json.py:1-17`) it accepts both list-of-pairs `[["k","v"]]` and dict `{"k":"v"}` shapes. **Decision (OQ1 below): canonical shape is the flat object.** Tighten `json_to_tuples` to accept *only* the dict shape and raise `ValueError` (which the CLI translates to `click.UsageError`) on lists, scalars, nested objects, or non-string values. Rationale: the dict shape matches `filter_history.json` (CONTRACTS §4.3) — one schema across the system.
4. **`select_filters_and_values` early return.** `fincli/cli/cli_stock_screener.py:11`: insert at the top of the function, before the `use_history` branch:

   ```python
   # Pseudocode — BACKEND will write the actual code. Position it before the use_history branch.
   if config.filters and not config.use_history and not config.scrape_link:
       return build_stock_screener_query(config.filters)
   ```

   Single if-statement, no other path changes. (`build_stock_screener_query` is already imported at line 8.)
5. **Strict filter validation.** New helper `fincli/resource/params/validators.py` walks `Fundamental_Params`, `Descriptive_Params`, `Technical_Params` and exposes:

   ```python
   def validate_filter_pairs(pairs: tuple[tuple[str, str], ...]) -> None:
       """Raises click.UsageError on unknown key or unknown value-for-key.

       The error message names the offending key/value and lists up to ~10 valid
       siblings (with an indication of more available via --help-filters).
       """
   ```

   Called from the configurator's non-interactive path (immediately after `json_to_tuples`) and from the early-return path described above. Closes the silent-drop hazard at `quary_builders.py:18-22` for structured input. Interactive input is already validated by the picker UI; `--scrape-link` and `--history` skip this validator (URL is opaque; history was previously valid by construction).
6. **`filter_history.json` writeback fix.** Move the writeback at `cli_stock_screener.py:40-42` *out* of the `if config.use_history:` block. Write on every run that produced a non-empty filter set, regardless of input mode (interactive, `--filter`, `--filters-json`, `--filters-file`). Skip writeback when `--scrape-link` is used (no filter set to record). This is the OQ7 resolution — a quiet bug fix that Pillar 1 depends on (otherwise the `--history` flag silently desyncs from the new input modes).

### 5.2 Pillar 2 — Deterministic Output Destination

New CLI option `--output PATH | -` plus an env-var override.

| Surface | Behavior |
|---|---|
| `--output PATH` | CSV is written to exactly `PATH`. Parent directory must exist (`click.Path(dir_okay=False, writable=True)`). No timestamp added. Overwrites if the file exists. |
| `--output -` | CSV bytes are streamed to **stdout**. Sentinel value, mirrors the Unix convention. Forces stream-discipline mode (Pillar 3) regardless of `--quiet` setting. |
| `FINCLI_OUTPUT_DIR=<dir>` env var | When set and `--output` is **not** passed: replaces only the *parent directory* in the default `Config.file_path` template. The filename remains `stock_screener_{YYYY-MM-DD_HH-MM}.csv`. |
| Neither set | Today's behavior: `os.path.join(os.getcwd(), 'workspace_output/stock_screener_{date}.csv')`. **Unchanged.** |

**Precedence (most explicit wins):**
```
--output PATH       >  --output -        >  FINCLI_OUTPUT_DIR  >  Config.file_path() default
```

**Implementation surface:**
- New Click option on `run_main` in `fincli/app/cli.py`; thread to `run_stock_screener` and into a new `Config` field `output_path: str = ""` (empty string = "use default", consistent with `scrape_link` precedent).
- Env-var read: in `core/configuration/configurator.py:build_config`, mirror the existing `HISTORY_DIR` block (lines 17-19) — read `FINCLI_OUTPUT_DIR` and stash on a new `Config.output_dir: Path | None` field.
- `Config.file_path(name)` becomes:
  ```python
  # Pseudocode for the new precedence. BACKEND writes the actual code.
  def file_path(self, name: str) -> str:
      if self.output_path:                      # caller pinned an exact path
          return self.output_path
      date = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M')
      basename = f'{name}_{date}.csv'
      if self.output_dir is not None:           # env-var override
          return str(self.output_dir / basename)
      return os.path.join(os.getcwd(), f'workspace_output/{basename}')  # default
  ```
  Note: `file_path` flips from `@staticmethod` to an instance method. This is a **backward-compatible signature change** because every caller already calls `config.file_path(name)` (instance call), which works whether or not the method is decorated `@staticmethod`. CONTRACTS §6 does not list `Config.file_path` and is unaffected.
- The stdout-sentinel `--output -` is detected in `run_stock_screener`, which hands `final_df.to_csv(sys.stdout, index=False)` instead of a path (pandas accepts a file-like object).

**Naming decision (OQ3):** `FINCLI_OUTPUT_DIR` (with the `FINCLI_` prefix) for namespace safety. The existing unprefixed `HISTORY_DIR` is grandfathered; rename to `FINCLI_HISTORY_DIR` is tracked as a separate harmonization spec (see §9).

### 5.3 Pillar 3 — stdout / stderr Discipline (Quiet + Structured Summary)

The contract a pipeline relies on:

> When `--output -` is set, stdout contains *only CSV bytes*. Everything else — progress, warnings, errors, the OUTPUT_PATH discovery line, the JSON summary — goes to stderr.

This is enforced by **stream routing keyed on `--output -`**, not by a separate `--quiet` flag (per refinement E1).

#### 5.3.1 New flags

| Flag | Behavior |
|---|---|
| `--quiet` / `-q` | Suppresses *human chatter* (progress, info, the welcome banner). Does **not** affect `--debug` level. Errors and warnings still emitted. Independent of stream routing — `--quiet` works regardless of `--output`. |
| `--json-summary` | At end of run, emit one single-line JSON object. Stream depends on `--output`: when `--output -` is set, the summary goes to **stderr**; otherwise to **stdout**. The summary is always the *last* line on its stream. |
| `--debug` (existing) | Logger level → `DEBUG`. With `--quiet`, level still applies but human chatter stays suppressed; debug records that *are* emitted (errors, structured handler output) survive. (OQ5 resolution: `--debug` wins on level, `--quiet` wins on routing/suppression.) |

#### 5.3.2 Stream-routing rules

| Mode | stdout | stderr |
|---|---|---|
| Default (no new flags) | Today's behavior (typing-effect logger writes here, banner, `File saved to ...`) | (largely empty; Click error tracebacks land here on failure) |
| `--quiet` | Suppressed except `--json-summary` (when not `--output -`) | Errors + warnings + `--json-summary` (when `--output -`) |
| `--output PATH ... --json-summary` | Progress (from the typing-effect / plain console handlers, which write to stdout by default) **plus** the summary JSON line at end. The summary is always the last JSON-shaped line on stdout; pair with `--quiet` if you want stdout to carry only the JSON. | `OUTPUT_PATH=<path>` line. Pure-JSON stdout requires `--quiet --json-summary` together; the workaround is documented in the §7.8 examples. |
| `--output -` | CSV bytes only (no header banner, no progress, no summary) | All progress + warnings + errors + `OUTPUT_PATH=-` line + (if `--json-summary`) the summary |
| `--output -` + `--quiet` | CSV bytes only | Errors + `OUTPUT_PATH=-` + (if `--json-summary`) the summary |

Implementation: when `output_path == '-'` is detected, the logger's `TypingConsoleHandler` and `ConsoleHandler` are reconfigured to stream to `sys.stderr` (these handlers extend `logging.StreamHandler` and the `print(...)` call in `handlers.py:12` and `:28-36` becomes `print(msg, file=stream)` where `stream = sys.stderr` in pipeline mode). The Singleton logger gains a `set_console_stream(stream)` method invoked once at `run_stock_screener` entry. Logger contract (CONTRACTS §5) is unchanged for default users — only the under-the-hood handler state changes.

The `click.echo("Welcome to the Stock Screener CLI!")` banner at `cli.py:32` becomes conditional: suppressed when `quiet` is set OR `output_path == '-'`.

#### 5.3.3 The `OUTPUT_PATH=` discovery line

A bare-bones "where did the CSV land" signal that works without `--json-summary`:

```
OUTPUT_PATH=<path-or-dash>
```

Always written to **stderr** (regardless of `--output` value), exactly once, immediately before exit. Format is:
- `OUTPUT_PATH=/abs/path/to/file.csv` for a file destination
- `OUTPUT_PATH=-` for stdout streaming

Pipeline integrators that don't want the JSON summary can `tail -n1 stderr | cut -d= -f2-`.

#### 5.3.4 `--json-summary` schema (OQ4 resolution)

One line of JSON, no trailing newline beyond the line terminator. Schema:

```json
{
  "schema_version": 1,
  "exit_code": 0,
  "output_path": "/abs/path/to/file.csv",
  "row_count": 42,
  "query_url": "https://finviz.com/screener.ashx?v=111&f=fa_pe_u20,sec_energy&ft=2",
  "filters": {"fa_pe": "u20", "sec": "energy"},
  "started_at": "2026-05-15T14:32:11.123456+00:00",
  "finished_at": "2026-05-15T14:32:13.789012+00:00",
  "duration_ms": 2665
}
```

| Field | Type | Notes |
|---|---|---|
| `schema_version` | int | Pinned to `1`. Bump on any breaking schema change. |
| `exit_code` | int | The same code the process is about to exit with. |
| `output_path` | str | Absolute path, or `"-"` for stdout. |
| `row_count` | int | Data rows excluding header. `0` for empty result. |
| `query_url` | str | The exact Finviz URL fetched (post-filter-build, pre-pagination). |
| `filters` | object \| null | The `{key: value}` dict resolved by Pillar 1, or `null` for `--scrape-link`. |
| `started_at` | str | ISO-8601 UTC at `run_stock_screener` entry. |
| `finished_at` | str | ISO-8601 UTC immediately before summary emission. |
| `duration_ms` | int | `finished_at - started_at` in milliseconds. |

`schema_version: 1` exists from day one so the field is parseable on every run. Adding fields is non-breaking; removing or renaming bumps `schema_version`.

#### 5.3.5 No TTY autodetection (refinement E2)

Stream routing is decided **only** by explicit flags. No `sys.stdout.isatty()` checks anywhere. Avoids surprises under `nohup`, `>` redirection, CI runners, and Windows job objects.

### 5.4 Pillar 4 — Differentiated Exit Codes

Replace the current "0 on success, 1 on uncaught exception" binary with five codes. Click parse errors are **not** wrapped — Click's default exit 2 is preserved (refinement E4).

| Code | Meaning | Trigger |
|---|---|---|
| `0` | Success | Run completed; CSV written (or streamed). Includes zero-row results. |
| `1` | Unexpected internal failure | Uncaught exception that escaped the orchestrator. Traceback to stderr + `logs/error.log`. |
| `2` | Usage / CLI input validation error | Click's default for `UsageError` and `BadParameter`. Includes mutual-exclusion errors (Pillar 1) and the new validator helper's unknown-key/unknown-value errors. |
| `3` | Upstream / network failure | `cfscrape` raised, HTTP error, DNS failure, timeout. |
| `4` | Data-contract / parse failure | `<table>` element missing, BeautifulSoup couldn't parse the page, columns mismatch `StockTableLocators.PD_TABLE_COLUMNS`. |

**Implementation surface:**
- `fincli/app/main.py:run_stock_screener` wraps the existing pipeline in a try/except chain that classifies exceptions:
  - `requests.exceptions.RequestException`, `cfscrape`-raised exceptions → exit 3
  - `IndexError`, `AttributeError`, `KeyError` originating in `fincli/stock_screening/` → exit 4 (catch at the orchestrator boundary; preserve traceback to error log)
  - All other unhandled → exit 1
- The classifier is a new module `fincli/app/exit_codes.py` with named constants (`SUCCESS=0`, `INTERNAL=1`, `USAGE=2`, `UPSTREAM=3`, `DATA=4`) and a `classify(exc: BaseException) -> int` function.
- Zero-row case (`main.py:71-74`): no longer returns silently. Build the (empty-data) DataFrame from the column locators, write the header-only CSV (or stream it), emit the OUTPUT_PATH line, emit the summary, exit 0. This makes the contract honest: every successful run produces a discoverable output.
- `--output -` zero-row case streams the header line with no data rows.
- Click's UsageError handling is left to Click (exit 2 happens automatically; no wrapping).

### 5.5 Adjacent Fix — `convert_market_cap_to_numeric` Contract

Replace `fincli/app/main.py:33-46` with a single source of truth. The new contract:

| Input shape | Output |
|---|---|
| `"1.2T"`, `"3.5B"`, `"450M"`, `"5K"` (case-insensitive suffix) | `float` value: `1.2 * 1e12`, etc. |
| Permitted noise: leading `$`, embedded `,`, leading/trailing whitespace, `'` thousands separator | Stripped before parsing |
| `"-"`, `"_"`, `""`, `None`, `"N/A"` (any case) | `pandas.NA` (missing-marker), serialized as empty CSV cell |
| `"1234567890"` (no suffix; numeric string) | `float(value)` |
| Anything else (e.g., `"foo"`, `"12X"`) | Logged as a warning, returned as `pandas.NA` |

Output dtype: the column is a **nullable float** (`pandas.Float64Dtype` via `pd.array(..., dtype="Float64")` — note capital F) so the missing values render as empty cells and not as `nan` strings or `0.0`. CONTRACTS §3.1's `Market Cap` row is updated to "nullable float (`Float64`); empty for unparseable / missing".

**No scientific notation in CSV.** When pandas writes nullable Float64 to CSV with default settings, large floats serialize as `1200000000.0` not `1.2e9`. If pandas does emit scientific notation under any value, the function applies `float_format="%.2f"` at the `to_csv` call site. (Validate during VERIFIER pass.)

The new function moves to its own module — `fincli/utils/market_cap.py` — to make it directly testable without importing the orchestrator. `main.py:build_data_frame` imports the helper.

### 5.6 Adjacent Clarification — `Symbol` Column Canonical Status

Two changes, both documentation-only except for the `--output -` carve-out:

1. **Column order is preserved.** Today's order (per `StockTableLocators.PD_TABLE_COLUMNS`, with `Link` dropped and `Symbol` appended) is left exactly as-is. CONTRACTS §3.1 currently lists `Symbol` last; the order stays. Reordering would be a breaking change per CONTRACTS §7 and is rejected (refinement E3).
2. **CONTRACTS §3.1 declares `Symbol` as the canonical automation column.** Add a note: "`Symbol` is the canonical machine-readable ticker. `Ticker` is the human/Excel-friendly column (wrapped as `=HYPERLINK(...)`). Pipeline consumers should read `Symbol`."
3. **`--output -` carve-out.** When and only when streaming to stdout (`--output -`), the `Ticker` column is replaced with the raw symbol (the formula wrap step at `main.py:29` is skipped). `Symbol` remains the raw symbol regardless. Rationale: stdout streaming is unambiguously a non-Excel context; emitting `=HYPERLINK(...)` would be hostile to `pandas.read_csv` consumers downstream. For file destinations (`--output PATH` and the default), the formula stays — preserving the existing Excel UX. Documented in CONTRACTS §3.1.

---

## 6. CLI Surface (Reference)

### 6.1 Full option table (post-spec)

| Option | Alias | Type | Default | Description |
|---|---|---|---|---|
| `--history` | `--hist` | flag | `False` | Reload the most recent filter selection. |
| `--debug` | — | flag | `False` | Logger level → `DEBUG`. |
| `--scrape-link` | — | string | `""` | Direct Finviz screener URL; bypasses interactive UI. |
| **`--filter`** | — | repeatable string | `[]` | **NEW.** Single `key=value` filter; repeatable. |
| **`--filters-json`** | — | string | `""` | **NEW.** Inline JSON dict of filters. |
| **`--filters-file`** | — | path | `None` | **NEW.** Path to a JSON file of filters. |
| **`--output`** | `-o` | string | `""` | **NEW.** CSV destination. `-` streams to stdout. |
| **`--quiet`** | `-q` | flag | `False` | **NEW.** Suppress human chatter. |
| **`--json-summary`** | — | flag | `False` | **NEW.** Emit a single JSON summary line at end. |

### 6.2 Mutual-exclusion matrix (OQ2 resolution)

The five **input mode** flags are pairwise mutually exclusive:

```
--filter        \
--filters-json   |  exactly one (or none = interactive)
--filters-file   |
--history       /
--scrape-link  /
```

Error message when more than one is set (mirrors the existing message at `cli.py:27-30`):

```
Usage: fincli [OPTIONS]
Error: --filter / --filters-json / --filters-file / --history / --scrape-link are mutually exclusive; pick one input mode.
```

`--quiet`, `--debug`, `--json-summary`, `--output` are **orthogonal** to the input-mode flags and to each other.

### 6.3 Precedence rules (consolidated)

- **Output destination:** `--output PATH` > `--output -` > `FINCLI_OUTPUT_DIR` env > `Config.file_path()` default (CWD-relative `workspace_output/`).
- **Logger level:** `--debug` > default INFO. `--quiet` does not change level; it gates the typing-console handler emit.
- **Stream routing:** `--output -` forces all human-readable output to stderr. Otherwise `--quiet` only suppresses; routing stays at today's "logger → stdout, errors → stderr (via Click on uncaught exceptions)".

---

## 7. Acceptance Criteria

Organized by pillar. Each item is a single observable, testable assertion.

### 7.1 Back-compat (must pass first; gate the rest)

- [ ] `fincli` with no flags runs the existing three-section interactive picker, writes to `workspace_output/stock_screener_{date}.csv` in CWD, exits 0.
- [ ] `fincli --history` works exactly as today (reads `<Config.history_dir>/filter_history.json`, runs the pipeline, writes the same CSV).
- [ ] `fincli --scrape-link=<url>` works exactly as today.
- [ ] `fincli --debug` lowers the level as today.
- [ ] No existing test in `tests/unit/app/test_cli.py` breaks.

### 7.2 Pillar 1 — Structured filter input

- [ ] `fincli --filter fa_pe=u20 --filter sec=energy --output -` produces a CSV on stdout matching what the same filters would produce via the interactive picker.
- [ ] `fincli --filters-json '{"fa_pe":"u20"}' --output ./out.csv` writes to `./out.csv`, exits 0.
- [ ] `fincli --filters-file ./filters.json --output -` reads the file and produces the same CSV as the inline-JSON form for the same payload.
- [ ] `fincli --filter bogus=u20 --output -` exits **2**, stderr names the unknown key and lists valid options.
- [ ] `fincli --filter fa_pe=bogus_value --output -` exits **2**, stderr names the unknown value for `fa_pe` and lists valid options.
- [ ] `fincli --filters-json '[["fa_pe","u20"]]' --output -` exits **2** (list shape is no longer accepted; only flat object).
- [ ] `fincli --filter fa_pe=u20 --history` exits **2** with the mutual-exclusion message.
- [ ] `fincli --filters-json '{"fa_pe":"u20"}' --filters-file foo.json` exits **2** with the mutual-exclusion message.
- [ ] After a non-interactive run with non-empty filters, `<Config.history_dir>/filter_history.json` is overwritten with that filter set (writeback fix). A subsequent `fincli --history` recovers them.
- [ ] After a `--scrape-link` run, `filter_history.json` is **not** overwritten (no filter set to record).

### 7.3 Pillar 2 — Deterministic output destination

- [ ] `fincli --output ./custom/path.csv ...` writes exactly to `./custom/path.csv`. Filename is **not** timestamped.
- [ ] `FINCLI_OUTPUT_DIR=/tmp/foo fincli ...` writes to `/tmp/foo/stock_screener_{date}.csv`.
- [ ] `--output PATH` overrides `FINCLI_OUTPUT_DIR` (precedence test).
- [ ] Without either flag/env, output goes to `<CWD>/workspace_output/stock_screener_{date}.csv` (no regression).
- [ ] `--output -` writes the CSV to stdout and emits no other bytes on stdout.

### 7.4 Pillar 3 — Stream discipline

- [ ] `fincli --output - ... > out.csv` produces a valid CSV in `out.csv` with no log lines, no banner, no `=HYPERLINK(...)` formulas.
- [ ] In the same invocation, **stderr** contains progress lines and an `OUTPUT_PATH=-` line as the last line.
- [ ] `fincli --output ./out.csv --json-summary` prints exactly one JSON line on stdout (the summary), all progress on stderr.
- [ ] `fincli --output - --json-summary` prints CSV bytes on stdout (only) and the JSON summary on stderr (after `OUTPUT_PATH=-`).
- [ ] `fincli --quiet ...` suppresses the welcome banner and progress lines on stdout but does not change the output destination.
- [ ] `fincli --debug --quiet ...` keeps debug-level messages routed normally; `--quiet` does not silence errors.
- [ ] The JSON summary validates against §5.3.4 schema with `schema_version: 1`.

### 7.5 Pillar 4 — Exit codes

- [ ] Successful happy-path run → exit 0.
- [ ] Zero-row result (`fincli --filter fa_pe=u5 --filter sec=basicmaterials --filter geo=monaco --output -`) → exit **0**, stdout contains the header row only, no data rows.
- [ ] Mutually-exclusive flags → exit **2**.
- [ ] Unknown filter key/value → exit **2**.
- [ ] Network failure (Finviz unreachable / cfscrape raises) → exit **3**, stderr contains the error.
- [ ] Parse failure (HTML missing the table) → exit **4**.
- [ ] Uncaught exception not in the above categories → exit **1** with traceback to stderr + `logs/error.log`.

### 7.6 Adjacent fix — `convert_market_cap_to_numeric`

- [ ] Returns `float` for `"1.2T"`, `"3.5B"`, `"450M"`, `"5K"` with correct multipliers.
- [ ] Returns `pandas.NA` for `"-"`, `"_"`, `""`, `None`, `"N/A"`.
- [ ] Returns `float` for `"1234567890"` (raw numeric string).
- [ ] Returns `pandas.NA` and logs a warning for unparseable inputs (e.g., `"12X"`).
- [ ] CSV output writes empty cells (not `nan`, not `<NA>`) for missing values.
- [ ] CSV output writes plain decimals, not scientific notation.
- [ ] Column dtype reported by `pandas.read_csv(..., dtype_backend='numpy_nullable')` is a nullable float.

### 7.7 Symbol column

- [ ] `--output PATH` and the default destination still wrap `Ticker` as `=HYPERLINK(...)`.
- [ ] `--output -` writes the raw symbol in `Ticker`.
- [ ] `Symbol` column is the raw symbol in all modes.
- [ ] Column order is unchanged (regression test against `StockTableLocators.PD_TABLE_COLUMNS` minus `Link` plus `Symbol`).
- [ ] CONTRACTS §3.1 documents `Symbol` as the canonical automation column.

### 7.8 Verbatim acceptance examples

```bash
# Happy-path pipeline run (file written, summary on stdout, OUTPUT_PATH on stderr)
fincli --filters-file filters.json --output ./out/today.csv --quiet --json-summary
# expected: exit 0; ./out/today.csv exists with N >= 1 rows;
#   stdout contains exactly one JSON line: {"output_path":"/abs/path/to/out/today.csv","row_count":N,"query_url":"https://finviz.com/...","filters":{...},"exit_code":0,"schema_version":1,...}
#   stderr contains exactly one line: OUTPUT_PATH=/abs/path/to/out/today.csv
#   (the OUTPUT_PATH= discovery line is unconditional — emitted on every run
#   regardless of --quiet; pipeline integrators rely on it for `tail -n1`.)
```

```bash
# Stdout streaming (CSV to pipe)
fincli --filter fa_pe=u20 --filter sec=energy --output - > out.csv
# expected: exit 0; out.csv contains header + N rows;
#   Ticker column contains raw symbol "AAPL" (not =HYPERLINK formula);
#   Symbol column unchanged (still raw symbol, last column);
#   stderr contains progress + final OUTPUT_PATH=- line
```

```bash
# Invalid filter key (silent-corruption prevention)
fincli --filter bogus_key=u20 --output -
# expected: exit 2 (Click usage error);
#   stderr: "Unknown filter key 'bogus_key'. Valid keys include: fa_pe, fa_pb, sec, ind, geo, ta_rsi14, ... (run with --help-filters for full list)";
#   no HTTP fetch, no CSV emitted on stdout
```

```bash
# Mutually exclusive input forms
fincli --filter fa_pe=u20 --history
# expected: exit 2; stderr: "--filter / --filters-json / --filters-file / --history / --scrape-link are mutually exclusive; pick one input mode."
```

```bash
# Zero-row result is success, not failure
fincli --filter fa_pe=u5 --filter sec=basicmaterials --filter geo=monaco --output -
# expected: exit 0; stdout contains CSV header line + zero data rows;
#   stderr: progress + "OUTPUT_PATH=-" + (if --json-summary) {"row_count":0,...}
```

> Note on `--help-filters`: the message above mentions a `--help-filters` flag for discoverability. **Implementation choice:** ship the long list helper as a `validators.list_valid_filters()` function and **omit `--help-filters` from the CLI in this spec** (defer to a separate trivial follow-up). The error message instead lists up to ~10 sibling keys/values inline. The text in the example above stays as-is for readability; BACKEND should produce a similar inline-list message and *not* surface a non-existent `--help-filters` flag in the help text.

---

## 8. Test Plan

All new tests land under the existing `tests/unit/` and a new `tests/integration/` directory. Phase 2 has not yet introduced fixtures or a real e2e harness; this spec adds **focused unit tests at the orchestrator boundary plus a small set of integration tests using `CliRunner`** (Click's built-in test runner — no HTTP traffic). HTML fixtures for the Finviz parser are out of scope for this spec (they belong to the broader Phase 2 test infrastructure cycle).

### 8.1 New test files

| File | Coverage |
|---|---|
| `tests/unit/utils/test_market_cap.py` | All §5.5 input shapes for `convert_market_cap_to_numeric` (T/B/M/K, lowercase, noise stripping, `-`, `_`, `""`, `None`, `"N/A"`, raw numeric, garbage). Asserts return type and value. |
| `tests/unit/converters/test_json_to_tuples.py` | Dict shape accepted; list shape rejected with `ValueError`; non-dict-or-list rejected; unicode keys; nested objects rejected. |
| `tests/unit/resource/params/test_validators.py` | `validate_filter_pairs` accepts known key/value; raises on unknown key (message names key, lists alternatives); raises on unknown value-for-known-key. |
| `tests/unit/configuration/test_configurator_filters.py` | `build_config(filters='{"fa_pe":"u20"}')` populates `config.filters` correctly; combining `filters` and `use_history=True` follows the existing precedence (history wins, per `configurator.py:34`). |
| `tests/unit/configuration/test_output_path.py` | `Config().file_path("x")` default unchanged; with `output_dir` set, parent dir overridden; with `output_path` set, path returned verbatim; precedence ordering. `FINCLI_OUTPUT_DIR` env var picked up by `build_config`. |
| `tests/unit/app/test_cli_pipeline.py` | New Click options accepted (`--filter`, `--filters-json`, `--filters-file`, `--output`, `--quiet`, `--json-summary`). Mutual-exclusion errors. Error messages match acceptance criteria. |
| `tests/unit/app/test_exit_codes.py` | `exit_codes.classify(...)` maps each exception class to its code. |
| `tests/unit/logger/test_stream_routing.py` | `Logger.set_console_stream(sys.stderr)` reroutes console handler emits; default routing is stdout. |
| `tests/integration/test_pipeline_streaming.py` | End-to-end with `CliRunner` and a mocked `fetch_page_sync` returning canned HTML: `--output -` streams CSV on stdout, log lines on stderr, `OUTPUT_PATH=-` last on stderr, `Ticker` column has raw symbol. |
| `tests/integration/test_pipeline_summary.py` | End-to-end with a mocked fetch: `--json-summary` emits a single JSON line matching the §5.3.4 schema; `schema_version == 1`; all required fields present; `duration_ms` is non-negative. |
| `tests/integration/test_zero_row_success.py` | End-to-end with a mocked fetch returning an empty result table: exit 0, CSV header written (no data rows), summary `row_count == 0`, `OUTPUT_PATH=` line emitted. |

### 8.2 Existing tests touched

- `tests/unit/app/test_cli.py` — extend with one regression test asserting that running `fincli` with no new flags still parses the existing three options. No existing assertion is modified.

### 8.3 TESTING.md additions

- Add a "Pipeline mode" section under §"Test layout" describing the new `tests/integration/` directory and the mock-the-fetch pattern (using `unittest.mock.patch` on `fincli.utils.web_scraper.fetch_page_sync`).
- Add a "Mocking strategy" subsection: `cfscrape` is never invoked in tests; `fetch_page_sync` is the seam.
- Note that the integration tests depend on a small canned-HTML fixture under `tests/integration/fixtures/` (one happy-path table, one zero-row table, one missing-table page for the parse-failure code).
- The Phase 2 / Phase 3 phase status in CLAUDE.md is **not changed** by this spec — these are unit + light integration tests; full Phase 2 e2e is still deferred.

---

## 9. Out of Scope (Deferred)

Tracked here so they don't get re-litigated during implementation:

| Item | Why deferred | Tracking |
|---|---|---|
| Make the `workspace_output/` default path portable (e.g., `platformdirs.user_cache_dir`) | Behavioral change for existing human users; needs its own migration story and FEEDBACK-LOG entry. | New refactor spec — `docs/refactoring/output-path-portability-spec.md`, when prioritized. |
| `--fail-on-empty` opt-in flag | Genuine pipeline use cases want zero-row = success (today's Finviz universe + tight filters legitimately produces empty). Add when a real consumer requests it. | Future feature spec. |
| Async / parallel page fetch | Cooperates with Finviz pacing; perf is not the bottleneck. | Not planned. |
| TUI / dashboard / web UI | Out of THESIS scope. | Not planned. |
| Subcommand restructure (`fincli screen ...`) | Single-mode is current THESIS direction. Re-open if a second mode appears. | Not planned. |
| Rename `HISTORY_DIR` → `FINCLI_HISTORY_DIR` for env-var namespace harmonization | Backward-compatibility window needed (read both for one release, deprecate the unprefixed). Cleaner as its own focused spec alongside any other env-var work. | New refactor spec — `docs/refactoring/env-var-namespace-spec.md`, when prioritized. |
| `--scrape-link` URL validation | THESIS Principle #2 — caller knows best at this trust boundary. | Not planned unless a real failure surfaces. |
| `--help-filters` CLI flag | Mentioned in error-message text only; the helper function lands but the CLI flag does not (avoids decision creep). | Trivial follow-up — one Click option, one call to `validators.list_valid_filters()`. |

---

## 10. Migration & Rollout

### 10.1 Back-compat guarantees

The single most important guarantee: **a user running `fincli` (no flags), `fincli --history`, `fincli --scrape-link=<url>`, or `fincli --debug` after this spec ships sees byte-identical behavior to before.**

Mechanically:

- No existing CLI option is renamed, removed, or has its default changed.
- No existing `Config` field is renamed or removed; only additive (`output_path: str = ""`, `output_dir: Path | None = None`).
- No existing CSV column is renamed, removed, or has its dtype changed (`Market Cap` was *declared* `float` in CONTRACTS but the actual code returned `float | str`; the fix tightens to nullable `Float64` — strictly more conformant to the existing CONTRACTS §3.1 declaration).
- No `Logger` public method is renamed; `set_console_stream` is **new** (additive).
- `Config.file_path` flips from `@staticmethod` to instance method — every existing caller already invokes `config.file_path(...)` so the call site is unchanged. CONTRACTS §6 doesn't list this method; safe.

### 10.2 Commit-message convention

One commit per BACKEND task in §12 (six commits total). Each commit's first line follows the existing repo convention (Conventional Commits-ish: `feat:`, `fix:`, `refactor:`):

```
feat(cli): add --filter / --filters-json / --filters-file structured input options
fix(market-cap): convert_market_cap_to_numeric returns nullable Float64 for all inputs
feat(cli): add --output and FINCLI_OUTPUT_DIR for deterministic output destination
feat(cli): add --quiet, --json-summary, and stdout/stderr stream discipline for pipeline mode
feat(cli): differentiate exit codes (0 success, 1 internal, 2 usage, 3 upstream, 4 data)
docs(contracts): document Symbol as canonical automation column; carve out --output - Ticker behavior
```

### 10.3 FEEDBACK-LOG.md entry template

```markdown
### 2026-05-XX — Pipeline mode (structured input + deterministic output + stream discipline + exit codes)

Shipped the `pipeline-mode-spec.md` umbrella feature. fincli is now usable as a single-shot building block in a downstream automation pipeline.

**Decisions captured:**
- Canonical filter-input shape: flat JSON object `{"fa_pe":"u20",...}`. List shape no longer accepted.
- Output destination precedence: `--output PATH` > `--output -` > `FINCLI_OUTPUT_DIR` env > `Config.file_path()` default.
- Stream routing keyed on `--output -`, not on a TTY check.
- `--quiet` suppresses chatter; routing and `--quiet` are independent concerns.
- Five exit codes: 0 success (incl. zero rows), 1 internal, 2 usage (Click default), 3 upstream, 4 data.
- `Symbol` is the canonical automation column; `Ticker` keeps the `=HYPERLINK(...)` wrap except under `--output -`.
- Latent bugs fixed in flight: `convert_market_cap_to_numeric` returns nullable Float64; `filter_history.json` writeback now triggers on every successful run regardless of input mode.

**Not shipped (tracked):**
- Default output-path portability (separate spec).
- `--fail-on-empty` (separate spec).
- `HISTORY_DIR` → `FINCLI_HISTORY_DIR` rename (env-var namespace harmonization spec).

Spec moved to `docs/features/archive/pipeline-mode-spec.md` with Shipped banner.
```

### 10.4 README snippet (added by BACKEND)

A small new section under "Usage" called "Pipeline mode" giving the two highest-leverage examples (file destination + JSON summary; and stdout streaming). Keep it under 20 lines.

---

## 11. File-by-file changes

| File | Lines / functions | Change |
|---|---|---|
| `fincli/app/cli.py` | 7-30 | Add 6 new `@click.option` decorators (`--filter`, `--filters-json`, `--filters-file`, `--output` w/ `-o`, `--quiet` w/ `-q`, `--json-summary`). Extend mutual-exclusion check to count input modes. Conditional banner (suppress when `quiet` or `output == '-'`). Forward all new params to `run_stock_screener`. |
| `fincli/app/main.py` | 33-46 | Delete `convert_market_cap_to_numeric` (move to new file). |
| `fincli/app/main.py` | 49-83 | `run_stock_screener` signature gains the new params. Wrap pipeline in try/except for exit-code classification. Reconfigure logger stream when `output == '-'`. Time `started_at`/`finished_at`. Replace zero-row early return (lines 71-74) with header-only DataFrame + write. Replace silent `to_csv(file_path)` with destination dispatch (file path vs `sys.stdout`). Emit `OUTPUT_PATH=` to stderr. Optionally emit `--json-summary`. Apply exit code via `sys.exit(...)`. |
| `fincli/app/main.py` | 24-31 (`build_data_frame`) | When `pipeline_mode_streaming=True`, skip the `=HYPERLINK(...)` wrap at line 29; `Ticker` keeps raw symbol. New parameter or new helper, BACKEND's choice. |
| `fincli/app/main.py` | 27 (`build_data_frame`) | `df["Market Cap"] = ...` updates to use the new `fincli.utils.market_cap.convert_market_cap_to_numeric` import. |
| `fincli/app/exit_codes.py` | NEW | Constants `SUCCESS=0`, `INTERNAL=1`, `USAGE=2`, `UPSTREAM=3`, `DATA=4`. `classify(exc: BaseException) -> int` function. |
| `fincli/utils/market_cap.py` | NEW | `convert_market_cap_to_numeric(value: str | None) -> float | pandas.NA`. Per §5.5 contract. |
| `fincli/cli/cli_stock_screener.py` | 11 (top of `select_filters_and_values`) | Insert early-return: if `config.filters and not config.use_history and not config.scrape_link: return build_stock_screener_query(config.filters)`. |
| `fincli/cli/cli_stock_screener.py` | 40-42 | Move writeback **out** of `if config.use_history:` block. Run on every path that produced a non-empty `selected_values`, not gated by `use_history`. (Pre-existing bug fix.) |
| `fincli/resource/params/validators.py` | NEW | `validate_filter_pairs(pairs)` raising `click.UsageError` on unknown key/value. `list_valid_filters()` for the error message and future `--help-filters` flag. |
| `core/configuration/configurator.py` | 9-37 | Signature gains `output_path: str = ""`. Read `FINCLI_OUTPUT_DIR` env (mirror the `HISTORY_DIR` block at 17-19). Assign to new `config.output_dir` field. After `json_to_tuples`, call `validators.validate_filter_pairs(config.filters)` to enforce strict validation (raises `click.UsageError` propagating to exit 2). |
| `core/converters/json.py` | 4-17 | Tighten: only dict shape accepted; raise `ValueError` on list, scalar, nested-object, non-string-value. Replace bare `print` calls with raises. |
| `config/config.py` | 12-26 | Add fields `output_path: str = ""` and `output_dir: Path | None = None`. Convert `file_path(name)` from `@staticmethod` to instance method with the precedence in §5.2. |
| `logger/logger.py` | (new method, in `Logger`) | Add `set_console_stream(stream)` that swaps both `typing_console_handler.stream` and `console_handler.stream`. |
| `logger/handlers.py` | 8-14, 17-38 | `ConsoleHandler.emit` and `TypingConsoleHandler.emit` use `print(..., file=self.stream)` (today they use bare `print()`). Default `self.stream` stays `sys.stdout` so default users see no change. |
| `CONTRACTS.md` | §1 (options table), §1 (behavior table), §1 (exit codes table), §3.1 (Market Cap dtype + Symbol canonical note + Ticker carve-out), §4.1 (new Config fields), §6.1 (`run_stock_screener` updated signature), §6.2 (`build_config` updated signature), §6.3 (`json_to_tuples` schema lockdown) | Per §13. |
| `ARCHITECTURE.md` | The CLI → Orchestration block; the side-effects block | Document new flags, new env var, new exit codes, new stream-routing rule. |
| `docs/MODULE_REFERENCE.md` | New entries for `fincli.utils.market_cap`, `fincli.app.exit_codes`, `fincli.resource.params.validators`. Updated entry for `fincli.app.main`, `core.configuration.configurator`, `core.converters.json`, `config.config`, `logger.logger`. | Per §13. |
| `docs/THESIS.md` | "Current phase" + "Roadmap" entries | Note that pipeline mode landed; cite this spec ID. |
| `docs/FEEDBACK-LOG.md` | Append the §10.3 entry. |
| `README.md` | New "Pipeline mode" section under "Usage". Per §10.4. |
| `TESTING.md` | New "Pipeline mode" subsection under test layout; mocking strategy note. Per §8.3. |
| `tests/unit/utils/test_market_cap.py` | NEW. |
| `tests/unit/converters/test_json_to_tuples.py` | NEW. |
| `tests/unit/resource/params/test_validators.py` | NEW. |
| `tests/unit/configuration/test_configurator_filters.py` | NEW. |
| `tests/unit/configuration/test_output_path.py` | NEW. |
| `tests/unit/app/test_cli_pipeline.py` | NEW. |
| `tests/unit/app/test_exit_codes.py` | NEW. |
| `tests/unit/logger/test_stream_routing.py` | NEW. |
| `tests/integration/test_pipeline_streaming.py` | NEW. |
| `tests/integration/test_pipeline_summary.py` | NEW. |
| `tests/integration/test_zero_row_success.py` | NEW. |
| `tests/integration/fixtures/finviz_happy.html` | NEW (small canned HTML fragment with a few rows). |
| `tests/integration/fixtures/finviz_empty.html` | NEW (canned HTML with zero result rows). |
| `tests/integration/fixtures/finviz_no_table.html` | NEW (canned HTML missing the screener table; for exit-code-4 test). |

---

## 12. Tasks by Agent

**BACKEND** is the only implementer (no FRONTEND, no UX_UI). Land tasks in this order — each task is a separate commit and a separate VERIFIER → REVIEWER → QA cycle if the iteration limit allows; otherwise batch the validation gates per the user's call.

### Task 1 — Back-compat regression seed

| | |
|---|---|
| Files | `tests/unit/app/test_cli.py` (extend), `tests/unit/configuration/test_output_path.py` (new — covers default unchanged) |
| Acceptance | New tests pass; existing `test_cli.py` tests pass. No production-code change. |
| Why first | Pin the today-behavior so subsequent tasks can't silently regress it. |
| Complexity | LOW |

### Task 2 — `convert_market_cap_to_numeric` fix

| | |
|---|---|
| Files | `fincli/utils/market_cap.py` (new), `fincli/app/main.py` (import + call site), `tests/unit/utils/test_market_cap.py` (new), CONTRACTS.md §3.1 |
| Acceptance | All §7.6 criteria pass. CONTRACTS §3.1 says `Market Cap` is nullable `Float64`. |
| Why second | Independent of the four pillars, lowest blast radius, fixes a latent ValueError. |
| Complexity | LOW |

### Task 3 — Pillar 1: Structured filter input

| | |
|---|---|
| Files | `fincli/app/cli.py` (3 new options + extended mutual-exclusion), `core/configuration/configurator.py` (validate after json_to_tuples), `core/converters/json.py` (schema lockdown), `fincli/cli/cli_stock_screener.py` (early return + writeback fix), `fincli/resource/params/validators.py` (new), tests under `tests/unit/configuration/`, `tests/unit/converters/`, `tests/unit/resource/params/`, `tests/unit/app/test_cli_pipeline.py`, CONTRACTS.md §1 + §6 |
| Acceptance | All §7.2 criteria pass. Existing back-compat (§7.1) still passes. |
| Complexity | MEDIUM |

### Task 4 — Pillar 2: Output destination

| | |
|---|---|
| Files | `fincli/app/cli.py` (`--output` option), `core/configuration/configurator.py` (env-var + new field), `config/config.py` (new fields + `file_path` instance method), `fincli/app/main.py` (destination dispatch), `tests/unit/configuration/test_output_path.py` (extend), CONTRACTS.md §1 + §4.1 |
| Acceptance | All §7.3 criteria pass. Existing back-compat still passes. |
| Complexity | MEDIUM |

### Task 5 — Pillar 3: Stream discipline + structured summary

| | |
|---|---|
| Files | `fincli/app/cli.py` (`--quiet`, `--json-summary`), `logger/logger.py` (`set_console_stream`), `logger/handlers.py` (use `self.stream`), `fincli/app/main.py` (timer + summary emission + OUTPUT_PATH line), `tests/unit/logger/test_stream_routing.py`, `tests/integration/test_pipeline_streaming.py`, `tests/integration/test_pipeline_summary.py`, CONTRACTS.md §1 + §5 |
| Acceptance | All §7.4 criteria pass. Existing back-compat still passes. |
| Complexity | MEDIUM-HIGH (the trickiest task; touches the logger). |

### Task 6 — Pillar 4: Exit codes + zero-row success + Symbol carve-out + docs

| | |
|---|---|
| Files | `fincli/app/exit_codes.py` (new), `fincli/app/main.py` (try/except classifier + zero-row write + `--output -` Ticker carve-out), `tests/unit/app/test_exit_codes.py`, `tests/integration/test_zero_row_success.py`, integration fixtures under `tests/integration/fixtures/`, CONTRACTS.md §1 (exit codes) + §3.1 (Symbol note + Ticker carve-out), ARCHITECTURE.md, docs/MODULE_REFERENCE.md, docs/THESIS.md, docs/FEEDBACK-LOG.md, README.md, TESTING.md |
| Acceptance | All §7.5, §7.7 criteria pass. Full §7.1 back-compat still passes. Spec is moved to `docs/features/archive/pipeline-mode-spec.md` with Shipped banner. |
| Complexity | MEDIUM |

---

## 13. Spec Updates

### 13.1 `CONTRACTS.md`

**§1 — CLI options table** add six rows:

```
| `--filter` | — | repeatable string | `[]` | Single `key=value` filter; repeatable. Mutually exclusive with `--filters-json`, `--filters-file`, `--history`, `--scrape-link`. |
| `--filters-json` | — | string | `""` | Inline JSON object of filters. Same exclusion. |
| `--filters-file` | — | path | `None` | Path to a JSON file of filters. Same exclusion. |
| `--output` | `-o` | string | `""` | CSV destination. `-` streams to stdout. Empty = `Config.file_path()` default. |
| `--quiet` | `-q` | flag | `False` | Suppress human chatter (banner, progress). Errors still emitted. |
| `--json-summary` | — | flag | `False` | Emit one JSON summary line at end of run. Schema version 1. |
```

**§1 — Behavior table** add three rows covering structured input, output destination precedence, and stream discipline.

**§1 — Exit codes table** replace with the §5.4 five-code table.

**§1 — Output side effects** add bullets:
- `OUTPUT_PATH=<path-or-dash>` line emitted to stderr immediately before exit on every run.
- When `--json-summary` is set, one line of JSON (schema version 1) on stdout (or stderr when `--output -`).

**§3.1 — `stock_screener_*.csv` table** update `Market Cap` row's dtype to `nullable Float64`. Add a note below the table:
> `Symbol` is the canonical machine-readable ticker column. `Ticker` is the human/Excel-friendly column wrapped as `=HYPERLINK(...)`. Pipeline consumers should read `Symbol`. Exception: when invoked with `--output -` (stdout streaming), the `Ticker` column is the raw symbol — the formula wrap is non-Excel-friendly in that context.

**§4.1 — `Config` Pydantic model** add to the model snippet:
```python
output_path: str = ""              # explicit destination, overrides default
output_dir: Path | None = None     # parent-dir override; populated from FINCLI_OUTPUT_DIR
```
Add a new sentence to the surrounding prose: "`output_dir` is read from the `FINCLI_OUTPUT_DIR` env var by `core.configuration.configurator.build_config`. When set and `--output` is not passed, the default filename's parent directory becomes `output_dir`."

**§4.2 — Builder signature** update to:
```python
def build_config(
    use_history: bool = False,
    filters: str = "",
    scrape_link: str = "",
    output_path: str = "",
) -> Config
```

**§4.3 — Filter history JSON** add a sentence: "The file is overwritten on every successful run that produced a non-empty filter set, regardless of how the filters were specified (interactive, `--filter`, `--filters-json`, `--filters-file`)."

**§5 — Logger contract** add §5.5:
> ### 5.5 Stream re-routing
>
> The Singleton `logger` exposes `set_console_stream(stream: TextIO)`. Both the typing-effect and plain console handlers swap their output to `stream`. Used by the CLI when `--output -` is set, to route all human-readable output to stderr so stdout can carry CSV bytes verbatim. Default stream is `sys.stdout`.

**§6.1 — `run_stock_screener` signature** update:
```python
def run_stock_screener(
    history: bool = False,
    debug: bool = False,
    scrape_link: str = "",
    filters: tuple = (),
    output_path: str = "",
    quiet: bool = False,
    json_summary: bool = False,
) -> int  # the exit code (0/1/3/4)
```

**§6.3 — `json_to_tuples` signature** update — accepts only dict shape:
```python
def json_to_tuples(filters_json: str) -> tuple[tuple[str, str], ...]
    # raises ValueError on non-dict shape, non-string value, nested object
```

**§7 — Stability policy** unchanged. Note that this spec ships zero breaking changes (every change is additive); the dtype tightening of `Market Cap` from "float in CONTRACTS but float-or-string in code" to "nullable Float64" is a *conformance* fix, not a breaking change.

### 13.2 `ARCHITECTURE.md`

Update the CLI → Orchestration arrow's prose to mention the three new input modes and the destination dispatch. Add a brief paragraph under "Side effects" describing the `OUTPUT_PATH=` discovery line and the JSON summary line. Mention exit codes (link to CONTRACTS §1).

### 13.3 `docs/MODULE_REFERENCE.md`

New entries:
- `fincli.utils.market_cap` — single function, contract per §5.5.
- `fincli.app.exit_codes` — constants + `classify`.
- `fincli.resource.params.validators` — `validate_filter_pairs` + `list_valid_filters`.

Updated entries:
- `fincli.app.main` — note the new try/except classifier and the destination dispatch.
- `fincli.app.cli` — note the new options.
- `core.configuration.configurator` — note the new `output_path` parameter and `FINCLI_OUTPUT_DIR` env var.
- `core.converters.json` — note the schema lockdown.
- `config.config` — note the new fields and the `file_path` instance method.
- `logger.logger` — note the `set_console_stream` method.
- `fincli.cli.cli_stock_screener` — note the early return on `config.filters` and the writeback fix.

### 13.4 `docs/THESIS.md`

Under "Current phase" or "Roadmap", add: "Pipeline mode shipped (see `docs/features/archive/pipeline-mode-spec.md`). fincli is now usable as a single-shot building block in downstream automation."

### 13.5 `docs/FEEDBACK-LOG.md`

Append the entry from §10.3 (template above).

### 13.6 `README.md`

New "Pipeline mode" section with the two highest-leverage examples from §7.8.

### 13.7 `TESTING.md`

Per §8.3.

---

## 14. Open Questions (HUMAN gate review)

The following are the residual questions after applying ARCH's reasoned defaults. None block BACKEND from starting Task 1 (back-compat seed) or Task 2 (market-cap fix); they should be resolved before Task 3 begins.

| # | Question | ARCH proposal | Notes |
|---|---|---|---|
| OQ1 | Canonical `--filters-json` / `--filters-file` shape: dict vs. list-of-pairs | **Dict** `{"fa_pe":"u20",...}`. Tighten `json_to_tuples` to reject other shapes. | Matches `filter_history.json` schema (CONTRACTS §4.3). One schema across the system. |
| OQ2 | Mutual-exclusion error message | "`--filter / --filters-json / --filters-file / --history / --scrape-link are mutually exclusive; pick one input mode.`" — mirrors today's `cli.py:27-30`. | Single message regardless of which two flags collided; lists the full set so the user knows the alternatives. |
| OQ3 | `OUTPUT_DIR` env-var name | **`FINCLI_OUTPUT_DIR`** (with `FINCLI_` prefix). | Namespace safety. `HISTORY_DIR` rename to `FINCLI_HISTORY_DIR` is a follow-up spec (§9). |
| OQ4 | `--json-summary` minimum field set | All of: `schema_version`, `exit_code`, `output_path`, `row_count`, `query_url`, `filters`, `started_at`, `finished_at`, `duration_ms` (per §5.3.4). | Pipelines benefit from timing; `schema_version` keeps future evolution safe. |
| OQ5 | `--quiet` interacts with `--debug` | `--debug` wins on level; `--quiet` wins on routing/suppression. They're orthogonal axes. | Documented in CONTRACTS §1 behavior table. |
| OQ6 | Validator scope | Structured input only (`--filter`, `--filters-json`, `--filters-file`). `--scrape-link` and `--history` skip the validator. | THESIS Principle #2 — caller knows best at the URL boundary; `filter_history.json` was previously valid by construction. |
| OQ7 | `filter_history.json` writeback under non-interactive runs | **Yes — write on every successful run with a non-empty filter set.** Skip when `--scrape-link` is used. | Quiet bug fix; otherwise `--history` desyncs from the new structured input modes. |

**Genuine unknowns** (no ARCH default; HUMAN call needed):

| # | Question | Why ARCH won't decide |
|---|---|---|
| OQ8 | Should the `fincli/cli/cli_stock_screener.py:40-42` writeback location move into `fincli/app/main.py` (orchestrator) instead of being inside `select_filters_and_values`? | Architectural placement — both are defensible. Inline keeps the diff small; orchestrator-level keeps `select_filters_and_values` pure. ARCH leaves the call to BACKEND but flags it for REVIEWER's eye. |
| OQ9 | When `--filters-file` JSON is malformed, do we exit 2 (treat as usage error) or exit 4 (treat as data error)? | Both are reasonable — the *file* is user input (exit 2) but the *parse* is a data-contract failure (exit 4). ARCH default: **exit 2** (the user provided the bad input; exit 2 is Click's default for `BadParameter`). Confirm. |
| OQ10 | Briefing item 7 mentions "no scientific notation in CSV" as a constraint, but pandas's default float formatter produces `1200000000.0` for our magnitudes — only very small (<1e-4) or very large (>1e16) floats trigger scientific notation. Market caps don't reach those. **Should we still pin `float_format` at the `to_csv` call site?** | ARCH default: **don't pin** unless VERIFIER finds a real case. Pinning adds noise; the constraint is satisfied by pandas defaults for the value range we encounter. |

---

## 15. Discrepancies Found Versus Briefing

Per the briefing's instruction to flag any briefing-vs-code mismatches loudly:

- **Briefing item 5** says CONTRACTS §1 declares "0 = run completed; CSV written" — confirmed at `CONTRACTS.md:45`. Briefing also says "currently a lie when zero-row results also exit 0". ARCH confirms: today's code at `main.py:71-74` returns silently with **no CSV written** when zero rows are found, but the process still exits 0. So the more precise framing is: today violates the contract by exiting 0 *without writing a CSV*. The fix in this spec keeps exit 0 (per the LOCKED decision A) but **also writes a header-only CSV**, so the contract becomes honest.
- **Briefing item 9** says the early-return at `select_filters_and_values` is "one if-statement, one import". ARCH confirms — `build_stock_screener_query` is **already imported** at `fincli/cli/cli_stock_screener.py:8`. So it's *one if-statement, zero imports*. Even smaller than the briefing claimed.
- **Briefing OQ7** describes the writeback at `cli_stock_screener.py:40-42` as being "inside an `if config.use_history:` block, which looks like a pre-existing bug". ARCH confirms, citing the exact lines: line 40 is `if config.use_history:` and lines 41-42 are the `with open(filepath, "w") ...` block. The bug is real (writeback never executes because `use_history` is the *read* path). Fix is in scope per Pillar 1, Task 3.
- **Briefing item 3** says the typing-effect logger writes to stdout via `print(...)` calls. ARCH confirms: `logger/handlers.py:28-36` uses `print(word, end="", flush=True)` (no `file=` arg, so defaults to stdout); `logger/handlers.py:12` uses bare `print(msg)`. The spec's plan to add `file=self.stream` to both handlers is correct.
- **One nuance not in the briefing:** `Logger.error(title, message="")` (`logger/logger.py:117`) has its parameter order flipped vs. the other methods (`title` is positional, message is kw). Existing code in `main.py:72` calls `logger.error("Data Handling --->", "No data was found ...")` — which is correct given the flipped signature. **This is not in scope for this spec** but is a small footgun BACKEND should be aware of when adding any new `logger.error(...)` calls.

No fundamental contradictions with the briefing. Proceeding with the spec as authored above.

---

## 16. Sign-off

This spec is COMPLETE for HANDOFF_TO BACKEND. BACKEND should begin with Task 1 (back-compat seed) and proceed in the §12 order. After each task, hand to VERIFIER. After Task 6, hand to QA, then HUMAN.
