"""Pydantic envelope for HTTP 4xx/5xx error responses (spec §5.2)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Error envelope for HTTP 4xx/5xx responses (spec §5.2).

    `error_class` is the discriminator. Clients route on it to choose
    a recovery strategy:
      - `validation` (HTTP 422): caller's input was bad — fix and retry
      - `upstream` (HTTP 502): Finviz fetch failed — retry with backoff
      - `parsing` (HTTP 502): Finviz HTML didn't parse — likely structural
        drift; retry rarely helps
      - `internal` (HTTP 500): unclassified bug — surface request_id to
        the operator for log cross-reference

    Maps from fincli's existing classifier at fincli/app/exit_codes.py
    (`classify(exc)` returns the int that the exception handler at
    fincli_api/exception_handlers.py translates into this envelope).

    Attributes:
        schema_version: Contract version (CONTRACTS §7); bump on breaking
            envelope changes.
        error_class: Discriminator selecting the recovery strategy.
        message: Human-readable explanation; safe to surface in UI.
        details: Error-class-specific structured payload; shape varies
            (see CONTRACTS §8).
        request_id: UUID4 for 5xx paths so operators can cross-reference
            server logs. Absent on 4xx.
    """

    schema_version: int = 1
    error_class: Literal["validation", "upstream", "parsing", "internal"]
    message: str = Field(
        ...,
        description="Human-readable; safe to surface in UI.",
    )
    details: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Error-class-specific structured payload. Shape varies by "
            "error_class (see CONTRACTS §8 for per-class schemas)."
        ),
    )
    request_id: str | None = Field(
        default=None,
        description=(
            "UUID4 generated for 5xx paths so operators can cross-reference "
            "the response with server logs. Absent on 4xx (caller's own "
            "fault — no log to look up)."
        ),
    )
