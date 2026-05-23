"""Shared fixtures for `tests/unit/api/` — TestClient + adapter mocks.

T5a tier (unit): the adapter boundary (`fincli_api.adapters.fincli`) is
mocked. No fincli internals run; no HTTP calls fire. Tests assert only
HTTP-layer behavior: routing, request/response shapes, validator-first
ordering, and the exception-handler envelope.
"""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from fincli_api.main import app
from fincli_api.models import FilterEntry, FilterInventory, ScreenResult, Stock


@pytest.fixture
def client() -> TestClient:
    """TestClient configured so the registered exception_handler is exercised.

    ``raise_server_exceptions=False`` is REQUIRED. The Starlette default
    re-raises exceptions through middleware in tests, bypassing our
    ``@app.exception_handler(Exception)``. Without this override every
    test that triggers a handler-mapped exception sees the raw exception
    instead of the JSONResponse envelope — making it impossible to pin
    the spec §5 contract from unit tests. See T4 BACKEND carryforward.
    """
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def mock_get_filter_inventory() -> Iterator[MagicMock]:
    """Patch the adapter at the IMPORT SITE inside the filters route module.

    The route does ``from fincli_api.adapters import get_filter_inventory``
    at import time, so the name bound inside ``fincli_api.routes.filters``
    is what the route handler actually invokes. Patching the source module
    would not redirect that already-resolved reference.
    """
    with patch("fincli_api.routes.filters.get_filter_inventory") as m:
        yield m


@pytest.fixture
def mock_run_screen() -> Iterator[MagicMock]:
    """Patch the run_screen adapter at the IMPORT SITE inside the screens route.

    Same import-binding rationale as ``mock_get_filter_inventory``. The
    route does ``from fincli_api.adapters import run_screen``; we patch
    ``fincli_api.routes.screens.run_screen`` so the route sees the mock.
    """
    with patch("fincli_api.routes.screens.run_screen") as m:
        yield m


@pytest.fixture
def sample_filter_inventory() -> FilterInventory:
    """Minimal FilterInventory fixture matching spec §4.4 shape."""
    return FilterInventory(
        schema_version=1,
        keys=["fa_pe", "sec"],
        filters={
            "fa_pe": FilterEntry(label="P/E", values={"u5": "Under 5", "u10": "Under 10"}),
            "sec": FilterEntry(label="Sector", values={"energy": "Energy"}),
        },
    )


@pytest.fixture
def sample_stock() -> Stock:
    """One Stock matching the spec §4.3 example shape."""
    return Stock(
        ticker="CNX",
        company="CNX Resources Corporation",
        sector="Energy",
        industry="Oil & Gas E&P",
        country="USA",
        market_cap=5234000000.0,
        pe="4.2",
        price="$34.55",
        change="+1.23%",
        volume="1.2M",
        rank=1,
        finviz_url="https://finviz.com/quote.ashx?t=CNX",
    )


@pytest.fixture
def sample_screen_result(sample_stock: Stock) -> ScreenResult:
    """ScreenResult matching spec §4.3 example (one stock row)."""
    return ScreenResult(
        schema_version=1,
        row_count=1,
        duration_ms=1843,
        started_at="2026-05-22T15:23:01.234Z",
        finished_at="2026-05-22T15:23:03.077Z",
        stocks=[sample_stock],
    )
