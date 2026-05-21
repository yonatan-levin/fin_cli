"""Tests for `fincli.resource.params._label_format.attr_to_label`.

Pins the mechanical label-derivation algorithm specified in
`docs/features/archive/list-filters-spec.md` §5.3 and acceptance §7.5.

These tests guard the contract that downstream JSON consumers (and the
upcoming `--list-filters --json` CLI flag) rely on:

  - Known acronyms (PE, ROA, EPS, RSI, ...) round-trip uppercase.
  - Connector words (to, and, of, ...) lowercase when not in the first
    position.
  - Everything else is title-cased per token.

The acronym preservation set + connector lowercasing set are themselves
spec-frozen — they belong to the public label contract even though the
module name is private. If a future spec adds new acronyms, the new test
cases should land alongside the constant change.
"""

from __future__ import annotations

import pytest

from fincli.resource.params._label_format import attr_to_label

# ---------------------------------------------------------------------------
# Spec §7.5 acceptance bullets + spec §5.3 docstring examples.
#
# Each row is one parametrized case so a regression fingerprint points
# at the exact attribute that drifted, not "label derivation broken".
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "attr, expected",
    [
        # --- Spec §7.5 acceptance bullets ---------------------------------
        # §7.5 bullet 1: single-token acronym round-trips uppercase.
        ("PE", "PE"),
        # §7.5 bullet 2: leading non-acronym title-cases; trailing acronym preserved.
        ("FORWARD_PE", "Forward PE"),
        # §7.5 bullet 3: connector word "TO" lowercased mid-attr.
        ("PRICE_TO_CASH", "Price to Cash"),
        # §7.5 bullet 4: multi-acronym + numeric token + plain words.
        ("EPS_GROWTH_NEXT_5_YEARS", "EPS Growth Next 5 Years"),
        # §7.5 bullet 5: acronym at start, connector mid, acronym at end (mixed-case input).
        ("LT_Debt_TO_Equity", "LT Debt to Equity"),
        # §7.5 bullet 6: all-lowercase-after-first connector handling on a long attr.
        (
            "Twenty_Day_Simple_Moving_Average",
            "Twenty Day Simple Moving Average",
        ),
        # §7.5 bullet 7: returns acronyms (three rapid-fire cases).
        ("ROA", "ROA"),
        ("ROE", "ROE"),
        ("ROI", "ROI"),
    ],
)
def test_attr_to_label_matches_spec_examples(attr: str, expected: str) -> None:
    """Every §7.5 acceptance bullet (and the §5.3 docstring examples that
    overlap with them) produces the documented label."""
    assert attr_to_label(attr) == expected


# ---------------------------------------------------------------------------
# Algorithmic edge cases (not directly listed in §7.5 but pinned by the
# §5.3 spec text: acronym preservation, connector-not-first, title-case
# fallback). These guard against future "improvements" that subtly shift
# behavior — e.g., lowercasing the first connector token or coercing
# multi-token output through a single `.title()` call.
# ---------------------------------------------------------------------------


def test_connector_word_at_position_zero_is_capitalized_not_lowercased() -> None:
    """A connector ("to", "of", "and", ...) appearing FIRST must title-case,
    not lowercase. The algorithm only lowercases connectors when ``i > 0``.

    Pins the §5.3 rule against a refactor that accidentally drops the
    position guard. Without the guard, an attr like ``"To_Date_Profit"``
    would render as ``"to Date Profit"`` (broken dropdown header).
    """
    assert attr_to_label("To_Date_Profit") == "To Date Profit"


def test_unknown_acronym_is_title_cased_not_preserved() -> None:
    """``QTR`` is intentionally NOT in the acronym set (see spec §5.3
    "Known cosmetic limitations" + spec §14 OQ5). The algorithm
    title-cases it like any other unknown token.

    Pins the documented limitation so a "fix" to the acronym set is a
    conscious choice (test update + spec amendment), not a silent drift.
    """
    assert attr_to_label("EPS_GROWTH_QTR_OVER_QTR") == "EPS Growth Qtr Over Qtr"


def test_single_unknown_token_title_cases() -> None:
    """A single non-acronym, non-connector token title-cases.

    Anchors the simplest branch of the algorithm; without this, a
    regression that always uppercases or always lowercases single-token
    attrs would slip through the §7.5 cases (all of which are either
    multi-token or known acronyms).
    """
    assert attr_to_label("Sector") == "Sector"
