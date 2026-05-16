---
alwaysApply: true
---
# Shared Workflow Documentation

This file contains shared workflow patterns used across all roles and modes for the **fin_cli** project (Python CLI for Finviz stock screening).

---

**BEFORE STARTING - MANDATORY STEPS:**

1. **READ SPECS FIRST** - Use Read tool on:
   - `ARCHITECTURE.md`
   - `CONTRACTS.md` (CLI command surface + CSV output schema)
   - `TESTING.md`
   - `AGENTS.md` (created in C6 of the harness rollout — skip gracefully if not present)

2. **USE MCP TOOLS** - You MUST call:
- **sequential-thinking**: Break down complex tasks into smaller steps
- **memory**: Store work context, thoughts, and conclusions
- **perplexity-ask**: Research unknown problems, search web for answers
- **context7**: Look up documentation for any code subject (Click, pandas, Pydantic, cfscrape, BeautifulSoup4)
- **mcp__zen__thinkdeep**: Deep thinking about architecture and complex problems
- **mcp__zen__codereview**: Systematic code review.
- **mcp__zen__debug**: Root cause analysis for bugs

3. **SHOW YOUR WORK** - Response must include:
   - Checklist acknowledgment
   - Tool call results
   - Reasoning before implementation

**If these steps are skipped, the implementation is INVALID.**


## Available Roles

Each role has a corresponding role file that defines its responsibilities and how to invoke it. Role files live in `agents/roles/` (repo root). Invoke them via Claude Code's Task tool with the matching `subagent_type`, or reference the file path directly.

| Role | Responsibility | Role File |
|------|----------------|-----------|
| **ARCH** | Architecture decisions, module boundaries, refactor plans, requirements clarification, spec updates | `agents/roles/code-architect.md` |
| **BACKEND** | Python implementation: screener pipeline in `fincli/app/main.py`, HTML parsing in `fincli/stock_screening/`, Finviz URL builder in `fincli/utils/quary_builders.py`, Click CLI commands, Pydantic configs, logger plumbing | `agents/roles/backend-architect.md` |
| **FRONTEND** | Click command groups, terminal output formatting (colorama), CSV-to-table presentation, TUI widgets, notebook helpers — *see footnote* | `agents/roles/frontend-developer.md` |
| **UX_UI** | CLI ergonomics, `--help` text quality, error-message clarity, prompt design, color/symbol conventions — *see footnote* | `agents/roles/ui-designer.md` |
| **VERIFIER** | Independent validation that implementation works — runs pytest, ruff, mypy, inspects CSV outputs, validates behavior | `agents/roles/verifier.md` |
| **QA** | Behavior verification, test coverage, regression checking, CLI / data / config debugging | `agents/roles/qa-debugger.md` |
| **REVIEWER** | Code review for readability, maintainability, security, performance — Python-specific patterns (PEP 8, type hints, Pydantic) | `agents/roles/code-reviewer.md` |

> **Note:** fin_cli has **no current frontend surface**. Invoke FRONTEND/UX_UI only when explicitly extending the system with UI (TUI / dashboard / notebook). For all non-UI work, BACKEND covers the full implementation surface.

---

## Validation Cycle (4-Stage)

```
+--------------------------------------------------------------------------------+
|                           VALIDATION CYCLE                                     |
+--------------------------------------------------------------------------------+
|                                                                                |
|  IMPLEMENTER --> VERIFIER --> REVIEWER --> QA --> HUMAN                        |
|       ^              |            |         |                                  |
|       |        NOT   |     REJECT |    FAIL |                                  |
|       |     VERIFIED |            |         |                                  |
|       +--------------+------------+---------+                                  |
|                                                                                |
|  Max 2-3 iterations before escalating to HUMAN                                 |
+--------------------------------------------------------------------------------+
```

### When VERIFIER is Required

| Condition | VERIFIER Required? |
|-----------|-------------------|
| PLAN_AND_CREATE (new features) | **MANDATORY** |
| DEBUG (bug fixes) | **MANDATORY** |
| EXECUTE (non-trivial changes) | **MANDATORY** |
| REFACTOR (structural changes) | **MANDATORY** |
| CODE_REVIEW (no implementation) | Skip |
| Trivial changes (docs, config) | Skip (with justification) |

---

## VERIFIER Responsibilities

- **Implementation Exists**: Claimed files/code actually exist, no placeholders or TODOs
- **Tests Pass**: All affected pytest suites pass
- **Functionality Works**: Happy path, error cases, and edge cases work correctly
- **Quality Standards**: ruff is clean, mypy issues are surfaced (advisory in Phase 1), code follows conventions
- **CSV Output Schema**: When CSV-producing code is touched, run the screener pipeline on fixture data and inspect column names + dtypes
- **No Regressions**: Existing functionality still works, no new issues introduced

**VERIFIER test-suite list:**

| Suite | Tooling | Status |
|-------|---------|--------|
| Unit tests | pytest | required when behavior changed |
| Domain tests | pytest | required for `fincli/stock_screening/` and pipeline changes |
| E2E tests | pytest with fixture data | required for full-pipeline changes |
| Lint | ruff | gate |
| Format | ruff format --check | gate |
| Types | mypy | **advisory only — Phase 4 promotes to gate** |
| Coverage | pytest-cov | **deferred (Phase 3, target 90%)** |
| Dependency audit | pip-audit | advisory |

**VERIFIER Output Format:**
```
# Result: VERIFIED | NOT VERIFIED | PARTIALLY VERIFIED

# Verification Summary
- What was claimed as complete
- What was actually tested

# Test Results
| Suite | Status | Details |
|-------|--------|---------|
| Unit (pytest) | OK/FAIL | X passed, Y failed |
| E2E (pytest) | OK/FAIL | X passed, Y failed |
| Lint (ruff) | OK/FAIL | X errors |
| Types (mypy) | advisory | X issues (non-blocking in Phase 1) |
| Coverage | deferred | Phase 3 |

# Issues Found (if any)
| Severity | Description | Location |
|----------|-------------|----------|
| BLOCKER | Tests failing | file:line |

# Next Steps
HANDOFF_TO: <BACKEND | FRONTEND | REVIEWER | HUMAN>
```

---

## REVIEWER Responsibilities

- **Readability**: Clear naming, proper structure, Google-style docstrings where appropriate
- **Maintainability**: Low complexity, no duplication, good cohesion, type hints where load-bearing
- **Security**: Input validation, no secrets exposed, no CSV injection (`=`/`+`/`-`/`@` prefixes), cfscrape User-Agent leak check, no hardcoded API keys
- **Performance**: No obvious bottlenecks in critical paths (sequential page fetch latency, pandas chained ops)
- **Tests**: Adequate coverage (target 90%, deferred to Phase 3), clear test names
- **Documentation**: Updates to ARCHITECTURE.md, CONTRACTS.md, TESTING.md, CLAUDE.md if needed

**REVIEWER Output Format:**
```
# Result: APPROVE | APPROVE_WITH_NITS | REJECT

# Strengths
- What was done well

# Issues
| Severity | Location | Type | Description |
|----------|----------|------|-------------|
| HIGH     | file:line| security | ... |

# Suggested Changes
- Specific code fixes (with snippets)

# Next Steps
HANDOFF_TO: <BACKEND | FRONTEND | QA | HUMAN>
```

---

## QA Responsibilities

- **Requirements**: Does implementation match ARCH specs?
- **CLI Spec**: Does the Click command surface match `CONTRACTS.md`?
- **Output Schema**: Does the CSV match the documented column set + dtypes?
- **Tests**: Do tests pass? Any regression risk?
- **Edge Cases**: Are error states handled (empty Finviz response, Cloudflare 503/429, missing or malformed table cells)?

**QA Output Format:**
```
# Result: PASS | FAIL

# Checks Performed
- List of verifications done

# Issues
| Severity | Agent | Description |
|----------|-------|-------------|
| HIGH     | BACKEND | (example) build_data_frame drops the Symbol column when --output - is set (regression vs CONTRACTS §3.1) |

# Suggested Fixes
- Specific fixes for each issue

# Next Steps
HANDOFF_TO: <BACKEND | FRONTEND | HUMAN>
```

---

## Standard Response Format (All Roles)

Every role response MUST follow this structure:

```
MODE: <PLAN_AND_CREATE | EXECUTE | REFACTOR | CODE_REVIEW | DEBUG | VERIFICATION>
ROLE: <ORCHESTRATOR | ARCH | BACKEND | FRONTEND | UX_UI | VERIFIER | QA | REVIEWER>

# Summary
Short, high-level description of what you did or will do.

# Analysis
Key observations, constraints, and assumptions.

# Plan
Bullet list of concrete steps.

# Output / Diff / Report
- Implementers: code changes (prefer diffs or annotated code blocks)
- ARCH / UX_UI: specs, contracts, task breakdowns
- REVIEWER / QA: review findings, issues, suggestions

# Tests
What tests you added/updated and how to run them.

# Next Steps
Who should act next and on what.

HANDOFF_TO: <ARCH | BACKEND | FRONTEND | UX_UI | VERIFIER | QA | REVIEWER | HUMAN>
```

---

## Critical Rules
0. **Always keep in context user rules**
1. **Spec-first**: Always check project docs before routing. Missing specs → ARCH first.
2. **Never skip quality gates**: Every implementation goes through VERIFIER → REVIEWER → QA → HUMAN.
3. **Small changes**: Break large tasks into smaller, reviewable chunks.
4. **Iteration limit**: Max 2-3 cycles of BACKEND/FRONTEND vs REVIEWER/QA before escalating to HUMAN.
5. **Preserve context**: Handoffs must include all relevant context.
6. **No scope creep**: Unrelated changes should be separate tasks.
7. **Explicit gaps**: Ask for clarification rather than guessing.
8. **Documentation**: Update ARCHITECTURE.md, CONTRACTS.md, TESTING.md, CLAUDE.md, docs/ as needed.

---

## Edge Cases

| Scenario | Handling |
|----------|----------|
| Ambiguous request | Ask clarifying questions before routing |
| Multi-domain task | Break into sub-tasks, route each appropriately |
| Urgent hotfix | EXECUTE → REVIEWER → HUMAN (skip QA with human approval) |
| Documentation only | ARCH for specs, HUMAN for README |
| Debugging request | DEBUG mode: QA triage → BACKEND fix → QA verify |
| Failing test | DEBUG mode: QA triage → identify area → implementer fixes |
| Production / data error | DEBUG mode (CRITICAL): QA triage → fast-track fix → verify |
| Performance issue | ARCH analyzes → BACKEND implements → full cycle |
| New CLI command | ARCH defines surface in `CONTRACTS.md` → BACKEND adds Click command → VERIFIER runs against fixture → QA |
| New CSV column | ARCH updates `CONTRACTS.md` schema → BACKEND adds calculator + writer → VERIFIER inspects output → QA validates dtypes |

---

## GitHub Issue Tracking Integration

Non-trivial work SHOULD be tracked via GitHub issues when the user opts in. Use the `@github-tracking` skill for issue operations.

### Repository
- **Target**: `yonatan-levin/fin_cli` (canonical; the local `origin` may still point at `GoBoldMS/fin_cli` which redirects)

### Issue Lifecycle Flow

```
+-----------------------------------------------------------------------------+
|                        GitHub Issue Lifecycle                               |
+-----------------------------------------------------------------------------+
|                                                                             |
|  User Request                                                               |
|       |                                                                     |
|       v                                                                     |
|  ORCHESTRATOR -----> Create issue (enhancement + planning)                  |
|       |               +-> Store issue # in memory                           |
|       v                                                                     |
|  ARCH -------------> Update issue body with plan + task list                |
|       |               +-> Add Architecture label                            |
|       v                                                                     |
|  BACKEND ----------> Log progress as comments                               |
|       |               +-> Labels: planning -> in-progress                   |
|       |               +-> Check task list items                             |
|       v                                                                     |
|  VERIFIER ---------> Add verification report comment                        |
|       |               +-> Labels: in-progress -> verification -> review     |
|       v                                                                     |
|  REVIEWER ---------> Add review findings comment                            |
|       |               +-> Labels: review -> qa                              |
|       v                                                                     |
|  QA ---------------> Add QA report comment                                  |
|       |               +-> Labels: qa -> Completed                           |
|       v                                                                     |
|  HUMAN ------------> Close issue                                            |
|                       +-> Only HUMAN closes issues                          |
|                                                                             |
+-----------------------------------------------------------------------------+
```

### Label Mapping

| Label | Status | Next State |
|-------|--------|------------|
| `planning` | Initial design phase | `in-progress` |
| `in-progress` | Active implementation | `verification` |
| `verification` | Awaiting VERIFIER | `review` or back |
| `review` | Awaiting REVIEWER | `qa` or back |
| `qa` | In QA validation | `Completed` or back |
| `Completed` | Done, ready for close | (closed by HUMAN) |

### Agent Responsibilities

| Agent | Issue Action | Command |
|-------|--------------|---------|
| **ORCHESTRATOR** | Create feature issue | `@github-tracking create-feature` |
| **ARCH** | Update plan + task list | `@github-tracking update-plan` |
| **BACKEND** | Log progress | `@github-tracking log-progress` |
| **VERIFIER** | Add verification report | `@github-tracking log-verification` |
| **REVIEWER** | Add review findings | `@github-tracking log-review` |
| **QA** | Add QA report | `@github-tracking log-qa` |
| **Any Agent** | Create bug issue | `@github-tracking create-bug` |

### When to Create Issues

| Scenario | Create Issue? | Type |
|----------|---------------|------|
| New feature (PLAN_AND_CREATE) | **YES** | `enhancement` |
| Bug found during development | **YES** | `bug` |
| Non-trivial EXECUTE task | **YES** | `enhancement` |
| Refactor with significant scope | **YES** | `enhancement` |
| Trivial fix (typo, small config) | No | - |
| Documentation-only update | Optional | `documentation` |

### Session Continuity

At session start:
1. Check memory for active issue: `memory:search_nodes("active-issue")`
2. If found: Load context with `@github-tracking get-context`
3. Resume work on that issue

At session end:
1. Log current progress to issue
2. Update memory with latest state
3. Include issue # in commit messages: `feat: add X (#123)`

### Bug Discovery Flow

When any agent discovers a bug during their work:

```
Bug Found
    |
    +-> Minor (doesn't block current work)
    |     +-> Create bug issue, note in parent issue, continue
    |
    +-> Major (blocks current work)
          +-> Create bug issue, escalate to DEBUG mode
```

### Best Practices

**Do:**
- Include issue # in all commit messages
- Log significant decisions as comments
- Update task checkboxes as work completes
- Reference related issues with `#number`
- Use collapsible sections for long content

**Don't:**
- Close issues without HUMAN approval
- Skip validation stages
- Leave issues without updates for extended periods
- Create issues for trivial changes

### Issue Templates

Use provided templates in `.github/ISSUE_TEMPLATE/` if present:
- `feature_request.md` - For new features
- `bug_report.md` - For bug reports

---
