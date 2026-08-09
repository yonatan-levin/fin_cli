# Pending Work Handoff Docs

Session handoff docs land here. One file per handoff event, dated.

## Naming

`YYYY-MM-DD-session-handoff.md` for general session-boundary handoffs, or `YYYY-MM-DD-<slug>-handoff.md` for topic-specific ones.

## Purpose

When a working session ends with substantive context that the next session (potentially a new Claude instance or a future human) needs to resume cleanly, write a handoff doc here. The doc should be readable end-to-end and provide everything needed to pick up productively without re-reading the entire prior conversation.

Typical sections:

1. **Branch / repo state** — current HEAD, what's clean, what's uncommitted
2. **Recently shipped** — last few commits, why they matter, links to specs
3. **Active agenda** — queued items in priority order with effort estimates
4. **Conventions and patterns established** — what worked this sprint, what to preserve
5. **Auto-memory pointers** — where session-spanning context lives
6. **How to resume immediately** — first-N-actions for the next session
7. **Open decisions deferred to the user** — questions surfaced but not closed

## When to write one

- End of a multi-cycle sprint where context window is hot
- Before a long pause (days off, switching repos)
- When transferring work between sessions / users / agents
- When the user explicitly asks for one

## Lifecycle

Open here. When the next session has picked up and the handoff is no longer the "current" context (i.e., the queued agenda items have been actioned or re-scoped), move the file to `docs/pendingwork/archive/` for historical reference.

Don't delete — these accumulate as a chronological record of session boundaries. Future-Claude reading the archive learns the project's working rhythm: what threads were in flight, what conventions evolved, what decisions were made between cycles.
