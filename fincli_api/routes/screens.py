"""POST /screens route — run a Finviz screen with structured filters."""

from __future__ import annotations

from fastapi import APIRouter

from fincli.resource.params.validators import validate_filter_pairs
from fincli_api.adapters import run_screen
from fincli_api.models import ErrorResponse, ScreenRequest, ScreenResult

router = APIRouter()


@router.post(
    "/screens",
    response_model=ScreenResult,
    summary="Run a Finviz screen with the given filter map.",
    description=(
        "Validates filter keys/values via fincli's chokepoint validator "
        "(unknown -> HTTP 422 via the API exception handler), then runs "
        "the screen and returns the matching stocks."
    ),
    # Declare error envelopes explicitly so polyglot SDK generators
    # (openapi-generator, oapi-codegen, etc.) emit typed error responses
    # for the 422 / 500 / 502 paths defined in spec §5.1. Without this,
    # ``ErrorResponse`` never lands in ``components.schemas`` and
    # consumers fall back to opaque ``map[string]any`` decoding.
    responses={
        422: {"model": ErrorResponse, "description": "Filter validation failed."},
        500: {"model": ErrorResponse, "description": "Unclassified internal error."},
        502: {"model": ErrorResponse, "description": "Upstream Finviz fetch or parse failed."},
    },
)
def run_screen_endpoint(request: ScreenRequest) -> ScreenResult:
    """Validate filters, then bridge to the adapter's run_screen.

    The validator call MUST precede the adapter call. Unknown filter keys
    would otherwise silently drop through ``fincli/utils/quary_builders.py``
    (lines 18-22 skip unregistered keys) and produce a deceptive HTTP 200
    with ``row_count=0`` instead of the spec §5-promised HTTP 422
    validation error. ``validate_filter_pairs`` raises ``click.UsageError``
    on any unknown key/value; the FastAPI exception handler catches it and
    shapes it as ``error_class: "validation"`` (HTTP 422). See the T3 QA
    carryforward and ``docs/features/archive/pipeline-mode-spec.md`` §5
    for the full hazard write-up.

    Args:
        request: Parsed ``ScreenRequest`` with the ``{query_key: value_code}``
            filter map.

    Returns:
        ``ScreenResult`` with row_count, timing metadata, and the matched
        stocks. An empty ``stocks`` list is still a 200 success (spec §5.1)
        — it only means Finviz returned zero rows for valid filters.
    """
    validate_filter_pairs(tuple(request.filters.items()))
    return run_screen(request.filters)
