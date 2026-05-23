"""Unit tests for ``GET /filters`` — adapter mocked.

Pins spec §4.4: the route is a thin pass-through of
``adapters.get_filter_inventory`` into the ``FilterInventory`` Pydantic
shape. Failures propagate so the global exception handler can map them
via ``classify()`` (spec §5).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from fincli_api.models import FilterInventory


def test_get_filters_returns_200_with_filter_inventory_shape(
    client: TestClient,
    mock_get_filter_inventory: MagicMock,
    sample_filter_inventory: FilterInventory,
) -> None:
    """200 + body deserializes back into a FilterInventory (spec §4.4 shape)."""
    mock_get_filter_inventory.return_value = sample_filter_inventory

    response = client.get("/filters")

    assert response.status_code == 200
    # Round-trip validates that the wire JSON conforms to the model contract
    # — not just that "some 200 came back".
    parsed = FilterInventory.model_validate(response.json())
    assert parsed.keys == ["fa_pe", "sec"]
    assert "fa_pe" in parsed.filters


@pytest.mark.parametrize("expected_key", ["schema_version", "keys", "filters"])
def test_get_filters_has_expected_top_level_keys(
    client: TestClient,
    mock_get_filter_inventory: MagicMock,
    sample_filter_inventory: FilterInventory,
    expected_key: str,
) -> None:
    """Pins the three top-level wire-JSON keys polyglot consumers depend on."""
    mock_get_filter_inventory.return_value = sample_filter_inventory

    body = client.get("/filters").json()

    assert expected_key in body


def test_get_filters_propagates_adapter_exception_to_500_internal(
    client: TestClient,
    mock_get_filter_inventory: MagicMock,
) -> None:
    """A bare ``Exception`` from the adapter classifies to 500 ``internal``."""
    mock_get_filter_inventory.side_effect = RuntimeError("inventory load broke")

    response = client.get("/filters")

    assert response.status_code == 500
    body = response.json()
    assert body["error_class"] == "internal"
    assert body["schema_version"] == 1
