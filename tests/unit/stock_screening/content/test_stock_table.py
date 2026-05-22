"""Unit tests for ``StockTableScreeningContent.page_count``.

Pins the three pagination shapes Finviz emits in the wild:

  * Zero ``screener-pages`` elements -> ``0`` (no pagination block).
  * Exactly one ``screener-pages`` element -> the integer of that single
    element (single-page result; selected, no ``is-next`` arrow).
  * Two or more ``screener-pages`` elements -> the integer of ``[-2]``
    (numeric links followed by the trailing ``is-next`` arrow).

The middle case is the regression: live single-page results crashed the
old ``content[-2]`` indexing with ``IndexError``. Inline BeautifulSoup
constructs avoid coupling these tests to any HTML fixture file.
"""

from __future__ import annotations

import pytest

from fincli.stock_screening.content.stock_table import StockTableScreeningContent


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        # No pagination block at all — empty Finviz result page shape.
        ("<html><body><table></table></body></html>", 0),
        # Single-page result — one selected element, no is-next arrow.
        (
            '<html><body><a class="screener-pages is-selected">1</a></body></html>',
            1,
        ),
        # Multi-page result — numeric links + trailing is-next arrow at [-1],
        # so the last numeric page count lives at [-2].
        (
            "<html><body>"
            '<a class="screener-pages is-selected">1</a>'
            '<a class="screener-pages">2</a>'
            '<a class="screener-pages">3</a>'
            '<a class="screener-pages is-next">next</a>'
            "</body></html>",
            3,
        ),
    ],
    ids=["no_pagination", "single_page", "multi_page"],
)
def test_page_count_handles_all_pagination_shapes(html: str, expected: int) -> None:
    content = StockTableScreeningContent(html)
    assert content.page_count == expected
