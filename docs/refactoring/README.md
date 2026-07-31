# Refactoring Work

Cross-cutting changes use three lifecycle directories:

- `spec/` — approved design and acceptance criteria.
- `implementations/` — executable implementation plans and validation evidence.
- `archive/` — shipped or intentionally retired historical material.

Name new specs `<topic>-spec.md` and plans `<topic>-plan.md`. Move terminal work
to `archive/` only after HUMAN acceptance and integration.

`docs/superpowers/` is retained as a historical feature-design archive; new
cross-cutting refactors belong here.
