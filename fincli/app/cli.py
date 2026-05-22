"""Click entry point for the Fin CLI stock screener.

Surfaces the screener pipeline as a single-command CLI with six mutually-
exclusive input modes (interactive picker, ``--history`` reload, direct URL
via ``--scrape-link``, structured input via ``--filter`` / ``--filters-json``
/ ``--filters-file``, and the metadata-dump mode ``--list-filters``). Adding
the structured-input options closes the gap that prevented fincli from being
driven non-interactively in a downstream pipeline — see
``docs/features/archive/pipeline-mode-spec.md`` §5.1 (Pillar 1). The
``--list-filters --json`` mode (``docs/features/archive/list-filters-spec.md``)
short-circuits the screener pipeline entirely and emits the filter inventory
as machine-readable JSON for non-Python consumers.

The CLI is the single normalization point: it collapses the three structured
forms into one canonical JSON string before handing off to
``run_stock_screener`` so the configurator stays single-shape (`filters: str`).
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from config.config import STDOUT_SENTINEL

# Canonical mutex message — change this and tests/unit/app/test_cli_pipeline.py
# may need updating in parallel. Kept as a module constant so it is trivially
# assertable from tests and so the wording stays consistent across every
# input-mode combination. Matches the verbatim text in
# docs/features/archive/list-filters-spec.md §6 (extended mutex set).
_MUTEX_MSG = (
    "--filter / --filters-json / --filters-file / --history / --scrape-link / "
    "--list-filters are mutually exclusive; pick one input mode."
)

# Schema version for the ``--list-filters --json`` payload. Mirrors the
# JSON_SUMMARY_SCHEMA_VERSION pattern in ``fincli/app/main.py``: a module-public
# constant (no leading underscore) so tests and external integrators can import
# it directly and assert on the wire value. Spec §5.2 stability policy:
# additions to the payload are non-breaking (schema_version stays 1);
# renames/removals/type changes bump this.
LIST_FILTERS_SCHEMA_VERSION = 1


def _normalize_filter_input(
    filter_pairs: tuple[str, ...],
    filters_json: str,
    filters_file: str | None,
) -> str:
    """Collapse the three structured-input forms into one JSON string.

    Args:
        filter_pairs: Output of repeated ``--filter key=value`` flags.
        filters_json: Inline JSON literal from ``--filters-json``.
        filters_file: Path from ``--filters-file`` (validated to exist by
            Click before this is called).

    Returns:
        A canonical flat-object JSON string, or ``""`` if none of the three
        inputs were set (interactive-mode marker).

    Raises:
        click.UsageError: If a ``--filter`` token is malformed (missing
            ``=``, empty key, or empty value). Empty value-codes are legal
            in the registry as the "Any" sentinel, but accepting them at
            the CLI hides typos like ``--filter fa_pe=`` so we reject.
    """
    # At most one of the three is non-default at this point — the input-mode
    # counter in `run_main` guarantees mutual exclusion; the zero-input case
    # falls through to the trailing `return ""` (interactive-mode marker).
    if filter_pairs:
        normalized: dict[str, str] = {}
        for token in filter_pairs:
            if "=" not in token:
                raise click.UsageError(f"Invalid --filter token {token!r}: expected 'key=value'.")
            key, _, value = token.partition("=")
            if not key:
                raise click.UsageError(f"Invalid --filter token {token!r}: empty key.")
            if not value:
                raise click.UsageError(f"Invalid --filter token {token!r}: empty value.")
            normalized[key] = value
        return json.dumps(normalized)

    if filters_json:
        # Pass through verbatim; `json_to_tuples` will validate the shape and
        # raise ValueError if it is not a flat object.
        return filters_json

    if filters_file:
        # Click already verified the path exists and is readable. Read with
        # an explicit encoding so the test suite (and Windows hosts) behave
        # predictably regardless of system locale.
        return Path(filters_file).read_text(encoding="utf-8")

    return ""


def _emit_filter_inventory() -> None:
    """Dump the filter inventory as JSON to stdout (caller handles exit 0).

    Builds the 3-key payload contract (``schema_version`` + ``keys`` +
    ``filters``) per ``docs/features/archive/list-filters-spec.md`` §5.2 + §5.5
    (amended per gpt-5.5 deep-think to surface a canonical ``keys``
    ordering that polyglot consumers can iterate against — Go's
    ``encoding/json`` decode into ``map[string]T`` randomizes iteration
    order, so the ``keys`` list is the contract consumers index into
    ``filters[key]`` with).

    Uses a local import (``list_valid_filters_with_labels``) so importing
    this module stays cheap for non-list-filters invocations, mirroring the
    existing local import of ``run_stock_screener``. ``json`` is already at
    module scope (used by ``_normalize_filter_input``), so re-importing it
    here would be redundant.
    """
    from fincli.resource.params.validators import list_valid_filters_with_labels

    inventory = list_valid_filters_with_labels()
    payload: dict[str, object] = {
        "schema_version": LIST_FILTERS_SCHEMA_VERSION,
        # Canonical ordering contract per spec §5.2: identical membership to
        # ``filters.keys()`` and same iteration order.
        "keys": list(inventory.keys()),
        "filters": inventory,
    }
    # Single-line JSON (no ``indent=``) + trailing newline from ``click.echo``.
    # ``ensure_ascii=False`` keeps the output clean if labels ever contain
    # non-ASCII characters; today's labels are all ASCII.
    click.echo(json.dumps(payload, ensure_ascii=False))


@click.group(invoke_without_command=True)
@click.option("--history", "--hist", is_flag=True, help="Use filters of recent search.")
@click.option("--debug", is_flag=True, help="Display details logging.")
@click.option(
    "--scrape-link",
    default="",
    help=(
        "Direct Finviz screener URL; bypasses interactive filter selection. "
        "Mutually exclusive with --history / --filter / --filters-json / --filters-file."
    ),
)
@click.option(
    "--filter",
    "filter_pairs",
    multiple=True,
    help=("Filter as 'key=value'; repeatable. Example: --filter fa_pe=u20 --filter sec=energy"),
)
@click.option(
    "--filters-json",
    default="",
    help=(
        'Inline JSON dict of filters, e.g. --filters-json \'{"fa_pe":"u20"}\'. '
        "Mutually exclusive with the other input-mode flags."
    ),
)
@click.option(
    "--filters-file",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    default=None,
    help=(
        "Path to a JSON file containing the filter dict. "
        "Mutually exclusive with the other input-mode flags."
    ),
)
@click.option(
    "--output",
    "-o",
    "output_path",
    default="",
    help=(
        "Exact CSV destination. Parent dir must exist. No timestamp added; "
        "overwrites if the file exists. Use '-' to stream CSV to stdout. "
        "Orthogonal to all input-mode flags."
    ),
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    help=(
        "Suppress human chatter (welcome banner + INFO/DEBUG console lines). "
        "Warnings and errors still surface. Does not change --debug level; "
        "debug records still land in logs/activity.log. Orthogonal to --output."
    ),
)
@click.option(
    "--json-summary",
    "json_summary",
    is_flag=True,
    help=(
        "Emit a single-line JSON summary of the run at end. Goes to stdout "
        "by default; routed to stderr when --output - streams CSV on stdout."
    ),
)
@click.option(
    "--list-filters",
    "list_filters",
    is_flag=True,
    help=(
        "Dump the filter inventory as JSON to stdout and exit 0. "
        "Requires --json (the only currently-supported format). "
        "Mutually exclusive with all input-mode flags. "
        "--output / --quiet / --debug / --json-summary are ignored in this mode."
    ),
)
@click.option(
    "--json",
    "json_format",
    is_flag=True,
    help=(
        "Format selector for --list-filters; the only currently-supported "
        "format. Silently ignored when --list-filters is not set."
    ),
)
@click.pass_context
def run_main(
    ctx: click.Context,
    history: bool = False,
    debug: bool = False,
    scrape_link: str = "",
    filter_pairs: tuple[str, ...] = (),
    filters_json: str = "",
    filters_file: str | None = None,
    output_path: str = "",
    quiet: bool = False,
    json_summary: bool = False,
    list_filters: bool = False,
    json_format: bool = False,
) -> None:
    """
    Welcome to the Stock Screener CLI!
    """
    # Count the active input modes; mutual exclusion is "at most one set".
    # An empty `filter_pairs` tuple counts as unset; a non-empty one counts
    # as one input mode regardless of how many --filter flags were repeated.
    # `--list-filters` joins the mutex set as a sixth alternative entry mode
    # (metadata-dump instead of screen-run) — spec §6 extended mutex set.
    input_modes_set = sum(
        [
            bool(filter_pairs),
            bool(filters_json),
            bool(filters_file),
            history,
            bool(scrape_link),
            list_filters,
        ]
    )
    if input_modes_set > 1:
        raise click.UsageError(_MUTEX_MSG)

    # --list-filters short-circuit: dump the filter inventory and exit 0
    # WITHOUT running the screener pipeline. Placed after the mutex check
    # (so combining --list-filters with an input mode still fails fast) but
    # BEFORE banner emission and BEFORE the local `run_stock_screener`
    # import — that import is intentionally lazy and we keep it lazy on the
    # metadata-dump path too. --output / --quiet / --debug / --json-summary
    # are orthogonal no-ops in this mode (spec §5.1 routing block + §7.2).
    if list_filters:
        if not json_format:
            # --json is the only currently-supported format; rejecting bare
            # --list-filters keeps the door open for future --yaml / --text.
            raise click.UsageError(
                "--list-filters requires --json (the only currently-supported format)."
            )
        _emit_filter_inventory()
        ctx.exit(0)

    # Collapse the three structured forms into the single JSON string the
    # configurator expects. Empty string means "no structured input" (and
    # combined with no --history / --scrape-link drops to interactive mode).
    filters_str = _normalize_filter_input(filter_pairs, filters_json, filters_file)

    # Suppress the human-friendly banner when CSV bytes own stdout (`--output -`)
    # or when the operator requested ``--quiet``. Even routing the banner to
    # stderr under ``--output -`` would be noise for the pipe consumer; the
    # banner has zero informational value to a downstream tool. ``--quiet``
    # extends this suppression to file-output modes as well so pipeline
    # integrators that want a clean stdout for the JSON summary can use it.
    # Spec §7.3 bullet 5 (no other bytes on stdout) and §7.4 (--quiet
    # suppresses the welcome banner and progress lines).
    if not quiet and output_path != STDOUT_SENTINEL:
        click.echo("Welcome to the Stock Screener CLI!")
    from .main import run_stock_screener

    if ctx.invoked_subcommand is None:
        # Translate schema-rejection errors from `core.converters.json.json_to_tuples`
        # (raised inside `build_config`) into `click.UsageError` so malformed
        # `--filters-json` / `--filters-file` payloads exit 2 with a clean
        # message instead of exit 1 with a Python traceback. Kept in the CLI
        # layer to preserve `core/`'s Click-free purity (see ARCHITECTURE.md
        # Module Map). Contract: docs/features/archive/pipeline-mode-spec.md §7.2
        # (exit-2 for schema-rejection).
        try:
            run_stock_screener(
                history=history,
                debug=debug,
                scrape_link=scrape_link,
                filters=filters_str,
                output_path=output_path,
                quiet=quiet,
                json_summary=json_summary,
            )
        except ValueError as exc:
            raise click.UsageError(str(exc)) from exc


if __name__ == "__main__":
    run_main()
