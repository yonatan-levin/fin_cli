"""Unit tests for ``POST /screens`` — adapter mocked, validator REAL.

Critical invariant pinned here: ``validate_filter_pairs`` runs BEFORE
``run_screen``. The screens route imports the real validator and only
mocks the adapter, so unknown keys/values must short-circuit to HTTP 422
without touching the adapter. This is the silent-drop-hazard gate that
drove the entire pipeline-mode validator integration (spec §5; T3 QA
carryforward).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from fincli_api.models import ScreenResult


def test_post_screens_valid_filters_returns_200_screen_result(
    client: TestClient,
    mock_run_screen: MagicMock,
    sample_screen_result: ScreenResult,
) -> None:
    """Happy path: valid filters -> adapter invoked, 200 with ScreenResult body."""
    mock_run_screen.return_value = sample_screen_result

    response = client.post("/screens", json={"filters": {"fa_pe": "u5", "sec": "energy"}})

    assert response.status_code == 200
    body = response.json()
    assert body["row_count"] == 1
    assert body["stocks"][0]["ticker"] == "CNX"
    mock_run_screen.assert_called_once_with({"fa_pe": "u5", "sec": "energy"})


def test_post_screens_unknown_filter_key_returns_422_validation(
    client: TestClient,
    mock_run_screen: MagicMock,
) -> None:
    """Unknown filter KEY -> 422 ``validation`` (not 200 empty; not 500)."""
    response = client.post("/screens", json={"filters": {"fa_pee": "u5"}})

    assert response.status_code == 422
    body = response.json()
    assert body["error_class"] == "validation"
    # Adapter must never have been called — validator short-circuited.
    mock_run_screen.assert_not_called()


def test_post_screens_unknown_filter_value_returns_422_validation(
    client: TestClient,
    mock_run_screen: MagicMock,
) -> None:
    """Known KEY + unknown VALUE -> 422 ``validation`` (adapter not invoked)."""
    response = client.post("/screens", json={"filters": {"fa_pe": "totally_bogus_value"}})

    assert response.status_code == 422
    assert response.json()["error_class"] == "validation"
    mock_run_screen.assert_not_called()


def test_post_screens_validator_called_before_adapter(
    client: TestClient,
    mock_run_screen: MagicMock,
    sample_screen_result: ScreenResult,
) -> None:
    """Pins call ORDER: validate_filter_pairs -> run_screen (spec §5 hazard)."""
    mock_run_screen.return_value = sample_screen_result
    call_order: list[str] = []

    def record_validator(_pairs: tuple[tuple[str, str], ...]) -> None:
        call_order.append("validator")

    def record_adapter(_filters: dict[str, str]) -> ScreenResult:
        call_order.append("adapter")
        return sample_screen_result

    with patch("fincli_api.routes.screens.validate_filter_pairs", side_effect=record_validator):
        mock_run_screen.side_effect = record_adapter
        response = client.post("/screens", json={"filters": {"fa_pe": "u5"}})

    assert response.status_code == 200
    assert call_order == ["validator", "adapter"]


def test_post_screens_stocks_have_finviz_url_single_slash(
    client: TestClient,
    mock_run_screen: MagicMock,
    sample_screen_result: ScreenResult,
) -> None:
    """Pins the spec §4.3 single-slash finviz_url contract per-stock."""
    mock_run_screen.return_value = sample_screen_result

    body = client.post("/screens", json={"filters": {"fa_pe": "u5"}}).json()

    for stock in body["stocks"]:
        url = stock["finviz_url"]
        assert url.startswith("https://finviz.com/quote.ashx?t=")
        # Asserts no double-slash after the scheme — the CSV path's
        # ticker_link legacy quirk must not leak into the API surface.
        assert "//" not in url[len("https://") :]
