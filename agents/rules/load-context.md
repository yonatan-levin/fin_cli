---
alwaysApply: true
---
# Load Context Skill (Smart Router)

When invoked with `@load-context {path}`, intelligently detect the type of path and load all relevant documentation and context for the **algo_beta** Python codebase.

## Purpose

Universal context loader that handles any path in the algo_beta project — modules, configuration, calculators, CLI surfaces, logger plumbing, scripts, tests, and documentation. Automatically detects the category and loads appropriate documentation.

## Supported Paths

### Top-Level Modules (Shorthand or Full Path)

| Input | Resolves To | Description |
|-------|-------------|-------------|
| `fincli` | `fincli/` | Stock screener: Finviz HTML fetch + parse + DataFrame export |
| `fundainsight` | `fundainsight/` | Fundamental analysis: Yahoo Finance enrichment + price-to-asset ratios |
| `core` | `core/` | Base configuration classes, JSON converters |
| `config` | `config/` | Pydantic configuration with history support |
| `logger` | `logger/` | Singleton logger (console / file / JSON handlers) |
| `scripts` | `scripts/` | Dependency-checking utilities |
| `tests` | `tests/` | pytest suites (unit / domain / e2e) |

### CLI Layer

| Input | Resolves To | Description |
|-------|-------------|-------------|
| `fincli-cli` | `fincli/app/cli.py` | Click command group for screening |
| `fundainsight-cli` | `fundainsight/app/cli.py` | Click command group for fundamental analysis |
| `cli` | both `app/cli.py` files | All CLI entry points |

### Domain Logic

| Input | Resolves To | Description |
|-------|-------------|-------------|
| `calculators` | `fundainsight/calculators/` | Price-to-asset ratio math, DataFrame filters |
| `equity-calc` | `fundainsight/calculators/equity_calc.py` | Asset adjustment + ratio computation |
| `filters` | `fundainsight/calculators/filters.py` | Country / sector / price filters |
| `picker` | `fundainsight/app/picker.py` | Fundamental analysis pipeline orchestration |
| `screener` | `fincli/app/main.py` | Screening pipeline orchestration |

### Web / Data Acquisition

| Input | Resolves To | Description |
|-------|-------------|-------------|
| `web-scraper` | `fincli/utils/web_scraper.py` | cfscrape-based Finviz HTML fetch (Cloudflare bypass) |
| `query-builder` | `fincli/utils/quary_builders.py` | Finviz URL query construction |
| `params` | `fincli/resource/params/` | Finviz filter parameter definitions |

### Configuration

| Input | Resolves To | Description |
|-------|-------------|-------------|
| `config-class` | `config/config.py` | Main `Config` Pydantic model |
| `configurator` | `core/configuration/configurator.py` | Config builder + validation pipeline |
| `system-settings` | `core/configuration/` | `SystemSettings` base class |

### Documentation

| Input | Resolves To | Description |
|-------|-------------|-------------|
| `docs` | `docs/` | Project docs (THESIS, MODULE_REFERENCE, FEEDBACK-LOG, bugs/) |
| `architecture` | `ARCHITECTURE.md` | Top-level system architecture |
| `contracts` | `CONTRACTS.md` | CLI command surface + CSV output schema |
| `testing` | `TESTING.md` | Test strategy and pytest layout |
| `tools-ref` | `TOOLS_REFERENCE.md` | MCP tools reference |
| `claude` | `CLAUDE.md` | Project guide for AI agents |
| `agents-md` | `AGENTS.md` | Loading contract |

## Automatic Actions

### Step 1: Detect Category

Analyze the input path and determine category:

```
Input -> Category Detection:
+-- fincli/* or fincli            -> SCREENER
+-- fundainsight/* or fundainsight -> ANALYSIS
+-- core/* or core                 -> CORE
+-- config/* or config             -> CONFIG
+-- logger/* or logger             -> LOGGER
+-- scripts/*                      -> SCRIPTS
+-- tests/*                        -> TESTS
+-- docs/*                         -> DOCS
+-- ARCHITECTURE.md / CONTRACTS.md / TESTING.md / CLAUDE.md / AGENTS.md / TOOLS_REFERENCE.md -> TOP_DOC
+-- (file path)                    -> SINGLE_FILE
```

### Step 2: Memory-Aware Context

Before loading docs, check memory:
1. `memory:search_nodes("{path} patterns")`
2. `memory:search_nodes("recent {path} issues")`
3. Include learnings in context

### Step 3: Load Documentation Based on Category

#### For SCREENER category (fincli):
Read using Read tool:
- `fincli/app/cli.py` — Click command group surface
- `fincli/app/main.py` — pipeline orchestration
- `fincli/utils/web_scraper.py` — HTTP fetching with Cloudflare bypass
- `fincli/utils/quary_builders.py` — URL query construction
- `fincli/resource/params/` — filter parameter definitions
- `CONTRACTS.md` (CLI command surface section)

#### For ANALYSIS category (fundainsight):
Read using Read tool:
- `fundainsight/app/cli.py` — Click command group surface
- `fundainsight/app/picker.py` — analysis pipeline orchestration
- `fundainsight/calculators/equity_calc.py` — financial math
- `fundainsight/calculators/filters.py` — DataFrame filtering
- `CONTRACTS.md` (CSV output schema section)

#### For CORE category:
Read using Read tool:
- `core/configuration/configurator.py` — config builder
- `core/configuration/` — `SystemSettings` base class
- `core/` — JSON converters and shared base classes

#### For CONFIG category:
Read using Read tool:
- `config/config.py` — main `Config` class (Pydantic)
- `core/configuration/configurator.py` — config builder + validation
- `CLAUDE.md` (configuration conventions)

#### For LOGGER category:
Read using Read tool:
- `logger/logger.py` — `Logger` singleton class
- Note: import via `from logger import logger`

#### For SCRIPTS category:
List all scripts in `scripts/` and describe their purpose based on filename. Key scripts include dependency-checking utilities.

#### For TESTS category:
Read using Read tool:
- `tests/` — pytest layout
- `TESTING.md` — test strategy and conventions
- Note: tests in Phase 1 are scaffolds; expect missing files

#### For DOCS category:
List all documentation files in `docs/` and summarize topics. Key checking areas:
- `docs/THESIS.md` — product direction
- `docs/MODULE_REFERENCE.md` — file-by-file map
- `docs/FEEDBACK-LOG.md` — review history
- `docs/bugs/` — bug specs
- `docs/superpowers/specs/` — design specs

#### For TOP_DOC category:
Read the specific top-level doc and provide context about its role.

#### For SINGLE_FILE category:
Read the specific file and provide context about its role in the codebase.

## Task-Specific Routing (Read These First)

| Task type | Read these docs first |
|-----------|------------------------|
| **API change** (CLI command surface or CSV schema) | `CONTRACTS.md` (CLI command surface + CSV schema sections) |
| **Domain-logic change** (price-to-asset math, filters) | `ARCHITECTURE.md` + `fundainsight/calculators/` |
| **Config change** (new flag, new config field) | `config/config.py` + `core/configuration/configurator.py` |
| **New CLI command** | `fincli/app/cli.py` or `fundainsight/app/cli.py` + Click conventions in `CLAUDE.md` |
| **Bug fix** | bug spec in `docs/bugs/<BUG-NNN>.md` if applicable; otherwise root-cause via `superpowers:systematic-debugging` |
| **Logger change** | `logger/logger.py` + the singleton pattern note in `CLAUDE.md` |
| **Test change** | `TESTING.md` + relevant `tests/<unit|domain|e2e>/` subtree |

### Step 4: Store in Memory

Use `memory:create_entities` to store:
- Path loaded
- Category detected
- Key patterns discovered

## Required Output Format

```
## Context Loaded: {path}

### Category: {SCREENER | ANALYSIS | CORE | CONFIG | LOGGER | SCRIPTS | TESTS | DOCS | TOP_DOC | SINGLE_FILE}

### Overview
{brief description based on loaded documentation}

### Key Information
{category-specific information}

### Structure
{path}/
+-- {relevant files/folders}
+-- ...

### Related Memories
{any relevant past context from memory}

### Context Stored in Memory
```

## Composability

This skill can be chained with:
- `@preflight` — run before this for full task context
- `@research {topic}` — if unknowns were identified

## Shorthand Reference

Quick reference for common shortcuts:

| Shorthand | Full Path |
|-----------|-----------|
| `fincli` | `fincli/` |
| `fundainsight` | `fundainsight/` |
| `core` | `core/` |
| `config` | `config/` |
| `logger` | `logger/` |
| `picker` | `fundainsight/app/picker.py` |
| `screener` | `fincli/app/main.py` |
| `calculators` | `fundainsight/calculators/` |
| `scripts` | `scripts/` |
| `tests` | `tests/` |
| `docs` | `docs/` |
