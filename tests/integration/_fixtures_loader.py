"""Canned Finviz HTML fixture loaders for the integration test suite.

The integration tests mock ``fincli.utils.web_scraper.fetch_page_sync`` to
return one of these fixtures so the suite never makes a real HTTP call to
Finviz. Centralising the loaders here gives the three integration test
files (``test_pipeline_streaming.py``, ``test_pipeline_summary.py``,
``test_zero_row_success.py``) one source of truth — REVIEWER raised the
duplicated inline ``_CANNED_FINVIZ_HTML`` constants as a Task-5 follow-up.

The HTML payloads themselves live as plain files under
``tests/integration/fixtures/`` so they read like Finviz HTML pages in a
diff and stay grep-friendly. Each helper here returns the file contents
as ``bytes`` (matching ``fetch_page_sync``'s return type) so callers can
pass the result directly to ``patch(..., return_value=...)``.

Module name leads with an underscore so pytest does not try to collect
it as a test module. No ``__init__.py`` lives under ``tests/integration/``
or ``tests/integration/fixtures/`` by design (briefing's "deliberate
decisions": no package markers anywhere under ``tests/``).
"""

from __future__ import annotations

from pathlib import Path

_FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _read_fixture(name: str) -> bytes:
    """Read a fixture HTML file as bytes.

    Args:
        name: File name under ``tests/integration/fixtures/``, e.g.
            ``"finviz_happy.html"``.

    Returns:
        Raw bytes matching the shape ``fetch_page_sync`` returns.
    """
    return (_FIXTURE_DIR / name).read_bytes()


def finviz_happy_html() -> bytes:
    """One-row screener result with a valid ticker link.

    Matches the column shape in ``StockTableLocators.PD_TABLE_COLUMNS``
    so the parser produces one valid row downstream (page_count = 0,
    so ``fetch_urls`` invokes the mock once).
    """
    return _read_fixture("finviz_happy.html")


def finviz_empty_html() -> bytes:
    """Screener page with the table present but empty ``<tbody>``.

    Drives the zero-row success branch in ``run_stock_screener``: the
    parser returns zero rows, the orchestrator writes a header-only CSV,
    and the process exits 0.
    """
    return _read_fixture("finviz_empty.html")


def finviz_no_table_html() -> bytes:
    """Screener page missing the table element entirely.

    Selector returns an empty list. In isolation this routes through the
    same zero-row branch as ``finviz_empty_html``; the malformed-row
    fixture is the one that actually triggers the DATA classifier.
    """
    return _read_fixture("finviz_no_table.html")


def finviz_malformed_row_html() -> bytes:
    """Screener page whose ``<td>`` cells are missing the link anchor.

    ``StockTableScreenerParser.ticker_link`` calls
    ``cells[1].find('a').get('href')``; with no ``<a>`` inside the cell,
    ``find`` returns ``None`` and ``.get('href')`` raises
    ``AttributeError`` — the DATA-class exception classified as exit 4.
    """
    return _read_fixture("finviz_malformed_row.html")
