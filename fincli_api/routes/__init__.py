"""HTTP routers for the Fin CLI API.

Public re-exports so ``fincli_api.main`` can include all three routers
via the package root rather than reaching into each submodule. Batched
here after the parallel T4a/T4b/T4c BACKEND wave to avoid 3-way write
conflicts on this file.

Each router exposes its own path (``/filters``, ``/screens``,
``/healthz``); main.py owns only the inclusion order.
"""

from fincli_api.routes.filters import router as filters_router
from fincli_api.routes.meta import router as meta_router
from fincli_api.routes.screens import router as screens_router

__all__ = [
    "filters_router",
    "meta_router",
    "screens_router",
]
