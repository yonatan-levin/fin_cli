# CLI Entry Point — Refactor Spec (Stub)

**Status:** STUB — design deferred until the user is ready to action this work.
**Parent:** `docs/superpowers/specs/2026-05-04-fincli-only-refactor-design.md` (v1.1, §6.6)
**Date opened:** 2026-05-04

---

## Goal

Add a `[project.scripts]` entry point to `pyproject.toml` so that `pip install -e .` exposes a bare `fincli` shell command instead of requiring users to type `python -m fincli`. The two invocations should be exactly equivalent — the new shell command is a thin wrapper, not a new code path.

This was explicitly deferred during the 2026-05-04 single-mode reduction (Q2 = Option B in the brainstorm). The reduction kept the existing `python -m fincli` invocation unchanged and pushed the entry-point work into this follow-up spec.

## Affected files

- `pyproject.toml` — add a new `[project.scripts]` table.
- `fincli/app/cli.py` — confirm or expose the callable that the entry point will reference. The current Click group is registered as `run_main` at module level; the spec author should confirm whether `fincli.app.cli:run_main` is the right reference or whether a thin wrapper named `cli` or `main` is preferable for consistency with the convention in other Python projects.
- `README.md` — update the "Quick Start" / "Run" section to show both `fincli` and `python -m fincli` invocations.
- `CONTRACTS.md` §1 — note the entry point exists; clarify that `python -m fincli` is the canonical fallback when the install layout does not place the entry point on `PATH`.
- `TOOLS_REFERENCE.md` — add the bare `fincli` command to the "Build / Run" table.
- `run.sh` / `run.bat` — optionally simplify to call `fincli` directly once the entry point is on `PATH`. (The current launchers call `python -m fincli`, which works whether or not the entry point is installed.)

## Open decisions deferred to the user

1. **Exact callable name.** The Click group in `fincli/app/cli.py` is currently named `run_main`. Should the entry point reference `run_main` directly, or should we rename it to `cli` / `main` first for convention?
2. **Subcommand structure.** The entry point currently exposes one default action (the screener). If the project later grows multiple subcommands (e.g. `fincli screen`, `fincli history clear`), the entry-point wiring may want to anticipate that. Decide whether the v1 entry point should pin the current single-action layout or be designed for subcommand expansion.
3. **Backward-compatible invocations.** Confirm that adding `[project.scripts]` does not break any currently-tested invocation (`./run.sh`, `run.bat`, `python -m fincli`). All three must continue to work.
4. **Reinstall guidance for existing dev environments.** Adding an entry point requires a `pip install -e .` re-run; document that in the spec body when this work is actioned.

## Non-goals

- Changing the screener's behavior. This is purely a packaging-surface change.
- Switching CLI frameworks. The project uses Click; that is unchanged.

## Next step

When the user is ready to action this work, expand this stub into a full design spec following the structure of `docs/superpowers/specs/2026-05-04-fincli-only-refactor-design.md` (Summary / Requirements / Architecture / Tasks / Verification / Acceptance).
