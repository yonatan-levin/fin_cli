"""FastAPI application entry point for the Fin CLI HTTP API.

Hosts the `app` instance discovered by uvicorn and ASGI tooling, plus the
`main()` callable bound to the ``fincli-api`` console script.

Composes the app from the three T4 routers (filters / screens / meta)
plus T4d's classifier-driven exception handler. Each router is
self-contained; this module owns only the wiring.
"""

from __future__ import annotations

import logging
import os
import sys

import uvicorn
from fastapi import FastAPI

from fincli_api.config import ApiConfig
from fincli_api.exception_handlers import register_exception_handlers
from fincli_api.routes import filters_router, meta_router, screens_router
from observability import ArtifactStore, configure_logging, install_observability

# Constants kept module-level so the OpenAPI dump script and tests can
# reference the same source of truth without instantiating the app.
API_TITLE = "Fin CLI HTTP API"
API_VERSION = "0.1.0"

app = FastAPI(title=API_TITLE, version=API_VERSION)

# Observability (workspace standard): JSON logs on stderr (stdout stays clean for
# the CLI's --json output), request-id correlation, and the health triad +
# Prometheus /metrics. The existing `/healthz` liveness route (meta_router) is
# kept alongside the standard `/health`.
configure_logging(
    level=os.getenv("FINCLI_API_LOG_LEVEL", "info"),
    fmt=os.getenv("FINCLI_API_LOG_FORMAT", "json"),
    stream=sys.stderr,
)
# The bespoke Singleton logger (logger/logger.py) attaches its own console/file
# handlers to these named loggers with propagate=True. Stop them propagating to
# the root JSON handler so a screener log line reached via the API is not ALSO
# re-emitted as JSON on stderr (it keeps its own console/file output). The CLI
# path avoids this by not reconfiguring root at all.
for _singleton_logger in ("TYPER", "LOGGER", "JSON_LOGGER"):
    logging.getLogger(_singleton_logger).propagate = False
# Artifact capture (?trace=1 / X-Strade-Trace / on-error per FINCLI_API_ARTIFACTS_*).
# Module-level so tests can repoint `artifact_store.root` at a tmp dir.
artifact_store = ArtifactStore.from_env("FINCLI_API_")
install_observability(
    app,
    service="fincli_api",
    version=API_VERSION,
    namespace="fincli",
    artifacts=artifact_store,
)

# Routers are mounted at the app root (no prefix). Each router declares
# its own path (`/filters`, `/screens`, `/healthz`); main.py owns only
# the inclusion order, which incidentally determines OpenAPI ordering.
app.include_router(filters_router)
app.include_router(screens_router)
app.include_router(meta_router)

# Classifier-driven exception handler (spec §5) — single seat that maps
# any uncaught exception through fincli.app.exit_codes.classify into the
# correct HTTP status + ErrorResponse envelope.
register_exception_handlers(app)


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
