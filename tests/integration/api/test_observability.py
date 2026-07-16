"""Observability surface: request-id correlation, health triad, and /metrics.

The standard endpoints are added alongside the existing ``/healthz`` liveness
probe. No adapters are exercised (these endpoints are dependency-free).
"""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from fincli_api.main import app

_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

client = TestClient(app, raise_server_exceptions=False)


def test_healthz_still_ok() -> None:
    # The pre-existing liveness contract is preserved.
    assert client.get("/healthz").json() == {"status": "ok"}


def test_health_ready_detailed() -> None:
    assert client.get("/health").status_code == 200
    ready = client.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    detailed = client.get("/health/detailed")
    assert detailed.status_code == 200
    assert detailed.json()["status"] == "healthy"


def test_request_id_minted_and_echoed() -> None:
    r = client.get("/healthz")
    assert _UUID.match(r.headers["x-request-id"])


def test_valid_request_id_echoed() -> None:
    r = client.get("/healthz", headers={"X-Request-ID": "trace-abc.1"})
    assert r.headers["x-request-id"] == "trace-abc.1"


def test_invalid_request_id_replaced() -> None:
    r = client.get("/healthz", headers={"X-Request-ID": "bad id with spaces!!"})
    assert r.headers["x-request-id"] != "bad id with spaces!!"
    assert _UUID.match(r.headers["x-request-id"])


def test_metrics_exposes_http_family() -> None:
    client.get("/healthz")  # a counted request (not a skip path)
    # follow_redirects=False: /metrics must serve 200 directly, not 307 -> /metrics/.
    m = client.get("/metrics", follow_redirects=False)
    assert m.status_code == 200
    assert "fincli_http_requests_total" in m.text
