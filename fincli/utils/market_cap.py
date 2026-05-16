"""Coerce Finviz `Market Cap` cells into a numeric value (or `pandas.NA`).

Carved out of `fincli.app.main` so the parser is directly testable without
importing the orchestrator. Contract is pinned in
`docs/features/archive/pipeline-mode-spec.md` §5.5 and `CONTRACTS.md` §3.1.

Replaces the legacy implementation that lived at `fincli/app/main.py:33-46`,
which had three latent defects: (1) an unassigned `.replace("'", "")` no-op,
(2) string `"N/A"` returns that polluted the column dtype, (3) a `float("-")`
crash on lone-dash cells.
"""

from __future__ import annotations

import pandas as pd

from logger.logger import logger

# Suffix multiplier for SI-style abbreviations Finviz emits in the Market Cap
# column. Case-insensitive lookup; the value is always upper-cased before the
# table is consulted.
_SUFFIX_MULTIPLIERS: dict[str, float] = {
    "T": 1_000_000_000_000.0,
    "B": 1_000_000_000.0,
    "M": 1_000_000.0,
    "K": 1_000.0,
}

# Tokens that Finviz (and the screener pipeline) use to mean "no value here".
# All compared case-insensitively after stripping. An empty string after noise
# stripping is also treated as missing.
_MISSING_TOKENS: frozenset[str] = frozenset({"", "-", "_", "N/A"})

# Noise characters that may appear in a Market Cap cell but are not part of the
# numeric value. Stripped before suffix detection so e.g. `" $1,200'000.00B "`
# parses cleanly.
_NOISE_CHARS: tuple[str, ...] = ("$", ",", "'")


def convert_market_cap_to_numeric(value: str | None) -> float | pd._libs.missing.NAType:
    """Convert a Finviz `Market Cap` cell into a `float` or `pandas.NA`.

    See `docs/features/archive/pipeline-mode-spec.md` §5.5 for the full input/output
    table. Summary:

    Args:
        value: The raw cell text, e.g. ``"1.2T"``, ``"450M"``, ``" $1,234 "``,
            ``"-"``, ``"N/A"``, ``None``. Suffix matching is case-insensitive.

    Returns:
        ``float`` for parseable numerics (suffix-scaled or raw). ``pandas.NA``
        for the missing-value tokens, for ``None``, and for any unparseable
        input. Unparseable inputs additionally emit a warning through the
        Singleton logger so the cell is not silently dropped.
    """
    # Treat None and any non-string input the same as a missing cell. Pandas
    # passes through stringly-typed columns, but defensive handling here keeps
    # the helper safe for ad-hoc / test usage.
    if value is None:
        return pd.NA
    if not isinstance(value, str):
        return pd.NA

    # Strip surrounding whitespace first so the missing-token comparison sees
    # a clean string. The `_NOISE_CHARS` pass below handles embedded noise.
    cleaned = value.strip()

    # Missing-token check happens BEFORE noise stripping so a literal "-" cell
    # is recognized; otherwise it would survive as "" and still match, but
    # checking up front keeps the intent explicit and short-circuits early.
    if cleaned.upper() in _MISSING_TOKENS:
        return pd.NA

    # Strip permitted noise characters: leading currency markers, comma
    # thousands separators, apostrophe thousands separators (some locales).
    for ch in _NOISE_CHARS:
        cleaned = cleaned.replace(ch, "")

    # If noise stripping emptied the cell, treat as missing (e.g. a cell that
    # was literally "$,").
    if cleaned == "":
        return pd.NA

    # Suffix detection: the last character drives the multiplier when it is a
    # known SI abbreviation. Comparison is upper-cased so "1.2t" works too.
    suffix = cleaned[-1].upper()
    if suffix in _SUFFIX_MULTIPLIERS:
        numeric_part = cleaned[:-1]
        try:
            return float(numeric_part) * _SUFFIX_MULTIPLIERS[suffix]
        except ValueError:
            logger.warn(
                f"Could not parse market cap value: {value!r}",
                title="Market Cap parse",
            )
            return pd.NA

    # No suffix -> attempt a plain numeric coerce. Anything that fails here
    # (e.g. "12X", "foo") is logged and reported as missing rather than
    # crashing the whole pipeline.
    try:
        return float(cleaned)
    except ValueError:
        logger.warn(
            f"Could not parse market cap value: {value!r}",
            title="Market Cap parse",
        )
        return pd.NA
