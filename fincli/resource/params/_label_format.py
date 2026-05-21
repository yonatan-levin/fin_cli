"""Mechanical label derivation for Finviz filter keys.

The params files store the human-readable VALUE labels alongside the
value codes (e.g., {"u5": "Under 5"}) but provide no human label for
the KEY itself — only the Python attribute name (e.g., `PE`,
`FORWARD_PE`, `EPS_GROWTH_NEXT_5_YEARS`). This module derives a
display label from that attribute name with three rules:

  1. Preserve known acronyms (PE, ROA, EPS, RSI, ...) as-is.
  2. Lowercase common connector words (to, and, of, ...) when not first.
  3. Title-case everything else.

Derived labels are a starting point only — consumers can override
locally for UX polish (e.g., "P/E" with a slash). Avoiding the
augmentation of params files keeps the existing two-element-list
contract stable per CONTRACTS §2.
"""

from __future__ import annotations

_ACRONYMS: frozenset[str] = frozenset(
    {
        # Fundamental ratios
        "PE",
        "PEG",
        "PB",
        "PS",
        "PC",
        "PFCF",
        # Returns
        "ROA",
        "ROE",
        "ROI",
        # Earnings / averages / volatility
        "EPS",
        "SMA",
        "ATR",
        "RSI",
        # Misc
        "LT",
        "IPO",
        "REIT",
    }
)

_CONNECTORS: frozenset[str] = frozenset({"to", "and", "or", "of", "in", "at", "by", "for", "with"})


def attr_to_label(attr: str) -> str:
    """Mechanical capitalization of a Python attribute name to display label.

    Args:
        attr: Python attribute name from a params class (e.g., ``"FORWARD_PE"``).

    Returns:
        A display label suitable for a dropdown title (e.g., ``"Forward PE"``).

    Examples:
        >>> attr_to_label("PE")
        'PE'
        >>> attr_to_label("FORWARD_PE")
        'Forward PE'
        >>> attr_to_label("PRICE_TO_CASH")
        'Price to Cash'
        >>> attr_to_label("EPS_GROWTH_NEXT_5_YEARS")
        'EPS Growth Next 5 Years'
        >>> attr_to_label("LT_Debt_TO_Equity")
        'LT Debt to Equity'
        >>> attr_to_label("Twenty_Day_Simple_Moving_Average")
        'Twenty Day Simple Moving Average'
    """
    parts = attr.split("_")
    out: list[str] = []
    for i, p in enumerate(parts):
        if p.upper() in _ACRONYMS:
            out.append(p.upper())
        elif i > 0 and p.lower() in _CONNECTORS:
            out.append(p.lower())
        else:
            out.append(p.capitalize())
    return " ".join(out)
