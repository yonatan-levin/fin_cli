# AGENTS.md — Context Loading Contract

This file defines the **canonical loading order** for any AI agent (Claude Code, Cursor, Copilot, etc.) working on the fin_cli codebase. If you are an AI agent opening this repository, **start here**.

The goal is simple: every agent reads the same files in the same order, so context is predictable and reproducible across sessions and tools.

> Principle: *If it's not written to a file, it doesn't exist.* Durable context lives on disk, not in conversation memory.

---

## Loading Order (Read Top-to-Bottom)

At the start of any work session, read these files in order. Stop at the first tier that gives you enough context for the task.

### Tier 1 — Identity & Direction (Always Read)

| # | File | Purpose |
|---|------|---------|
| 1 | `CLAUDE.md` | Project identity, tech stack, conventions, important files, run commands |
| 2 | `AGENTS.md` (this file) | Loading contract and cross-file relationships |
| 3 | `docs/THESIS.md` | Product direction, current phase, roadmap, scope boundaries |

### Tier 2 — Working Memory (Read When Resuming Work)

| # | File | Purpose |
|---|------|---------|
| 4 | `.claude/projects/<project-hash>/memory/MEMORY.md` | Index of durable facts, preferences, architectural decisions |
| 5 | `docs/FEEDBACK-LOG.md` | User corrections and preferences not yet promoted to MEMORY |
| 6 | `.claude/projects/<project-hash>/memory/daily/YYYY-MM-DD.md` | Today's session notes (if exists) |

> **Note:** Tier 2 files are populated as the project matures. If `MEMORY.md`, the daily log, or `FEEDBACK-LOG.md` are absent or empty, skip gracefully — they accumulate over time as durable insights are recorded.

### Tier 3 — Operational Rules (Read When Acting in a Specific Role)

| # | File | Purpose |
|---|------|---------|
| 7 | `agents/rules/_shared-workflow.md` | Shared workflow for all roles (auto-loaded by `.claude/hooks/load-rules.js` for Claude Code) |
| 8 | `agents/rules/preflight.md` | Pre-implementation checklist (auto-loaded by hook) |
| 9 | `agents/rules/orchestrator.md` | Routing logic and specialist dispatch (auto-loaded by hook) |
| 10 | `agents/rules/load-context.md` | On-demand context loading patterns (read when acting in load-context mode) |
| 11 | `agents/rules/scaffold-module.md` | Module scaffolding rules (read when creating new Python modules) |
| 12 | `agents/roles/<role>.md` | Role-specific operational rules: `backend-architect`, `code-architect`, `code-reviewer`, `frontend-developer`, `project-planning-handoff-specialist`, `qa-debugger`, `ui-designer`, `verifier` (8 roles total) |

### Tier 4 — Task-Specific Deep Dive (Read Only When Relevant)

| # | File | Purpose |
|---|------|---------|
| 13 | `docs/MODULE_REFERENCE.md` | Full module reference: fincli, core, config, logger internals |
| 14 | `CONTRACTS.md` | Data contracts, function signatures, input/output schemas |
| 15 | `ARCHITECTURE.md` | System architecture, data flow diagrams, component relationships |
| 16 | `TESTING.md` | Testing strategy, test layout, how to run, coverage targets |
| 17 | `TOOLS_REFERENCE.md` | Tool reference: Click CLI patterns, pandas idioms, cfscrape usage |
| 18 | `docs/superpowers/specs/` | Per-feature design specs (chronological by date) |
| 19 | `docs/superpowers/plans/` | Per-feature implementation plans (chronological by date) |
| 20 | `docs/bugs/` | Bug tracker and known-issue registry |
| 21 | `docs/refactoring/` | Refactoring specs and upgrade design docs |
| 22 | `docs/reviewer/` | Review follow-up tracker |
| 23 | `docs/features/` | Feature-restoration / feature-addition specs; shipped specs move to `archive/` |
| 24 | `docs/pendingwork/` | Session handoff docs (dated); historical handoffs move to `archive/` |
| 25 | `fincli/` | Stock screener source code |
| 26 | `core/` | Base configuration and JSON converter utilities |
| 27 | `config/` | Pydantic-based configuration with history support |
| 28 | `logger/` | Singleton logger (console typing effect, file, JSON handlers) |

> **API test paths** (subset of `TESTING.md` for quick orientation):
> - `tests/unit/api/` — FastAPI `TestClient` + mocked adapter (~19 tests, <500ms)
> - `tests/integration/api/` — `TestClient` + real fincli + mocked Finviz HTML (~11 tests, <3s; conftest patches `fincli.app.main.fetch_page_sync` per the local-binding rule)
> - `tests/e2e/api/` — `TestClient` + live Finviz HTTP, opt-in via `pytest -m live` (~3 tests, ~3s)
>
> Full testing strategy: see `TESTING.md` (API tests section).

---

## File Roles (Quick Reference)

| Role | Files | Lifecycle |
|------|-------|-----------|
| **Identity** | `CLAUDE.md` | Rarely changes; updated when project scope shifts |
| **Direction** | `docs/THESIS.md` | Changes per major phase or pivot |
| **Durable memory** | `memory/MEMORY.md` + linked files | Curated weekly; keep concise (~150 lines for index) |
| **Volatile preferences** | `docs/FEEDBACK-LOG.md` | Append-only; pruned quarterly |
| **Daily notes** | `memory/daily/YYYY-MM-DD.md` | Append during session; promoted to MEMORY weekly |
| **Operational rules** | `agents/rules/*.md`, `agents/roles/*.md` | Changes when workflow evolves |
| **Reference docs** | `docs/*`, `CONTRACTS.md`, `ARCHITECTURE.md`, `TESTING.md`, `TOOLS_REFERENCE.md` | Updated alongside code changes |

---

## When to Write to These Files

### Write to `MEMORY.md` (durable)
- User tells you something non-obvious about the project that should persist across sessions
- A design decision is made that constrains future work
- A recurring pattern is identified (e.g., "always use `from logger import logger`, never `logging.getLogger`")

### Write to `FEEDBACK-LOG.md` (corrections)
- User explicitly corrects an approach: "don't do X, do Y"
- User validates a non-obvious choice: "yes, that synchronous-fetch decision was right"
- Include **Why** and **How to apply** so future sessions can judge edge cases

### Write to `memory/daily/YYYY-MM-DD.md` (session notes)
- In-progress findings during a work session
- Commands run and their outputs
- Decisions made that may or may not be durable yet

### Write to `docs/THESIS.md` (direction)
- Phase completion
- Scope addition or removal
- Roadmap adjustment

---

## Curation Rhythm

| Cadence | Action |
|---------|--------|
| **Per session** | Append to `memory/daily/YYYY-MM-DD.md` as findings emerge |
| **End of session** | Promote durable insights from daily log to `MEMORY.md`; append corrections to `FEEDBACK-LOG.md` |
| **Weekly** | Review `FEEDBACK-LOG.md` → promote recurring items to `MEMORY.md`; archive stale daily logs |
| **Per phase** | Update `docs/THESIS.md` with completed/new milestones |

---

## Sub-Agent Context Diet

When spawning a sub-agent (via Claude Code's Agent tool or similar), **do not** inject the full Tier 1-4 context. Sub-agents should receive only:

- The task prompt (self-contained, with relevant file paths and line numbers)
- The specific `agents/roles/<role>.md` file matching their role
- The specific files they need to read (by path)

This keeps sub-agent context tight and avoids compaction pressure.

---

## What This File Is NOT

- **Not a tutorial** — see `docs/MODULE_REFERENCE.md` for that
- **Not a personality/tone guide** — fin_cli has no agent personality; `CLAUDE.md` defines project conventions
- **Not a replacement for `agents/rules/`** — those remain the authoritative mode/role rules; this file just tells you when to read them

---

## How Claude Code Auto-Loads Tier 3 Rules

The hook at `.claude/hooks/load-rules.js` reads three foundation rules from `agents/rules/` on every `SessionStart`:

1. `agents/rules/_shared-workflow.md`
2. `agents/rules/preflight.md`
3. `agents/rules/orchestrator.md`

It injects them into context with a header `# Loaded Workflow Rules (agents/rules/)`. Deduplication is session+content-hash based with a 1-hour TTL.

The remaining rules (`load-context.md`, `scaffold-module.md`) are **not auto-loaded** — they are read on-demand when acting in the corresponding mode.

### Cursor Users

Cursor auto-discovers rules from `.cursor/rules/` only. Since the canonical location is now `agents/rules/`, Cursor will no longer auto-attach these rules. Options:

- **(Recommended)** Invoke rules explicitly with `@agents/rules/<name>.md` when using Cursor.
- **(Alternative)** Create symlinks from `.cursor/rules/` to `agents/rules/` if Cursor auto-attach is needed.

---

## Change Log

| Date | Change |
|------|--------|
| 2026-05-04 | Single-mode reduction. Tier 4 module list trimmed to `fincli`, `core`, `config`, `logger` (the `fundainsight/` row was removed alongside the deletion of that package; see `docs/superpowers/specs/2026-05-04-fincli-only-refactor-design.md`). `TOOLS_REFERENCE.md` retargeted from `yahooquery` examples to `cfscrape` examples. `docs/MODULE_REFERENCE.md` description updated to single-mode. |
| 2026-05-02 | Initial file. Adapted from upstream reference project. Retargeted Go→Python, REST→CLI. Tier 3 references `.md` (not `.mdc`) extensions matching fin_cli conventions. Tier 4 retargeted from upstream REST/API docs to fin_cli CLI module reference, CONTRACTS, ARCHITECTURE, TESTING, TOOLS_REFERENCE, and source packages. 8 roles catalogued (FRONTEND/UX_UI hedged for future UI surface). |
