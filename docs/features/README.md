# Feature Specs

Feature-restoration / feature-addition specs land here. One file per feature. Naming: `<topic>-spec.md` (e.g., `scrape-link-restoration-spec.md`).

This is distinct from `docs/refactoring/` (cross-cutting refactor specs that change existing surfaces with no behavior expansion) and `docs/superpowers/specs/` (chronological per-cycle design specs by date).

## Lifecycle

Open here. When the feature ships, move to `docs/features/archive/` and prepend a Shipped banner above the original heading:

```markdown
> **Shipped:** YYYY-MM-DD. <one-sentence description of what landed.>

---
```

Banner format matches the precedent in `docs/refactoring/archive/` and `docs/reviewer/archive/`. The original content is preserved verbatim below the banner — the archive is a frozen historical record.

## Shipped entries

| Spec | Shipped | Commit range | One-line summary |
|---|---|---|---|
| `docs/features/archive/scrape-link-restoration-spec.md` | 2026-05-13 | `930f05d` | Restored the `--scrape-link` CLI option lost during the May-2026 single-mode refactor. |
| `docs/features/archive/pipeline-mode-spec.md` | 2026-05-16 | `f775b7e..HEAD` | Pipeline mode umbrella — four pillars (structured filter input, deterministic output destination, stream discipline + JSON summary, differentiated exit codes 0/1/2/3/4) + two adjacent fixes (`convert_market_cap_to_numeric` nullable Float64, `Symbol` canonical + `--output -` Ticker carve-out). `fincli` is now consumable by another program. See `docs/FEEDBACK-LOG.md` 2026-05-16 entry for decisions captured. |

## Active entries

None at the moment.
