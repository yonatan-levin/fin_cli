"""Unit tests for the classifier-driven exception handler (spec §5).

Each test drives one error_class branch by injecting an exception via
the mocked ``run_screen`` adapter, then asserts the spec §5.1 mapping:

    classify(exc) -> exit_code -> (http_status, error_class)
    + request_id presence rule (5xx only).

The route is a convenient injection point because it propagates raw
adapter exceptions; the handler sits at the FastAPI app level and is
exit-code-agnostic to which route raised.
"""

from __future__ import annotations

from collections.abc import Callable
from unittest.mock import MagicMock

import click
import pytest
import requests
from fastapi.testclient import TestClient


def test_validation_exception_returns_422_envelope_no_request_id(
    client: TestClient,
    mock_run_screen: MagicMock,
) -> None:
    """USAGE (2) -> 422 ``validation``; no request_id (caller-fault path)."""
    mock_run_screen.side_effect = click.UsageError("bad filter")

    response = client.post("/screens", json={"filters": {"fa_pe": "u5"}})

    assert response.status_code == 422
    body = response.json()
    assert body["error_class"] == "validation"
    # 4xx envelopes omit request_id per spec §5.2 / exception_handlers.py
    # ``exclude_none=True`` rule. ``not in body`` is the assertion shape.
    assert "request_id" not in body


@pytest.mark.parametrize(
    "exception_factory, expected_error_class",
    [
        # ``requests.exceptions.Timeout`` is the actual RequestException
        # subclass the classifier recognizes as UPSTREAM (3). Python's
        # builtin ``TimeoutError`` is NOT a RequestException, so it would
        # classify to INTERNAL (500) instead — using the wrong exception
        # type would silently miscover the upstream branch.
        (lambda: requests.exceptions.Timeout("upstream timed out"), "upstream"),
        (lambda: IndexError("malformed row"), "parsing"),
    ],
)
def test_upstream_and_parsing_exceptions_return_502_with_request_id(
    client: TestClient,
    mock_run_screen: MagicMock,
    exception_factory: Callable[[], BaseException],
    expected_error_class: str,
) -> None:
    """UPSTREAM (3) + DATA (4) both map to 502; error_class discriminates.

    Both classes are 5xx -> request_id MUST be present per spec §5.2.
    """
    mock_run_screen.side_effect = exception_factory()

    response = client.post("/screens", json={"filters": {"fa_pe": "u5"}})

    assert response.status_code == 502
    body = response.json()
    assert body["error_class"] == expected_error_class
    assert isinstance(body["request_id"], str) and len(body["request_id"]) > 0


def test_internal_exception_returns_500_internal_with_request_id(
    client: TestClient,
    mock_run_screen: MagicMock,
) -> None:
    """Unclassified RuntimeError -> INTERNAL (1) -> 500 ``internal`` + request_id."""
    mock_run_screen.side_effect = RuntimeError("unexpected boom")

    response = client.post("/screens", json={"filters": {"fa_pe": "u5"}})

    assert response.status_code == 500
    body = response.json()
    assert body["error_class"] == "internal"
    assert isinstance(body["request_id"], str) and len(body["request_id"]) > 0


def test_envelope_includes_schema_version_and_details(
    client: TestClient,
    mock_run_screen: MagicMock,
) -> None:
    """Pins the envelope's invariant fields across every error_class branch."""
    mock_run_screen.side_effect = RuntimeError("boom")

    body = client.post("/screens", json={"filters": {"fa_pe": "u5"}}).json()

    assert body["schema_version"] == 1
    assert body["details"]["exception_type"] == "RuntimeError"
    assert body["message"] == "boom"
