"""Runtime configuration for the Fin CLI HTTP API server.

Pydantic Settings model so host/port/log-level can be overridden via
environment variables (prefix ``FINCLI_API_``) without code changes — e.g.
``FINCLI_API_PORT=9000 fincli-api``. Defaults are localhost-only per the
spec's deployment posture (§3.4) — there is no production hardening here,
and binding to a public interface is an explicit caller decision.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiConfig(BaseSettings):
    """Server configuration knobs surfaced via environment variables.

    Attributes:
        host: Network interface uvicorn binds. Defaults to loopback per
            spec §3.4 (localhost only; no auth, no TLS, no rate limits).
        port: TCP port uvicorn binds. Default 8000 matches the spec's
            Postman / curl examples.
        log_level: uvicorn's log level (``critical``/``error``/``warning``/
            ``info``/``debug``/``trace``). Does not affect the fincli
            singleton logger — that has its own level set by the API
            request lifecycle in later tasks.
    """

    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "info"

    model_config = SettingsConfigDict(env_prefix="FINCLI_API_", extra="ignore")
