"""Health / readiness router factory: ``/health`` (liveness), ``/ready``
(dependency probe), ``/health/detailed`` (component map) — the midas triad on
FastAPI.

Readiness/detailed checks are pluggable callables the service supplies (broker
connected, feed reachable, downstream tools up). A probe that raises is treated
as unhealthy, never propagated — a health endpoint must not 500.

Core module — FastAPI only.
"""

from __future__ import annotations

import inspect
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import APIRouter
from fastapi.responses import JSONResponse


@dataclass
class ComponentHealth:
    healthy: bool
    message: str = ""
    degraded: bool = False
    details: dict[str, object] | None = None


HealthCheck = Callable[[], "ComponentHealth | Awaitable[ComponentHealth]"]


async def _run(check: HealthCheck) -> ComponentHealth:
    try:
        result = check()
        if inspect.isawaitable(result):
            result = await result
        return result
    except Exception as exc:  # a probe must never surface as a 500
        return ComponentHealth(healthy=False, message=f"{type(exc).__name__}: {exc}")


def build_health_router(
    *,
    service: str,
    version: str = "",
    started_at: float | None = None,
    readiness_checks: dict[str, HealthCheck] | None = None,
    detailed_checks: dict[str, HealthCheck] | None = None,
    include_liveness: bool = True,
) -> APIRouter:
    """Build the health triad. Set ``include_liveness=False`` when the service
    already exposes its own ``GET /health`` with an established contract — only
    ``/ready`` and ``/health/detailed`` are then registered."""
    router = APIRouter()
    started = started_at if started_at is not None else time.time()
    readiness = readiness_checks or {}
    detailed = detailed_checks if detailed_checks is not None else dict(readiness)

    def _uptime() -> float:
        return round(time.time() - started, 3)

    if include_liveness:

        @router.get("/health", include_in_schema=False)
        async def health() -> dict[str, object]:  # liveness — always 200
            return {
                "status": "ok",
                "service": service,
                "version": version,
                "uptime_s": _uptime(),
            }

    @router.get("/ready", include_in_schema=False)
    async def ready() -> JSONResponse:
        results = {name: await _run(chk) for name, chk in readiness.items()}
        ok = all(c.healthy for c in results.values())
        return JSONResponse(
            {
                "status": "ready" if ok else "not_ready",
                "checks": {
                    n: {"healthy": c.healthy, "message": c.message} for n, c in results.items()
                },
            },
            status_code=200 if ok else 503,
        )

    @router.get("/health/detailed", include_in_schema=False)
    async def detailed_health() -> JSONResponse:
        results = {name: await _run(chk) for name, chk in detailed.items()}
        if any(not c.healthy for c in results.values()):
            status, code = "unhealthy", 503
        elif any(c.degraded for c in results.values()):
            status, code = "degraded", 206
        else:
            status, code = "healthy", 200
        return JSONResponse(
            {
                "status": status,
                "service": service,
                "version": version,
                "uptime_s": _uptime(),
                "components": {
                    n: {
                        "healthy": c.healthy,
                        "degraded": c.degraded,
                        "message": c.message,
                        "details": c.details,
                    }
                    for n, c in results.items()
                },
            },
            status_code=code,
        )

    return router
