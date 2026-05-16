"""End-to-end Ticker / Symbol carve-out tests (Pillar 4 — spec §5.6 + §7.7).

Pins the Pillar-4 ``--output -`` carve-out for the ``Ticker`` column:

  * ``--output -`` -> ``Ticker`` is the raw symbol (no ``=HYPERLINK`` wrap).
  * ``--output PATH`` -> ``Ticker`` keeps the Excel ``=HYPERLINK(...)`` wrap.
  * ``Symbol`` is the raw symbol in *all* modes.
  * Column order is unchanged (regression against
    ``StockTableLocators.PD_TABLE_COLUMNS`` minus ``Link`` plus ``Symbol``).

These pin §7.7 bullets 1–4. CONTRACTS §3.1 (bullet 5) documents the
canonical-status of ``Symbol`` — that's a doc-only assertion, covered by
the doc sweep in this same task.
"""

from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from _fixtures_loader import finviz_happy_html
from click.testing import CliRunner

from fincli.app.cli import run_main
from fincli.stock_screening.locators.stock_table_locators import StockTableLocators

# Column order produced by ``build_data_frame``: locator order minus
# ``Link`` plus ``Symbol``. Pinned here so the regression assertion below
# fails loudly on any future reorder.
_EXPECTED_COLUMNS = [col for col in StockTableLocators.PD_TABLE_COLUMNS if col != "Link"] + [
    "Symbol"
]

_CANNED_HTML = finviz_happy_html()


def _parse_csv(text: str) -> tuple[list[str], list[list[str]]]:
    """Parse a CSV text blob into (header, data_rows)."""
    reader = csv.reader(StringIO(text))
    rows = list(reader)
    assert rows, "Expected at least the header row"
    return rows[0], rows[1:]


# ---------------------------------------------------------------------------
# `--output -` -> raw symbol in Ticker; Symbol still raw.
# ---------------------------------------------------------------------------


def test_stdout_streaming_ticker_column_has_raw_symbol() -> None:
    """`--output -` writes the raw symbol in ``Ticker`` (no =HYPERLINK wrap).

    Pins §7.7 bullet 2.
    """
    runner = CliRunner()
    with patch("fincli.app.main.fetch_page_sync", return_value=_CANNED_HTML):
        result = runner.invoke(
            run_main,
            ["--filter", "fa_pe=u20", "--output", "-"],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, f"stderr: {result.stderr}"

    header, data_rows = _parse_csv(result.stdout)
    assert data_rows, "Expected at least one data row from the canned HTML"

    ticker_idx = header.index("Ticker")
    symbol_idx = header.index("Symbol")
    # Raw symbol everywhere — no formula wrap on stdout.
    assert data_rows[0][ticker_idx] == "AAPL", (
        f"Expected raw symbol 'AAPL' in Ticker column on stdout; got {data_rows[0][ticker_idx]!r}"
    )
    # The =HYPERLINK formula MUST NOT appear in stdout under --output -.
    assert "=HYPERLINK" not in result.stdout, (
        "Excel formula leaked into stdout — pipeline consumers using "
        "pandas.read_csv would be poisoned"
    )
    # Symbol column is also the raw symbol — always.
    assert data_rows[0][symbol_idx] == "AAPL"


# ---------------------------------------------------------------------------
# `--output PATH` -> =HYPERLINK formula in Ticker; Symbol still raw.
# ---------------------------------------------------------------------------


def test_file_output_ticker_column_has_hyperlink_formula(tmp_path: Path) -> None:
    """`--output PATH` keeps the Excel ``=HYPERLINK(...)`` wrap.

    Pins §7.7 bullet 1.
    """
    target = tmp_path / "out.csv"
    runner = CliRunner()
    with patch("fincli.app.main.fetch_page_sync", return_value=_CANNED_HTML):
        result = runner.invoke(
            run_main,
            ["--filter", "fa_pe=u20", "--output", str(target)],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, f"stderr: {result.stderr}"
    assert target.exists()

    text = target.read_text(encoding="utf-8")
    header, data_rows = _parse_csv(text)
    assert data_rows, "Expected at least one data row"

    ticker_idx = header.index("Ticker")
    symbol_idx = header.index("Symbol")
    # `=HYPERLINK("https://finviz.com/quote.ashx?t=AAPL", "AAPL")` is the
    # full formula shape. csv reader strips the wrapping quote pair so
    # the cell still starts with `=HYPERLINK`.
    assert data_rows[0][ticker_idx].startswith("=HYPERLINK("), (
        f"Expected =HYPERLINK formula in Ticker for file output; got {data_rows[0][ticker_idx]!r}"
    )
    assert "AAPL" in data_rows[0][ticker_idx]
    # Symbol stays raw regardless.
    assert data_rows[0][symbol_idx] == "AAPL"


# ---------------------------------------------------------------------------
# Column order regression — same shape in both modes; Symbol last.
# ---------------------------------------------------------------------------


def test_stdout_streaming_column_order_matches_locator_plus_symbol() -> None:
    """Pins §7.7 bullet 4 — column order is `LOCATORS - Link + Symbol`."""
    runner = CliRunner()
    with patch("fincli.app.main.fetch_page_sync", return_value=_CANNED_HTML):
        result = runner.invoke(
            run_main,
            ["--filter", "fa_pe=u20", "--output", "-"],
            catch_exceptions=False,
        )

    assert result.exit_code == 0
    header, _ = _parse_csv(result.stdout)
    assert header == _EXPECTED_COLUMNS, (
        f"Column-order regression on stdout streaming: expected {_EXPECTED_COLUMNS!r}, "
        f"got {header!r}"
    )


def test_file_output_column_order_matches_locator_plus_symbol(tmp_path: Path) -> None:
    """Pins §7.7 bullet 4 — same column order for file destinations."""
    target = tmp_path / "out.csv"
    runner = CliRunner()
    with patch("fincli.app.main.fetch_page_sync", return_value=_CANNED_HTML):
        result = runner.invoke(
            run_main,
            ["--filter", "fa_pe=u20", "--output", str(target)],
            catch_exceptions=False,
        )

    assert result.exit_code == 0
    text = target.read_text(encoding="utf-8")
    header, _ = _parse_csv(text)
    assert header == _EXPECTED_COLUMNS, (
        f"Column-order regression on file output: expected {_EXPECTED_COLUMNS!r}, got {header!r}"
    )


# ---------------------------------------------------------------------------
# Symbol-column raw-symbol guarantee in both modes (parametrized).
# ---------------------------------------------------------------------------


def test_symbol_column_raw_in_stdout_streaming() -> None:
    """Pins §7.7 bullet 3 — `Symbol` is raw on stdout streaming."""
    runner = CliRunner()
    with patch("fincli.app.main.fetch_page_sync", return_value=_CANNED_HTML):
        result = runner.invoke(
            run_main,
            ["--filter", "fa_pe=u20", "--output", "-"],
            catch_exceptions=False,
        )
    header, data_rows = _parse_csv(result.stdout)
    symbol_idx = header.index("Symbol")
    assert data_rows[0][symbol_idx] == "AAPL"


def test_symbol_column_raw_in_file_output(tmp_path: Path) -> None:
    """Pins §7.7 bullet 3 — `Symbol` is raw on file output."""
    target = tmp_path / "out.csv"
    runner = CliRunner()
    with patch("fincli.app.main.fetch_page_sync", return_value=_CANNED_HTML):
        result = runner.invoke(
            run_main,
            ["--filter", "fa_pe=u20", "--output", str(target)],
            catch_exceptions=False,
        )
    assert result.exit_code == 0, f"stderr: {result.stderr}"
    text = target.read_text(encoding="utf-8")
    header, data_rows = _parse_csv(text)
    symbol_idx = header.index("Symbol")
    assert data_rows[0][symbol_idx] == "AAPL"
