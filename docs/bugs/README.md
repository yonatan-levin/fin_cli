# Bug Tracker

This folder is a flat list of bug specs. Each bug gets one Markdown file.

## Naming

`BUG-NNN-slug.md` (e.g., `BUG-001-equity-calc-not-int-truthy.md`).

## Template

`````markdown
# BUG-NNN — Title

**Date opened:** YYYY-MM-DD
**Status:** open | fixed | wontfix
**Severity:** critical | high | medium | low

## Symptom

What the user sees / what's wrong.

## Repro

Exact steps. Include CLI invocation, input data, expected vs actual.

## Root cause

Once known.

## Fix

Once known. Reference commit/PR.

## Regression test

Once written. Reference test file.
`````

## Lifecycle

Open in `docs/bugs/`. When fixed and the regression test lands, move to `docs/bugs/archive/`.
