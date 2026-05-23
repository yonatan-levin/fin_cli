"""GET /filters route — dumps the full Finviz filter inventory."""

from __future__ import annotations

from fastapi import APIRouter

from fincli_api.adapters import get_filter_inventory
from fincli_api.models import ErrorResponse, FilterInventory

router = APIRouter()


@router.get(
    "/filters",
    response_model=FilterInventory,
    summary="List all valid Finviz filter keys with labels and value codes.",
    description=(
        "Returns the full filter inventory matching `fincli --list-filters --json`. "
        "Polyglot consumers should iterate the `keys` array (not the `filters` map "
        "directly) to lock iteration order — Go's `encoding/json` decode-into-map "
        "randomizes key order, so the explicit `keys` list is the canonical sequence."
    ),
    # Declare the only realistic failure envelope here (no upstream / no
    # validation surface — the inventory load is in-process). Surfacing
    # 500 is enough to pull ``ErrorResponse`` into ``components.schemas``
    # for polyglot SDK generators.
    responses={
        500: {"model": ErrorResponse, "description": "Unclassified internal error."},
    },
)
def list_filters() -> FilterInventory:
    """Return the full Finviz filter inventory.

    Thin wrapper over the adapter; no HTTP-layer logic. Any exception raised
    by the adapter propagates so the global handler (T4d) can map it via
    ``classify()`` to the appropriate status code.

    Returns:
        FilterInventory: filter keys, per-key labels, and value-code maps.
    """
    return get_filter_inventory()
