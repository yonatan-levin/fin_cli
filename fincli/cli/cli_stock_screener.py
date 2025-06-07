import json
import os
import click
from typing import Union
from config.config import Config
from shared.infrastructure.config import BaseConfig
from ..resource.params.fundamental_params import Fundamental_Params as fp
from ..resource.params.descriptive_params import Descriptive_Params as dp
from ..resource.params.technical_params import Technical_Params as tp
from ..utils.quary_builders import build_stock_screener_query


def select_filters_and_values(config: Union[Config, BaseConfig]):
    # Define filepath here so it's available throughout the function
    filepath = os.path.join(os.path.realpath('fincli'), "stock_screening",
                            "local_history", 'filter_history.json')

    # Add checks for use_history
    if config.use_history:
        click.echo(f"Fetching user history from filter_history.json {filepath}")

        with open(filepath, 'r') as f:
            selected_values_and_filters = json.load(f)

        query = build_stock_screener_query(selected_values_and_filters.items())
        return query

    options, queryOptions = extract_dict_options([fp, dp, tp])
    click.echo("Available filters:")

    # Display Fundamental, Descriptive and Technical Params
    next_start_idx = display_options(fp, options, "Fundamental Params")
    next_start_idx = display_options(
        dp, options, "Descriptive Params", next_start_idx, 'yellow')
    display_options(tp, options, "Technical Params", next_start_idx, 'red')

    # Select filters
    selected_filters_indices = get_filters_indices(options)

    # Select filter values
    selected_values = select_values(
        selected_filters_indices, queryOptions)

    # Save selected values
    if config.use_history:
        with open(filepath, 'w') as outfile:
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

def display_options(options_group, options, title, start_idx=1, color='blue'):

    click.echo(click.style(f"\nAvailable filters for {title}:"))

    # Filter the keys from the options that are also attributes of options_group
    grouped_keys = [filter_key for filter_key in options.keys()
                    if filter_key in vars(options_group)]

    for i in range(0, len(grouped_keys), 5):
        # Use a list comprehension here to generate the formatted keys for this group
        formatted_keys = [
            f"{start_idx + idx}. {grouped_keys[idx]}" for idx in range(i, min(i + 5, len(grouped_keys)))]
        click.echo(click.style(" | ".join(formatted_keys), fg=color))
        start_idx += len(formatted_keys)  # Update start_idx for the next group

    return start_idx

def get_filters_indices(options):
    input_msg = click.style(
        "\nEnter the numbers of the filters you want to use (comma separated)", fg='yellow')
    filters_indices = click.prompt(input_msg, type=str).split(',')
    return [{list(options.keys())[int(idx) - 1]: list(options.values())[int(idx) - 1]} for idx in filters_indices]

def select_values(selected_filters, queryOptions):
    selected_values = {}

    for filter_dict in selected_filters:
        for filter_outer_key, filter_inner_dict in filter_dict.items():
            click.echo(click.style(
                f"\nAvailable values for {filter_outer_key}:", fg='blue'))
            items_list = list(filter_inner_dict.items())

            for i in range(0, len(items_list), 5):
                items_to_echo = [
                    f"{idx + 1}: {items[0]} - {items[1]}" for idx, items in enumerate(items_list[i:i+5],start=i)]
                click.echo(click.style(
                    f"{' | '.join(items_to_echo)}", fg='green'))

            value_idx = click.prompt(click.style(
                f"Select a value for {filter_outer_key}", fg='yellow'), type=int) - 1
            selected_values[queryOptions[filter_outer_key]
                            ] = items_list[value_idx][0]
    return selected_values
