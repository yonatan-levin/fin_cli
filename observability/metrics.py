"""Prometheus metrics: a dedicated registry (never the global default), the four
HTTP families midas exposes, a timing middleware, and the ``/metrics`` ASGI app.

Cardinality rule (load-bearing, from midas): never put high-cardinality values
(ticker, request_id, raw path params) in labels — only ``method`` /
normalized-``endpoint`` (the route template) / ``status``. Using a fresh
``CollectorRegistry`` per service avoids the global-default double-registration
foot-gun midas hit (PREX-1).

Core module — starlette types + prometheus_client only.
"""

from __future__ import annotations

import time

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class Metrics:
    """Owns a private registry and the standard HTTP metric families."""

    def __init__(self, *, namespace: str = "") -> None:
        self.registry = CollectorRegistry()
        prefix = f"{namespace}_" if namespace else ""
        self.requests_total = Counter(
            f"{prefix}http_requests_total",
            "Total HTTP requests.",
            ["method", "endpoint", "status"],
            registry=self.registry,
        )
        self.request_duration = Histogram(
            f"{prefix}http_request_duration_seconds",
            "HTTP request latency in seconds.",
            ["method", "endpoint"],
            registry=self.registry,
        )
        self.in_flight = Gauge(
            f"{prefix}http_requests_in_flight",
            "In-flight HTTP requests.",
            registry=self.registry,
        )
        self.response_size = Histogram(
            f"{prefix}http_response_size_bytes",
            "HTTP response size in bytes.",
            ["method", "endpoint"],
            buckets=(100, 1_000, 10_000, 100_000, 1_000_000),
            registry=self.registry,
        )

    def render(self, request: Request) -> Response:
        """Prometheus exposition as a Starlette Response.

        Wire as a route — ``app.add_route("/metrics", metrics.render, methods=["GET"])``
        — NOT ``app.mount("/metrics", ...)``. A mount makes ``/metrics`` 307-redirect
        to ``/metrics/``, which most Prometheus scrapers do not follow; a route serves
        ``/metrics`` at 200 directly (matching midas).
        """
        return Response(generate_latest(self.registry), media_type=CONTENT_TYPE_LATEST)


def _endpoint(scope: Scope) -> str:
    """The route template (bounded cardinality), falling back to the raw path."""
    template = getattr(scope.get("route"), "path", None)
    if isinstance(template, str):
        return template
    path = scope.get("path")
    return path if isinstance(path, str) else "unknown"


class MetricsMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        metrics: Metrics,
        *,
        skip_paths: frozenset[str] = frozenset(),
    ) -> None:
        self.app = app
        self.metrics = metrics
        self.skip_paths = skip_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") in self.skip_paths:
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "")
        self.metrics.in_flight.inc()
        start = time.perf_counter()
        state = {"status": 0, "bytes": 0}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                state["status"] = message["status"]
            elif message["type"] == "http.response.body":
                state["bytes"] += len(message.get("body", b"") or b"")
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            endpoint = _endpoint(scope)  # route template is populated post-routing
            elapsed = time.perf_counter() - start
            self.metrics.in_flight.dec()
            self.metrics.requests_total.labels(method, endpoint, str(state["status"])).inc()
            self.metrics.request_duration.labels(method, endpoint).observe(elapsed)
            self.metrics.response_size.labels(method, endpoint).observe(state["bytes"])
