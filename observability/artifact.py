"""On-disk artifact bundles: midas's Tier-3 shape, HTTP-boundary only.

A traced request (``?trace=1`` or ``X-Strade-Trace: 1``) — or, when enabled, a
request that ends >= 500 — writes a bundle folder::

    <root>/<YYYY-MM-DD>/req_<request_id>/
        00-manifest.json   # trigger, method, path, status, latency_ms, ts
        01-request.json    # method/path/query, redacted headers, body (capped)
        02-response.json   # status, redacted headers, body (capped)
        99-logs.jsonl      # this request's log records

Fail-open like midas: a capture/write failure logs a warning and never fails the
request. Secrets never land on disk: auth-bearing headers are redacted and
bodies are capped. Core module — stdlib + starlette types only.
"""

from __future__ import annotations

import base64
import datetime as _dt
import json
import logging
import re
import shutil
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .context import get_request_id, resolve_request_id
from .logging import JsonFormatter

TRACE_HEADER = b"x-strade-trace"
TRACE_QUERY = b"trace"
_TRUTHY = {b"1", b"true", b"yes", b"on"}
BODY_CAP = 64 * 1024  # per captured body
MAX_LOG_RECORDS = 1000  # per bundle
_REDACT_HEADERS = {
    "x-api-key",
    "authorization",
    "cookie",
    "set-cookie",
    "proxy-authorization",
}
_REDACT_QUERY_KEYS = {
    "api_key",
    "apikey",
    "token",
    "secret",
    "password",
    "key",
    "authorization",
}
_DATE_DIR = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_UNSAFE_PATH_CHARS = re.compile(r"[^A-Za-z0-9_.-]")

logger = logging.getLogger("observability.artifact")

# Log-record buffers for in-flight traced requests, keyed by request_id. Each
# request registers its OWN buffer (a list per concurrent request sharing the
# same id — duplicate inbound ids must not merge or overwrite each other's
# bundles); the BundleLogHandler fans a record out to every buffer under its id.
_active: dict[str, list[list[str]]] = {}


def _env_bool(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(value: str | None, default: int) -> int:
    """Parse a non-negative int; a bad value falls back to the default (a config
    typo must not fail app boot — from_env runs at import time in some services)."""
    try:
        return max(0, int(value)) if value else default
    except ValueError:
        logger.warning("invalid ARTIFACTS int %r; using %d", value, default)
        return default


class ArtifactStore:
    """Owns the bundle root, the config switches, and startup retention pruning."""

    def __init__(
        self,
        root: str | Path = "./artifacts",
        *,
        enabled: bool = True,
        on_error: bool = False,
        retention_days: int = 7,
    ) -> None:
        self.root = Path(root)
        self.enabled = enabled
        self.on_error = on_error
        self.retention_days = retention_days
        if enabled:
            self._prune()

    @classmethod
    def from_env(cls, prefix: str) -> ArtifactStore:
        """Build from ``<PREFIX>ARTIFACTS_{ENABLED,DIR,ON_ERROR,RETENTION_DAYS}``."""
        import os

        return cls(
            os.getenv(f"{prefix}ARTIFACTS_DIR") or "./artifacts",
            enabled=_env_bool(os.getenv(f"{prefix}ARTIFACTS_ENABLED"), True),
            on_error=_env_bool(os.getenv(f"{prefix}ARTIFACTS_ON_ERROR"), False),
            retention_days=_env_int(os.getenv(f"{prefix}ARTIFACTS_RETENTION_DAYS"), 7),
        )

    def _prune(self) -> None:
        """Remove date-dirs older than retention_days. Fail-open."""
        try:
            if not self.root.is_dir():
                return
            cutoff = _dt.date.today() - _dt.timedelta(days=self.retention_days)
            for entry in self.root.iterdir():
                if entry.is_dir() and _DATE_DIR.match(entry.name):
                    try:
                        if _dt.date.fromisoformat(entry.name) < cutoff:
                            shutil.rmtree(entry, ignore_errors=True)
                    except ValueError:
                        continue
        except OSError:
            logger.warning("artifact retention prune failed", exc_info=True)

    def bundle_dir(self, request_id: str) -> Path:
        """A fresh bundle dir for this request. Concurrent/repeated requests
        sharing one request_id get a disambiguating suffix instead of merging
        into (and overwriting) the same folder."""
        safe = _UNSAFE_PATH_CHARS.sub("_", request_id)[:128]
        # UTC date to match the manifest ts (no local/UTC split near midnight).
        base = self.root / _dt.datetime.now(_dt.UTC).date().isoformat() / f"req_{safe}"
        if not base.exists():
            return base
        return base.with_name(f"{base.name}-{uuid.uuid4().hex[:6]}")


def _decode_headers(raw: list[tuple[bytes, bytes]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for name_b, value_b in raw:
        name = name_b.decode("latin-1").lower()
        out[name] = "<redacted>" if name in _REDACT_HEADERS else value_b.decode("latin-1")
    return out


def _redact_query(query_string: bytes) -> str:
    """Redact values of credential-shaped query keys (defensive — no Strade
    service takes secrets via query today, but a future ?token= must not land
    on disk verbatim)."""
    parts = []
    for pair in query_string.split(b"&"):
        key, sep, _val = pair.partition(b"=")
        if sep and key.decode("latin-1").lower() in _REDACT_QUERY_KEYS:
            parts.append(key + b"=<redacted>")
        else:
            parts.append(pair)
    return b"&".join(parts).decode("latin-1")


def _encode_body(buf: bytes, truncated: bool) -> dict[str, Any]:
    try:
        return {"text": buf.decode("utf-8"), "truncated": truncated}
    except UnicodeDecodeError:
        return {"base64": base64.b64encode(buf).decode("ascii"), "truncated": truncated}


def _is_traced(scope: Scope) -> bool:
    headers = dict(scope.get("headers") or [])
    value = headers.get(TRACE_HEADER)
    if value is not None and value.strip().lower() in _TRUTHY:
        return True
    for pair in (scope.get("query_string") or b"").split(b"&"):
        key, _, val = pair.partition(b"=")
        if key == TRACE_QUERY and val.strip().lower() in _TRUTHY:
            return True
    return False


class BundleLogHandler(logging.Handler):
    """Routes log records of in-flight traced requests into their bundle buffer."""

    def __init__(self, request_id_getter: Callable[[], str | None]) -> None:
        super().__init__()
        self._getter = request_id_getter
        self._fmt = JsonFormatter()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            rid = getattr(record, "request_id", None)
            if not rid or rid == "-":
                rid = self._getter()
            buffers = _active.get(rid) if rid else None
            if not buffers:
                return
            line = self._fmt.format(record)
            for buf in buffers:  # concurrent same-id requests each get the line
                if len(buf) < MAX_LOG_RECORDS:
                    buf.append(line)
        except Exception:  # a log hook must never raise
            pass


class ArtifactMiddleware:
    """Raw-ASGI capture middleware. Sits just INSIDE the request-id middleware so
    the correlation id is already bound when a bundle opens.

    ``capture_logger`` names the logger whose subtree feeds ``99-logs.jsonl``
    ("" = root; borker passes "borker" since its tree doesn't propagate to root).
    """

    def __init__(
        self,
        app: ASGIApp,
        store: ArtifactStore,
        *,
        service: str = "",
        request_id_getter: Callable[[], str | None] = get_request_id,
        capture_logger: str = "",
    ) -> None:
        self.app = app
        self.store = store
        self.service = service
        self._getter = request_id_getter
        target = logging.getLogger(capture_logger)
        if not any(isinstance(h, BundleLogHandler) for h in target.handlers):
            target.addHandler(BundleLogHandler(request_id_getter))

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self.store.enabled:
            await self.app(scope, receive, send)
            return

        manual = _is_traced(scope)
        if not manual and not self.store.on_error:
            await self.app(scope, receive, send)
            return

        rid = resolve_request_id(scope) or self._getter() or "unknown"
        # This request's OWN log buffer — concurrent requests sharing an id each
        # register one, so bundles never merge (see the _active comment).
        log_buf: list[str] = []
        _active.setdefault(rid, []).append(log_buf)
        start = time.perf_counter()
        req_body = bytearray()
        resp_body = bytearray()
        state: dict[str, Any] = {
            "status": 0,
            "resp_headers": [],
            "req_trunc": False,
            "resp_trunc": False,
        }

        async def receive_wrapper() -> Message:
            message = await receive()
            if message["type"] == "http.request":
                chunk = message.get("body", b"") or b""
                room = BODY_CAP - len(req_body)
                if room > 0:
                    req_body.extend(chunk[:room])
                if len(chunk) > room:
                    state["req_trunc"] = True
            return message

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                state["status"] = message["status"]
                state["resp_headers"] = list(message.get("headers") or [])
            elif message["type"] == "http.response.body":
                chunk = message.get("body", b"") or b""
                room = BODY_CAP - len(resp_body)
                if room > 0:
                    resp_body.extend(chunk[:room])
                if len(chunk) > room:
                    state["resp_trunc"] = True
            await send(message)

        try:
            await self.app(scope, receive_wrapper, send_wrapper)
        except Exception as exc:
            # An unhandled exception escapes to Starlette's ServerErrorMiddleware
            # (outside us), which builds the 500 — we never see that response, so
            # record the failure here and re-raise.
            state["status"] = int(state["status"]) or 500
            state["error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            buffers = _active.get(rid)
            if buffers is not None:
                if log_buf in buffers:
                    buffers.remove(log_buf)
                if not buffers:
                    _active.pop(rid, None)
            log_lines = log_buf
            status = int(state["status"])
            trigger: str | None
            if manual:
                trigger = "manual"
            elif status >= 500 and self.store.on_error:
                trigger = "on_error"
            else:
                trigger = None
            if trigger is not None:
                self._write(scope, rid, trigger, start, req_body, resp_body, state, log_lines)

    def _write(
        self,
        scope: Scope,
        rid: str,
        trigger: str,
        start: float,
        req_body: bytearray,
        resp_body: bytearray,
        state: dict[str, Any],
        log_lines: list[str],
    ) -> None:
        try:
            bundle = self.store.bundle_dir(rid)
            bundle.mkdir(parents=True, exist_ok=True)
            method = scope.get("method", "")
            path = scope.get("path", "")
            manifest = {
                "service": self.service,
                "request_id": rid,
                "ts": _dt.datetime.now(_dt.UTC).isoformat().replace("+00:00", "Z"),
                "trigger": trigger,
                "method": method,
                "path": path,
                "status": state["status"],
                "latency_ms": round((time.perf_counter() - start) * 1000.0, 2),
            }
            if state.get("error"):
                manifest["error"] = state["error"]
            request_doc = {
                "method": method,
                "path": path,
                "query": _redact_query(scope.get("query_string") or b""),
                "headers": _decode_headers(scope.get("headers") or []),
                "client": list(scope.get("client") or ()),
                "body": _encode_body(bytes(req_body), state["req_trunc"]),
            }
            response_doc = {
                "status": state["status"],
                "headers": _decode_headers(state["resp_headers"]),
                "body": _encode_body(bytes(resp_body), state["resp_trunc"]),
            }
            for name, doc in (
                ("00-manifest.json", manifest),
                ("01-request.json", request_doc),
                ("02-response.json", response_doc),
            ):
                (bundle / name).write_text(
                    json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8"
                )
            (bundle / "99-logs.jsonl").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
        except Exception:  # fail-open: capture must never fail the request
            logger.warning("artifact bundle write failed for %s", rid, exc_info=True)
