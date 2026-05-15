"""Click entry point for the Fin CLI stock screener.

Surfaces the screener pipeline as a single-command CLI with five mutually-
exclusive input modes (interactive picker, ``--history`` reload, direct URL
via ``--scrape-link``, structured input via ``--filter`` / ``--filters-json``
/ ``--filters-file``). Adding the structured-input options closes the gap
that prevented fincli from being driven non-interactively in a downstream
pipeline — see ``docs/features/pipeline-mode-spec.md`` §5.1 (Pillar 1).

The CLI is the single normalization point: it collapses the three structured
forms into one canonical JSON string before handing off to
``run_stock_screener`` so the configurator stays single-shape (`filters: str`).
"""

from __future__ import annotations

import json
from pathlib import Path

import click

# Canonical mutual-exclusion message kept as a module constant so it is
# trivially assertable from tests and so the wording stays consistent across
# every input-mode combination. Matches the verbatim text in spec §6.2.
_MUTEX_MSG = (
    "--filter / --filters-json / --filters-file / --history / --scrape-link "
    "are mutually exclusive; pick one input mode."
)


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
@click.pass_context
def run_main(
    ctx: click.Context,
    history: bool = False,
    debug: bool = False,
    scrape_link: str = "",
    filter_pairs: tuple[str, ...] = (),
    filters_json: str = "",
    filters_file: str | None = None,
) -> None:
    """
    Welcome to the Stock Screener CLI!
    """
    # Count the active input modes; mutual exclusion is "at most one set".
    # An empty `filter_pairs` tuple counts as unset; a non-empty one counts
    # as one input mode regardless of how many --filter flags were repeated.
    input_modes_set = sum(
        [
            bool(filter_pairs),
            bool(filters_json),
            bool(filters_file),
            history,
            bool(scrape_link),
        ]
    )
    if input_modes_set > 1:
        raise click.UsageError(_MUTEX_MSG)

    # Collapse the three structured forms into the single JSON string the
    # configurator expects. Empty string means "no structured input" (and
    # combined with no --history / --scrape-link drops to interactive mode).
    filters_str = _normalize_filter_input(filter_pairs, filters_json, filters_file)

    click.echo("Welcome to the Stock Screener CLI!")
    from .main import run_stock_screener

    if ctx.invoked_subcommand is None:
        # Translate schema-rejection errors from `core.converters.json.json_to_tuples`
        # (raised inside `build_config`) into `click.UsageError` so malformed
        # `--filters-json` / `--filters-file` payloads exit 2 with a clean
        # message instead of exit 1 with a Python traceback. Kept in the CLI
        # layer to preserve `core/`'s Click-free purity (see ARCHITECTURE.md
        # Module Map). Contract: docs/features/pipeline-mode-spec.md §7.2
        # (exit-2 for schema-rejection).
        try:
            run_stock_screener(
                history=history,
                debug=debug,
                scrape_link=scrape_link,
                filters=filters_str,
            )
        except ValueError as exc:
            raise click.UsageError(str(exc)) from exc


if __name__ == "__main__":
    run_main()
