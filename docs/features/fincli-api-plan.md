# Fin CLI HTTP API — Implementation Plan

> **For executing agents:** This plan translates an already-approved spec into sequenced, parallelizable tasks. Do NOT re-design — the spec at `docs/superpowers/specs/2026-05-22-fincli-api-design.md` is the source of truth for *what* and *why*. This plan owns *how* and *in what order*. Each task is gated by VERIFIER → REVIEWER → QA → HUMAN per the pipeline-mode + list-filters precedent.

---

## §1 — Plan Status & Cross-References

| Field | Value |
|---|---|
| Plan Status | DRAFT (pending HUMAN approval) |
| Version | 0.1 DRAFT |
| Drafted | 2026-05-22 |
| Author | ARCH (plan-and-create Phase 1, on top of HUMAN-approved spec) |
| Mode | PLAN_AND_CREATE |
| Spec source | `docs/superpowers/specs/2026-05-22-fincli-api-design.md` |
| Spec status transition | DESIGN → IN_PROGRESS when T1 starts; → SHIPPED on T-FINAL commit (then archived to `docs/superpowers/specs/archive/` or per project convention) |
| Branch | `feat/fincli-api` (already created) |
| Cycle | plan-and-create → execute |
| Owner agent rotation | ARCH (this file) → HUMAN-approve plan → BACKEND (T1..T-FINAL) with VERIFIER + REVIEWER + QA + HUMAN gates between each |
| Iteration cap per gate | 2–3 round-trips, then escalate to HUMAN (per §6 below) |
| Related precedents | `docs/features/archive/list-filters-plan.md` (3-task multi-commit rollout with VERIFIER/REVIEWER/QA/HUMAN gates; archive-on-ship banner); `docs/features/archive/pipeline-mode-spec.md` (six-task rollout) |

**Section-level mapping back to spec** (so the executing agent can verify nothing in this plan contradicts an approved decision):

| Plan task | Spec section it implements |
|---|---|
| T1 (skeleton + helper) | §3.1 module layout; §3.2 boundary helper note (`screen_to_dataframe` in `fincli/app/main.py`); §7 `pyproject.toml` row |
| T2a/T2b/T2c (Pydantic models) | §4.2 `ScreenRequest`; §4.3 `ScreenResult` + `Stock`; §4.4 `FilterInventory` + `FilterEntry`; §5.2 `ErrorResponse` |
| T3 (adapter) | §3.2 `get_filter_inventory` + `run_screen`; §3.3 sync process model |
| T4a/T4b/T4c (routes + exception handlers) | §4.1 endpoint table; §4.2–§4.4 endpoint shapes; §5.1–§5.3 error handling; §3.3 sync endpoints |
| T5a (unit tests) | §6.1 unit tier |
| T5b (integration tests) | §6.2 integration tier (reuses `tests/integration/_fixtures_loader.py` fixtures) |
| T5c (e2e tests) | §6.3 e2e tier + §6.3 mandatory live-Finviz gate |
| T6 (OpenAPI snapshot + dump script) | §7 row for `docs/api/openapi.yaml` + spec text "small dump helper script" |
| T7a..T7d (early docs) | §7 rows: `CLAUDE.md`, `THESIS.md`, `FEEDBACK-LOG.md`, `README.md` |
| T8a..T8f (post-code docs) | §7 rows: `CONTRACTS.md`, `MODULE_REFERENCE.md`, `INTEGRATION.md`, `TESTING.md`, `AGENTS.md`, plus spec archive flip |
| T-FINAL (live e2e gate + acceptance walkthrough) | §6.3 mandatory live gate; §8 acceptance criteria 1–10 |

---

## §2 — Summary

Twelve tasks (with internal letter-suffixed parallel siblings, totalling ~21 atomic units) deliver the `fincli_api/` HTTP server alongside the existing CLI. T1 establishes the project skeleton (pyproject deps + script entry + package discovery, the `fincli_api/` package tree, the small `screen_to_dataframe` helper in `fincli/app/main.py`, the OpenAPI dump helper). T2a/T2b/T2c land the three Pydantic model modules in parallel (filters, screens, errors — no shared state, three independent files). T3 ships the `fincli_api/adapters/fincli.py` boundary (the only file allowed to import from `fincli/`). T4a/T4b/T4c land the three routers in parallel + T4d ships the exception handler. T5a (unit), T5b (integration), T5c (e2e) land the three-tier test pyramid; T5a can begin alongside T4 (mocked adapter), T5b waits on T3+T4, T5c waits on everything. T6 generates the committed `docs/api/openapi.yaml` snapshot. T7a–T7d update early-eligible docs (no shipped-shape dependency) in parallel; T8a–T8f update post-code docs (need final shapes) in parallel. T-FINAL runs the live-Finviz gate and walks the §8 acceptance criteria for HUMAN sign-off.

Longest sequential chain: **T1 → T2 (models) → T3 (adapter) → T4 (routes) → T5b (integration) → T6 (openapi.yaml) → T8 (post-code docs) → T-FINAL**. Eight sequential waves; everything else parallelizes inside each wave. Spec ambiguity resolved inline: §9 below documents the choice to keep the OpenAPI dump helper in `scripts/dump_openapi.py` (matches existing `scripts/check_requirements.py` precedent) rather than under `fincli_api/`.

---

## §3 — Inputs (specs/docs this plan derives from)

- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\algo_beta\docs\superpowers\specs\2026-05-22-fincli-api-design.md` — authoritative design spec (G1-G8, N1-N10, §3 architecture, §4 API surface, §5 error model, §6 testing, §7 docs sweep, §8 acceptance criteria)
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\algo_beta\docs\features\archive\list-filters-plan.md` — structural template for THIS plan (section ordering, validation-gate format, parallelization-section pattern)
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\algo_beta\docs\features\archive\pipeline-mode-spec.md` — precedent for archive-on-ship banner format
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\algo_beta\CLAUDE.md` — Build & Run + Conventions + Phase Status (Phase 4 mypy ambition → new `fincli_api/` code must be fully typed)
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\algo_beta\AGENTS.md` — workflow rules + role files (`tests/{unit,integration,e2e}/api/` paths get added in T8e)
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\algo_beta\ARCHITECTURE.md` — layer structure; the new entry point is documented as a sibling, not a layer change
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\algo_beta\CONTRACTS.md` — current §7 stability list; new §8 HTTP API surface (T8a)
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\algo_beta\INTEGRATION.md` — gets restructured into two sub-modes in T8c
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\algo_beta\TESTING.md` — gets API-tier test pyramid section in T8d
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\algo_beta\pyproject.toml` — gets `fastapi`/`uvicorn[standard]`/`httpx` deps, `fincli-api` script, `fincli_api*` package discovery, `live` pytest marker (T1)
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\algo_beta\fincli\app\main.py` — gets `screen_to_dataframe` helper added (T1); existing `_emit_run_tail` + `_build_summary` shape the `ScreenResult` model (T2b)
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\algo_beta\fincli\app\exit_codes.py` — `classify()` reused by exception handler (T4d)
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\algo_beta\fincli\resource\params\validators.py` — `list_valid_filters_with_labels` drives `GET /filters` (T3)
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\algo_beta\fincli\utils\quary_builders.py` — Finviz ticker URL builder (existing; reused by T3 adapter to populate `Stock.finviz_url`)
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\algo_beta\fincli\utils\market_cap.py` — `convert_market_cap_to_numeric` already coerces market cap (existing; the `Stock.market_cap: float | None` type tracks this)
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\algo_beta\tests\integration\_fixtures_loader.py` — existing HTML fixture loader (reused by T5b)
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\algo_beta\scripts\check_requirements.py` — existing `scripts/` precedent; `scripts/dump_openapi.py` is added in T1

---

## §4 — Task Dependency Graph

```
                         T1 (skeleton + helper + dump script + deps)
                                       |
            +--------------+-----------+----------------+
            |              |                            |
         T2a (filters)  T2b (screens)             T2c (errors)
            |              |                            |
            +------+-------+----------------------------+
                   |
                  T3 (adapters/fincli.py)
                   |
       +-----------+-----------+-------------+
       |           |           |             |
    T4a (filters T4b (screens T4c (meta   T4d (exception
     route)       route)       route)      handlers)
       |           |           |             |
       +-----------+----+------+-------------+
                        |
              +---------+---------+
              |                   |
           T5a (unit)         T5b (integration)
              |                   |
              +---------+---------+
                        |
                    T5c (e2e — mocked + structural)
                        |
                       T6 (commit openapi.yaml snapshot via dump script)
                        |
                +-------+--------+
                |                |
         T7a-T7d (early)   T8a-T8f (post-code)
         in parallel       in parallel
         (CLAUDE,          (CONTRACTS, MODULE_REFERENCE,
          THESIS,          INTEGRATION, TESTING, AGENTS,
          FEEDBACK-LOG,    spec archive flip)
          README)
                |                |
                +-------+--------+
                        |
                  T-FINAL (live-Finviz gate + §8 walkthrough + HUMAN sign-off)
```

**Parallel waves (in execution order):**

| Wave | Tasks | Depends on | Parallelism |
|---|---|---|---|
| W1 | T1 | none | sequential |
| W2 | T2a, T2b, T2c | T1 | 3-way parallel |
| W3 | T3 | T2a, T2b, T2c | sequential |
| W4 | T4a, T4b, T4c, T4d | T3 | 4-way parallel |
| W5 | T5a, T5b | T4* | 2-way parallel (T5a can start mid-W4 with mocked adapter) |
| W6 | T5c | T5a, T5b | sequential |
| W7 | T6 | T5c | sequential |
| W7' | T7a, T7b, T7c, T7d | T1 (can run concurrently with W2-W7) | 4-way parallel, eligible from W2 onward |
| W8 | T8a, T8b, T8c, T8d, T8e, T8f | T6 | 6-way parallel |
| W9 | T-FINAL | T7*, T8* | sequential |

**Critical path** (longest sequential chain): W1 → W2 → W3 → W4 → W5 (T5b) → W6 → W7 → W8 → W9 = **9 waves**.

---

## §5 — Tasks

### T1 — Project skeleton + cross-cutting bootstrap

| Field | Value |
|---|---|
| Owner | BACKEND |
| Effort | M (half-day) |
| Depends on | none |
| Can run in parallel with | none (everything else depends on this) |

**Scope (files touched, exhaustive):**

- Modify `pyproject.toml`:
  - `[project] dependencies` adds: `fastapi`, `uvicorn[standard]`
  - `[project.optional-dependencies] dev` adds: `httpx`
  - `[project.scripts]` adds: `fincli-api = "fincli_api.main:main"`
  - `[tool.setuptools.packages.find]` `include` adds: `"fincli_api*"`
  - `[tool.pytest.ini_options]` registers `markers = ["live: hits live Finviz; opt-in via -m live"]`; `addopts = "-m 'not live'"` (per spec §6.3 + §7)
  - `[[tool.mypy.overrides]]` for `cfscrape` left untouched; no new overrides needed (FastAPI, uvicorn, httpx all have inline type info)
- Create `fincli_api/__init__.py` (empty package marker, version string optional)
- Create `fincli_api/main.py` STUB:
  - `app = FastAPI(title="Fin CLI API", version="0.1.0")` with title/version constants
  - `def main() -> None:` calls `uvicorn.run("fincli_api.main:app", host=..., port=..., reload=False)` reading from `ApiConfig`
  - NO route includes yet (routers land in T4); add `# routes wired in T4` placeholder comment
  - Health endpoint stub deferred to T4c (so this file's content is intentionally minimal)
- Create `fincli_api/config.py`:
  - `class ApiConfig(BaseSettings)` with `host: str = "127.0.0.1"`, `port: int = 8000`, `log_level: str = "info"`, env prefix `FINCLI_API_`
- Create `fincli_api/routes/__init__.py` (empty)
- Create `fincli_api/models/__init__.py` (empty)
- Create `fincli_api/adapters/__init__.py` (empty)
- Modify `fincli/app/main.py`:
  - Add public helper `screen_to_dataframe(filters: dict[str, str]) -> pd.DataFrame` (or rename per BACKEND discretion within spec §3.2 wording). MUST be the same code path the existing `run_stock_screener` already uses for the CSV write — extract a shared internal so CSV write and in-memory return cannot drift. Do NOT change the public signature of `run_stock_screener` or its CSV-write behavior.
- Create `scripts/dump_openapi.py`:
  - Imports `app` from `fincli_api.main`, calls `app.openapi()`, writes pretty-printed YAML to `docs/api/openapi.yaml` (use `pyyaml` if already a dep, else JSON sibling at `docs/api/openapi.json` — confirm with `pyproject.toml`). Per §9 spec-ambiguity resolution.
  - Add a `__main__` block so `python scripts/dump_openapi.py` works
- Create `docs/api/` directory (committed as empty `.gitkeep` if needed; the actual `openapi.yaml` lands in T6 to avoid stale-snapshot churn during W4-W5)

**Out-of-scope reminders:**
- DO NOT add any Pydantic models in this task — that's T2
- DO NOT wire any routes — that's T4
- DO NOT add the `/healthz` handler — that's T4c
- DO NOT write `docs/api/openapi.yaml` content — T6 generates it after routes/models are stable

**Acceptance gates (T1-specific):**
- `pip install -e ".[dev]"` succeeds in a clean venv; `import fincli_api` and `import fincli_api.main` both work
- `python -c "from fincli_api.main import app; print(app.title)"` prints `Fin CLI API`
- `python scripts/dump_openapi.py` runs without error and produces a non-empty file at `docs/api/openapi.yaml` (or `.json`) — content shape is whatever FastAPI emits for an empty router set; T6 re-runs this after routes are wired
- `python -c "from fincli.app.main import screen_to_dataframe; print(screen_to_dataframe.__doc__)"` prints the Google-style docstring
- `ruff check fincli_api/ scripts/dump_openapi.py fincli/app/main.py` clean
- `ruff format --check fincli_api/ scripts/dump_openapi.py fincli/app/main.py` clean
- `mypy fincli_api/ scripts/dump_openapi.py` clean (strict; FastAPI/Pydantic/uvicorn typed)
- `mypy fincli/app/main.py` does not REGRESS from current state (advisory channel; the new helper is fully typed)
- `pytest tests/ -m "not live"` stays green (no behavior change to existing CLI)

**Per-task commit message:**
```
chore(api): scaffold fincli_api package + pyproject wiring + screen_to_dataframe helper (fincli-api-spec)

Adds the empty fincli_api/ package tree (main.py with FastAPI app stub,
config.py with ApiConfig, routes/ models/ adapters/ subpackages),
wires fincli-api script entry point and fastapi/uvicorn/httpx deps in
pyproject.toml, registers the `live` pytest marker (excluded by
default), and lands the screen_to_dataframe helper in fincli/app/main.py
that the upcoming adapter will use to obtain in-memory DataFrames
without writing CSV files. Also ships scripts/dump_openapi.py for
producing the committed OpenAPI snapshot.

Refs docs/superpowers/specs/2026-05-22-fincli-api-design.md §3.1, §3.2, §7.
```

---

### T2a — Pydantic models: `fincli_api/models/filters.py`

| Field | Value |
|---|---|
| Owner | BACKEND |
| Effort | S (1-2 hours) |
| Depends on | T1 |
| Can run in parallel with | T2b, T2c |

**Scope:**

- Create `fincli_api/models/filters.py` with two classes per spec §4.4:
  - `class FilterEntry(BaseModel)`: `label: str`, `values: dict[str, str]`
  - `class FilterInventory(BaseModel)`: `schema_version: int = 1`, `keys: list[str]`, `filters: dict[str, FilterEntry]`
- Add Pydantic v2 `model_config = ConfigDict(extra="forbid")` (strict) on both classes
- Add `Field(..., description=...)` annotations so OpenAPI schemas render with human prose
- Add ONE example payload via `model_config["json_schema_extra"]` for `FilterInventory` so Swagger UI's "Try it out" shows a realistic example

**Out-of-scope reminders:**
- DO NOT import from `fincli/` — models are pure data classes
- DO NOT define `ScreenRequest`/`ScreenResult` here (T2b) or `ErrorResponse` (T2c)
- DO NOT wire into a router (T4a)

**Acceptance gates (T2a-specific):**
- `python -c "from fincli_api.models.filters import FilterInventory, FilterEntry; print(FilterInventory.model_json_schema())"` emits valid JSON schema with `schema_version`, `keys`, `filters` properties
- `ruff check fincli_api/models/filters.py` clean
- `mypy fincli_api/models/filters.py` clean

---

### T2b — Pydantic models: `fincli_api/models/screens.py`

| Field | Value |
|---|---|
| Owner | BACKEND |
| Effort | S (1-2 hours) |
| Depends on | T1 |
| Can run in parallel with | T2a, T2c |

**Scope:**

- Create `fincli_api/models/screens.py` per spec §4.2, §4.3:
  - `class ScreenRequest(BaseModel)`: `filters: dict[str, str]` with `Field(..., examples=[{"fa_pe": "u5", "sec": "energy"}], description="...")`
  - `class Stock(BaseModel)`: 12 fields per spec §4.3 (`ticker`, `company`, `sector`, `industry`, `country`, `market_cap: float | None`, `pe: str | None`, `price: str`, `change: str`, `volume: str`, `rank: int`, `finviz_url: str`)
  - `class ScreenResult(BaseModel)`: `schema_version: int = 1`, `row_count: int`, `duration_ms: int`, `started_at: str`, `finished_at: str`, `stocks: list[Stock]`
- `model_config = ConfigDict(extra="forbid")` on `ScreenRequest` and `Stock`; mirror the JSON-summary shape from `fincli/app/main.py:_build_summary` for `ScreenResult` field naming consistency
- Add `Field(..., description=...)` per field; example payloads for `ScreenRequest` and `ScreenResult` (use the JSON example block in spec §4.3 as the `ScreenResult` example)
- Use `datetime` with `Field(..., examples=["2026-05-22T15:23:01.234Z"])` only if BACKEND prefers — spec specifies `str` for `started_at`/`finished_at` so leave as `str` unless a `datetime` field provides stricter ISO 8601 validation. Resolve in implementation; either is spec-conformant.

**Out-of-scope reminders:**
- DO NOT add `finviz_url` builder logic here — that's T3's adapter
- DO NOT call `fincli` from this module

**Acceptance gates (T2b-specific):**
- `python -c "from fincli_api.models.screens import ScreenRequest, ScreenResult, Stock; print(ScreenResult.model_json_schema())"` emits valid JSON schema
- A round-trip test (informal): construct a `ScreenResult` from the spec §4.3 example JSON via `ScreenResult.model_validate_json(...)` succeeds and `.model_dump_json()` produces semantically equivalent JSON
- `ruff check fincli_api/models/screens.py` clean
- `mypy fincli_api/models/screens.py` clean

---

### T2c — Pydantic models: `fincli_api/models/errors.py`

| Field | Value |
|---|---|
| Owner | BACKEND |
| Effort | S (1 hour) |
| Depends on | T1 |
| Can run in parallel with | T2a, T2b |

**Scope:**

- Create `fincli_api/models/errors.py` per spec §5.2:
  - `class ErrorResponse(BaseModel)`: `schema_version: int = 1`, `error_class: Literal["validation", "upstream", "parsing", "internal"]`, `message: str`, `details: dict | None = None`, `request_id: str | None = None`
- Add `Field` examples for each of the four `error_class` variants (one per spec §5.2 example block)
- The `Literal["validation", "upstream", "parsing", "internal"]` produces a discriminator-friendly OpenAPI enum — REVIEWER should confirm Swagger UI renders this correctly in T4d's gate

**Out-of-scope reminders:**
- DO NOT register exception handlers here — that's T4d
- DO NOT reference `classify()` from this module

**Acceptance gates (T2c-specific):**
- `python -c "from fincli_api.models.errors import ErrorResponse; e = ErrorResponse(error_class='validation', message='x'); print(e.model_dump_json())"` works
- `ruff check fincli_api/models/errors.py` clean
- `mypy fincli_api/models/errors.py` clean

---

### T3 — Adapter: `fincli_api/adapters/fincli.py`

| Field | Value |
|---|---|
| Owner | BACKEND |
| Effort | M (half-day) |
| Depends on | T1, T2a, T2b |
| Can run in parallel with | none (gating for T4) |

**Scope:**

- Create `fincli_api/adapters/fincli.py` per spec §3.2:
  - `def get_filter_inventory() -> FilterInventory`:
    - Imports `from fincli.resource.params.validators import list_valid_filters_with_labels`
    - Wraps the returned `{schema_version, keys, filters}` dict into a `FilterInventory` instance
    - Returns the `FilterInventory` (NOT the raw dict — keeps the route handler pure pass-through)
  - `def run_screen(filters: dict[str, str]) -> ScreenResult`:
    - Calls `screen_to_dataframe(filters)` (the T1 helper)
    - Times the call (`time.perf_counter` start/finish; `datetime.utcnow().isoformat() + "Z"` for `started_at`/`finished_at`)
    - Converts DataFrame rows to `list[Stock]`. For each row:
      - `ticker` from the Excel-formula `=HYPERLINK("...","TICKER")` column — strip the formula wrapper to recover the bare ticker (helper extracted if not already present)
      - `finviz_url` built by reusing `fincli.utils.quary_builders` (or whichever module already constructs `https://finviz.com/quote.ashx?t={ticker}` — spec §3.2 explicitly says "Reuses the URL-builder fincli already uses for the Excel HYPERLINK wrap so `finviz_url` cannot drift"). If no such builder exists as a public function, EXTRACT one in this task; do not duplicate the URL pattern.
      - `rank` from the Finviz `"No."` column (1-based)
      - `market_cap` from the `Market Cap` column (already coerced via `convert_market_cap_to_numeric`; just cast/forward)
      - `pe`, `price`, `change`, `volume` — string-preserved per spec §4.3 "numeric vs string preservation rule"
    - Returns `ScreenResult(schema_version=1, row_count=len(stocks), duration_ms=..., started_at=..., finished_at=..., stocks=stocks)`
    - On any exception raised by `fincli`, let it propagate — the T4d handler converts it to an HTTP response
- This is the ONLY file in `fincli_api/` allowed to `import fincli.*` — REVIEWER enforces

**Out-of-scope reminders:**
- DO NOT add HTTP-status mapping here — T4d owns the classifier integration
- DO NOT register a FastAPI dependency here — T4 routes import the functions directly
- DO NOT write CSV files (spec §3.2 explicit non-goal)
- DO NOT spawn a subprocess (spec N6)

**Acceptance gates (T3-specific):**
- `python -c "from fincli_api.adapters.fincli import get_filter_inventory; inv = get_filter_inventory(); print(len(inv.keys))"` prints a positive integer (~66)
- `ruff check fincli_api/adapters/fincli.py` clean
- `mypy fincli_api/adapters/fincli.py` clean
- Manual smoke (BACKEND, no test infra needed): construct a `dict[str, str]` filter map for `{"fa_pe": "u5", "sec": "energy"}` and call `run_screen` — confirm it returns a `ScreenResult` with `row_count > 0` (or graceful upstream-exception propagation if Finviz is unreachable; the latter is a deferred T5c check)
- If a finviz-URL builder was extracted as a public function in this task, all existing CSV-write tests still pass (no behavioral change to the Excel-formula wrap)

---

### T4a — Route: `fincli_api/routes/filters.py`

| Field | Value |
|---|---|
| Owner | BACKEND |
| Effort | S (1-2 hours) |
| Depends on | T3 |
| Can run in parallel with | T4b, T4c, T4d |

**Scope:**

- Create `fincli_api/routes/filters.py`:
  - `router = APIRouter(tags=["filters"])`
  - `@router.get("/filters", response_model=FilterInventory, summary="...", description="...")`
  - Handler is `def` (NOT `async def`) per spec §3.3; body is one-line `return get_filter_inventory()`
- Modify `fincli_api/main.py` to `app.include_router(filters.router)` (coordinate with T4b/T4c/T4d to avoid merge conflicts — see §7 cross-cutting concerns)

**Out-of-scope reminders:**
- DO NOT add caching headers (out of N-list but premature for personal use; defer to a future spec)
- DO NOT call `list_valid_filters_with_labels` directly — go through the adapter

**Acceptance gates (T4a-specific):**
- Hand-written unit test (lands in T5a but the BACKEND smoke-test it manually): `client.get("/filters").status_code == 200` and response JSON has `schema_version`, `keys`, `filters` top-level keys
- `ruff check fincli_api/routes/filters.py` clean
- `mypy fincli_api/routes/filters.py` clean

---

### T4b — Route: `fincli_api/routes/screens.py`

| Field | Value |
|---|---|
| Owner | BACKEND |
| Effort | S (2 hours) |
| Depends on | T3 |
| Can run in parallel with | T4a, T4c, T4d |

**Scope:**

- Create `fincli_api/routes/screens.py`:
  - `router = APIRouter(tags=["screens"])`
  - `@router.post("/screens", response_model=ScreenResult, responses={422: {"model": ErrorResponse}, 502: {"model": ErrorResponse}, 500: {"model": ErrorResponse}})`
  - Handler is `def` (NOT `async def`); body is one-line `return run_screen(request.filters)`
- Modify `fincli_api/main.py` to `app.include_router(screens.router)`

**Out-of-scope reminders:**
- DO NOT catch exceptions in the handler — T4d's global exception handler owns translation to HTTP responses
- DO NOT add pagination params (spec §4.2 wrapping under `filters` key leaves room; no need to add now)

**Acceptance gates (T4b-specific):**
- Smoke: `client.post("/screens", json={"filters": {"fa_pe": "u5", "sec": "energy"}}).status_code == 200` (with mocked adapter — full validation in T5a/T5b)
- `ruff check fincli_api/routes/screens.py` clean
- `mypy fincli_api/routes/screens.py` clean

---

### T4c — Route: `fincli_api/routes/meta.py`

| Field | Value |
|---|---|
| Owner | BACKEND |
| Effort | S (30 min) |
| Depends on | T3 (only to keep dependency edge identical; the route itself doesn't use the adapter) |
| Can run in parallel with | T4a, T4b, T4d |

**Scope:**

- Create `fincli_api/routes/meta.py`:
  - `router = APIRouter(tags=["meta"])`
  - `@router.get("/healthz")` returns `{"status": "ok"}` (no Pydantic model required; return a `dict[str, str]` for simplicity, OpenAPI auto-infers)
- Modify `fincli_api/main.py` to `app.include_router(meta.router)`

**Out-of-scope reminders:**
- DO NOT add readiness, dependency-check, or `/metrics` endpoints (spec N10)

**Acceptance gates (T4c-specific):**
- `client.get("/healthz").json() == {"status": "ok"}` and status 200
- `ruff check fincli_api/routes/meta.py` clean
- `mypy fincli_api/routes/meta.py` clean

---

### T4d — Exception handlers: `fincli_api/exception_handlers.py`

| Field | Value |
|---|---|
| Owner | BACKEND |
| Effort | M (3-4 hours; the trickiest non-skeleton task) |
| Depends on | T2c, T3 |
| Can run in parallel with | T4a, T4b, T4c |

**Scope:**

- Create `fincli_api/exception_handlers.py` per spec §5.3:
  - `def register(app: FastAPI) -> None:` (called from `fincli_api/main.py` AFTER all routers are included)
  - Single `@app.exception_handler(Exception)` registered inside `register`. Body:
    1. `exit_code = fincli.app.exit_codes.classify(exc)` — single source of truth
    2. Map `exit_code` to `(http_status, error_class)` per spec §5.1 table:
       - 2 → (422, "validation")
       - 3 → (502, "upstream")
       - 4 → (502, "parsing")
       - 1 → (500, "internal")
       - 0 → unreachable (success path doesn't raise); guard with `assert exit_code != 0` or fall-through to 500/internal
    3. Build `ErrorResponse(schema_version=1, error_class=..., message=str(exc), details={...}, request_id=...)`
       - `details` for validation: extract the offending key/value from `click.UsageError` message (best-effort; spec §5.2 example shows `{"key": "fa_pee", "suggestions": [...]}`; suggestions can be a future enhancement — for now `{"key": <best-effort>}` is acceptable as long as REVIEWER agrees)
       - `details` for upstream: `{"url": <if available from exc>, "timeout_s": 10}` (best-effort)
       - `details` for parsing: `{"exception_type": type(exc).__name__, "exception_message": str(exc)}`
       - `details` for internal: `None` (don't leak internals; `request_id` is the bridge to logs)
       - `request_id`: `uuid.uuid4().hex` ONLY for 5xx paths (spec §5.2)
    4. Log full traceback via `from logger import logger; logger.error("API exception", str(exc) + "\n" + traceback.format_exc())` (note the flipped param order documented in CLAUDE.md "Known Issues")
    5. Return `JSONResponse(status_code=http_status, content=error_response.model_dump(exclude_none=True))`
- Modify `fincli_api/main.py` to call `register(app)` after router includes; coordinate with T4a/T4b/T4c

**Out-of-scope reminders:**
- DO NOT shadow FastAPI's built-in 422 handler for Pydantic validation errors (spec §5.3 last paragraph: "FastAPI handles `400 / 404 / 405 / 422-from-Pydantic` automatically; our handler only takes the 500-catch-all"). If `RequestValidationError` reaches our handler, FastAPI is misconfigured — leave that handler alone.
- DO NOT add error-class-specific @exception_handler decorators (`@app.exception_handler(click.UsageError)`, etc.) — single catch-all via `classify()` is the spec's design (§5.3 step 1).

**Acceptance gates (T4d-specific):**
- Unit test (in T5a) covers all four `error_class` branches
- Manual smoke: raise each of `click.UsageError("bad")`, `requests.exceptions.Timeout`, `IndexError`, `RuntimeError` from a one-off test endpoint and confirm HTTP status + envelope shape match spec §5.1
- `ruff check fincli_api/exception_handlers.py` clean
- `mypy fincli_api/exception_handlers.py` clean

---

### T5a — Unit tests: `tests/unit/api/`

| Field | Value |
|---|---|
| Owner | BACKEND |
| Effort | M (half-day) |
| Depends on | T2 (models), T4d (handler shapes settled); can BEGIN against T4 stubs once T2a-T2c land |
| Can run in parallel with | T5b (T5b uses real adapter; T5a uses mocked adapter — no shared fixtures) |

**Scope:**

- Create `tests/unit/api/__init__.py` (empty)
- Create `tests/unit/api/conftest.py`:
  - `client` fixture returning `TestClient(app)` (after exception handlers are registered)
  - `mock_adapter` fixture using `monkeypatch.setattr` on `fincli_api.adapters.fincli.get_filter_inventory` / `.run_screen`
- Create `tests/unit/api/test_filters_route.py` (~3 tests):
  - 200 happy path with mocked adapter returning a synthetic `FilterInventory`
  - Adapter raises → 500/internal envelope
  - Response JSON matches `FilterInventory` schema (use `FilterInventory.model_validate(response.json())`)
- Create `tests/unit/api/test_screens_route.py` (~6 tests):
  - 200 happy path with mocked adapter
  - 422 on Pydantic validation (missing `filters` key) — proves FastAPI's built-in 422 is intact (spec §5.3)
  - Adapter raises `click.UsageError` → 422 / `error_class: "validation"`
  - Adapter raises a stand-in upstream exception → 502 / `error_class: "upstream"`
  - Adapter raises `IndexError` → 502 / `error_class: "parsing"`
  - Adapter raises `RuntimeError` → 500 / `error_class: "internal"` with `request_id` present
- Create `tests/unit/api/test_meta_route.py` (~2 tests):
  - `/healthz` returns `{"status": "ok"}`
  - `/healthz` is reachable without a trailing slash
- Create `tests/unit/api/test_openapi.py` (~2 tests):
  - `/openapi.json` returns 200 + valid OpenAPI 3.0 (`openapi.startswith("3.")`)
  - Both `/filters` and `/screens` endpoints appear in the spec with the expected `responses` shapes (200, 422, 500, 502)
- Create `tests/unit/api/test_exception_handlers.py` (~4 tests covering the classify() mapping for each exit_code → (status, error_class) tuple)

**Out-of-scope reminders:**
- DO NOT exercise the real `fincli` orchestrator here (that's T5b)
- DO NOT hit live Finviz (that's T5c)
- DO NOT add fixtures that load HTML files (T5b)

**Acceptance gates (T5a-specific):**
- `pytest tests/unit/api/ -v` all green, total runtime <500ms (spec §6.1 target)
- `pytest tests/unit/api/ --cov=fincli_api --cov-report=term` shows ≥90% line coverage of `fincli_api/` (spec §6.4)
- `ruff check tests/unit/api/` clean
- `mypy tests/unit/api/` clean (or pragma-allowed; pytest fixture types are notoriously verbose — Phase 4 tightening can come later)

---

### T5b — Integration tests: `tests/integration/api/`

| Field | Value |
|---|---|
| Owner | BACKEND |
| Effort | M (half-day) |
| Depends on | T3, T4 (all routes wired) |
| Can run in parallel with | T5a (different mocking strategy — no shared state) |

**Scope:**

- Create `tests/integration/api/__init__.py` (empty)
- Create `tests/integration/api/conftest.py`:
  - `client` fixture (real `app`, real exception handlers, real adapter)
  - `mock_fetch_page_sync` fixture using `monkeypatch.setattr` on `fincli.utils.web_scraper.fetch_page_sync` to return fixture HTML from `tests/integration/_fixtures_loader.py`
- Create `tests/integration/api/test_screens_happy_path.py`:
  - Uses `finviz_happy_html()` from `_fixtures_loader` → 200 with `row_count > 1` and matching `Stock` shapes
  - Uses `finviz_one_page_html()` → 200 with the single-page row count (the bug screener-fix commit `8d22af7` originally caught)
  - Uses `finviz_empty_html()` → 200 with `row_count == 0` and `stocks == []`
- Create `tests/integration/api/test_screens_error_paths.py`:
  - `finviz_no_table_html()` → 502 / `error_class: "parsing"`
  - `finviz_malformed_row_html()` → 502 / `error_class: "parsing"`
- Create `tests/integration/api/test_filters_e2e_local.py`:
  - `GET /filters` returns the FULL inventory from real `validators.list_valid_filters_with_labels` (no fixture HTML needed)
  - Byte-equivalent check: shell out via `subprocess.run(["python", "-m", "fincli", "--list-filters", "--json"])`, parse stdout, compare to `client.get("/filters").json()` — spec G2 / §4.4 "byte-equivalent modulo HTTP framing"

**Out-of-scope reminders:**
- DO NOT hit live Finviz (that's T5c)
- DO NOT mock the adapter (that's T5a's job)
- DO NOT add fixtures NEW to this task — reuse the five existing HTML fixtures listed in spec §6.2

**Acceptance gates (T5b-specific):**
- `pytest tests/integration/api/ -v` all green, total runtime <3s (spec §6.2 target)
- The byte-equivalent check in `test_filters_e2e_local.py` passes (this is the regression guard against CLI/API drift)
- `ruff check tests/integration/api/` clean
- `mypy tests/integration/api/` clean

---

### T5c — E2E tests: `tests/e2e/api/`

| Field | Value |
|---|---|
| Owner | BACKEND |
| Effort | S (3 hours; only 3 tests but each hits live Finviz) |
| Depends on | T5a, T5b (so we know the structure is right before going live) |
| Can run in parallel with | none |

**Scope:**

- Create `tests/e2e/api/__init__.py` (empty)
- Create `tests/e2e/api/conftest.py` (real `app`, no mocking)
- Create `tests/e2e/api/test_live_finviz.py` per spec §6.3:
  - `@pytest.mark.live` at module level (or per-test)
  - Test 1: `GET /filters` returns 66 keys (or the count current `list_valid_filters_with_labels` produces — assert lower bound `>= 60` to avoid brittle exact-match)
  - Test 2: `POST /screens` with `{"filters": {"fa_pe": "u5", "sec": "energy"}}` returns 200 with `row_count >= 1` and a valid `Stock[]`
  - Test 3: `POST /screens` with `{"filters": {"fa_pe": "u5", "sec": "basicmaterials", "geo": "monaco"}}` returns 200 with `row_count == 0` and `stocks == []`
- The marker `live` was registered in T1's `pyproject.toml` edit; `pytest tests/e2e/api/ -m live` runs these explicitly; default test runs do NOT pick them up (`addopts = "-m 'not live'"`).

**Out-of-scope reminders:**
- DO NOT add tests beyond the three in spec §6.3 (keep the live tier small to minimize CI cost / Finviz-anti-bot risk)
- DO NOT assert exact stock counts (Finviz returns variable results day-to-day; use `>= 1` and `== 0` thresholds only)
- DO NOT add retries (spec is silent on retries; defer to a future spec if needed)

**Acceptance gates (T5c-specific):**
- `pytest -m live tests/e2e/api/ -v` all green when run with network access; total runtime <30s (spec §6.3 target)
- `pytest tests/` (default) excludes these — `--collect-only` confirms zero collected tests under `tests/e2e/api/` without `-m live`
- `ruff check tests/e2e/api/` clean
- `mypy tests/e2e/api/` clean

---

### T6 — OpenAPI snapshot: `docs/api/openapi.yaml`

| Field | Value |
|---|---|
| Owner | BACKEND |
| Effort | S (1 hour) |
| Depends on | T5c (so routes/models are confirmed stable against live Finviz before snapshotting) |
| Can run in parallel with | none |

**Scope:**

- Run `python scripts/dump_openapi.py` to (re-)generate `docs/api/openapi.yaml` (or `.json` per T1's resolution).
- `git add docs/api/openapi.yaml`; the snapshot becomes the committed contract for change tracking (spec §7).
- Verify the snapshot is loadable into Postman ("Import OpenAPI URL" or "Import File"); ARCH did this once manually as part of plan acceptance (spec acceptance criterion #7).
- Verify the snapshot includes all four error-class response shapes under `/screens`.

**Out-of-scope reminders:**
- DO NOT hand-edit the YAML — it's generated; manual edits will get blown away on the next regeneration
- DO NOT add Postman collection JSON here (optional per spec §7; deferred unless HUMAN requests)
- DO NOT add an OpenAPI lint step (e.g., `redocly lint`) — out of scope for this umbrella; can be a future hygiene PR

**Acceptance gates (T6-specific):**
- `docs/api/openapi.yaml` exists, is valid YAML, declares `openapi: 3.x`
- File diff against the T1-stub snapshot shows the post-routes shape (paths /filters, /screens, /healthz; schemas FilterInventory, ScreenRequest, ScreenResult, Stock, ErrorResponse)

---

### T7a — Early docs: `CLAUDE.md`

| Field | Value |
|---|---|
| Owner | BACKEND |
| Effort | S (1-2 hours) |
| Depends on | T1 (so the package name + script entry are confirmed) |
| Can run in parallel with | T7b, T7c, T7d, all T8* (with caveat — see §7) |

**Scope (per spec §7 CLAUDE.md row):**

- "Project Overview" first paragraph rewritten for two co-equal entry points (fincli CLI + fincli-api server)
- "Build & Run" adds:
  - `uvicorn fincli_api.main:app --reload --host 127.0.0.1 --port 8000`
  - `fincli-api` (the entry-point script alias)
  - `pytest -m live tests/e2e/api/` for the live gate
- "Important Files" table adds rows for `fincli_api/main.py`, `fincli_api/adapters/fincli.py`, `fincli_api/routes/`, `fincli_api/models/`, `fincli_api/exception_handlers.py`, `fincli_api/config.py`, `scripts/dump_openapi.py`, `docs/api/openapi.yaml`
- "Phase Status" adds: **Phase 5 — HTTP API mode** (Status: Shipped on T-FINAL date)
- "Conventions" gains a short "API tier" note pointing to TESTING.md §API tests

**Out-of-scope reminders:**
- DO NOT add per-route documentation — that lives in `docs/api/openapi.yaml` + `CONTRACTS.md §8`
- DO NOT update Phase 4 status (mypy promotion is a separate gate)

**Acceptance gates (T7a-specific):**
- Grep for `fincli_api` in `CLAUDE.md` returns rows in Project Overview, Build & Run, Important Files, Phase Status sections
- Markdown lints clean (no broken anchors, no orphan tables)

---

### T7b — Early docs: `THESIS.md`

| Field | Value |
|---|---|
| Owner | BACKEND |
| Effort | S (30 min) |
| Depends on | T1 |
| Can run in parallel with | T7a, T7c, T7d, all T8* |

**Scope:**

- "Project Vision" paragraph rewritten: two co-equal entry points; CLI + HTTP API as siblings, not layers
- "Current Phase" entry: add row for Phase 5 (HTTP API mode shipped 2026-05-22 — date filled at T-FINAL merge)
- "Change Log" entry: `2026-05-22 — HTTP API mode shipped (fincli_api/ package + 2 endpoints + OpenAPI snapshot)`

**Acceptance gates (T7b-specific):**
- Change Log has the new dated entry
- Project Vision opens with two-entry-point framing

---

### T7c — Early docs: `FEEDBACK-LOG.md`

| Field | Value |
|---|---|
| Owner | BACKEND |
| Effort | S (30 min) |
| Depends on | T1 |
| Can run in parallel with | T7a, T7b, T7d, all T8* |

**Scope (per spec §7 FEEDBACK-LOG.md row):**

- Append a new 2026-05-22 entry:
  ```
  ### 2026-05-22 — HTTP API mode launched; live-Finviz e2e gate is mandatory for any API/parser change

  The list-filters umbrella shipped with a mocked-only test suite that passed
  while real Finviz scraping silently regressed (caught by screener-fix commit
  8d22af7 — single-page case). The HTTP API umbrella institutionalizes the
  fix: pytest -m live tests/e2e/api/ MUST be run before HUMAN approval on any
  change to fincli_api/ OR fincli/stock_screening/. Captured here as a durable
  rule so future contributors know why the live gate exists.
  ```

**Acceptance gates (T7c-specific):**
- Entry exists at the top of the log (append-only convention: newest first OR newest last — match the file's existing convention)

---

### T7d — Early docs: `README.md`

| Field | Value |
|---|---|
| Owner | BACKEND |
| Effort | S (1 hour) |
| Depends on | T1 |
| Can run in parallel with | T7a, T7b, T7c, all T8* |

**Scope (per spec §7 README.md row):**

- Add a new "HTTP API" section AFTER the "Pipeline mode" section:
  - Quick-start: `pip install -e ".[dev]"` then `fincli-api` (or `uvicorn fincli_api.main:app --reload`)
  - Link to `http://localhost:8000/docs` (Swagger UI)
  - Sample `curl` for `GET /filters` and `POST /screens`
  - Cross-link to `INTEGRATION.md` (HTTP API mode subsection — added in T8c) and `docs/api/openapi.yaml`

**Acceptance gates (T7d-specific):**
- New section exists with curl examples that copy-paste cleanly
- Pipeline mode section is unchanged (this is a pure addition)

---

### T8a — Post-code docs: `CONTRACTS.md` §8

| Field | Value |
|---|---|
| Owner | BACKEND |
| Effort | M (3-4 hours; this is the contract document) |
| Depends on | T6 (the OpenAPI snapshot is the source of truth for response shapes) |
| Can run in parallel with | T8b, T8c, T8d, T8e, T8f |

**Scope (per spec §7 CONTRACTS.md row):**

- New `§8 HTTP API surface` section with sub-sections:
  - §8.1 — Endpoint table (mirror spec §4.1 verbatim)
  - §8.2 — `GET /filters` request/response schema (point at `docs/api/openapi.yaml`; embed the §4.4 shape inline for cross-doc readability)
  - §8.3 — `POST /screens` request schema (spec §4.2)
  - §8.4 — `POST /screens` response schema (spec §4.3) including the snake_case rule and numeric-vs-string preservation rule
  - §8.5 — Error envelope (spec §5.2) including the discriminator union and the exit-code → HTTP-status mapping table (spec §5.1)
  - §8.6 — OpenAPI pointer: `docs/api/openapi.yaml` is the committed snapshot; regenerate via `python scripts/dump_openapi.py`
- Extend `§7 Stability` bullets to cover `§8` (the API response shapes + error envelope are stability-locked from this commit onward)

**Acceptance gates (T8a-specific):**
- §8 exists with all six sub-sections
- §7 stability list includes the new bullet covering §8 shapes
- Exit-code → HTTP-status table matches the live `fincli/app/exit_codes.py` constants AND `fincli_api/exception_handlers.py` mapping

---

### T8b — Post-code docs: `MODULE_REFERENCE.md`

| Field | Value |
|---|---|
| Owner | BACKEND |
| Effort | M (3 hours) |
| Depends on | T6 (so module names + signatures are final) |
| Can run in parallel with | T8a, T8c, T8d, T8e, T8f |

**Scope (per spec §7 MODULE_REFERENCE.md row):**

- New module entries (one per submodule, mirror existing entry format — Purpose / Public surface / Data shapes / Error modes):
  - `fincli_api.main` (FastAPI app + uvicorn entry)
  - `fincli_api.config` (`ApiConfig`)
  - `fincli_api.routes.filters` (`router`, `/filters` handler)
  - `fincli_api.routes.screens` (`router`, `/screens` handler)
  - `fincli_api.routes.meta` (`router`, `/healthz` handler)
  - `fincli_api.models.filters` (`FilterEntry`, `FilterInventory`)
  - `fincli_api.models.screens` (`ScreenRequest`, `ScreenResult`, `Stock`)
  - `fincli_api.models.errors` (`ErrorResponse`)
  - `fincli_api.adapters.fincli` (`get_filter_inventory`, `run_screen` — the only fincli importer)
  - `fincli_api.exception_handlers` (`register`)
- Extend the existing `fincli.app.main` entry to mention the new public `screen_to_dataframe` helper

**Acceptance gates (T8b-specific):**
- All ten new module entries exist
- The `fincli.app.main` entry references `screen_to_dataframe`
- Public surfaces match the shipped code (REVIEWER verifies)

---

### T8c — Post-code docs: `INTEGRATION.md` restructure

| Field | Value |
|---|---|
| Owner | BACKEND |
| Effort | M (3-4 hours) |
| Depends on | T6, T8a |
| Can run in parallel with | T8a (T8a finishes first OR they coordinate), T8b, T8d, T8e, T8f |

**Scope (per spec §7 INTEGRATION.md row):**

- Restructure INTEGRATION.md into two top-level sub-modes:
  - **Mode 1: Subprocess (CLI) mode** — wraps the existing content (bootstrap, per-screen call flow, exit-code routing, OUTPUT_PATH=, etc.) unchanged in scope. The existing content moves under this heading.
  - **Mode 2: HTTP API mode** — NEW. Sub-sections:
    - When to use (vs CLI mode)
    - Quick-start (uvicorn / fincli-api script)
    - OpenAPI pointer (`docs/api/openapi.yaml` + `/openapi.json` + `/docs`)
    - `curl` examples for `GET /filters` and `POST /screens`
    - Postman quick-import (import URL: `http://localhost:8000/openapi.json`)
    - Error handling guidance (the §5.1 mapping table; reference CONTRACTS §8.5)
    - When you'd choose CLI mode anyway (cookbook scripting, batch jobs, no Python-server runtime)

**Acceptance gates (T8c-specific):**
- The two-mode restructure is clean (no orphan content)
- HTTP API mode sub-section has working curl examples
- Existing Mode 1 (CLI) content is preserved verbatim (or near-verbatim) — REVIEWER spot-checks

---

### T8d — Post-code docs: `TESTING.md`

| Field | Value |
|---|---|
| Owner | BACKEND |
| Effort | S (1-2 hours) |
| Depends on | T5c (so the test paths + marker are stable) |
| Can run in parallel with | T8a, T8b, T8c, T8e, T8f |

**Scope (per spec §7 TESTING.md row):**

- New "API tests" section:
  - Three-tier pyramid description (unit / integration / e2e) with file-path roots
  - `pytest -m "not live"` is default (configured in `pyproject.toml`)
  - `pytest -m live tests/e2e/api/` is the opt-in live gate
  - Reuse of the five HTML fixtures via `tests/integration/_fixtures_loader.py` for the integration tier
  - Mocking strategy: TestClient + adapter-mock (unit), TestClient + `fetch_page_sync`-mock (integration), TestClient + nothing-mocked (e2e)

**Acceptance gates (T8d-specific):**
- "API tests" section exists with the three-tier description
- Live-marker invocation is documented
- File-path roots match the actual T5a/T5b/T5c layout

---

### T8e — Post-code docs: `AGENTS.md`

| Field | Value |
|---|---|
| Owner | BACKEND |
| Effort | S (30 min) |
| Depends on | T5c (so test paths are stable) |
| Can run in parallel with | T8a, T8b, T8c, T8d, T8f |

**Scope (per spec §7 AGENTS.md row):**

- Add a brief mention of `tests/{unit,integration,e2e}/api/` paths so role-context files know where API tests live (likely in the section that already enumerates test layouts)
- No change to workflow rules; this is purely a path enumeration update

**Acceptance gates (T8e-specific):**
- Grep for `api/` in `AGENTS.md` returns the new test-path enumeration

---

### T8f — Spec archive flip

| Field | Value |
|---|---|
| Owner | BACKEND |
| Effort | S (15 min) |
| Depends on | T8a, T8b, T8c, T8d, T8e (entire doc sweep complete) |
| Can run in parallel with | none (final action of W8 wave) |

**Scope:**

- Flip `docs/superpowers/specs/2026-05-22-fincli-api-design.md` status: DESIGN → SHIPPED
- Add the SHIPPED banner at the top (mirror `pipeline-mode-spec.md` banner format: one-paragraph summary + Status flip + Date shipped + final commit SHA reference; SHA = T-FINAL's merge commit, fill at merge time)
- `git mv docs/superpowers/specs/2026-05-22-fincli-api-design.md docs/superpowers/specs/archive/2026-05-22-fincli-api-design.md` (CONFIRM the archive directory location with project convention — `list-filters-plan.md` archived under `docs/features/archive/`, but design specs may archive under `docs/superpowers/specs/archive/`; pick whichever convention exists in the repo at this time)
- This plan file (`docs/features/fincli-api-plan.md`) also flips to SHIPPED in the same commit — move to `docs/features/archive/fincli-api-plan.md` if convention dictates

**Acceptance gates (T8f-specific):**
- Spec file is at `docs/superpowers/specs/archive/2026-05-22-fincli-api-design.md` (or wherever the convention dictates)
- `git log --diff-filter=R --name-status` shows the rename (R)
- The SHIPPED banner matches the precedent's format

---

### T-FINAL — Live-Finviz gate + §8 acceptance walkthrough + HUMAN sign-off

| Field | Value |
|---|---|
| Owner | BACKEND (runs gates) + HUMAN (signs off) |
| Effort | S (1 hour active; depends on Finviz responsiveness) |
| Depends on | T7a, T7b, T7c, T7d, T8a, T8b, T8c, T8d, T8e, T8f |
| Can run in parallel with | none |

**Scope:**

- Run `pytest -m live tests/e2e/api/ -v` — MUST be all-green. This is the spec §6.3 mandatory gate.
- Walk the spec §8 acceptance criteria with HUMAN, end-to-end on a developer machine:
  1. `uvicorn fincli_api.main:app` starts on port 8000 with no errors
  2. `curl http://localhost:8000/healthz` → `{"status": "ok"}`, HTTP 200
  3. `curl http://localhost:8000/filters` → valid JSON matching `--list-filters --json` byte-equivalently
  4. `curl -X POST http://localhost:8000/screens -H "Content-Type: application/json" -d '{"filters": {"fa_pe": "u5", "sec": "energy"}}'` → 200 with `ScreenResult` shape; `stocks[*].finviz_url` present
  5. `curl -X POST .../screens -d '{"filters": {"fa_pee": "u5"}}'` → 422 with `error_class: "validation"`
  6. `http://localhost:8000/docs` shows Swagger UI with both endpoints + all schemas
  7. `http://localhost:8000/openapi.json` returns valid OpenAPI 3.0; loadable into Postman via "Import OpenAPI URL"
  8. `pytest tests/` runs full unit + integration suite green (default `-m "not live"` excludes E2E)
  9. `pytest -m live tests/e2e/api/` runs the three live-Finviz smoke tests green
  10. `ruff check . && ruff format --check . && mypy fincli fincli_api` all clean
- HUMAN approves → merge `feat/fincli-api` to `master` (or open PR per project convention)
- Post-merge: any final SHA placeholders in the SHIPPED banner are backfilled

**Out-of-scope reminders:**
- DO NOT skip the live-Finviz gate even if "integration tests are green" — that's the entire point of spec §6.3 + the FEEDBACK-LOG rule

**Acceptance gates (T-FINAL specific):**
- All 10 §8 acceptance criteria pass
- Live-Finviz e2e gate is green
- HUMAN says "ship it"

---

## §6 — Validation gates per task (cross-cutting)

Each task above has its own per-task acceptance gates. This section captures what's COMMON across all tasks:

| Gate | Common-to-all-tasks check |
|---|---|
| VERIFIER | `ruff check` + `ruff format --check` + `mypy` clean on touched files; `pytest -m "not live"` green (no regressions in pre-existing suite) |
| REVIEWER | New code follows project conventions (Google-style docstrings, `from logger import logger`, `Config` for runtime config not env vars, snake_case files); architectural boundary respected (only `fincli_api/adapters/fincli.py` imports from `fincli/`); spec sections cited in commit messages |
| QA | Spec section-by-section conformance check for the relevant `§4`/`§5`/`§6` items; cross-doc consistency check (e.g., CONTRACTS §8.5 mapping table matches `exception_handlers.py` code) |
| HUMAN | Binary approve/block; if blocked, provides direction back to BACKEND or ARCH |

**Iteration cap per gate:** 2-3 round-trips before escalating to HUMAN (per §10 below). Identical to list-filters-plan precedent.

---

## §7 — Parallelization plan (subagent dispatch)

If BACKEND uses `superpowers:subagent-driven-development`, dispatch subagents as follows. Otherwise, a single-session BACKEND can execute waves sequentially — parallelism is a nice-to-have, not a correctness requirement.

### Wave 1: T1 (sequential)

One subagent OR single-session BACKEND. No parallelism opportunity inside T1 — `pyproject.toml` edits, package skeleton, and the `screen_to_dataframe` helper are interleaved and small.

### Wave 2: T2a + T2b + T2c (3-way parallel)

Three subagents dispatched concurrently. Each creates one model file (`filters.py`, `screens.py`, `errors.py`). No cross-file imports between the three. Merge order doesn't matter; final commit aggregates all three OR each lands as its own commit (BACKEND discretion within spec convention).

### Wave 3: T3 (sequential)

One subagent. Imports from all three T2 models + `fincli.app.main.screen_to_dataframe` (from T1). No parallelism.

### Wave 4: T4a + T4b + T4c + T4d (4-way parallel, with main.py-edit coordination)

Four subagents. Each writes one new file (`routes/filters.py`, `routes/screens.py`, `routes/meta.py`, `exception_handlers.py`). **Coordination point:** all four touch `fincli_api/main.py` to add `app.include_router(...)` or `register(app)`. RECOMMENDED: BACKEND lead does the `main.py` wiring in a single follow-on commit AFTER the four parallel subagents land their files, OR uses a single subagent for the wiring after the parallel branch. Avoids merge conflicts on `main.py`.

### Wave 5: T5a + T5b (2-way parallel)

Two subagents. T5a uses mocked adapters (no fincli/Finviz dependencies); T5b uses real fincli + mocked `fetch_page_sync` with HTML fixtures. Different mocking layers, no shared fixtures → safe to dispatch concurrently.

### Wave 6: T5c (sequential)

One subagent. Live-Finviz dependency is fragile; don't parallelize.

### Wave 7: T6 (sequential)

One subagent. `scripts/dump_openapi.py` re-run + commit the YAML snapshot.

### Wave 7': T7a + T7b + T7c + T7d (4-way parallel, ELIGIBLE from W2 onward)

Four subagents. Each edits ONE early-doc file. None of these need shipped-shape information beyond the package name + script entry (which T1 provides). Can run concurrently with W2-W7 if BACKEND has subagent capacity, OR after W6 in a single doc-sweep wave with W8.

### Wave 8: T8a + T8b + T8c + T8d + T8e + T8f (6-way parallel)

Six subagents. Each edits ONE post-code doc file. Cross-references between docs (e.g., CONTRACTS §8.5 mentioned in INTEGRATION.md) work as long as both files land before commit. **Coordination point:** T8f (spec archive) MUST be the final commit of the wave; gate it on T8a-T8e landing.

### Wave 9: T-FINAL (sequential)

BACKEND runs the live-Finviz gate; HUMAN walks the §8 acceptance criteria. Cannot be parallelized.

**Total subagent dispatch budget (worst case):** ~21 atomic units across 9 waves. With aggressive parallelism (5 subagent processes), end-to-end wall-clock is ~3-4 days; sequential single-session is ~6-8 days.

---

## §8 — Cross-cutting concerns

### 8.1 Error envelope shape consistency

The `ErrorResponse` shape is defined in T2c, consumed in T4d, documented in T8a (CONTRACTS §8.5), and exercised in T5a + T5b. ANY change to its shape mid-implementation requires a coordinated edit across all five points. REVIEWER must verify the shape is identical across all five touchpoints in the final review.

### 8.2 `fincli_api/main.py` is touched by 4 tasks (T1 stub, T4a/T4b/T4c router includes, T4d handler registration)

Already addressed in §7 Wave 4 parallelization note: a coordination commit after the parallel router-and-handler tasks land. Alternatively, BACKEND lead writes the wiring inline as the final step of each W4 subagent and resolves merge conflicts.

### 8.3 OpenAPI snapshot timing (T6 vs T8a)

`docs/api/openapi.yaml` is generated AFTER routes + models are stable (T6 follows T5c). CONTRACTS §8 (T8a) references the YAML pointer but does NOT need the YAML's content inlined. If a late spec change to a model (e.g., adding a field to `Stock`) lands AFTER T6, BOTH T6 and T8a must be re-run; the OpenAPI yaml is the source-of-truth and the CONTRACTS doc is the prose layer.

### 8.4 Test marker convention (`live`)

Registered in T1's `pyproject.toml` edit; `addopts = "-m 'not live'"` excludes by default. ANY new live test in the project (beyond T5c) MUST use the same marker; do not invent `slow`, `network`, `e2e_live` parallel markers. Captured in T8d (TESTING.md).

### 8.5 Logging integration (the flipped `Logger.error` param order)

T4d's exception handler calls `logger.error(...)`. Per CLAUDE.md "Known Issues", the signature is `error(title, message="")` (FLIPPED relative to `info`/`debug`/`warn`). Do not "fix" this in T4d; mirror the documented order. REVIEWER verifies.

### 8.6 Type-hint coverage (Phase 4 ambition)

New code in `fincli_api/` is fully typed from day one (FastAPI + Pydantic make this cheap). Per-task acceptance gates include "mypy clean on touched files." This raises the Phase 4 coverage without modifying existing `fincli/` modules. T8b (MODULE_REFERENCE.md) documents typed-from-day-one explicitly.

### 8.7 No new mypy overrides for new deps

`fastapi`, `uvicorn`, `httpx`, `pydantic` all ship with inline type info. No `[[tool.mypy.overrides]]` entries needed in T1. `cfscrape` override stays.

---

## §9 — Open questions (resolved inline)

The spec §10 declared "None — all design decisions resolved during brainstorming." Planning surfaced ONE implementation-level ambiguity:

| # | Question | Resolution | Rationale |
|---|---|---|---|
| OQ-1 | Where does `dump_openapi.py` live: `scripts/dump_openapi.py` or `fincli_api/dump_openapi.py`? | `scripts/dump_openapi.py` | Matches existing `scripts/check_requirements.py` precedent; keeps the runtime package free of dev-tooling scripts. Conforms to spec §7's instruction that this is a "small dump helper script" — no other guidance, so existing convention wins. |

No blocking questions remain.

---

## §10 — Risks and mitigations

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Finviz rate-limits or blocks the live e2e tests, blocking T-FINAL approval | M | H | Live tests are minimal (3 tests, single requests each, ~30s total). On block: BACKEND retries with a fresh User-Agent; if persistent, escalate to HUMAN (a Finviz block is a real-world signal, not a test bug). |
| R2 | The `screen_to_dataframe` helper extraction in T1 inadvertently regresses the CSV-write path in `fincli/app/main.py` | M | H | T1 acceptance gate explicitly runs the full pre-existing pytest suite; any regression caught before T2 begins. REVIEWER spot-checks the refactor for behavioral preservation. |
| R3 | `cfscrape` URL builder pattern inside the existing CSV code isn't a public function — T3 has to extract one, and the extraction breaks the Excel-formula `=HYPERLINK(...)` shape | M | M | T3 acceptance gate includes "all existing CSV-write tests still pass." If extraction is non-trivial, BACKEND can keep both paths (CSV-write inlined, API-builder public) and refactor in a follow-on PR — DON'T block T3 on a perfect dedupe. |
| R4 | The OpenAPI snapshot at T6 diverges from a late model change in T8a's CONTRACTS prose | L | M | §8.3 cross-cutting concern: T6 + T8a coordinated; any post-T6 model change re-triggers T6. REVIEWER cross-checks. |
| R5 | The `Logger.error(title, message)` flipped-order footgun bites T4d | L | L | Captured in §8.5; REVIEWER verifies. If it slips through, log output is uglier than intended but no functional break. |
| R6 | Postman import of `/openapi.json` fails because FastAPI's auto-generated schema uses a feature Postman doesn't support (e.g., `oneOf` discriminator for `ErrorResponse`) | L | M | Spec acceptance criterion #7 explicitly requires this works; T6 acceptance includes a manual Postman import smoke. If Postman barfs, FALLBACK is to flatten the discriminator union in `errors.py` (lose the OpenAPI discriminator but keep the `error_class` literal). This is a spec amendment if it happens — escalate. |
| R7 | The default test run `pytest tests/` inadvertently picks up live tests (marker misconfigured) | L | H | T1 acceptance + T5c acceptance both verify `pytest --collect-only` excludes `tests/e2e/api/` by default. Defense-in-depth: marker is set in `pyproject.toml` AND `tests/e2e/api/conftest.py` could add a `pytestmark = pytest.mark.live` module marker as a belt-and-braces measure. |

---

## §11 — Acceptance criteria for plan completion (the FINAL HUMAN gate)

Restated from spec §8 — these are the §10-minute reviewer checks that HUMAN runs at T-FINAL:

1. `uvicorn fincli_api.main:app` starts on port 8000 with no errors
2. `curl http://localhost:8000/healthz` → `{"status": "ok"}`, HTTP 200
3. `curl http://localhost:8000/filters` → valid JSON matching `fincli --list-filters --json` byte-equivalently
4. `curl -X POST http://localhost:8000/screens -H "Content-Type: application/json" -d '{"filters": {"fa_pe": "u5", "sec": "energy"}}'` → 200 with `ScreenResult` shape; `stocks[*].finviz_url` present and well-formed
5. `curl -X POST .../screens -d '{"filters": {"fa_pee": "u5"}}'` → 422 with `error_class: "validation"`
6. `http://localhost:8000/docs` shows Swagger UI with both endpoints + all schemas
7. `http://localhost:8000/openapi.json` returns valid OpenAPI 3.0; loadable into Postman via "Import OpenAPI URL"
8. `pytest tests/` runs full unit + integration suite green (default `-m "not live"` excludes E2E)
9. `pytest -m live tests/e2e/api/` runs the three live-Finviz smoke tests green
10. `ruff check . && ruff format --check . && mypy fincli fincli_api` all clean

When all 10 pass, HUMAN signs off and `feat/fincli-api` merges to `master`.

---

## §12 — Change log

- 2026-05-22 — v0.1 DRAFT — initial plan derived from HUMAN-approved spec `docs/superpowers/specs/2026-05-22-fincli-api-design.md`. Twelve tasks across nine waves; one spec ambiguity (OQ-1, `dump_openapi.py` location) resolved inline. Pending HUMAN plan-review before BACKEND dispatch.

---

HANDOFF_TO: HUMAN (for plan review before BACKEND dispatch)
