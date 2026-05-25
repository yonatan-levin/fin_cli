"""Generate / verify the committed OpenAPI 3.0 snapshot for the Fin CLI API.

Run modes:
    python scripts/dump_openapi.py            # regenerate docs/api/openapi.{yaml,json}
    python scripts/dump_openapi.py --check    # compare current generation vs. on-disk
                                              # snapshot; exit 1 if they differ

The committed snapshot at ``docs/api/openapi.yaml`` is the source of truth
for downstream consumers (Postman import target, contract diff in PRs).
The JSON sibling at ``docs/api/openapi.json`` is convenience for tools that
prefer JSON. Spec § 7 ("docs/api/openapi.yaml row"); plan T6 commits the
snapshot — T1 only ships this script.

The script is intentionally idempotent: running it twice in a row produces
byte-identical files. The ``--check`` mode is the same comparison wrapped
in an exit code, suitable for CI / pre-commit hooks.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

# Repo-root-relative output paths. Importing this script as a module is not
# supported; it expects to be run via ``python scripts/dump_openapi.py`` from
# the repo root (or via the ``__main__`` block below).
REPO_ROOT = Path(__file__).resolve().parent.parent
OPENAPI_DIR = REPO_ROOT / "docs" / "api"
YAML_PATH = OPENAPI_DIR / "openapi.yaml"
JSON_PATH = OPENAPI_DIR / "openapi.json"


def _load_openapi() -> dict[str, Any]:
    """Import the FastAPI app and return its OpenAPI dict.

    Deferred import so ``--help`` works even without the API deps installed
    (useful for CI cache warmers and IDE tooling). The import does NOT
    bind any network sockets — ``FastAPI(...)`` is a pure constructor.
    """
    from fincli_api.main import app

    return app.openapi()


def _render(spec: dict[str, Any]) -> tuple[str, str]:
    """Render the OpenAPI dict to deterministic YAML and JSON strings.

    Determinism rules:
        - YAML: ``sort_keys=False`` to preserve FastAPI's insertion order
          (which mirrors the order routes/models were declared, the most
          human-readable choice). ``default_flow_style=False`` for block
          style. ``allow_unicode=True`` so non-ASCII descriptions survive.
        - JSON: ``indent=2`` + ``sort_keys=False`` + ``ensure_ascii=False``
          for glyph parity with the YAML sibling (the em-dash in module
          docstrings round-trips as the literal character in both files
          rather than ``\\u2014`` in JSON only). Trailing newline for
          POSIX-friendly diffs.
    """
    yaml_text = yaml.safe_dump(
        spec,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
    )
    json_text = json.dumps(spec, indent=2, sort_keys=False, ensure_ascii=False) + "\n"
    return yaml_text, json_text


def _write_snapshot(yaml_text: str, json_text: str) -> None:
    """Write the rendered snapshot to ``docs/api/`` (creating dir if needed)."""
    OPENAPI_DIR.mkdir(parents=True, exist_ok=True)
    YAML_PATH.write_text(yaml_text, encoding="utf-8", newline="\n")
    JSON_PATH.write_text(json_text, encoding="utf-8", newline="\n")


def _check_snapshot(yaml_text: str, json_text: str) -> int:
    """Compare in-memory render vs. on-disk snapshot; return process exit code.

    Returns ``0`` on match, ``1`` on mismatch (or missing snapshot). The
    mismatch message names the divergent file so CI logs point at the fix
    target without forcing the user to diff manually.
    """
    for path, expected in ((YAML_PATH, yaml_text), (JSON_PATH, json_text)):
        if not path.exists():
            print(f"missing snapshot: {path} (run without --check to generate)", file=sys.stderr)
            return 1
        actual = path.read_text(encoding="utf-8")
        if actual != expected:
            print(
                f"snapshot drift: {path} differs from current FastAPI app.openapi() output; "
                "run scripts/dump_openapi.py to refresh",
                file=sys.stderr,
            )
            return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    """Argparse entry point. Returns process exit code (0 success, 1 drift)."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify on-disk snapshot matches current FastAPI app.openapi(); "
        "exit 1 on mismatch. Use as a CI / pre-commit gate.",
    )
    args = parser.parse_args(argv)

    spec = _load_openapi()
    yaml_text, json_text = _render(spec)

    if args.check:
        return _check_snapshot(yaml_text, json_text)

    _write_snapshot(yaml_text, json_text)
    print(f"wrote {YAML_PATH.relative_to(REPO_ROOT)}")
    print(f"wrote {JSON_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
