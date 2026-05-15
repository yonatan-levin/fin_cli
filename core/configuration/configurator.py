import json
import os
from pathlib import Path

from config.config import Config
from fincli.resource.params.validators import validate_filter_pairs

from ..converters.json import json_to_tuples


def build_config(
    use_history: bool = False,
    filters: str = "",
    scrape_link: str = "",
    output_path: str = "",
) -> Config:
    """Create the configuration.

    Args:
        use_history: When True, reload the most recent selection from
            ``<Config.history_dir>/filter_history.json``. Wins over `filters`.
        filters: A JSON string in the canonical flat-object shape (see
            ``core.converters.json.json_to_tuples``). Validated against the
            registered Finviz filter inventory after parse — unknown keys or
            values raise ``click.UsageError`` (CLI exit 2).
        scrape_link: A direct Finviz URL that bypasses query construction.
            Filter validation is skipped when this is set (URL is opaque).
        output_path: Caller-pinned CSV destination from ``--output PATH`` (or
            the ``-`` sentinel for stdout streaming). Empty string means "no
            pin"; ``Config.file_path`` then falls through to the
            ``FINCLI_OUTPUT_DIR`` env override or the default. Spec §5.2.

    Returns:
        A populated ``Config`` instance.
    """
    config = Config()

    history_dir_env = os.getenv("HISTORY_DIR")
    if history_dir_env:
        config.history_dir = Path(history_dir_env)

    # `FINCLI_OUTPUT_DIR` is the env-var tier of the Pillar-2 precedence chain
    # (spec §5.2). Mirrors the `HISTORY_DIR` block above. Loses to an explicit
    # `--output PATH` because `Config.file_path` checks `output_path` first.
    output_dir_env = os.getenv("FINCLI_OUTPUT_DIR")
    if output_dir_env:
        config.output_dir = Path(output_dir_env)

    # Propagate the direct-URL bypass into Config so downstream orchestration
    # can short-circuit query construction. Empty string means "interactive flow".
    if scrape_link:
        config.scrape_link = scrape_link

    # Caller-pinned output destination (Pillar 2). Empty string means "fall
    # through to env / default"; the `-` sentinel signals stdout streaming
    # (resolved at the orchestrator boundary, not here).
    if output_path:
        config.output_path = output_path

    if use_history:
        config.use_history = use_history

        filepath = config.history_dir / "filter_history.json"
        with open(filepath, "r") as f:
            history_filters = json.load(f)
            config.filters = tuple(history_filters.items())

    if filters != "" and not use_history:
        config.filters = json_to_tuples(filters)
        # Single chokepoint for structured-input validation. Unknown keys or
        # values raise ``click.UsageError`` here, which the Click runner
        # surfaces to the user as exit 2 with a helpful message. See
        # docs/features/pipeline-mode-spec.md §5.1 step 5.
        validate_filter_pairs(config.filters)

    return config
