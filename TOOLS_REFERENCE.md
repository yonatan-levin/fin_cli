# TOOLS_REFERENCE.md - Fin CLI Tools, Skills, and Commands Reference

A single-page reference for every command, skill, MCP tool, and Claude Code hook used in this repo. Keep entries terse — one line each. For deeper context, follow the cross-reference at the bottom.

---

## Build / Run

| Command | What it does |
|---|---|
| `pip install -e ".[dev]"` | Editable install with the `dev` extra (ruff, mypy, pytest, pytest-cov, types-beautifulsoup4, pip-audit). |
| `pip install -r requirements.txt` | Install runtime deps only (no dev tooling). |
| `python -m fincli` | Run the screener (interactive). |
| `python -m fincli --history` | Run the screener with the last filter selection. |
| `python -m fincli --debug` | Run the screener with `DEBUG`-level logging. |
| `./run.sh` | Linux / macOS launcher: install requirements, then `python -m fincli "$@"`. |
| `run.bat` | Windows launcher: install requirements, then `python -m fincli %*`. |
| `python -c "import fincli"` | Smoke-import test (Python has no separate build step). |

---

## Test

| Command | What it does |
|---|---|
| `pytest tests/` | Run all tests. |
| `pytest tests/unit/` | Run unit-layer tests only. |
| `pytest tests/domain/` | Run domain-layer tests only. |
| `pytest tests/e2e/` | Run end-to-end tests only. |
| `pytest -k <pattern>` | Run tests whose name matches a substring/expression. |
| `pytest -x` | Stop at first failure. |
| `pytest -v` | Verbose output (one line per test). |
| `pytest --cov=fincli --cov=core --cov=config --cov-report=term-missing` | Coverage report (informational; gate deferred to Phase 3). |
| `pytest -ra` | Short summary of skipped/xfailed/errored tests (default via `pyproject.toml`). |

> Test bodies land in Phase 2 of the agent-harness rollout (`docs/superpowers/specs/2026-05-02-agent-harness-replication-design.md` §8.1). Until then `pytest tests/` collects nothing.

---

## Lint

| Command | What it does |
|---|---|
| `ruff check .` | Lint the whole repo (rules `E F W I B UP N SIM`). |
| `ruff check --fix .` | Auto-fix mechanical issues (unused imports, formatting drift). |
| `ruff check --diff .` | Show what `--fix` would change without writing. |
| `ruff check <module>/` | Lint one module (used by hooks). |

---

## Format

| Command | What it does |
|---|---|
| `ruff format .` | Format the whole repo (black-compatible). |
| `ruff format --check .` | Verify formatting without writing (CI / Stop hook). |
| `ruff format <file>` | Format one file (used by `post-edit.js`). |

---

## Type check

| Command | What it does |
|---|---|
| `mypy fincli core config logger` | Type-check the active modules in strict mode (Phase 1: advisory; Phase 4: blocking). |
| `mypy <file>` | Check one file (used by `post-edit.js`). |
| `mypy --no-incremental` | Bypass mypy's cache when diagnosing weirdness. |

`pyproject.toml` contains the `[tool.mypy]` config: `strict = true` from day one, with `ignore_missing_imports = true` for `cfscrape` (no upstream stubs). `bs4` is typed via the `types-beautifulsoup4` dev dep.

---

## Vulnerability audit

| Command | What it does |
|---|---|
| `pip-audit -r requirements.txt` | Check runtime deps for known vulnerabilities (skipped gracefully if not on PATH). |

---

## MCP Tools

One-line "when to reach for it" for the MCP servers wired in this repo.

### Reasoning / agentic

| Tool | Use when |
|---|---|
| `sequential-thinking` | You need to break a multi-step problem into ordered steps before acting. |
| `zen-mcp` (`thinkdeep`) | A second model should chew on an architectural / hard-tradeoff question. |
| `zen-mcp` (`codereview`) | Pre-PR systematic review pass on changed files. |
| `zen-mcp` (`debug`) | Root-cause analysis for a bug that resists fix-and-retry. |
| `zen-mcp` (`planner`, `analyze`, `consensus`, `tracer`, `refactor`, `precommit`, `secaudit`, `testgen`, `docgen`) | Specialized agentic passes; see TOOLS_REFERENCE in the parent harness for full table. |

### Research / docs

| Tool | Use when |
|---|---|
| `context7` (`resolve-library-id` -> `query-docs`) | Looking up Click / pandas / Pydantic / cfscrape / BeautifulSoup4 / requests docs — preferred over web search for library docs. |
| `perplexity-ask` | "How do other projects solve X" web research. |

### Memory

| Tool | Use when |
|---|---|
| `memory` (`create_entities`, `search_nodes`, `read_graph`, ...) | Persisting cross-session project knowledge (data shapes, decisions). |
| `plugin_claude-mem_mcp-search` (`smart_search`, `timeline`, ...) | Searching prior session observations / project timeline. |

### Calling pattern

```text
1. context7:  resolve-library-id("cfscrape")  -> id
              query-docs(id, topic="create_scraper")
2. memory:    search_nodes("CSV output schema")  -> nodes
              open_nodes(["fincli stock_screener_csv"])
3. zen:       thinkdeep(model="gpt-5.2-pro", question="...")
```

---

## Skills

Invoke pattern: `Skill(skill="<name>")`.

### User-scope / general

| Skill | When to invoke |
|---|---|
| `update-config` | Configure the harness via `settings.json` — hooks, permissions, env vars. |
| `code-review` | Review existing diff/branch/PR before commit/merge — does NOT write new code. |
| `debug` | Diagnose and fix a reported bug, failing test, or production error. |
| `docs-update` | Update stale docs after code changes. |
| `execute` | Implement a well-defined solution where the spec is settled. |
| `plan-and-create` | Turn a high-level idea into a working feature — design then implement. |
| `refactor` | Improve structure / readability without changing behavior. |
| `research` | Research unfamiliar libraries / APIs / approaches. |
| `review-prep` | Prepare changes for PR / handoff before reviewer pickup. |
| `session-startup` | Catch up on the project after time away. |
| `tdd-setup` | Write failing tests before implementation (RED phase of TDD). |
| `local-ci` | Run lint/type/tests locally on changed files before commit. |
| `simplify` | Review changed code for reuse/quality/efficiency, then fix. |
| `github-tracking` | Manage GitHub issues — create, log progress, transition labels. |
| `loop` | Run a prompt or slash command on a recurring interval. |
| `schedule` | Manage scheduled remote agents (cron routines). |

### `superpowers:*` plugin

| Skill | When to invoke |
|---|---|
| `superpowers:using-superpowers` | Bootstrap rules for finding/using skills (auto-loaded at session start). |
| `superpowers:brainstorming` | MUST use before any creative work — explores intent, requirements, design. |
| `superpowers:writing-plans` | Author multi-step implementation plans before touching code. |
| `superpowers:executing-plans` | Execute a written plan in a separate session with checkpoints. |
| `superpowers:subagent-driven-development` | Execute a plan via subagents in the current session. |
| `superpowers:dispatching-parallel-agents` | Coordinate 2+ independent tasks across parallel subagents. |
| `superpowers:test-driven-development` | Enforce test-first discipline. |
| `superpowers:systematic-debugging` | Structured root-cause investigation before fixing. |
| `superpowers:verification-before-completion` | Run verification commands and confirm output before claiming done. |
| `superpowers:requesting-code-review` | Request review before merge. |
| `superpowers:receiving-code-review` | Process review feedback rigorously. |
| `superpowers:finishing-a-development-branch` | Decide how to integrate completed work — merge / PR / cleanup. |
| `superpowers:using-git-worktrees` | Isolate feature work in a worktree before executing a plan. |
| `superpowers:writing-skills` | Create / edit / verify skills before deployment. |

### Slash commands

> Slash commands are typed by the user; the agent does not call them programmatically.

| Command | What it does |
|---|---|
| `/init` | Initialize a new `CLAUDE.md`. |
| `/review` | Review the current pull request. |
| `/security-review` | Security audit of pending changes on the current branch. |
| `/clear` | Clear the conversation context. |
| `/resume` | Resume a prior session. |
| `/help` | Get help with using Claude Code. |
| `/config` | Adjust simple settings (theme, model). |
| `/loop <interval> <prompt>` | Run a prompt/command repeatedly on an interval. |
| `/schedule` | Manage scheduled remote agents. |

---

## Claude Code Hook Reference

The hooks listed below are wired in `.claude/settings.json` and live under `.claude/hooks/`. Each fires automatically on the named event; none of them needs to be invoked by hand.

| Event | Hook script | Timeout | Purpose |
|---|---|---|---|
| `SessionStart` | `.claude/hooks/load-rules.js` | 10 s | Auto-injects `agents/rules/_shared-workflow.md`, `preflight.md`, and `orchestrator.md` into the new session's context under the header `# Loaded Workflow Rules (agents/rules/)`. |
| `PreToolUse:Read` | `.claude/hooks/pre-read.js` | 10 s | Guard rail before file reads — skips known sensitive paths and very large files; surfaces a helpful note if a denied path is read. |
| `PostToolUse:Edit\|Write` | `.claude/hooks/post-edit.js` | 120 s | After every save: `ruff check --fix <file>`, `ruff format <file>`, `mypy <file>`. Also runs the secret/OWASP regex scan on the saved file and surfaces a doc-update reminder when the saved file matches `DOC_TRIGGER_PATTERNS` (e.g., editing a Finviz `params/*.py` reminds you to update `CONTRACTS.md`). |
| `Stop` | `.claude/hooks/on-stop.js` | 600 s | At the end of a session: run repo-wide `ruff check .`, `ruff format --check .`, `mypy fincli core config logger`, `pytest tests/`, and `pip-audit -r requirements.txt` (skipped if not on PATH). **Phase 1**: mypy results go through the `warnings` channel (advisory, non-blocking). Coverage check is stubbed as `{skipped: true, reason: "Phase 3 deferred"}`. **Phase 4** (after `mypy ... ` returns zero errors) flips mypy to the `issues` channel so it blocks Stop. **Phase 3** (after Phase 2 establishes a real test suite) enables a 90% coverage gate. |

### Shared utilities

`.claude/hooks/utils.js` carries:

- Project-root detection.
- Git Bash path normalization (Windows → POSIX-form for hook scripts).
- Session edit tracking (`.session-edits.json` — gitignored).
- Secret / sensitive-file / security regex tables.
- I/O helpers (`readStdin`, `respondOk`, `respondBlock`).
- The `SERVICES` map of module → runtime config used by `on-stop.js`.

`.claude/hooks/.gitignore` keeps the per-session state files (`.session-edits.json`, `.rules-loaded`) out of git.

### Hook env-var overrides

| Env var | Default | Effect |
|---|---|---|
| `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` | `1` (set in `settings.json`) | Enables the agent-team feature used by sub-agent role files. |
| `CLAUDE_HOOKS_DISABLE` | unset | If set to `1`, all hook scripts short-circuit to `respondOk()`. Useful when reproducing a bug without hook noise. |

---

## How to reference these in a command or sub-agent file

### Activating a skill from an instruction file

```markdown
Before writing any implementation code, invoke the
`superpowers:test-driven-development` skill via the Skill tool.
Follow its checklist exactly.
```

The model translates that to: `Skill(skill="superpowers:test-driven-development")`.

### Calling an MCP tool from an instruction file

```markdown
When the user asks about a third-party library's API:
1. Call `mcp__context7__resolve-library-id` with the library name.
2. Then call `mcp__context7__query-docs` with the returned ID and a focused topic.
Do NOT answer from training data without consulting context7 first.
```

### Sub-agent `tools:` allowlist

Each tool a sub-agent calls must appear in its frontmatter:

```markdown
---
name: api-researcher
tools: Read, Grep, Skill, mcp__context7__resolve-library-id, mcp__context7__query-docs
---
```

Without this, the sub-agent literally cannot make the call.

---

## Server-specific reminders

| Server | Reminder |
|---|---|
| `context7` | Prefer over web search for library/framework docs (Click, pandas, Pydantic, cfscrape, BeautifulSoup4). Do NOT use for refactoring, business-logic debugging, or generic programming concepts. |
| `zen-mcp` | Default model `gpt-5.2-pro` unless the user names a different one. |
| `claude-in-chrome` | Each tool must be loaded with `ToolSearch("select:<tool_name>", 1)` before calling. Always start a session with `tabs_context_mcp`. |
| `claude.ai Postman` | Read its instructions resource completely before answering API-related questions. |

---

## Cross-reference

- Build/run conventions, file map, phase status: [`CLAUDE.md`](CLAUDE.md)
- System architecture, layering, threading: [`ARCHITECTURE.md`](ARCHITECTURE.md)
- CLI surface, CSV schema, stability policy: [`CONTRACTS.md`](CONTRACTS.md)
- Test layout, mocking strategy, Phase 2/3/4 roadmap: [`TESTING.md`](TESTING.md)
- Master agent index (Tier 1–4 reading order, sub-agent context diet): [`AGENTS.md`](AGENTS.md)
- Project vision and roadmap: [`docs/THESIS.md`](docs/THESIS.md)
