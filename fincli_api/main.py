"""FastAPI application entry point for the Fin CLI HTTP API.

Hosts the `app` instance discovered by uvicorn and ASGI tooling, plus the
`main()` callable bound to the ``fincli-api`` console script.

T1 deliberately ships an empty router set — routes, models, adapters, and
exception handlers land in T2-T4 per
``docs/features/fincli-api-plan.md``. FastAPI still auto-generates a valid
OpenAPI 3.0 document for an empty app, which T1's acceptance gates rely on
to prove the wiring is sound.
"""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from fincli_api.config import ApiConfig

# Constants kept module-level so the OpenAPI dump script and tests can
# reference the same source of truth without instantiating the app.
API_TITLE = "Fin CLI HTTP API"
API_VERSION = "0.1.0"

app = FastAPI(title=API_TITLE, version=API_VERSION)

# Routes wired in T4 (filters / screens / meta) — kept empty here so this
# module stays the minimal "compose the app" file. Exception handlers also
# land in T4d.


def main() -> None:
    """Run the API server via uvicorn using `ApiConfig` defaults / env overrides.

    Bound to the ``fincli-api`` console script. Reload is disabled by
    design — dev iteration uses ``uvicorn fincli_api.main:app --reload``
    directly; the script entry is the "just run it" path. Spec §3.3.
    """
    config = ApiConfig()
    uvicorn.run(
        "fincli_api.main:app",
        host=config.host,
        port=config.port,
        log_level=config.log_level,
        reload=False,
    )
