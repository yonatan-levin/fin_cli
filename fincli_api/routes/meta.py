"""Meta routes — liveness/health checks."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthStatus(BaseModel):
    """Liveness response payload."""

    status: str


@router.get(
    "/healthz",
    response_model=HealthStatus,
    summary="Liveness check.",
    description='Returns 200 + {"status": "ok"} if the process is up. No dependencies checked.',
)
def healthz() -> HealthStatus:
    """Bare liveness probe — does not exercise fincli or Finviz."""
    # Intentionally dependency-free: this is a process-up check, not a full-stack
    # health check. Adding upstream calls here would defeat its purpose as a fast
    # Kubernetes-style liveness probe (spec §4.1).
    return HealthStatus(status="ok")
