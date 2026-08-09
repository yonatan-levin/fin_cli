"""Observability surface: request-id correlation, health triad, and /metrics.

The standard endpoints are added alongside the existing ``/healthz`` liveness
probe. No adapters are exercised (these endpoints are dependency-free).
"""

from __future__ import annotations

import json
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


def test_trace_query_writes_redacted_bundle(tmp_path) -> None:
    # Repoint the module-level store at a tmp dir for the duration of the test.
    from fincli_api.main import artifact_store

    original_root = artifact_store.root
    artifact_store.root = tmp_path
    try:
        r = client.get("/healthz?trace=1", headers={"X-Request-ID": "art-a1"})
        assert r.status_code == 200
    finally:
        artifact_store.root = original_root
    bundles = list(tmp_path.glob("*/req_art-a1"))
    assert len(bundles) == 1
    manifest = json.loads((bundles[0] / "00-manifest.json").read_text(encoding="utf-8"))
    assert manifest["trigger"] == "manual"
    assert manifest["status"] == 200
    assert (bundles[0] / "01-request.json").exists()
    assert (bundles[0] / "02-response.json").exists()
    assert (bundles[0] / "99-logs.jsonl").exists()


def test_untraced_request_writes_no_bundle(tmp_path) -> None:
    from fincli_api.main import artifact_store

    original_root = artifact_store.root
    artifact_store.root = tmp_path
    try:
        assert client.get("/healthz").status_code == 200
    finally:
        artifact_store.root = original_root
    assert list(tmp_path.glob("*/req_*")) == []
