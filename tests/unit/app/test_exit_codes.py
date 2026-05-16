"""Unit tests for `fincli.app.exit_codes` (Pillar 4 classifier).

Pins the §5.4 mapping table from `docs/features/archive/pipeline-mode-spec.md`:

  * ``requests.exceptions.RequestException`` -> UPSTREAM (3)
  * ``IndexError`` / ``AttributeError`` / ``KeyError`` -> DATA (4)
  * Anything else -> INTERNAL (1)

Hardcoded integers are intentionally NOT used in the assertions: tests
import the named constants so a future renumbering touches one file.
"""

from __future__ import annotations

import pytest
import requests

from fincli.app import exit_codes

# ---------------------------------------------------------------------------
# Constant-value pinning. The exit codes are part of the stable CLI surface
# (CONTRACTS §1 + §7). Renumbering any of these breaks downstream pipelines
# that branch on the code; this test makes any silent change loud.
# ---------------------------------------------------------------------------


def test_success_constant_is_zero() -> None:
    assert exit_codes.SUCCESS == 0


def test_internal_constant_is_one() -> None:
    assert exit_codes.INTERNAL == 1


def test_usage_constant_is_two() -> None:
    """Pinned to 2 — matches Click's default for UsageError / BadParameter."""
    assert exit_codes.USAGE == 2


def test_upstream_constant_is_three() -> None:
    assert exit_codes.UPSTREAM == 3


def test_data_constant_is_four() -> None:
    assert exit_codes.DATA == 4


# ---------------------------------------------------------------------------
# `classify(exc)` — UPSTREAM family (requests.exceptions hierarchy).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "exc_instance",
    [
        requests.exceptions.RequestException("base class"),
        requests.exceptions.ConnectionError("connection refused"),
        requests.exceptions.Timeout("read timed out"),
        requests.exceptions.HTTPError("503 Service Unavailable"),
        requests.exceptions.SSLError("bad cert"),
        requests.exceptions.TooManyRedirects("loop"),
        requests.exceptions.ChunkedEncodingError("bad chunk"),
    ],
    ids=[
        "RequestException-base",
        "ConnectionError",
        "Timeout",
        "HTTPError",
        "SSLError",
        "TooManyRedirects",
        "ChunkedEncodingError",
    ],
)
def test_classify_requests_exceptions_returns_upstream(
    exc_instance: BaseException,
) -> None:
    """Every requests.exceptions subclass classifies as UPSTREAM (3).

    `cfscrape` raises `requests` subclasses internally so this single
    isinstance check covers both libraries' failure surface.
    """
    assert exit_codes.classify(exc_instance) == exit_codes.UPSTREAM


# ---------------------------------------------------------------------------
# `classify(exc)` — DATA family (BS4 parse-failure trio).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "exc_instance",
    [
        IndexError("list index out of range"),
        AttributeError("'NoneType' object has no attribute 'get'"),
        KeyError("missing column"),
    ],
    ids=["IndexError", "AttributeError", "KeyError"],
)
def test_classify_parse_exceptions_returns_data(
    exc_instance: BaseException,
) -> None:
    """IndexError / AttributeError / KeyError -> DATA (4).

    These are the three exception types BS4 row parsing raises when the
    HTML shape drifts (short row -> IndexError; missing link -> AttributeError;
    missing column -> KeyError).
    """
    assert exit_codes.classify(exc_instance) == exit_codes.DATA


# ---------------------------------------------------------------------------
# `classify(exc)` — INTERNAL fallback (everything not in the above two sets).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "exc_instance",
    [
        ValueError("column count mismatch"),
        RuntimeError("unexpected state"),
        TypeError("incompatible types"),
        ZeroDivisionError("oops"),
        Exception("generic"),
    ],
    ids=[
        "ValueError",
        "RuntimeError",
        "TypeError",
        "ZeroDivisionError",
        "Exception-base",
    ],
)
def test_classify_unknown_exceptions_returns_internal(
    exc_instance: BaseException,
) -> None:
    """Unrecognized exception types fall back to INTERNAL (1).

    The classifier is deliberately narrow — guessing UPSTREAM or DATA for
    unfamiliar exceptions would hide the root cause behind a misleading
    code. Exit 1 + traceback is the honest default.
    """
    assert exit_codes.classify(exc_instance) == exit_codes.INTERNAL


def test_classify_returns_int_type() -> None:
    """Return type is plain `int` (not e.g. an enum) so `sys.exit(code)` works."""
    result = exit_codes.classify(RuntimeError("test"))
    assert isinstance(result, int)
    assert type(result) is int


# ---------------------------------------------------------------------------
# Regression guard: subclass-hierarchy correctness. A custom subclass of
# RequestException must still classify as UPSTREAM (isinstance check, not
# direct-class compare).
# ---------------------------------------------------------------------------


def test_classify_custom_request_subclass_still_upstream() -> None:
    class CustomNetworkError(requests.exceptions.RequestException):
        pass

    assert exit_codes.classify(CustomNetworkError("oops")) == exit_codes.UPSTREAM


def test_classify_custom_lookup_subclass_still_data() -> None:
    class CustomLookupError(KeyError):
        pass

    assert exit_codes.classify(CustomLookupError("nope")) == exit_codes.DATA
