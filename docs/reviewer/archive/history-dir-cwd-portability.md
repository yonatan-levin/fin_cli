> **Shipped:** 2026-05-10. The CWD-portability follow-up shipped in this commit via the `platformdirs`-resolved default + `HISTORY_DIR` env-var override (directions #2 + #3 from the "Possible directions" list below). The other proposed directions (#1, #4, #5) were rejected as documented in `docs/FEEDBACK-LOG.md`.

---

# fincli --history: portable cache directory

**Date opened:** 2026-05-09
**Status:** open
**Severity:** low — latent UX limitation, no current user impact

## Problem

After the 2026-05-09 history-path-config refactor (`docs/refactoring/archive/history-path-config-spec.md`), the `--history` cache directory is exposed as a `Config.history_dir` field, but the default is still a CWD-relative path (`Path("fincli/local_history")`). Running `fincli --history` from any CWD that does not contain a `fincli/` subdirectory fails with `FileNotFoundError`. The refactor exposed this limitation as configurable but deliberately did not fix it — the scope was pure plumbing.

## Why it didn't block

- The current user invokes `fincli` from the repo root.
- `--history` is a power-user convenience; first-time users go through the interactive flow.
- Fixing requires a UX decision (which portable-path strategy?), which warrants its own scope.

## Possible directions

1. **`__file__`-relative resolution** — `Path(fincli.__file__).parent / "local_history"`. Works anywhere `fincli` is importable, but writes inside the package (read-only on non-editable installs).
2. **`platformdirs` / XDG convention** — `~/.local/share/fincli/` (Linux), `~/Library/Application Support/fincli/` (macOS), `%LOCALAPPDATA%\fincli\` (Windows). Standard, writable, survives reinstalls; adds a runtime dep.
3. **`FINCLI_HISTORY_DIR` env var** — read in `ConfigBuilder.build_config_from_env`, extending the existing `USE_HISTORY` env-var pattern. No new dep; scriptable.
4. **`--history-dir` CLI flag** — discoverable via `--help`; adds CLI surface.
5. **Layered defaults** — #3 override > #2 default > optional #4 flag.

Recommended starting point: #3 (env-var override) is the smallest scope that meaningfully helps users who set it; layer in #2 if/when the friction warrants.

## Acceptance for closing

- Running `fincli --history` from any CWD produces either: (a) the cached filter set from a default platform-appropriate location, or (b) a clear error message explaining how to configure the path.
- Strategy decision documented in a new spec under `docs/refactoring/`.
- `CONTRACTS.md` §4.1 updated to document the resolution.

## References

- Shipped 2026-05-09: `docs/refactoring/archive/history-path-config-spec.md` — the refactor that exposed this.
- Shipped 2026-05-06: `docs/refactoring/archive/cli-entry-point-spec.md` — the bare `fincli` command that made invocation from any CWD a realistic scenario.
