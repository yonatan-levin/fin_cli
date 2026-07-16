"""Strade observability: structured JSON logging + request-id correlation +
access/metrics middleware + health endpoints.

Copy this package into a service's source tree as a subpackage and:

  1. call ``configure_logging(...)`` once at process startup (API and CLI), and
  2. call ``install_observability(app, ...)`` on the FastAPI app.

Core files (context/logging/middleware/metrics/health) use only stdlib +
starlette + prometheus_client with relative imports, so this package can later
be lifted verbatim into a shared ``strade_observability`` distribution.

CLI surfaces (no FastAPI app) skip ``install_observability`` and instead bind a
``run_id`` themselves::

    configure_logging(level=..., fmt="json", logger_name="myservice")
    set_request_id(coerce_id(cli_supplied_id))   # the run_id
"""

from __future__ import annotations

from fastapi import FastAPI

from .context import (
    bind,
    coerce_id,
    get_extra,
    get_request_id,
    is_valid_id,
    new_id,
    reset_request_id,
    resolve_request_id,
    set_request_id,
)
from .health import ComponentHealth, HealthCheck, build_health_router
from .logging import ContextFilter, JsonFormatter, configure_logging, get_logger
from .metrics import Metrics, MetricsMiddleware
from .middleware import REQUEST_ID_HEADER, AccessLogMiddleware, RequestContextMiddleware

DEFAULT_SKIP_PATHS = frozenset({"/metrics", "/health", "/ready"})

__all__ = [
    "bind",
    "coerce_id",
    "get_extra",
    "get_request_id",
    "is_valid_id",
    "new_id",
    "reset_request_id",
    "resolve_request_id",
    "set_request_id",
    "ComponentHealth",
    "HealthCheck",
    "build_health_router",
    "ContextFilter",
    "JsonFormatter",
    "configure_logging",
    "get_logger",
    "Metrics",
    "MetricsMiddleware",
    "REQUEST_ID_HEADER",
    "AccessLogMiddleware",
    "RequestContextMiddleware",
    "DEFAULT_SKIP_PATHS",
    "install_observability",
]


def install_observability(
    app: FastAPI,
    *,
    service: str,
    version: str = "",
    namespace: str = "",
    metrics_enabled: bool = True,
    readiness_checks: dict[str, HealthCheck] | None = None,
    detailed_checks: dict[str, HealthCheck] | None = None,
    include_liveness: bool = True,
    skip_paths: frozenset[str] = DEFAULT_SKIP_PATHS,
    extra_read_headers: tuple[bytes, ...] = (),
    echo_headers: tuple[bytes, ...] = (REQUEST_ID_HEADER,),
) -> Metrics | None:
    """Wire the full stack onto a FastAPI app; return the ``Metrics`` handle (or
    ``None`` when metrics are disabled).

    Middleware precedence: Starlette applies the *last* added middleware as the
    outermost, so ``RequestContextMiddleware`` is added last — it wraps access
    logging, metrics, handlers and exception handlers, guaranteeing every line
    they emit carries the correlation id.

    Call ``configure_logging(...)`` separately at startup — logging config is
    process-wide and shared with the CLI surface, so it does not belong here.
    """
    metrics = Metrics(namespace=namespace) if metrics_enabled else None

    if metrics is not None:
        app.mount("/metrics", metrics.asgi_app())
        app.add_middleware(MetricsMiddleware, metrics=metrics, skip_paths=skip_paths)
    app.add_middleware(AccessLogMiddleware, skip_paths=skip_paths)
    app.add_middleware(
        RequestContextMiddleware,
        extra_read_headers=extra_read_headers,
        echo_headers=echo_headers,
    )

    app.include_router(
        build_health_router(
            service=service,
            version=version,
            readiness_checks=readiness_checks,
            detailed_checks=detailed_checks,
            include_liveness=include_liveness,
        )
    )
    return metrics
