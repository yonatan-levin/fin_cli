---
alwaysApply: true
---
# Pre-Flight Checklist Rule

Always-on rule, not a skill: it runs before any implementation in the
**fin_cli** repository (Finviz stock screener — CLI + HTTP API).
`@preflight` is an optional mid-session re-invocation, not the only trigger.

## Where This Fits

Preflight owns three things only — everything else is a pointer, not a copy:
**flow** → `/sdlc`; **policy** (validation cycle, exit criteria, regression
tiers, model routing, closure mechanics) → `agents/rules/_shared-workflow.md`;
**context loading** → `AGENTS.md`. Preflight itself owns: worktree isolation
(Step 0), the layer decision (Step 1), mode + role detection (Step 3).

## Automatic Actions

### Step 0: Isolate the working tree — MANDATORY (workspace-wide git rule)

**Before ANY edit (feature, fix, refactor, docs, closeout), work in a dedicated git worktree — never a bare branch in the main checkout, and never edit `master`'s working tree.**

- **Create it with portable git:** `git worktree add ../algo_beta_<topic> -b
  <type>/<slug> master`; do ALL edits/tests/commits there. Underscore, not
  hyphen, between `algo_beta` and the topic — a hyphenated worktree directory
  becomes the package directory in this `package-dir='.'` repo, so ruff N999 +
  mypy reject the invalid module name before any edit (issue #55). (Prefer
  `git worktree add` over any framework-specific tool — it works for every
  agent/CLI.)
- **Why:** the workspace runs multiple concurrent sessions over a shared
  checkout; a parallel `git checkout` swaps the branch underneath you and
  contaminates merges/verification. A worktree isolates the *working tree*,
  not just the branch pointer.
- **Push/PR/merge:** never merge or push the default branch (`master`) on an
  agent's own initiative, but the **SDLC HUMAN acceptance gate is the
  authorization point**, not a later separate step — an unmerged PR is a
  legitimate reviewable work product (opening one mid-task is fine); merging
  and fast-forwarding `master` happen at/after that gate, after which removing
  the worktree and deleting the merged branch is REQUIRED (`/sdlc` closure
  step 6).
- **Baseline probe:** before editing, run this repo's gates once in the
  worktree's own venv (e.g. `python -m ruff check .`, `python -m mypy`,
  `python -m pytest`) — if something is already red, it is not yours to fix
  silently (say so).
- Authority: parent `../CLAUDE.md` "Git workflow (workspace-wide)", this
  repo's `docs/FEEDBACK-LOG.md`. If already inside a linked worktree
  (`git rev-parse --git-dir` ≠ `--git-common-dir`), you're isolated — proceed.

### Step 1: Determine the Layer & Break Down the Task

1. Layer: CLI (`fincli/`), HTTP API (`fincli_api/`), or shared core
   (`core/`, `config/`, `logger/`)? Respect the architectural boundary —
   `fincli_api/adapters/fincli.py` is the ONLY file in `fincli_api/` allowed
   to import from `fincli/` (`CLAUDE.md` §3.2 / architecture boundary).
2. Classification, planning, and intake are `/sdlc`'s job — invoke it rather
   than re-deriving them here.

### Step 2: Load Context

Defer to `AGENTS.md`'s loading contract — Tier 1 always, Tiers 2–4 as Step
1's layer decision implicates. Honor its Sub-Agent Context Diet when
dispatching sub-agents instead of injecting full Tier 1–4 context.

### Step 3: Identify Role and Mode

- **Mode**: PLAN_AND_CREATE | EXECUTE | REFACTOR | DEBUG | CODE_REVIEW
- **Role**: ARCH | BACKEND | FRONTEND | UX_UI | VERIFIER | QA | REVIEWER

### Step 4: Duplicate-Work Check & Research

Both are `/sdlc`'s job — intake mandates the claude-mem duplicate-work check;
its MCP-nudges table (and the role file's Skill and Tool Triggers) cover
research per phase. Invoke `/sdlc` instead of restating either here.

## Required Output Format

```
## Pre-Flight Checklist OK

### Task Summary
{brief description}

### Layer
- CLI (`fincli/`) | HTTP API (`fincli_api/`) | Core/Config/Logger (`core/`, `config/`, `logger/`)

### Mode & Role
- Mode: {detected}
- Role: {detected}

### Worktree
- Path: {worktree path}
- Branch: {branch name}

### Key Constraints
- ...

### Ready to Proceed
```

## Composability

- `@load-context {path}` — for module / config / domain context
- `@tdd-setup {feature}` — set up tests before implementation
- `/sdlc` — classification, planning, implementation-cycle routing, closure

## Example Usage

```
User: @preflight add a --max-tickers cap to the fincli screener

AI: [Step 0: git worktree add ../algo_beta_max-tickers-cap -b
     feat/max-tickers-cap master]
    [Step 1: layer = CLI (fincli/app/cli.py) + core config; /sdlc handles
     classification]
    [Step 2: AGENTS.md tier contract]
    [Step 3: Mode=EXECUTE, Role=BACKEND]
    [Step 4: /sdlc intake already ran the duplicate-work check]
    [Hands off to /sdlc's task route → /execute]
```
