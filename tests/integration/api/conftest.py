"""Shared fixtures for `tests/integration/api/` — TestClient + Finviz HTTP mock.

T5b tier (integration): the REAL adapter + REAL ``screen_to_dataframe`` +
REAL BS4 parser all run end-to-end. Only ``fincli.app.main.fetch_page_sync``
(the Finviz HTTP boundary) is mocked, so canned HTML fixtures drive every
downstream code path without touching the network.

Mock-target rule (carryforward from T3 BACKEND surprise): patch
``fincli.app.main.fetch_page_sync`` — NOT ``fincli.utils.web_scraper.fetch_page_sync``.
``fincli/app/main.py`` does ``from fincli.utils.web_scraper import
fetch_page_sync`` at import time; patching the source module would not
redirect the already-resolved local binding inside ``main``. Same rationale
already pinned by ``tests/integration/test_pipeline_exit_codes.py``.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from fincli_api.main import app

# Make `tests/integration/_fixtures_loader.py` importable as a top-level
# module. Pytest adds this conftest's immediate dir (`tests/integration/api/`)
# to sys.path during collection, not its parent — so without this hop,
# the test files' `from _fixtures_loader import ...` cannot resolve.
# The sibling integration suites (`tests/integration/test_pipeline_*.py`)
# don't need this because they live at the same level as the loader.
# This package intentionally has NO `__init__.py` (basename collision
# with `tests/unit/api/conftest.py` if both packages are formed).
_INTEGRATION_ROOT = Path(__file__).resolve().parent.parent
if str(_INTEGRATION_ROOT) not in sys.path:
    sys.path.insert(0, str(_INTEGRATION_ROOT))


@pytest.fixture
def client() -> TestClient:
    """TestClient configured so the registered exception_handler is exercised.

    ``raise_server_exceptions=False`` is REQUIRED. The Starlette default
    re-raises exceptions through middleware in tests, bypassing our
    ``@app.exception_handler(Exception)``. Without this override every
    test that triggers a handler-mapped exception sees the raw exception
    instead of the JSONResponse envelope — making it impossible to pin
    the spec §5 contract from integration tests. See T4 BACKEND carryforward.
    """
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def mock_fetch() -> Iterator[MagicMock]:
    """Patch ``fincli.app.main.fetch_page_sync`` — the Finviz HTTP chokepoint.

    Tests assign ``mock_fetch.return_value = <canned HTML bytes>`` (typical
    happy/edge-case fixtures) or ``mock_fetch.side_effect = <Exception>``
    (the UPSTREAM-failure path). The real adapter + parser run; only the
    HTTP call is faked.

    Pagination note (T3 BACKEND surprise): ``_screen_from_query`` issues
    ONE direct ``fetch_page_sync`` call (line 169) to discover ``page_count``,
    then ``fetch_urls`` issues ``page_count + 1`` more. The direct call's
    response is used ONLY to compute the page count — it does NOT contribute
    parsed rows. So:

      * Fixtures with no pagination markup (``page_count = 0``) -> 1 fetch
        via ``fetch_urls`` -> rows parsed once -> NO doubling.
      * Fixtures with ``<a class="screener-pages is-selected">1</a>``
        (``page_count = 1``) -> 2 fetches via ``fetch_urls`` -> SAME fixture
        returned twice -> rows DOUBLED. (See ``finviz_one_page.html``.)
    """
    with patch("fincli.app.main.fetch_page_sync") as m:
        yield m
