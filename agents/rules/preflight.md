---
alwaysApply: true
---
# Pre-Flight Checklist Skill

When invoked with `@preflight`, execute this mandatory checklist before any implementation in the **algo_beta** repository.

## Purpose

Ensures all required context is loaded, the task is properly broken down, and MCP tools are utilized before coding begins. Tailored to the algo_beta Python/CLI surface.

## Automatic Actions

### Step 1: Break Down the Task

Use `sequential-thinking` MCP tool to:
1. Identify the task scope
2. Break into small, testable steps
3. Identify dependencies and blockers
4. Estimate complexity

### Step 2: Load Relevant Documentation

Based on the task, read these files using the Read tool:
- Root `CLAUDE.md` — project identity, tech stack, conventions, important files
- Root `AGENTS.md` — loading contract and cross-file relationships (created in C6 of the harness rollout — skip gracefully if not present)
- Root `ARCHITECTURE.md` — overall system architecture (fincli + fundainsight + supporting modules)
- Root `CONTRACTS.md` — CLI command surface + CSV output schema
- Root `TESTING.md` — testing requirements and pytest layout
- Root `TOOLS_REFERENCE.md` — MCP tooling reference
- `docs/THESIS.md` — product direction, current phase, roadmap, scope boundaries
- `docs/MODULE_REFERENCE.md` — file-by-file map of public functions
- Module-specific docs under `docs/` if relevant

### Step 3: Identify Role and Mode

Determine from context:
- **Mode**: PLAN_AND_CREATE | EXECUTE | REFACTOR | DEBUG | CODE_REVIEW
- **Role**: ARCH | BACKEND | FRONTEND | UX_UI | VERIFIER | QA | REVIEWER

### Step 4: Run Local Quality Probes (advisory in Phase 1)

For any source-code change, before writing implementation:
- [ ] Ran `ruff check <touched module>` — note any pre-existing findings
- [ ] Ran `ruff format --check <touched module>`
- [ ] Ran `mypy <touched module>` — **results are advisory in Phase 1**, but capture the baseline
- [ ] Located the relevant Click command in `fincli/app/cli.py` or `fundainsight/app/cli.py`
- [ ] Located the relevant Pydantic config class in `config/config.py` or `core/configuration/configurator.py`
- [ ] Identified affected modules across `fincli/`, `fundainsight/`, `core/`, `config/`, `logger/`

### Step 5: Store Context in Memory

Use `memory:create_entities` to store:
- Task summary
- Identified files to modify
- Key constraints
- Dependencies

### Step 6: Research

If new implementation patterns or unfamiliar libraries are involved:
- Use `perplexity-ask` for general research
- Use `context7` for library documentation (yahooquery, pandas, Click, Pydantic, cfscrape, colorama, beautifulsoup4)

### Step 7: Memory Sync

Check for previous session data:
1. Use `memory:search_nodes` for related past work
2. Include relevant context in the current task

## Required Output Format

```
## Pre-Flight Checklist OK

### Task Summary
{brief description of what needs to be done}

### Context Loaded
- [x] CLAUDE.md - {1-line summary}
- [x] ARCHITECTURE.md - {1-line summary}
- [x] CONTRACTS.md - {1-line summary}
- [x] TESTING.md - {1-line summary}
- [x] AGENTS.md - {1-line summary} (created in C6 of the harness rollout — skip gracefully if not present)
- [x] docs/THESIS.md or docs/MODULE_REFERENCE.md - {if applicable}

### Task Breakdown (via sequential-thinking)
1. {step 1}
2. {step 2}
3. {step 3}
...

### Mode & Role
- **Mode**: {detected mode}
- **Role**: {detected role}
- **Rule File**: {corresponding rules file to follow}

### Local Probes
- ruff check: {clean | N findings}
- ruff format --check: {clean | N findings}
- mypy: {N issues — advisory in Phase 1}

### Affected Modules
- {fincli | fundainsight | core | config | logger | scripts | tests}

### Key Constraints
- {constraint 1}
- {constraint 2}

### Dependencies
- {any external dependencies or blockers}

### Memory
- {session id} - {session name}

### Ready to Proceed
```

## Composability

This skill can be chained with:
- `@load-context {path}` — for module / config / domain context
- `@tdd-setup {feature}` — to set up tests before implementation
- `@research {topic}` — if unknowns were identified

## Example Usage

```
User: @preflight I need to add a new --min-market-cap filter to fundainsight

AI: [Executes sequential-thinking]
    [Reads CLAUDE.md, ARCHITECTURE.md, CONTRACTS.md]
    [Reads fundainsight/app/cli.py and fundainsight/calculators/filters.py]
    [Runs ruff/mypy probes on touched modules]
    [Stores context in memory]
    [Outputs pre-flight checklist]
```
