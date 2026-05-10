> **Shipped:** 2026-05-09. The history-path-config refactor landed in this commit. The "Open decisions" section below is preserved as-is for historical context but is no longer pending — see the commit message and `docs/FEEDBACK-LOG.md` for the resolutions.

---

# History Path via Config — Refactor Spec (Stub)

**Status:** STUB — design deferred until the user is ready to action this work.
**Parent:** `docs/superpowers/specs/2026-05-04-fincli-only-refactor-design.md` (v1.1, §6.6)
**Date opened:** 2026-05-04

---

## Goal

Move the `--history` filter-cache path out of `core/configuration/configurator.py`'s hardcoded module-name string into a `Config`-driven setting. Today the path is computed via `os.path.join(os.path.realpath('fincli'), 'local_history', 'filter_history.json')` — a literal that the 2026-05-04 single-mode reduction swapped from `'fundainsight'` to `'fincli'` (Q4 = Option A in the brainstorm). The literal swap unblocked the deletion of `fundainsight/`, but the cleaner fix is to express the path as a Pydantic field on `Config` so it can be overridden per environment without editing source.

## Affected files

- `core/configuration/configurator.py` — replace the `os.path.realpath('fincli')` call with a read of `config.history_dir` (or whatever the new field is named).
- `config/config.py` — add a new field, e.g. `history_dir: Path = Path("fincli/local_history")`, with appropriate Pydantic validation.
- `core/configuration/config_base.py` — if the new field belongs at the `SystemSettings` level rather than on `Config`, lift it there instead.
- `CLAUDE.md` "Known Issues / Tech Debt" — strike the hard-coded-history-path entry once this spec is actioned.
- `CONTRACTS.md` §4 — document the new `Config` field.
- `docs/MODULE_REFERENCE.md` `core/` section — update the description of `configurator.build_config` to reflect the new path-resolution mechanism.
- `tests/domain/test_configurator_history.py` (Phase 2) — add round-trip tests that prove the path can be overridden via the new field.

## Open decisions deferred to the user

1. **Field name.** Candidates: `history_dir`, `history_path`, `filter_history_dir`. Pick one consistent with existing field naming in `Config`.
2. **Field type.** `pathlib.Path` is the obvious choice. Confirm that Pydantic v2's `Path` validation behaves correctly when the path is supplied as a string from JSON history.
3. **Default.** Should the default be `Path("fincli/local_history")` (relative to CWD, matches today's behavior) or an absolute path resolved against the project root? The first is more portable; the second avoids surprises when the user runs the CLI from a different directory.
4. **Migration for existing users.** The 2026-05-04 reduction was the first move from `fundainsight/local_history/` to `fincli/local_history/`. Anyone with a stale `fundainsight/local_history/filter_history.json` on disk has lost their cache (the directory was deleted with `fundainsight/`). When this spec is actioned, decide whether to add a one-time migration helper that reads the old path if it still exists. Likely answer: no — the directory was already removed from disk in Commit 3 of the 2026-05-04 refactor, so the migration window has passed.
5. **Whether to surface `--history-dir` as a CLI flag.** Currently the path is implicit. Adding an explicit `--history-dir` Click option is a downstream UX decision that may or may not belong in the same spec.

## Non-goals

- Restoring the `fundainsight/local_history/` codepath. The fundainsight package is gone.
- Changing the JSON schema of `filter_history.json`. Schema is untouched; only the directory containing it moves out of source.

## Next step

When the user is ready to action this work, expand this stub into a full design spec following the structure of `docs/superpowers/specs/2026-05-04-fincli-only-refactor-design.md` (Summary / Requirements / Architecture / Tasks / Verification / Acceptance). Coordinate with `docs/refactoring/archive/cli-entry-point-spec.md` (shipped 2026-05-06) if both ship close together — the two share `pyproject.toml` and `Config` surfaces.
