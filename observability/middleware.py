"""ASGI middleware: correlation-id binding + access logging.

Raw-ASGI (not ``BaseHTTPMiddleware``) so the contextvar set here survives into
route handlers *and* exception handlers on the same task — the borker pattern
(``borker/app/middleware.py``). ``BaseHTTPMiddleware`` runs handlers in a
separate task and would lose the binding.

Core module — stdlib + starlette types only.
"""

from __future__ import annotations

import logging
import time

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .context import coerce_id, reset_request_id, set_request_id

REQUEST_ID_HEADER = b"x-request-id"

_access_log = logging.getLogger("access")


class RequestContextMiddleware:
    """Read/validate/mint the correlation id, bind it to the context, and echo it
    back on the response.

    ``extra_read_headers`` lets a service also honour a legacy header (e.g.
    orchestrator's ``x-correlation-id``); ``echo_headers`` controls which response
    headers carry the id back to the caller.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        header: bytes = REQUEST_ID_HEADER,
        extra_read_headers: tuple[bytes, ...] = (),
        echo_headers: tuple[bytes, ...] = (REQUEST_ID_HEADER,),
    ) -> None:
        self.app = app
        self.header = header
        self.extra_read_headers = extra_read_headers
        self.echo_headers = echo_headers

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        incoming = headers.get(self.header)
        for alt in self.extra_read_headers:
            if incoming is None:
                incoming = headers.get(alt)
        rid = coerce_id(incoming.decode("latin-1") if incoming else None)
        token = set_request_id(rid)
        # Also stash the id on the shared ASGI scope state. The scope dict is passed
        # by reference up the whole stack, so exception handlers that run in
        # Starlette's ServerErrorMiddleware — OUTSIDE this middleware, after the
        # contextvar has already been reset — can still recover it via
        # request.state.request_id (see context.resolve_request_id).
        state = scope.get("state")
        if isinstance(state, dict):
            state["request_id"] = rid
        else:
            scope["state"] = {"request_id": rid}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                raw = list(message.get("headers") or [])
                encoded = rid.encode("latin-1")
                for name in self.echo_headers:
                    raw.append((name, encoded))
                message["headers"] = raw
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            reset_request_id(token)


class AccessLogMiddleware:
    """Emit one structured access line per request after the handler completes.

    Paths in ``skip_paths`` (probes: /metrics, /health, /ready) are logged at
    DEBUG to cut noise, matching midas's AccessLogSkipPaths.
    """

    def __init__(self, app: ASGIApp, *, skip_paths: frozenset[str] = frozenset()) -> None:
        self.app = app
        self.skip_paths = skip_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

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
            path = scope.get("path", "")
            level = logging.DEBUG if path in self.skip_paths else logging.INFO
            route = scope.get("route")
            _access_log.log(
                level,
                "access",
                extra={
                    "http_method": scope.get("method", ""),
                    "path": path,
                    "route": getattr(route, "path", path),
                    "status": state["status"],
                    "latency_ms": round((time.perf_counter() - start) * 1000.0, 2),
                    "bytes_out": state["bytes"],
                },
            )
