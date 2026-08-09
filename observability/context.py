"""Correlation context shared by logs, middleware and error handlers.

The Python analogue of midas's ``internal/observability/logctx``: a single
``ContextVar`` holds the correlation id (``request_id`` on the HTTP surface,
``run_id`` on the CLI surface) so every log line emitted while handling a
request/run inherits it without threading it through call signatures.

Core module — stdlib only. Copy verbatim into every service; the future shared
``strade_observability`` package is this file unchanged.
"""

from __future__ import annotations

import contextvars
import re
import uuid
from collections.abc import Mapping
from typing import Any

# A caller-supplied X-Request-ID / X-Correlation-ID is trusted verbatim only if
# it matches this shape; otherwise a fresh id is minted. Mirrors midas's
# isValidRequestID (server.go): ^[A-Za-z0-9_.:-]{1,128}$.
_VALID_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")

_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "observability_request_id", default=None
)
# Optional post-auth enrichment (midas adds user_id / key_id after auth). Kept
# separate so log lines can inherit it without re-binding the id.
_extra: contextvars.ContextVar[dict[str, str] | None] = contextvars.ContextVar(
    "observability_extra", default=None
)
# Whether the CURRENT request was explicitly traced (?trace=1 / X-Strade-Trace).
# Set by ArtifactMiddleware; outbound HTTP clients read it via is_traced() to
# propagate the trace flag downstream so the whole chain writes bundles.
_traced: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "observability_traced", default=False
)


def new_id() -> str:
    """Mint a fresh correlation id (UUID v4, matching midas)."""
    return str(uuid.uuid4())


def is_valid_id(value: str) -> bool:
    return bool(_VALID_ID.match(value))


def coerce_id(value: str | None) -> str:
    """Return a trusted correlation id: the caller's if valid, else a fresh one."""
    if value and is_valid_id(value):
        return value
    return new_id()


def set_request_id(value: str) -> contextvars.Token[str | None]:
    """Bind ``value`` as the current correlation id. Returns a reset token."""
    return _request_id.set(value)


def reset_request_id(token: contextvars.Token[str | None]) -> None:
    _request_id.reset(token)


def get_request_id() -> str | None:
    return _request_id.get()


def bind(**fields: str | None) -> None:
    """Merge extra fields (e.g. ``key_id``) onto the current context for log
    enrichment. ``None`` values are ignored."""
    current = dict(_extra.get() or {})
    current.update({k: v for k, v in fields.items() if v is not None})
    _extra.set(current)


def get_extra() -> dict[str, str]:
    return dict(_extra.get() or {})


def set_traced(value: bool) -> contextvars.Token[bool]:
    return _traced.set(value)


def reset_traced(token: contextvars.Token[bool]) -> None:
    _traced.reset(token)


def is_traced() -> bool:
    """True while handling a request that was explicitly traced. Outbound tool
    clients use this to forward ``X-Strade-Trace: 1`` so downstream services
    write their own bundles for the same correlated run."""
    return _traced.get()


def resolve_request_id(scope: Mapping[str, Any] | None = None) -> str | None:
    """Best-effort correlation id for error handlers.

    Prefers the id stashed on the ASGI ``scope`` state by
    ``RequestContextMiddleware`` — which survives even when a handler runs in
    Starlette's ``ServerErrorMiddleware`` (outside the middleware, after the
    contextvar was reset) — then falls back to the contextvar. Pass
    ``request.scope`` from a FastAPI/Starlette handler.
    """
    if scope is not None:
        state = scope.get("state")
        if isinstance(state, dict):
            rid = state.get("request_id")
            if isinstance(rid, str):
                return rid
    return get_request_id()
