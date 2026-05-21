# List-Filters — Feature Spec

> **SHIPPED — 2026-05-21.** Three sequential tasks landed across commits `82d3d6e..HEAD` on the `refactor/fincli-only` branch (T1 helpers — `attr_to_label` + `list_valid_filters_with_labels` + shared `_iter_param_entries`; T2 CLI wiring — `--list-filters --json` short-circuit + extended six-flag mutex + `_emit_filter_inventory`; T3 doc sweep — this banner + `CONTRACTS.md` §5.6 + new `INTEGRATION.md` at repo root + `docs/MODULE_REFERENCE.md` + `docs/THESIS.md` Change Log + `docs/FEEDBACK-LOG.md` + `README.md` pointer + `TESTING.md` + spec archive move). Closes the polyglot-discoverability gap that pipeline mode (shipped 2026-05-16) intentionally deferred — non-Python consumers (Go, Node, Rust) can now discover the full Finviz filter vocabulary via `fincli --list-filters --json` and follow `INTEGRATION.md` for the subprocess pattern. 16 new tests, 0 regressions in the pre-existing 229 cases. Field decisions captured in `docs/FEEDBACK-LOG.md` (2026-05-21 entry). The earlier deep-think pass at `16c79ec` amended both this spec and the implementation plan with the canonical `keys` ordering contract before T1 began.

**Status:** SHIPPED (was DRAFT)
**Spec ID:** `list-filters`
**Date drafted:** 2026-05-17
**Date shipped:** 2026-05-21
**Author:** brainstorming skill (interactive design with user)
**Related:**
- `docs/features/archive/pipeline-mode-spec.md` (Pillar 1 validator + §6.7) — the umbrella that made the subprocess pattern viable
- `CONTRACTS.md` §1 (CLI surface), §5.5 (JSON summary precedent for `schema_version`), §5.6 (this feature's inventory schema), §7 (stability policy)
- `INTEGRATION.md` (NEW at repo root) — language-agnostic subprocess patterns for non-Python integrators
- `fincli/resource/params/validators.py` (sibling helpers `list_valid_filters` + `list_valid_filters_with_labels` consuming a shared `_iter_param_entries` walker)

---

## 1. Status / Metadata

| Field | Value |
|---|---|
| Status | SHIPPED |
| Drafted | 2026-05-17 |
| Shipped | 2026-05-21 |
| Author | brainstorming skill (interactive design with user) |
| Spec ID | list-filters |
| Related | `docs/features/archive/pipeline-mode-spec.md` (Pillar 1 validator + §6.7); `CONTRACTS.md` §1 (CLI surface), §5.5 (JSON summary precedent for `schema_version`), §5.6 (this feature's inventory schema); `INTEGRATION.md` (NEW at repo root); `fincli/resource/params/validators.py` (sibling helper `list_valid_filters_with_labels`) |

---

## 2. Goal

Add a single new CLI option — `fincli --list-filters --json` — that dumps fincli's filter inventory as machine-readable JSON, so non-Python consumers (a Go project, future polyglot callers) can build dropdowns, validate input, and discover the Finviz vocabulary without reading Python source files. Plus a new top-level `INTEGRATION.md` documenting the language-agnostic subprocess pattern for non-Python consumers of pipeline mode.

This is the first feature added after the pipeline-mode umbrella shipped (2026-05-16); it closes the discoverability gap that umbrella intentionally deferred.

---

## 3. Non-Goals

- **No HTTP server.** The existing CLI subprocess pattern (shipped in pipeline mode) stays the integration boundary.
- **No JSON output mode for screen results.** Screen results remain CSV per CONTRACTS §3.1. This spec only adds JSON for the *inventory metadata* dump.
- **No changes to the four pillars shipped in pipeline mode** (input flags, output destination, stream discipline, exit codes).
- **No per-language cookbook code examples in INTEGRATION.md** (Go, Node, etc.). Deferred to a follow-up; this spec lands the language-agnostic patterns only.
- **No business logic for the downstream Go consumer.** That lives in the consumer's own project.
- **No `--help-filters` (human-readable variant).** Could be added later; out of scope here. `--help-filters` was referenced as a future flag in `validators.py` docstring + the pipeline-mode spec §6.7 — naming the new flag `--list-filters` (not `--help-filters`) leaves `--help-filters` available for a future terminal-friendly human view.

---

## 4. Background

### 4.1 What pipeline mode shipped

The umbrella (`docs/features/archive/pipeline-mode-spec.md`, shipped 2026-05-16) made fincli consumable via subprocess: `fincli --filters-json '{"fa_pe":"u20"}' --output - --json-summary` produces a CSV on stdout, a JSON summary on stderr, and exits with a classified code (0/1/2/3/4). That's enough for any language that can spawn a process to drive fincli end-to-end.

### 4.2 What's still missing for non-Python consumers

A Go (or any non-Python) developer integrating fincli today must know:

| Information | How they get it today |
|---|---|
| Which filter `query_key`s are valid | Read Python source files OR hit fincli with bad input and parse the `UsageError` suggestions |
| Which `value_code`s are valid per key | Same — Python source files only |
| Human-readable labels for dropdowns | Same |
| CSV column schema | Read `CONTRACTS.md` §3.1 manually |
| JSON summary schema | Read `CONTRACTS.md` §5.5 manually |
| Exit-code meanings | Read `CONTRACTS.md` §1 manually |

The first three rows are the painful ones — they force the integrator to either hardcode the Finviz vocabulary (which drifts when fincli adds params) or build a Python source-file reader (gross from Go). The rest are one-time CONTRACTS reads that don't need machine-readable form.

### 4.3 The fix

A new `--list-filters --json` flag that dumps the full inventory in one shot, plus an `INTEGRATION.md` that points the non-Python integrator at the existing CLI surface with the right idioms.

---

## 5. Design

### 5.1 CLI surface

| Flag | Type | Default | Behavior |
|---|---|---|---|
| `--list-filters` | flag | `False` | Dump the filter inventory to **stdout** as JSON and exit **0**. Honors no other flags except `--json` (which is the only format today; reserved for future `--yaml` / `--text`). |
| `--json` | flag | `False` | Format selector for `--list-filters`. Today the only valid format — passing `--list-filters` without `--json` exits **2** with a usage error directing the caller to add `--json` (or, in the future, another format flag). Reserved so the inventory contract can grow new formats without breaking. |

**Mutex set**: `--list-filters` is mutually exclusive with all input-mode flags (`--filter`, `--filters-json`, `--filters-file`, `--history`, `--scrape-link`). Combining them = exit **2** with the extended canonical mutex message. Rationale: `--list-filters` is a metadata-dump mode, not a screen-run mode; there's no "screen these filters AND also dump the inventory" use case.

**Click implementation**: extend `run_main` in `fincli/app/cli.py` with two new options. The mutex-counter at the existing input-mode check site (`cli.py:_normalize_filter_input` site) gains a new branch — if `list_filters` is set, the function short-circuits and calls a new `_emit_filter_inventory()` helper, then `sys.exit(0)`. No interaction with `run_stock_screener` — the screener pipeline never runs in this mode.

**Routing**: stdout. `--output PATH` and `--output -` are NOT honored in `--list-filters` mode (they're screen-result destinations; the inventory dump is metadata, always to stdout). `--quiet`, `--json-summary`, `--debug` are also no-ops in this mode (no progress to suppress, no summary to emit).

### 5.2 JSON payload contract

**Top-level shape** (mirrors the `JSON_SUMMARY_SCHEMA_VERSION = 1` pattern from Pillar 3's §5.5):

```json
{
  "schema_version": 1,
  "keys": ["fa_pe", "sec", "ta_rsi"],
  "filters": {
    "fa_pe": {
      "label": "PE",
      "values": {
        "": "Any",
        "low": "Low (<15)",
        "profitable": "Profitable (>0)",
        "u5": "Under 5",
        "u10": "Under 10",
        "u20": "Under 20"
      }
    },
    "sec": {
      "label": "Sector",
      "values": {
        "": "Any",
        "basicmaterials": "Basic Materials",
        "communicationservices": "Communication Services"
      }
    },
    "ta_rsi": {
      "label": "RSI 14",
      "values": { "": "Any", "ob70": "Overbought (70)", "os30": "Oversold (30)" }
    }
  }
}
```

**Field contract**:

| Field | Type | Notes |
|---|---|---|
| `schema_version` | int | Pinned to `1`. Bump on any breaking change (rename, remove, dtype change). Adding new filter entries or new value codes inside an existing entry is **additive** and does NOT bump the version. |
| `keys` | list[str] | **Canonical ordering contract.** Lists every Finviz `query_key` in canonical declaration order (Fundamental → Descriptive → Technical). Consumers that need stable order (Go's `encoding/json` decode into `map[string]T` randomizes iteration; JS object iteration is engine-defined) MUST iterate `keys` and index into `filters[key]`. Length and membership must equal `filters.keys()` exactly — this is a tested invariant per §7.3. |
| `filters` | dict | Keyed by Finviz `query_key` (NOT the Python attribute name). Python emits in `keys` order, but consumers MUST NOT rely on JSON-object iteration order across languages — use the `keys` field instead. |
| `filters[key].label` | str | Human-readable label for the key, derived per §5.3. Starting-point only; consumers can override locally for UX polish. |
| `filters[key].values` | dict | `{value_code: value_label}`. The empty `""` value-code (the "Any" sentinel) is included — it's a legal filter value the validator accepts. Same iteration-order caveat as `filters` — if value-order ever matters to a consumer, raise an OQ for a parallel `values_keys` array (out of scope today; not needed for the Go consumer per spec §4.2). |

**Source of truth**: walks the same three param classes (`Fundamental_Params`, `Descriptive_Params`, `Technical_Params`) that `validators.py:list_valid_filters()` walks. Reuses the existing walker logic; extends it to capture the human label (today's helper drops it).

**Payload size**: ~46 KB across the 3 classes (66 filter keys total: 29 Fundamental + 18 Descriptive + 19 Technical, measured live post-T2 at 47,216 bytes). Small enough to fetch once at consumer-app startup and cache.

**Key-ordering nuance**: `keys` ordering is by **class membership**, not by key-prefix. Keys with prefix `sh_*` appear in both `Fundamental_Params` (insider/institutional ownership: `sh_insiderown`, `sh_insidertrans`, `sh_instown`, `sh_insttrans`) and `Descriptive_Params` (shares outstanding / average volume / price / float: `sh_outstanding`, `sh_opt`, `sh_avgvol`, `sh_relvol`, `sh_curvol`, `sh_price`, `sh_float`); both groups respect the Fundamental → Descriptive → Technical class order even though their prefixes interleave. Consumers iterating `keys` see all Fundamental `sh_*` entries first, then a switch into Descriptive entries (some of which are also `sh_*`), then Technical.

**Stability policy**: the JSON payload format is added to `CONTRACTS.md` §7 stability list alongside the JSON summary schema (§5.5).

### 5.3 Label derivation algorithm

New private module: `fincli/resource/params/_label_format.py`. Single function `attr_to_label(attr: str) -> str` that mechanically derives a display label from a Python attribute name.

```python
"""Mechanical label derivation for Finviz filter keys.

The params files store the human-readable VALUE labels alongside the
value codes (e.g., {"u5": "Under 5"}) but provide no human label for
the KEY itself — only the Python attribute name (e.g., `PE`,
`FORWARD_PE`, `EPS_GROWTH_NEXT_5_YEARS`). This module derives a
display label from that attribute name with three rules:

  1. Preserve known acronyms (PE, ROA, EPS, RSI, ...) as-is.
  2. Lowercase common connector words (to, and, of, ...) when not first.
  3. Title-case everything else.

Derived labels are a starting point only — consumers can override
locally for UX polish (e.g., "P/E" with a slash). Avoiding the
augmentation of params files keeps the existing two-element-list
contract stable per CONTRACTS §2.
"""

from __future__ import annotations

_ACRONYMS: frozenset[str] = frozenset(
    {
        # Fundamental ratios
        "PE", "PEG", "PB", "PS", "PC", "PFCF",
        # Returns
        "ROA", "ROE", "ROI",
        # Earnings / averages / volatility
        "EPS", "SMA", "ATR", "RSI",
        # Misc
        "LT", "IPO", "REIT",
    }
)

_CONNECTORS: frozenset[str] = frozenset(
    {"to", "and", "or", "of", "in", "at", "by", "for", "with"}
)


def attr_to_label(attr: str) -> str:
    """Mechanical capitalization of a Python attribute name to display label.

    Args:
        attr: Python attribute name from a params class (e.g., ``"FORWARD_PE"``).

    Returns:
        A display label suitable for a dropdown title (e.g., ``"Forward PE"``).

    Examples:
        >>> attr_to_label("PE")
        'PE'
        >>> attr_to_label("FORWARD_PE")
        'Forward PE'
        >>> attr_to_label("PRICE_TO_CASH")
        'Price to Cash'
        >>> attr_to_label("EPS_GROWTH_NEXT_5_YEARS")
        'EPS Growth Next 5 Years'
        >>> attr_to_label("LT_Debt_TO_Equity")
        'LT Debt to Equity'
        >>> attr_to_label("Twenty_Day_Simple_Moving_Average")
        'Twenty Day Simple Moving Average'
    """
    parts = attr.split("_")
    out: list[str] = []
    for i, p in enumerate(parts):
        if p.upper() in _ACRONYMS:
            out.append(p.upper())
        elif i > 0 and p.lower() in _CONNECTORS:
            out.append(p.lower())
        else:
            out.append(p.capitalize())
    return " ".join(out)
```

**Known cosmetic limitations** (intentional, not bugs):
- Preserves the typo `Fifty_Tow_Day_High_Low` → `"Fifty Tow Day High Low"` (separate fix-the-typo PR can address it without touching this contract).
- `PE` renders as `"PE"`, not `"P/E"`. Consumer adds the slash if it wants the canonical financial-press form.
- `QTR` (in `EPS_GROWTH_QTR_OVER_QTR`) renders as `"Qtr"` (not in `_ACRONYMS`). Add to the acronyms set if reviewers prefer `"EPS Growth QTR Over QTR"`.

### 5.4 Inventory builder

New private function in `fincli/resource/params/validators.py` (sibling of the existing `list_valid_filters()`):

```python
def list_valid_filters_with_labels() -> dict[str, dict[str, object]]:
    """Return the inventory in §5.2 shape — keys, labels, value-label maps.

    Used by `fincli --list-filters --json` to dump the inventory as JSON
    for non-Python consumers (Go, Node, etc.) per docs/features/list-filters-spec.md.
    """
```

Walks the same `_PARAM_CLASSES` constant that `list_valid_filters()` uses. **Implementation note**: BACKEND should extract a shared private helper (e.g., `_iter_param_entries() -> Iterator[tuple[str, str, dict[str, str]]]` yielding `(attr_name, query_key, values_dict)` triples) that both functions consume, rather than copy-pasting the walker logic. Keeps the param-class-introspection rule in one place. Per-entry shape for the new function: `{"label": attr_to_label(attr_name), "values": dict(values_dict)}`. Insertion order matches the param-class declaration order.

Existing `list_valid_filters()` stays unchanged in its public signature/behavior — it's called by `validate_filter_pairs()` for the codes-only validation path. The new function is a parallel labels-included view; refactoring its internals to use the shared walker is a side-effect of this spec, not a separate change.

### 5.5 Output emission

New private helper in `fincli/app/cli.py`:

```python
def _emit_filter_inventory() -> None:
    """Dump the filter inventory as JSON to stdout, exit 0.

    Called from `run_main` when --list-filters --json is set. Short-circuits
    the screener pipeline entirely. See docs/features/list-filters-spec.md §5.5.
    """
    import json
    from fincli.resource.params.validators import list_valid_filters_with_labels

    inventory = list_valid_filters_with_labels()
    payload = {
        "schema_version": 1,
        "keys": list(inventory.keys()),  # canonical ordering contract per §5.2
        "filters": inventory,
    }
    click.echo(json.dumps(payload, ensure_ascii=False))
    # caller (run_main) handles the exit
```

The constant `1` is pulled from a module-level `_LIST_FILTERS_SCHEMA_VERSION = 1` in `cli.py` so tests can import it directly (mirrors the `JSON_SUMMARY_SCHEMA_VERSION` pattern from Pillar 3).

JSON serialization: `json.dumps(..., ensure_ascii=False)` — single-line by default, no `indent=` kwarg. The Finviz labels are pure ASCII today, but `ensure_ascii=False` keeps the output clean if labels ever contain `&`, `<`, or non-ASCII characters. `click.echo` adds a trailing newline (standard stdout convention) so the stdout shape is `<single-line-json>\n` exactly.

---

## 6. CLI Surface (Reference — post-spec)

| Option | Alias | Type | Default | Description |
|---|---|---|---|---|
| `--history` | `--hist` | flag | `False` | (existing) |
| `--debug` | — | flag | `False` | (existing) |
| `--scrape-link` | — | string | `""` | (existing) |
| `--filter` | — | repeatable string | `()` | (existing — Pillar 1) |
| `--filters-json` | — | string | `""` | (existing — Pillar 1) |
| `--filters-file` | — | path | `None` | (existing — Pillar 1) |
| `--output` | `-o` | string | `""` | (existing — Pillar 2) |
| `--quiet` | `-q` | flag | `False` | (existing — Pillar 3) |
| `--json-summary` | — | flag | `False` | (existing — Pillar 3) |
| **`--list-filters`** | — | flag | `False` | **NEW.** Dump filter inventory and exit 0. Mutex with all input-mode flags. Requires `--json` (the only format today). |
| **`--json`** | — | flag | `False` | **NEW.** Format selector for `--list-filters`. Today the only valid format. |

**Extended mutex set** (input-mode flags now 6):
```
--filter / --filters-json / --filters-file / --history / --scrape-link / --list-filters
are mutually exclusive; pick one input mode.
```

`--list-filters` joins the mutex set because it's an alternative entry mode (metadata-dump instead of screen-run). `--output` / `--quiet` / `--debug` / `--json-summary` remain orthogonal to the mutex.

`--json` is a sub-flag of `--list-filters` — silently ignored when `--list-filters` is not set, so adding `--json` to an unrelated invocation doesn't break it. If future commands reuse `--json` for their own formats, revisit then. See OQ2 in §14.

---

## 7. Acceptance Criteria

### 7.1 Back-compat (must pass first)
- [ ] All existing tests (203 + 1 skipped post-pipeline-mode) still pass.
- [ ] `fincli` (no flags) still launches the interactive picker.
- [ ] `fincli --history`, `fincli --scrape-link <url>`, `fincli --filter fa_pe=u20`, etc. unchanged in behavior.
- [ ] CONTRACTS §1 mutex message extended with `--list-filters`; existing mutex tests still pass with the updated message.

### 7.2 New flag — CLI surface
- [ ] `fincli --list-filters --json` exits **0**.
- [ ] `fincli --list-filters` (without `--json`) exits **2** with a UsageError message naming `--json` as required.
- [ ] `fincli --list-filters --json --filter fa_pe=u20` exits **2** with the extended mutex message.
- [ ] `fincli --list-filters --json --history` exits **2** with the extended mutex message.
- [ ] `fincli --list-filters --json --scrape-link=<url>` exits **2** with the extended mutex message.
- [ ] `fincli --list-filters --json --output ./foo.csv` — `--output` is ignored (inventory always goes to stdout); exits 0; no file created at `./foo.csv`.
- [ ] `fincli --list-filters --json --quiet --debug --json-summary` — all three orthogonal flags ignored; exits 0; stdout = JSON inventory only.
- [ ] `fincli --help` lists `--list-filters` and `--json` with their descriptions.

### 7.3 JSON payload — schema
- [ ] Stdout contains exactly one JSON object on a single line (no pretty-printing — see OQ1; tests assert by parsing the line, not by counting newlines beyond the trailing `\n` that `click.echo` adds).
- [ ] Top-level keys: exactly `["schema_version", "keys", "filters"]`.
- [ ] `schema_version == 1`.
- [ ] `keys` is a non-empty list of strings.
- [ ] `set(keys) == set(filters.keys())` (membership matches exactly — no orphan keys, no missing entries).
- [ ] `len(keys) == len(filters)` (no duplicate keys).
- [ ] `keys` order matches param-class declaration order: every Fundamental key appears before every Descriptive key; every Descriptive before every Technical.
- [ ] `filters` is a non-empty dict.
- [ ] Every value in `filters` is a dict with exactly the keys `["label", "values"]`.
- [ ] Every `filters[k].label` is a non-empty string.
- [ ] Every `filters[k].values` is a non-empty dict with string keys and string values.
- [ ] Insertion order: first entries are from `Fundamental_Params`, then `Descriptive_Params`, then `Technical_Params`.

### 7.4 JSON payload — content sampling
- [ ] `filters["fa_pe"].label == "PE"`.
- [ ] `filters["fa_pe"].values[""] == "Any"`.
- [ ] `filters["fa_pe"].values["u20"] == "Under 20"`.
- [ ] `filters["sec"].label == "Sector"`.
- [ ] `filters["sec"].values["basicmaterials"] == "Basic Materials"`.
- [ ] `filters["ta_rsi"].label == "RSI 14"`.
- [ ] At least one filter from each of the three param classes is present in `filters`.

### 7.5 Label derivation
- [ ] `attr_to_label("PE") == "PE"`.
- [ ] `attr_to_label("FORWARD_PE") == "Forward PE"`.
- [ ] `attr_to_label("PRICE_TO_CASH") == "Price to Cash"`.
- [ ] `attr_to_label("EPS_GROWTH_NEXT_5_YEARS") == "EPS Growth Next 5 Years"`.
- [ ] `attr_to_label("LT_Debt_TO_Equity") == "LT Debt to Equity"`.
- [ ] `attr_to_label("Twenty_Day_Simple_Moving_Average") == "Twenty Day Simple Moving Average"`.
- [ ] `attr_to_label("ROA") == "ROA"`, `"ROE"` → `"ROE"`, `"ROI"` → `"ROI"`.

### 7.6 Integration doc
- [ ] `INTEGRATION.md` exists at repo root.
- [ ] Contains: audience/scope, bootstrap flow (`--list-filters`), call flow (`--filters-json` + `--output -` + `--json-summary`), exit-code routing table (0/1/2/3/4 → recommended consumer behavior), OUTPUT_PATH= recovery pattern, concurrency notes, caching guidance.
- [ ] Per-language cookbook section exists with a placeholder noting Go/Node examples are deferred.
- [ ] README.md "Pipeline mode" section gets a one-line pointer to INTEGRATION.md.

---

## 8. Test Plan

**New test files** (3):

| File | Cases | Coverage |
|---|---|---|
| `tests/unit/resource/params/test_label_format.py` | ~10 (parametrize) | Every example from §5.3 + acronym preservation + connector-word lowercasing + edge cases (single-word, all-caps, mixed-case input) |
| `tests/unit/app/test_cli_list_filters.py` | ~8 | Option parses; `--json` requirement; mutex with each of the 5 input modes; orthogonal-flag no-op behavior (`--output`, `--quiet`, `--json-summary`, `--debug` all ignored when `--list-filters` is set); `--help` lists the new flags |
| `tests/integration/test_list_filters_output.py` | ~5 | Subprocess invoke `python -m fincli --list-filters --json`, parse stdout as JSON, validate every §7.3 + §7.4 acceptance bullet; assert exit code 0 |

**Existing tests touched**: `tests/unit/app/test_cli_pipeline.py` — extend the mutex tests to include `--list-filters` pairings (so the extended mutex set is exercised). Existing assertions stay; new cases added.

**Mocking strategy**: no HTTP — `--list-filters` short-circuits the pipeline before any scrape, so no `fetch_page_sync` mock needed.

**TESTING.md note** (one-paragraph addition): the new test files follow the existing layout convention (`tests/unit/resource/params/`, `tests/unit/app/`, `tests/integration/`).

---

## 9. Out of Scope (Deferred)

- **Per-language cookbook examples in INTEGRATION.md** (Go, Node, Rust, etc.). The user decided to think about these later; the doc lands with a placeholder section.
- **`--help-filters` (human-readable terminal view)**. Could be added later as a sibling flag; this spec leaves the name available.
- **Other format flags** (`--list-filters --yaml`, `--list-filters --text`). The `--json` flag is reserved for future format flexibility but only the JSON format ships now.
- **Typo fix for `Fifty_Tow_Day_High_Low`** (should be `Two`). Separate one-line PR; this spec preserves the existing label to avoid conflating cleanup with feature work.
- **Augmenting params files with explicit `label` field**. Considered and rejected — derives mechanically is cheaper and avoids touching CONTRACTS §2's stable 2-element-list contract.
- **HTTP server / gRPC layer / `fincli serve`**. Out of scope; existing subprocess pattern is the integration boundary.
- **JSON output mode for screen results** (`fincli --filter ... --output - --format json`). Not requested; CSV stays the screen-result contract per CONTRACTS §3.1.

---

## 10. Migration & Rollout

### 10.1 Back-compat guarantees

100% additive. Zero breaking changes. Per CONTRACTS §7:
- New CLI options with safe defaults (`--list-filters: False`, `--json: False`) — **non-breaking**.
- New private module (`_label_format.py`) — internal only, not in §6 importable surface.
- New private function (`list_valid_filters_with_labels`) — internal; not yet documented in §6.
- New JSON payload schema — documented in CONTRACTS §5.6 (new sub-section) with `schema_version: 1` pinning.
- Existing `validate_filter_pairs` / `list_valid_filters` / `select_filters_and_values` / `run_stock_screener` / `build_config` signatures unchanged.
- CLI mutex message text changes (adds `--list-filters` to the canonical list) — flagged as a doc-text update, not a contract-shape change.

### 10.2 Commit-message convention

Three commits recommended:

1. `feat(params): add attr_to_label + list_valid_filters_with_labels helpers (list-filters-spec)` — the pure-Python helpers + their unit tests. Independent of CLI wiring; can verify in isolation.
2. `feat(cli): add --list-filters --json flag for non-Python consumers (list-filters-spec)` — the CLI option, mutex extension, output emission. + CLI tests + integration test.
3. `docs(integration,contracts): add INTEGRATION.md + CONTRACTS §5.6 for filter inventory dump` — INTEGRATION.md, CONTRACTS edits, README pointer, MODULE_REFERENCE entry, THESIS Change Log, FEEDBACK-LOG entry.

If diff sizes are small, can fold 1 + 2 into a single commit.

### 10.3 FEEDBACK-LOG entry template

```markdown
### 2026-05-XX — Filter inventory dump (--list-filters --json)

Closes the polyglot-discoverability gap that pipeline mode (shipped
2026-05-16) intentionally deferred. Adds a single new CLI flag plus a
new INTEGRATION.md for non-Python consumers (initially a Go project,
future polyglot callers).

**Decisions captured:**

- **Polyglot framing**: JSON is the format; all four shape options were
  JSON. Picked nested-with-labels (`{label, values: {...}}`) over flat
  codes-only or grouped-by-category. Anti-polyglot Python-tuple form
  rejected. Spec §5.2.

- **Label algorithm = mechanical derivation, not data augmentation**.
  Avoids touching params files' 2-element-list contract (CONTRACTS §2).
  Acronyms preserved via hardcoded set; connector words lowercased.
  Spec §5.3.

- **`schema_version: 1` pinned** mirroring JSON summary §5.5 pattern.
  Adding new filters/values is non-breaking; rename/remove bumps version.

- **`--list-filters` not `--help-filters`**: leaves `--help-filters`
  available for a future human-readable terminal view. Spec §3.

- **No HTTP server**: subprocess pattern stays the integration boundary
  (CLI was made pipeline-ready in the umbrella for exactly this purpose).
  Spec §3 / §9.

- **Per-language cookbook examples deferred**. INTEGRATION.md lands the
  language-agnostic patterns now; Go/Node working examples added when
  the consumer project is further along.
```

---

## 11. File-by-File Changes

| File | Lines / functions | Change |
|---|---|---|
| `fincli/resource/params/_label_format.py` | NEW | `_ACRONYMS` + `_CONNECTORS` constants + `attr_to_label(attr: str) -> str` function. Per §5.3. |
| `fincli/resource/params/validators.py` | + new function | Add `list_valid_filters_with_labels()` (the inventory walker that returns the §5.2 shape). Reuses existing `_PARAM_CLASSES`. Import `attr_to_label` from `_label_format`. Per §5.4. |
| `fincli/app/cli.py` | new options + helper + mutex branch | Add `@click.option("--list-filters", is_flag=True)` and `@click.option("--json", "json_format", is_flag=True)`. Extend mutex counter at the input-mode check site. New `_emit_filter_inventory()` helper. New module constant `_LIST_FILTERS_SCHEMA_VERSION = 1`. Update `_MUTEX_MSG` to include `--list-filters`. Per §5.1 + §5.5. |
| `tests/unit/resource/params/test_label_format.py` | NEW, ~10 cases | Per §8 row 1. |
| `tests/unit/app/test_cli_list_filters.py` | NEW, ~8 cases | Per §8 row 2. |
| `tests/integration/test_list_filters_output.py` | NEW, ~5 cases | Per §8 row 3. |
| `tests/unit/app/test_cli_pipeline.py` | extend | Add `--list-filters` pairings to the mutex test set. |
| `INTEGRATION.md` | NEW (root) | Per §12 below. |
| `CONTRACTS.md` | §1 (option table + behavior table + mutex message), new §5.6 (inventory JSON schema), §7 (add inventory schema to stability list) | Per §13.1 below. |
| `docs/MODULE_REFERENCE.md` | new entry | `fincli.resource.params._label_format` (private) + extended entry for `validators.py` (new `list_valid_filters_with_labels` function). |
| `docs/THESIS.md` | Change Log | Add 2026-05-XX entry: "Filter inventory dump (`--list-filters --json`) + INTEGRATION.md shipped." |
| `docs/FEEDBACK-LOG.md` | New dated entry | Per §10.3 template. |
| `README.md` | "Pipeline mode" section | One-line pointer: `For non-Python integrators (Go, Node, etc.), see [INTEGRATION.md](INTEGRATION.md).` |
| `TESTING.md` | "Pipeline mode" subsection | One-paragraph note about the new test files following existing layout. |

---

## 12. INTEGRATION.md structure

```markdown
# INTEGRATION.md — Non-Python Consumers

This document is for **non-Python apps** (Go, Node, Rust, etc.) that
want to use fincli's pipeline mode via subprocess. Python integrators
should use the importable surface (see CONTRACTS §6).

## Audience & scope
[brief — who this is for, what's covered]

## Bootstrap: discover the filter inventory
- Run `fincli --list-filters --json` once at app startup
- Cache the result (filter inventory rarely changes)
- Use it to validate user input + build dropdowns / autocomplete
- Schema: see CONTRACTS §5.6

## Per-screen call flow
- `fincli --filters-json '{...}' --output - --json-summary`
- Read CSV from stdout; parse JSON summary from stderr's last line
- Check exit code per the routing table below

## Exit-code routing
| Code | Meaning | Recommended consumer behavior |
|---|---|---|
| 0 | Success (incl. zero rows) | Process results |
| 1 | Internal failure | Surface error; do not retry |
| 2 | Usage / input validation | Bug in caller; fix the input |
| 3 | Upstream / network | Retry with backoff |
| 4 | Data / parse failure | Surface error; do not retry (Finviz layout likely changed) |

## OUTPUT_PATH= discovery (when --json-summary not used)
- Last line of stderr is always `OUTPUT_PATH=<value>`
- `<value>` is absolute path for file mode, literal `-` for stdout mode
- Extract via `tail -n1 stderr | cut -d= -f2-`

## Concurrency notes
- fincli is stateless per-run; safe to spawn multiple subprocesses in parallel
- cfscrape's anti-bot pacing is in-process; concurrent calls = independent scrape contexts (no shared rate-limit state)

## Caching guidance
- Filter inventory: cache hours-to-days (rarely changes)
- Screen results: cache per filter-set if your access pattern is repeated (fincli scrapes are slow — ~0.5-2s per Finviz page)

## Per-language cookbook
**Deferred.** Working Go / Node examples will be added in a follow-up.
Today this section is a placeholder so contributors know where the
canonical examples will live.

## Reference
- Full CLI surface: CONTRACTS.md §1
- CSV schema: CONTRACTS.md §3.1
- JSON summary schema: CONTRACTS.md §5.5
- Filter inventory schema: CONTRACTS.md §5.6
- Exit-code classifier source: fincli/app/exit_codes.py
```

---

## 13. Spec Updates

### 13.1 CONTRACTS.md

**§1 — Options table**: add `--list-filters` and `--json` rows per §6.

**§1 — Mutex message**: extend the canonical text to include `--list-filters`:
```
--filter / --filters-json / --filters-file / --history / --scrape-link / --list-filters
are mutually exclusive; pick one input mode.
```

**§1 — Behavior table**: add new row:
> `--list-filters --json` | Dump filter inventory as JSON to stdout, exit 0. No screen run. `--output` / `--quiet` / `--json-summary` / `--debug` ignored. `--list-filters` without `--json` exits 2 with a usage error. Mutex with all input-mode flags.

**§5.6 — NEW**: filter inventory JSON schema (mirrors §5.5 JSON summary section style). Document the §5.2 top-level shape, field contract, `schema_version: 1` policy, and source-of-truth (`fincli.resource.params.validators.list_valid_filters_with_labels`).

**§7 — Stability policy**: add bullet:
- *"The §5.6 filter inventory JSON schema (field set, types, value constraints) — additions are non-breaking and bump no version; removals/renames/semantic changes bump `schema_version` and are breaking."*

### 13.2 docs/MODULE_REFERENCE.md

Add new entry for `fincli.resource.params._label_format` (private; `attr_to_label`). Extend existing `validators.py` entry with the new `list_valid_filters_with_labels` function.

### 13.3 docs/THESIS.md

Change Log entry: `2026-05-XX | Filter inventory dump shipped (--list-filters --json) + INTEGRATION.md for non-Python consumers. Closes polyglot-discoverability gap deferred by pipeline mode umbrella.`

### 13.4 docs/FEEDBACK-LOG.md

Per §10.3 template.

### 13.5 README.md

"Pipeline mode" section gets a final-line pointer to INTEGRATION.md.

### 13.6 TESTING.md

"Pipeline mode" subsection: one paragraph noting the three new test files and that they follow the existing layout (`tests/unit/resource/params/`, `tests/unit/app/`, `tests/integration/`).

---

## 14. Open Questions (HUMAN gate review)

| # | Question | ARCH proposal | Notes |
|---|---|---|---|
| OQ1 | Pretty-print the JSON output or single-line? | **Single-line**. Smaller payload, idiomatic for machine consumption, simpler for tests to assert. Pretty-print is for humans; this output is for non-Python apps. | If a human ever wants to read it, `\| python -m json.tool` is one pipe away. |
| OQ2 | `--json` flag — silently ignored when `--list-filters` is not set, or rejected with a usage error? | **Silently ignored.** Adding `--json` to an unrelated invocation shouldn't break it. If future commands reuse `--json`, revisit then. | Trade-off: tighter validation vs forward-compat with future format selectors. |
| OQ3 | Should `--list-filters` honor `--quiet`? | **No** (no-op). The output is the result, not chatter. `--quiet` wouldn't suppress JSON output anyway. | Documented behavior in §5.1. |
| OQ4 | Should the spec also fix the `Fifty_Tow_Day_High_Low` typo? | **No.** Conflating typo cleanup with feature work obscures both. Separate one-line PR after this ships. | Spec §9. |
| OQ5 | Add `QTR` to `_ACRONYMS` so `EPS_GROWTH_QTR_OVER_QTR` renders as `"EPS Growth QTR Over QTR"`? | **No** (renders as `"Qtr"`). Reasonable consumer can override. Avoid micro-tuning the acronym list. | If reviewer disagrees, one-line addition to `_ACRONYMS`. |

---

## 15. Sign-off

This spec is **DRAFT** pending HUMAN review per the brainstorming-skill flow. After approval, plan-and-create's writing-plans skill produces the implementation plan; BACKEND ships in 2–3 commits per §10.2; VERIFIER → REVIEWER → QA → HUMAN gates close out per pipeline-mode precedent.
