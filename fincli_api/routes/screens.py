"""POST /screens route — run a Finviz screen with structured filters."""

from __future__ import annotations

from fastapi import APIRouter

from fincli.resource.params.validators import validate_filter_pairs
from fincli_api.adapters import run_screen, run_screen_from_link
from fincli_api.models import ErrorResponse, ScreenRequest, ScreenResult

router = APIRouter()


@router.post(
    "/screens",
    response_model=ScreenResult,
    summary="Run a Finviz screen from a filter map or a direct scrape_link URL.",
    description=(
        "Exactly one of `filters` or `scrape_link` must be set (422 if both or "
        "neither — see ScreenRequest). `filters` is validated via fincli's "
        "chokepoint validator (unknown key/value -> HTTP 422 via the API exception "
        "handler) before the screen runs. `scrape_link` is fetched verbatim with NO "
        "filter-inventory validation (mirrors the CLI's --scrape-link) and is "
        "restricted to finviz.com and its subdomains (SSRF guard, enforced by "
        "ScreenRequest at request-parse time)."
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
    """Branch on the request shape, then bridge to the matching adapter.

    ``ScreenRequest``'s own validator already guarantees exactly one of
    ``filters`` / ``scrape_link`` is set (both-set / neither-set is
    rejected at request-parse time as a standard 422, before this handler
    ever runs) — see that model's docstring for why that's a distinct
    envelope from the ``ErrorResponse`` used below.

    The ``scrape_link`` branch skips ``validate_filter_pairs`` entirely:
    there is no filter map to validate, and the URL is opaque (same as the
    CLI's ``--scrape-link``). The ``filters`` branch keeps the existing
    validator-first ordering: ``validate_filter_pairs`` MUST precede the
    adapter call, or unknown filter keys would otherwise silently drop
    through ``fincli/utils/quary_builders.py`` (lines 18-22 skip
    unregistered keys) and produce a deceptive HTTP 200 with
    ``row_count=0`` instead of the spec §5-promised HTTP 422 validation
    error. ``validate_filter_pairs`` raises ``click.UsageError`` on any
    unknown key/value; the FastAPI exception handler catches it and shapes
    it as ``error_class: "validation"`` (HTTP 422). See the T3 QA
    carryforward and ``docs/features/archive/pipeline-mode-spec.md`` §5
    for the full hazard write-up.

    Args:
        request: Parsed ``ScreenRequest`` — either the ``{query_key:
            value_code}`` filter map or a ``scrape_link`` URL.

    Returns:
        ``ScreenResult`` with row_count, timing metadata, and the matched
        stocks. An empty ``stocks`` list is still a 200 success (spec §5.1)
        — it only means Finviz returned zero rows.
    """
    if request.scrape_link is not None:
        return run_screen_from_link(request.scrape_link)

    # ScreenRequest's validator guarantees `filters` is populated whenever
    # `scrape_link` is not — narrow the Optional for mypy.
    filters = request.filters
    assert filters is not None
    validate_filter_pairs(tuple(filters.items()))
    return run_screen(filters)
