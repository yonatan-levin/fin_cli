"""Unit tests for ``GET /healthz`` — process-up liveness probe (spec §4.1)."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient


def test_get_healthz_returns_200_status_ok(client: TestClient) -> None:
    """Pins the literal Kubernetes-style liveness response."""
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_healthz_does_not_call_fincli(
    client: TestClient,
    mock_get_filter_inventory: MagicMock,
    mock_run_screen: MagicMock,
) -> None:
    """/healthz must be dependency-free — no adapter calls, no fincli imports.

    Pins the spec §4.1 design intent: ``/healthz`` is a process-up check,
    not a full-stack health check. Adding upstream calls here would defeat
    its purpose as a fast liveness probe.
    """
    response = client.get("/healthz")

    assert response.status_code == 200
    mock_get_filter_inventory.assert_not_called()
    mock_run_screen.assert_not_called()
