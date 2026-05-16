"""Contract tests for `fincli.utils.market_cap.convert_market_cap_to_numeric`.

Pinned to the input/output table in `docs/features/archive/pipeline-mode-spec.md` §5.5
and the dtype assertions in `CONTRACTS.md` §3.1.

Covers:
  - SI suffix scaling (T/B/M/K), case-insensitive
  - Noise stripping (`$`, `,`, `'`, leading/trailing whitespace)
  - Missing-value tokens (`-`, `_`, `""`, `None`, `"N/A"` / `"n/a"`)
  - Raw numeric strings
  - Garbage input (logged as warning, returns NA)
  - Round-trip through `pd.array(..., dtype="Float64")` -> CSV -> read_csv,
    asserting empty cells (not "nan" / "<NA>" / "0.0") and a nullable float
    dtype on read-back.
"""

from __future__ import annotations

import io
from typing import Any

import pandas as pd
import pytest

from fincli.utils.market_cap import convert_market_cap_to_numeric

# ---------------------------------------------------------------------------
# Suffix-scaling happy paths.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1.2T", 1.2e12),
        ("3.5B", 3.5e9),
        ("450M", 450e6),
        ("5K", 5e3),
        # Lower-case suffix must work too (case-insensitive).
        ("1.2t", 1.2e12),
        ("3.5b", 3.5e9),
        ("450m", 450e6),
        ("5k", 5e3),
        # Integer mantissa (no decimal point).
        ("2B", 2e9),
    ],
)
def test_suffix_scaling(raw: str, expected: float) -> None:
    """SI suffixes scale the mantissa per the §5.5 multiplier table."""
    result = convert_market_cap_to_numeric(raw)
    assert isinstance(result, float)
    assert result == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Noise stripping — leading $, embedded commas, ' thousands separator, ws.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("$1.2B", 1.2e9),
        ("1,234M", 1234e6),
        # Apostrophe thousands separator (some EU locales use this form).
        ("1'234M", 1234e6),
        # Leading + trailing whitespace.
        ("  3.5B  ", 3.5e9),
        # Combined: currency + commas + whitespace + suffix.
        ("  $1,200B  ", 1200e9),
    ],
)
def test_noise_stripping(raw: str, expected: float) -> None:
    """Permitted noise is stripped before suffix detection (§5.5)."""
    result = convert_market_cap_to_numeric(raw)
    assert isinstance(result, float)
    assert result == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Missing-value tokens -> pandas.NA.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "-",
        "_",
        "",
        "N/A",
        "n/a",
        "N/a",
    ],
)
def test_missing_tokens_return_na(raw: str) -> None:
    """All §5.5 missing-value tokens normalize to `pandas.NA`."""
    result = convert_market_cap_to_numeric(raw)
    assert result is pd.NA


def test_none_input_returns_na() -> None:
    """`None` input -> `pandas.NA` (defensive — pandas string columns shouldn't
    pass None, but the helper is also called directly in tests / ad-hoc use)."""
    result = convert_market_cap_to_numeric(None)
    assert result is pd.NA


def test_whitespace_only_returns_na() -> None:
    """A cell that contains only whitespace strips to `""` and is missing."""
    result = convert_market_cap_to_numeric("   ")
    assert result is pd.NA


# ---------------------------------------------------------------------------
# Raw numeric strings (no suffix).
# ---------------------------------------------------------------------------


def test_plain_numeric_string() -> None:
    """A plain numeric string parses directly to `float` (§5.5)."""
    result = convert_market_cap_to_numeric("1234567890")
    assert isinstance(result, float)
    assert result == 1234567890.0


def test_plain_numeric_with_noise() -> None:
    """Noise stripping applies to plain numerics too."""
    result = convert_market_cap_to_numeric("$1,234,567")
    assert isinstance(result, float)
    assert result == 1234567.0


# ---------------------------------------------------------------------------
# Garbage input -> NA + warning logged.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "foo",
        "12X",  # Unknown suffix
        "abc.def",
        "1.2.3B",  # Malformed mantissa with valid suffix
    ],
)
def test_garbage_input_returns_na_and_warns(raw: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Unparseable input emits a warning through the singleton logger and
    returns `pandas.NA` rather than crashing the pipeline."""
    captured: list[tuple[str, str]] = []

    def fake_warn(message: str, title: str = "", title_color: str = "") -> None:
        captured.append((message, title))

    monkeypatch.setattr("fincli.utils.market_cap.logger.warn", fake_warn)

    result = convert_market_cap_to_numeric(raw)
    assert result is pd.NA
    assert len(captured) == 1, f"Expected exactly one warning for {raw!r}, got {len(captured)}"
    message, _title = captured[0]
    assert repr(raw) in message, f"Warning message should include repr of input; got {message!r}"


# ---------------------------------------------------------------------------
# Type contract: signature accepts `str | None` and never raises ValueError.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        # Lone-dash that previously crashed the legacy implementation with
        # `float("-")` ValueError.
        "-",
        # Cells of the form `<noise>` only -> empty after stripping -> NA.
        "$",
        "$,",
    ],
)
def test_no_value_error_on_legacy_crash_inputs(raw: str) -> None:
    """Inputs that crashed the pre-fix implementation now return `pd.NA`."""
    # Should not raise.
    result = convert_market_cap_to_numeric(raw)
    assert result is pd.NA


# ---------------------------------------------------------------------------
# CSV round-trip — proves missing values render as empty cells, not "nan" /
# "<NA>" / "0.0", and that read_csv reports a nullable-float dtype.
# ---------------------------------------------------------------------------


def test_csv_roundtrip_renders_empty_cells_for_missing() -> None:
    """Build the column the same way `build_data_frame` does, write to CSV,
    read it back, and confirm:
      - Missing cells are empty (not 'nan', not '<NA>', not '0.0').
      - Numeric cells use plain decimal notation (no scientific notation).
      - The read-back dtype is a nullable float (per CONTRACTS §3.1).
    """
    raw_inputs: list[str | None] = ["1.2B", "-", "450M", "N/A", "5K", None, "12X"]

    # Mirror exactly what `build_data_frame` does so the test is faithful.
    arr = pd.array(
        [convert_market_cap_to_numeric(v) for v in raw_inputs],
        dtype="Float64",
    )
    df = pd.DataFrame({"Market Cap": arr})

    buf = io.StringIO()
    df.to_csv(buf, index=False)
    csv_text = buf.getvalue()

    # Forbidden literal renderings of the missing marker.
    assert "nan" not in csv_text.lower(), f"Found 'nan' in CSV output: {csv_text}"
    assert "<NA>" not in csv_text, f"Found '<NA>' in CSV output: {csv_text}"

    # Numeric cells must NOT use scientific notation. 1.2B = 1_200_000_000 -
    # well within the magnitude where pandas defaults to plain decimal.
    assert "e+" not in csv_text.lower(), f"Found scientific notation: {csv_text}"
    assert "e-" not in csv_text.lower(), f"Found scientific notation: {csv_text}"

    # Sanity-check expected values are present in plain-decimal form.
    assert "1200000000" in csv_text
    assert "450000000" in csv_text
    assert "5000" in csv_text

    # Read back with the nullable backend; the column must be a nullable float.
    read_back = pd.read_csv(io.StringIO(csv_text), dtype_backend="numpy_nullable")
    dtype: Any = read_back["Market Cap"].dtype
    # Pandas nullable float dtype is `Float64Dtype()`; its name attribute is
    # "Float64". Either check is acceptable per §7.6.
    assert pd.api.types.is_float_dtype(dtype), f"Expected nullable float, got {dtype!r}"
    assert dtype.name == "Float64", f"Expected Float64 dtype, got {dtype.name!r}"

    # The row count after read-back must match the input length, and the
    # missing inputs must have read as NA. raw_inputs has 4 NA-producing
    # entries: "-", "N/A", None, "12X" (the last one logs a warning and
    # returns NA per the §5.5 contract).
    assert len(read_back) == len(raw_inputs)
    assert read_back["Market Cap"].isna().sum() == 4
    # "1.2B", "450M", "5K" -> 3 numeric values survive the round-trip.
    assert (~read_back["Market Cap"].isna()).sum() == 3
