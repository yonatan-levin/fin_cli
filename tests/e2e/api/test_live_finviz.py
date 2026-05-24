"""Live Finviz smoke tests for the fincli_api HTTP surface (spec §6.3).

Three opt-in tests that hit REAL Finviz via the real fincli adapter --
no HTTP mocking. This is the gate that catches what the mocked unit /
integration tiers miss (see ``docs/FEEDBACK-LOG.md`` 2026-05-22 entry
for the durable rationale: the umbrella's near-miss 1-page IndexError).

All tests are marked ``@pytest.mark.live`` so the default
``pytest tests/`` run excludes them; the gate runs via
``pytest -m live tests/e2e/api/``.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.mark.live
def test_e2e_get_filters_returns_66_keys(client: TestClient) -> None:
    """Live: GET /filters returns the full 66-key Finviz filter inventory."""
    response = client.get("/filters")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["keys"]) == 66


@pytest.mark.live
def test_e2e_post_screens_narrow_energy_filter_returns_stocks(client: TestClient) -> None:
    """Live: POST /screens with narrow energy filter returns >=1 stock with finviz_url."""
    response = client.post(
        "/screens",
        json={"filters": {"fa_pe": "u5", "sec": "energy"}},
    )
    assert response.status_code == 200, (
        f"unexpected status: {response.status_code} body={response.text[:200]}"
    )
    payload = response.json()
    assert payload["row_count"] >= 1, f"expected >=1 stock, got payload: {payload}"
    for stock in payload["stocks"]:
        assert stock["finviz_url"].startswith("https://finviz.com/quote.ashx?t="), (
            f"unexpected finviz_url for ticker={stock.get('ticker')!r}: {stock['finviz_url']!r}"
        )


@pytest.mark.live
def test_e2e_post_screens_zero_row_combo(client: TestClient) -> None:
    """Live: POST /screens with narrow combo returns 0 stocks at 200 (zero-row success)."""
    response = client.post(
        "/screens",
        json={"filters": {"fa_pe": "u5", "sec": "basicmaterials", "geo": "monaco"}},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["row_count"] == 0
    assert payload["stocks"] == []
