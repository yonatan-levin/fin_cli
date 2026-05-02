---
name: scaffold-module
description: Create a new Python module following algo_beta conventions. Generates the module skeleton (Click CLI + main pipeline + utils), Pydantic config wiring, logger import, and parallel test scaffolds.
globs:
  - "fincli/**"
  - "fundainsight/**"
  - "core/**"
  - "config/**"
  - "logger/**"
  - "tests/**"
---

# Scaffold Module Skill

When invoked with `@scaffold-module {module-name}`, create a complete module structure following the algo_beta Python/Click conventions documented in `CLAUDE.md`.

## Purpose

Quickly bootstrap new feature modules with consistent structure, reducing boilerplate and ensuring conformance with the project's `app/cli.py` -> `app/main.py` -> domain logic pattern.

## Prerequisites

Before scaffolding:
1. Check `ARCHITECTURE.md` to verify the new module's boundary and intended placement.
2. Review existing modules (`fincli/`, `fundainsight/`) for consistency.
3. Confirm with the user whether the module is a new top-level module or a sub-component of an existing one.

## Module Structure

```
{module-name}/
+-- __init__.py                  # Exports public API surface
+-- app/
|   +-- __init__.py
|   +-- cli.py                   # Click command group
|   +-- main.py                  # Pipeline orchestration
+-- utils/
|   +-- __init__.py
|   +-- {helper}.py              # Module-specific utilities (e.g., web_scraper, query builders)
+-- resource/                    # Optional — static parameter definitions
|   +-- __init__.py
|   +-- params/                  # Filter / option definitions

tests/
+-- unit/{module-name}/          # Unit tests (mock external IO)
|   +-- test_{component}.py
+-- domain/{module-name}/        # Domain-logic tests (pure functions)
|   +-- test_{component}.py
+-- e2e/{module-name}/           # End-to-end tests (fixture data only)
    +-- test_pipeline.py
```

## File Templates

### Module `__init__.py`

```python
"""{ModuleName} — short description of what this module does."""
from __future__ import annotations

# Re-export the public API surface here when stable.
```

### Click Command Group (`{module-name}/app/cli.py`)

```python
"""Click command group for {module-name}."""
from __future__ import annotations

import click

from logger import logger

from .main import run as _run


@click.group(name="{module-name}")
def cli() -> None:
    """Top-level command group for {module-name}."""


@cli.command()
@click.option(
    "--example",
    type=str,
    default=None,
    help="Example option.",
)
def main(example: str | None) -> None:
    """Run the {module-name} pipeline."""
    logger.info("Starting {module-name}")
    _run(example=example)
```

### Pipeline Orchestration (`{module-name}/app/main.py`)

```python
"""{ModuleName} pipeline orchestration."""
from __future__ import annotations

from logger import logger


def run(*, example: str | None = None) -> None:
    """Execute the {module-name} pipeline.

    Args:
        example: Optional example argument.
    """
    logger.info("Running {module-name} pipeline")
    # 1. Load configuration
    # 2. Fetch / parse / transform data
    # 3. Apply domain logic
    # 4. Write CSV output to workspace_output/
    raise NotImplementedError("scaffolded — implement me")
```

### Pydantic Config (`config/config.py` — append to existing `Config` model)

```python
from __future__ import annotations

from pydantic import Field

from core.configuration import SystemSettings


class {ModuleName}Settings(SystemSettings):
    """Settings for the {module-name} module.

    Extend SystemSettings; values can be overridden via JSON config history.
    """

    enabled: bool = Field(default=True, description="Enable {module-name}.")
    # Add module-specific fields here.

    model_config = {  # noqa: RUF012
        "extra": "forbid",
    }
```

Then wire into the main `Config` class:

```python
class Config(SystemSettings):
    # ... existing fields ...
    {module_name}: {ModuleName}Settings = Field(default_factory={ModuleName}Settings)
```

### Test Scaffold (`tests/unit/{module-name}/test_{component}.py`)

```python
"""Unit tests for {module-name}.{component}."""
from __future__ import annotations

import pytest

from {module-name}.app.main import run


def test_run_smoke() -> None:
    """Smoke test: pipeline can be invoked with default args."""
    with pytest.raises(NotImplementedError):
        run()
```

### Module Entry Script Wiring (optional)

If the module has its own `python -m` entry point, add `{module-name}/__main__.py`:

```python
"""Entry point: python -m {module-name}."""
from __future__ import annotations

from .app.cli import cli

if __name__ == "__main__":
    cli()
```

## Post-Scaffold Actions

1. **Wire CLI into entry scripts**: Add the new Click group to `run.sh` / `run.bat` if it should be runnable from the entry scripts.
2. **Update `pyproject.toml`**: If the module ships console_scripts entry points, declare them under `[project.scripts]`.
3. **Update top-level docs**: Reflect the new module in `ARCHITECTURE.md`, `CLAUDE.md` (Important Files table), and `docs/MODULE_REFERENCE.md`.
4. **Add CSV output schema** (if applicable): Document new CSV columns in `CONTRACTS.md`.
5. **Write tests**: Replace the smoke test with real unit / domain / e2e tests as the implementation lands.
6. **Logger usage**: Import via `from logger import logger` (singleton). Do NOT instantiate a new logger.

## Required Output Format

```
## Module Scaffolded: {module-name}

### Created Files
- [x] {module-name}/__init__.py
- [x] {module-name}/app/__init__.py
- [x] {module-name}/app/cli.py
- [x] {module-name}/app/main.py
- [x] {module-name}/utils/__init__.py
- [x] tests/unit/{module-name}/test_smoke.py
- [x] tests/domain/{module-name}/__init__.py
- [x] tests/e2e/{module-name}/__init__.py

### Next Steps
1. Add a {ModuleName}Settings class in config/config.py
2. Wire into run.sh / run.bat / pyproject.toml [project.scripts] if needed
3. Implement the pipeline in app/main.py
4. Document new CSV columns (if any) in CONTRACTS.md
5. Replace smoke tests with real unit / domain / e2e tests
6. Update ARCHITECTURE.md, CLAUDE.md, docs/MODULE_REFERENCE.md
```

## Example Usage

```
User: @scaffold-module growth_estimator

AI: [Verifies architectural placement]
    [Creates Python file structure for app/, utils/, tests/]
    [Creates template files using Click + Pydantic + logger conventions]
    [Outputs summary with next-step checklist]
```
