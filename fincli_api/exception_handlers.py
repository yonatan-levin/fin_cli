"""Exception-handler registration — routes via ``fincli.app.exit_codes.classify``.

Spec ref: ``docs/superpowers/specs/2026-05-22-fincli-api-design.md`` §5.

This module is the architectural anti-drift seat between the CLI's
differentiated exit codes (Pillar 4) and the HTTP API's error envelope:
the API does NOT reinvent failure classification. It defers entirely to
``fincli.app.exit_codes.classify(exc)`` so a future change to the
classifier (e.g. a new failure family) propagates to both surfaces from
a single edit.

The mapping table (spec §5.1) is the only API-specific layer added on
top of the classifier:

    exit code     ->  HTTP status  ->  error_class
    SUCCESS=0     ->  200          ->  (unused; success path bypasses handler)
    INTERNAL=1    ->  500          ->  "internal"
    USAGE=2       ->  422          ->  "validation"
    UPSTREAM=3    ->  502          ->  "upstream"
    DATA=4        ->  502          ->  "parsing"

FastAPI's automatic 400/404/405/422-from-Pydantic responses are NOT
touched by this handler; the ``@app.exception_handler(Exception)``
decorator only catches what FastAPI itself does not already convert.

Known limitation (2026-05-23, deferred): malformed Finviz HTML that
parses successfully but yields no rows is currently coerced to a 200
empty result instead of the 502 "parsing" envelope spec §5.1 implies.
Distinguishing "Finviz returned junk" from "zero rows matched" requires
parser-level changes in ``fincli/stock_screening/`` and is out of scope
for the T4 wave — tracked for a follow-up spec.
"""

from __future__ import annotations

import logging
import uuid
from typing import Literal, cast

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from fincli.app import exit_codes
from fincli_api.models import ErrorResponse

logger = logging.getLogger(__name__)

# Per-exit-code HTTP status + error_class discriminator. The SUCCESS row is
# cosmetic — the handler is never invoked on the success path — but is kept
# for table completeness so future readers can see the full mapping at a
# glance. ``error_class`` strings must match the Literal in
# ``ErrorResponse.error_class``; the cast at the call site preserves that
# narrowing for mypy.
_EXIT_TO_HTTP: dict[int, tuple[int, str]] = {
    # Unreachable (handler never runs on success); kept for table completeness.
    # "internal" is the neutral fallback string — anything classified to
    # SUCCESS through this map would be a bug, so we avoid the misleading
    # "validation" label that earlier versions used.
    exit_codes.SUCCESS: (200, "internal"),
    exit_codes.INTERNAL: (500, "internal"),
    exit_codes.USAGE: (422, "validation"),
    exit_codes.UPSTREAM: (502, "upstream"),
    exit_codes.DATA: (502, "parsing"),
}

# Fallback for the (theoretically unreachable) case where ``classify``
# returns an integer not in ``_EXIT_TO_HTTP``. Treating an unmapped code
# as INTERNAL/500 keeps the API safe-by-default if the classifier's
# return surface ever grows without a corresponding mapping update.
_FALLBACK_HTTP: tuple[int, str] = (500, "internal")

# UUIDs are truncated to 12 hex chars for log-grep friendliness; full
# 36-char UUID is overkill for in-memory log correlation and clutters
# error responses surfaced in operator dashboards.
_REQUEST_ID_LEN = 12


def _classify_to_envelope(exc: Exception) -> tuple[int, ErrorResponse]:
    """Translate an exception to ``(http_status, ErrorResponse)`` per spec §5.1.

    The classifier (``fincli.app.exit_codes.classify``) is the single
    source of truth for *what kind of failure occurred*; this function
    only adds the HTTP-specific layer (status code, response envelope,
    optional request_id for 5xx log cross-reference).

    Args:
        exc: The exception caught by the registered handler.

    Returns:
        A 2-tuple ``(http_status, envelope)`` ready to be serialised by
        ``JSONResponse``. ``request_id`` is populated on 5xx envelopes
        only — 4xx is the caller's fault, so no server log lookup is
        needed.
    """
    exit_code = exit_codes.classify(exc)
    http_status, error_class = _EXIT_TO_HTTP.get(exit_code, _FALLBACK_HTTP)

    # 5xx-only request_id: 4xx means the caller's input was bad, so they
    # already have everything needed to fix it; correlating to a server
    # log is unnecessary noise. 5xx means we have something in
    # ``logs/error.log`` worth grepping for.
    request_id = str(uuid.uuid4())[:_REQUEST_ID_LEN] if http_status >= 500 else None

    # Preserve ``str(exc)`` for human-readable context; fall back to the
    # exception's type name when ``str(exc)`` is empty (some exceptions
    # have no message — e.g. ``IndexError()`` with no args).
    message = str(exc) or type(exc).__name__

    # Per-class richer ``details`` payloads (spec §5.2 / CONTRACTS §8)
    # can be added in a future spec version once consumers ask for
    # them. For now, surfacing the exception type alone gives operators
    # enough to triage from the response without leaking framework
    # internals or stack frames.
    details = {"exception_type": type(exc).__name__}

    return http_status, ErrorResponse(
        schema_version=1,
        error_class=cast(Literal["validation", "upstream", "parsing", "internal"], error_class),
        message=message,
        details=details,
        request_id=request_id,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Wire the catch-all exception handler onto a FastAPI app.

    Called from ``fincli_api/main.py`` after app instantiation. The
    registered handler catches anything route handlers raise (that
    FastAPI didn't already convert to a 400/404/405/422), logs the full
    traceback to the module logger, and returns the spec §5.2
    ``ErrorResponse`` envelope with the HTTP status from spec §5.1.

    The traceback is logged via ``exc_info=exc`` to a SEPARATE channel
    from the response body — operators see the stack frame in
    ``logs/error.log`` while clients receive the redacted envelope.

    Args:
        app: The FastAPI application to register the handler on.
    """

    # Async handler signature is FastAPI's idiom even when the body
    # itself is sync; FastAPI awaits the return value uniformly.
    @app.exception_handler(Exception)
    async def _classify_handler(request: Request, exc: Exception) -> JSONResponse:
        http_status, envelope = _classify_to_envelope(exc)

        # 5xx -> error log (operator action required); 4xx -> warning
        # log (caller-fixable, not a server fault). ``exc_info=exc``
        # attaches the full traceback to the log record without
        # serialising it into the response body.
        log_method = logger.error if http_status >= 500 else logger.warning
        log_method(
            "request failed: %s -> %d %s",
            type(exc).__name__,
            http_status,
            envelope.error_class,
            exc_info=exc,
        )

        # ``exclude_none=True`` drops null ``details``/``request_id``
        # fields from the JSON body so OpenAPI examples stay clean and
        # 4xx responses don't carry a stray ``"request_id": null``.
        return JSONResponse(
            status_code=http_status,
            content=envelope.model_dump(exclude_none=True),
        )
