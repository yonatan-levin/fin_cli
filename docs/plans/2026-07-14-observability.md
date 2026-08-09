# Plan — Observability integration (algo_beta / Fin CLI)

**Date:** 2026-07-14 · **Slug:** observability · **Author role:** ARCH
**Standard:** `../../../docs/OBSERVABILITY.md` (workspace) · **Reference module:** `../../../docs/observability-reference/observability/`
**Sibling reference impl:** swinger (PR yonatan-levin/swinger#1, all gates green).

## 1. Summary

Make algo_beta **traceable like midas** on its **HTTP API surface** (`fincli_api`),
and introduce a correlation `run_id` on the **CLI surface** (`fincli`).
algo_beta is the outlier: a bespoke Singleton logger (`logger/logger.py`, imported
`from logger import logger`), two config systems, `/healthz` (not `/health`), no
inbound auth, `pytest.ini` (not pyproject), and a flat multi-package layout.

**Goals**
- API: request-id correlation (`X-Request-ID` read/mint/echo), JSON logs carrying
  `request_id`, `/health` + `/ready` + `/health/detailed` + `/metrics`.
- API: unify the error-envelope `request_id` with the echoed `X-Request-ID`
  (today `fincli_api/exception_handlers.py` mints an independent 12-char uuid on
  5xx — the catch-all is algo_beta's PRIMARY error path, so this matters).
- CLI: bind a `run_id` contextvar at command entry.

**Non-goals**
- **Not** ripping out or JSON-ifying the Singleton logger (`logger/logger.py`) — it
  is mandated and CLI-wide. Full CLI log correlation via the Singleton is a
  documented **follow-up**, not this change.
- No inbound auth / `key_id` (algo_beta has none).
- Keep `/healthz` (existing liveness contract) alongside the new `/health`.

## 2. Requirements

Functional (API)
- Inbound `X-Request-ID` honored if it matches `^[A-Za-z0-9_.:-]{1,128}$`, else a
  UUIDv4 is minted; echoed on every response.
- The catch-all exception handler's envelope `request_id` equals the echoed
  `X-Request-ID` for the request (including 5xx).
- `GET /health` (new, liveness), `GET /ready` (process-up), `GET /health/detailed`,
  `GET /metrics` (`fincli_`-prefixed families). Keep `GET /healthz`.
- JSON logs on the API process carry `request_id`.

Functional (CLI)
- A `run_id` (UUIDv4) is minted and bound at `fincli/app/cli.py:run_main` entry so
  any stdlib logging during a run is correlated. (Singleton output correlation =
  follow-up.)

Non-functional
- **Logs → stderr** (stdout carries `fincli --json` machine output).
- Gates green: `ruff`, `ruff format`, `mypy --strict` (its `files` list), `pytest`
  (config in `pytest.ini`). `urllib3<2` pin is untouched.

## 3. Architecture

### 3.1 Vendored module
Copy `docs/observability-reference/observability/` → `algo_beta/observability/`
(byte-identical), a **new top-level package** imported as `from observability import ...`.
`pyproject.toml`:
- add `prometheus-client>=0.20` to `dependencies`,
- add `"observability*"` to `[tool.setuptools.packages.find] include`,
- add `"observability"` to `[tool.mypy] files` (so the module is strict-checked;
  note `fincli_api` is deliberately NOT in that list, so the API wiring itself is
  not mypy-gated — unchanged project choice).

### 3.2 Canonical-module enhancements (shared — see the orchestrator plan §3.2)
This integration **requires** the two canonical additions:
1. `configure_logging(..., stream=sys.stderr)` for the stderr requirement.
2. `RequestContextMiddleware` stashing the id on `scope["state"]["request_id"]` so
   the catch-all handler in `ServerErrorMiddleware` (which runs after the contextvar
   is reset) reads it via `request.state.request_id`. **Load-bearing here** — it's
   the only way the 5xx envelope can carry the echoed id.
Both are added to the canonical reference and re-synced into swinger/borker so all
copies stay byte-identical.

### 3.3 Files touched (real paths, algo_beta worktree)
| File | Change |
|---|---|
| `observability/` (new) | vendored module (6 files) |
| `fincli_api/main.py` | at import/startup call `configure_logging(stream=sys.stderr, fmt=json, level=…)` (root); `install_observability(app, service="fincli_api", version=API_VERSION, namespace="fincli", include_liveness=True)` → adds `/health`, `/ready`, `/health/detailed`, `/metrics` + request-id/access/metrics middleware. Keep the existing `register_exception_handlers(app)` and the `/healthz` router |
| `fincli_api/exception_handlers.py` | source `request_id` from `request.state.request_id` (fallback `observability.get_request_id()`) instead of minting an independent uuid; keep the classifier mapping + envelope shape. Populate on ALL responses that carry an envelope (not just 5xx) so the id always matches the header |
| `fincli/app/cli.py` | at `run_main` entry: `configure_logging(stream=sys.stderr, …)` + `set_request_id(coerce_id(None))` (mint a run_id) |
| `pyproject.toml` | dep + packages.find include + mypy files |
| `tests/…/api/` | new observability tests (see §6); the existing `tests/unit/api/test_exception_handlers.py` may need a tweak if it asserts the 12-char uuid shape |
| `CONTRACTS.md` / API docs | document the new endpoints + `X-Request-ID` behavior + envelope `request_id` change |

### 3.4 The 500-correlation fix (key decision)
`fincli_api/exception_handlers.py` registers `@app.exception_handler(Exception)` —
handled by Starlette's `ServerErrorMiddleware`, the outermost layer, OUTSIDE the
request-id middleware. By the time it runs, the request-id contextvar is reset. So
the handler reads the id from `request.state.request_id` (set by the middleware on
the shared `scope`), guaranteeing the 5xx envelope's `request_id` equals the echoed
`X-Request-ID`. The independent 12-char-uuid minting is removed. (This changes the
envelope's `request_id` from a 12-char fragment to the full request id — a
documented CONTRACTS change.)

## 4. API contracts
| Endpoint | Before | After |
|---|---|---|
| `GET /healthz` | `200 {"status":"ok"}` | unchanged (kept) |
| `GET /health` | — | liveness, `200` |
| `GET /ready` | — | `200 {"status":"ready"}` (process-up) |
| `GET /health/detailed` | — | component map `200/206/503` (no components → healthy) |
| `GET /metrics` | — | Prometheus (`fincli_http_requests_total`, …) |
| error envelope | `request_id`: 12-char uuid, 5xx only | `request_id` = full request id, matches `X-Request-ID` |
| every response | no correlation header | echoes `X-Request-ID` |

## 5. Tasks by agent
**BACKEND**
1. Vendor `observability/`; edit `pyproject.toml` (dep + packages.find + mypy files).
2. `fincli_api/main.py`: `configure_logging(stream=stderr)` + `install_observability`.
3. `fincli_api/exception_handlers.py`: source `request_id` from `request.state`.
4. `fincli/app/cli.py`: mint + bind `run_id`.
5. Tests (§6); update `CONTRACTS.md` / API docs.

**VERIFIER / REVIEWER / QA** — §7.

## 6. Test plan (pytest.ini; tests/{unit,integration,e2e}/api/ with per-tier conftest)
- `/metrics` exposes `fincli_http_requests_total`.
- `/health`, `/ready` (200), `/health/detailed` respond; `/healthz` still `200`.
- Response echoes `X-Request-ID`: a valid inbound one is honored, a missing one is
  minted (UUIDv4), an invalid one is replaced.
- A forced 5xx: the envelope `request_id` equals the echoed `X-Request-ID` header
  (this exercises the `ServerErrorMiddleware` path + `request.state` stash).
- Update `tests/unit/api/test_exception_handlers.py` if it asserts the old
  12-char-uuid shape.
- No network (mock-target gotcha: patch `fincli.app.main.fetch_page_sync` locally
  if a screener path is touched — tests here shouldn't need it). Default excludes
  `-m live`.

## 7. Validation cycle (mandatory)
VERIFIER (run algo_beta's own gates from the worktree — `ruff check .`,
`ruff format --check .`, `mypy .`, `pytest` per pytest.ini; confirm edge cases) →
REVIEWER (quality; Singleton untouched; no secret leaks) → QA (matches plan +
CONTRACTS; `/healthz` intact; envelope request_id change intentional/documented) →
HUMAN acceptance. Cap 2–3 iterations.

## 8. Spec updates
- `CONTRACTS.md` / API docs: new endpoints, `X-Request-ID`, envelope `request_id`.
- Note the deferred Singleton-logger JSON-ification as a follow-up.

## 9. Alternatives considered
1. **API-surface parity + CLI run_id, Singleton untouched (CHOSEN).** Delivers full
   HTTP traceability + metrics now; defers the invasive Singleton rework. Lowest risk.
2. **Replace the Singleton logger with the vendored JSON logging everywhere.** Large
   blast radius (CLI-wide, mandated import), high regression risk on the oldest
   codebase. Rejected for this change; candidate follow-up.
3. **Keep the independent 12-char uuid on 5xx.** Leaves envelope id ≠ echoed header
   (two ids per failed request) — defeats correlation. Rejected.
