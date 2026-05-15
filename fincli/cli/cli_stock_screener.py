"""Interactive filter-selection UI plus early-return path for structured input.

Two changes in `docs/features/pipeline-mode-spec.md` Pillar 1 land here:

  1. **Early-return.** When `Config.filters` is preloaded by the configurator
     (from --filter / --filters-json / --filters-file), skip the interactive
     picker entirely and build the query directly. Without this, structured
     input parses but the picker still prompts.
  2. **Writeback fix.** `filter_history.json` is now overwritten on every
     successful run that produced a non-empty filter set, regardless of input
     mode. The pre-existing code gated the write inside `if config.use_history:`
     which meant it never executed (the read branch already returned). OQ7
     resolution; quiet bug fix Pillar 1 depends on so `--history` stays in
     sync with the new input modes.

`--scrape-link` deliberately skips the writeback (no filter set to record);
that path bypasses this function entirely from `run_stock_screener`.
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from config.config import Config

from ..resource.params.descriptive_params import Descriptive_Params as dp
from ..resource.params.fundamental_params import Fundamental_Params as fp
from ..resource.params.technical_params import Technical_Params as tp
from ..utils.quary_builders import build_stock_screener_query

# Filename written to `Config.history_dir` on every successful run that
# produced filters. Kept as a module constant so the read and write paths
# share one source of truth.
_HISTORY_FILENAME = "filter_history.json"


def _write_history(config: Config, selected_values: dict[str, str]) -> None:
    """Persist `selected_values` to `<history_dir>/filter_history.json`.

    Centralized so every code path that produces filters writes through the
    same chokepoint. Skips silently when `selected_values` is empty (no
    filter set to record) and creates `history_dir` if it doesn't exist.
    """
    if not selected_values:
        return
    history_dir = Path(config.history_dir)
    history_dir.mkdir(parents=True, exist_ok=True)
    history_path = history_dir / _HISTORY_FILENAME
    with open(history_path, "w", encoding="utf-8") as outfile:
        json.dump(selected_values, outfile)


def select_filters_and_values(config: Config):
    # Early-return path for structured input (--filter / --filters-json /
    # --filters-file). The configurator has already populated and validated
    # `config.filters`; build the query and persist the selection so a
    # subsequent `--history` recovers it. Spec §5.1 step 4 + step 6.
    if config.filters and not config.use_history and not config.scrape_link:
        # The early-return branch persists the same dict shape that the
        # interactive branch uses, so `--history` reads it back identically.
        _write_history(config, dict(config.filters))
        return build_stock_screener_query(config.filters)

    # Add checks for use_history
    if config.use_history:
        filepath = Path(config.history_dir) / _HISTORY_FILENAME
        click.echo(f"Fetching user history from filter_history.json {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            selected_values_and_filters = json.load(f)

        query = build_stock_screener_query(selected_values_and_filters.items())
        return query

    options, queryOptions = extract_dict_options([fp, dp, tp])
    click.echo(
        "Available filters (each section is shown one at a time; press Enter to skip a section):"
    )

    selected_filters_indices = []
    selected_filters_indices += prompt_section(fp, options, "Fundamental Params", color="blue")
    selected_filters_indices += prompt_section(dp, options, "Descriptive Params", color="yellow")
    selected_filters_indices += prompt_section(tp, options, "Technical Params", color="red")

    # Select filter values
    selected_values = select_values(selected_filters_indices, queryOptions)

    # Persist on every interactive run that produced a non-empty selection,
    # regardless of `use_history`. (The pre-Pillar-1 code gated this on
    # `use_history`, which meant it never ran — see module docstring + spec
    # §5.1 step 6.)
    _write_history(config, selected_values)

    # Generate the query
    query = build_stock_screener_query(selected_values.items())
    return query


def extract_dict_options(classes):
    options, queryOptions = {}, {}

    for cls in classes:
        for attr_name, attr_value in vars(cls).items():
            if isinstance(attr_value, list) and not attr_name.startswith("__"):
                queryOptions[attr_name] = attr_value[0]
                options[attr_name] = attr_value[1]
    return options, queryOptions


def prompt_section(options_group, options, title, color="blue"):
    click.echo(click.style(f"\nAvailable filters for {title}:"))

    grouped_keys = [
        filter_key for filter_key in options.keys() if filter_key in vars(options_group)
    ]

    if not grouped_keys:
        return []

    for i in range(0, len(grouped_keys), 5):
        formatted = [
            f"{idx + 1}. {grouped_keys[idx]}" for idx in range(i, min(i + 5, len(grouped_keys)))
        ]
        click.echo(click.style(" | ".join(formatted), fg=color))

    input_msg = click.style(
        f"\nEnter the numbers of {title} filters you want "
        "(comma separated, or just press Enter to skip)",
        fg="yellow",
    )
    max_idx = len(grouped_keys)

    while True:
        raw = click.prompt(input_msg, type=str, default="", show_default=False)
        if not raw.strip():
            return []

        try:
            parsed = [int(token.strip()) for token in raw.split(",") if token.strip()]
        except ValueError as exc:
            click.echo(
                click.style(
                    f"Invalid input — expected comma-separated integers ({exc}). Try again.",
                    fg="red",
                )
            )
            continue

        out_of_range = [n for n in parsed if not (1 <= n <= max_idx)]
        if out_of_range:
            click.echo(
                click.style(
                    f"Filter numbers out of range: {out_of_range}. "
                    f"Valid range is 1..{max_idx}. Try again.",
                    fg="red",
                )
            )
            continue

        return [{grouped_keys[n - 1]: options[grouped_keys[n - 1]]} for n in parsed]


def select_values(selected_filters, queryOptions):
    selected_values = {}

    for filter_dict in selected_filters:
        for filter_outer_key, filter_inner_dict in filter_dict.items():
            click.echo(click.style(f"\nAvailable values for {filter_outer_key}:", fg="blue"))
            items_list = list(filter_inner_dict.items())

            for i in range(0, len(items_list), 5):
                items_to_echo = [
                    f"{idx + 1}: {items[0]} - {items[1]}"
                    for idx, items in enumerate(items_list[i : i + 5], start=i)
                ]
                click.echo(click.style(f"{' | '.join(items_to_echo)}", fg="green"))

            value_idx = (
                click.prompt(
                    click.style(f"Select a value for {filter_outer_key}", fg="yellow"), type=int
                )
                - 1
            )
            selected_values[queryOptions[filter_outer_key]] = items_list[value_idx][0]
    return selected_values
