import json
import os
import click
from config.config import Config
from ..resource.params.fundamental_params import Fundamental_Params as fp
from ..resource.params.descriptive_params import Descriptive_Params as dp
from ..resource.params.technical_params import Technical_Params as tp
from ..utils.quary_builders import build_stock_screener_query


def select_filters_and_values(config: Config):

    # Add checks for use_history
    if config.use_history:
        filepath = os.path.join(
            os.path.realpath("fincli"), "stock_screening", "local_history", "filter_history.json"
        )
        click.echo(f"Fetching user history from filter_history.json {filepath}")

        with open(filepath, "r") as f:
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

    # Save selected values
    if config.use_history:
        with open(filepath, "w") as outfile:
            json.dump(selected_values, outfile)

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
