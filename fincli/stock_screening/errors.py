"""Screener HTML layout-contract exceptions."""

from __future__ import annotations


class ScreenerLayoutError(Exception):
    """Finviz screener HTML does not match the expected layout contract.

    Raised by the stock-screening parsers/content extractors when the HTML
    shape drifts in a way that would otherwise silently corrupt or hide
    data: a missing screener table with no legitimate empty-result marker,
    or a ticker cell whose visible text disagrees with its link href (the
    GitHub issue #14 duplicated-first-letter bug on Finviz's redesigned
    layout, e.g. "KTOS" rendering as "KKTOS"). Classified as ``DATA``
    (exit 4 / HTTP 502 ``parsing``) by ``fincli.app.exit_codes.classify``
    — see that module for the full classifier contract.
    """
