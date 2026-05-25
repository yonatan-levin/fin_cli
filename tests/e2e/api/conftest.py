"""Shared fixtures for `tests/e2e/api/` — live Finviz HTTP, no mocking.

T5c tier (e2e): TestClient + real fincli + REAL Finviz HTTP calls.
The gate that catches what mocked tests miss -- see docs/FEEDBACK-LOG.md
2026-05-22 entry for the near-miss that motivated this tier (the
1-page IndexError would have shipped without a live check).

Opt-in only: tests are marked ``@pytest.mark.live`` and excluded by
default via ``pytest.ini``'s ``addopts = -q -ra -m "not live"``. Run
the gate explicitly with ``pytest -m live tests/e2e/api/``.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from fincli_api.main import app


@pytest.fixture
def client() -> TestClient:
    """TestClient configured so the registered exception_handler envelope is exercised.

    ``raise_server_exceptions=False`` is REQUIRED (carryforward from T4 /
    T5b). Starlette's default re-raises through middleware in tests, which
    bypasses ``@app.exception_handler(Exception)``. With live Finviz on
    the wire, that override is what lets timeouts / malformed HTML /
    rate-limit pages surface as the spec §5 502 envelope instead of a
    raw exception bubbling out of the TestClient.
    """
    return TestClient(app, raise_server_exceptions=False)
