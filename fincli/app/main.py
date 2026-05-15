import logging
import sys
import pandas as pd
from config.config import STDOUT_SENTINEL
from core.configuration import configurator
from fincli.stock_screening.content.stock_table import StockTableScreeningContent
from fincli.cli.cli_stock_screener import select_filters_and_values
from logger.logger import logger
from fincli.stock_screening.locators.stock_table_locators import StockTableLocators
from fincli.utils.market_cap import convert_market_cap_to_numeric
from fincli.utils.web_scraper import fetch_page_sync


def fetch_urls(quarry, page_count):
    urls = [f"{quarry}&r={abs(20*(i) + 1)}" for i in range(page_count + 1)]
    return [fetch_page_sync(url) for url in urls]


def aggregate_rows(pages):
    rows = []
    for page_content in pages:
        tab = StockTableScreeningContent(page_content)
        rows.extend(tab.all_table_content)
    return [row.table_data for row in rows]


def build_data_frame(data_rows):
    df = pd.concat([pd.DataFrame(row) for row in data_rows])
    df.columns = StockTableLocators.PD_TABLE_COLUMNS
    # Coerce the Market Cap column into a nullable Float64 array so unparseable
    # cells render as empty CSV cells rather than the literal strings "nan",
    # "<NA>", or 0.0. Contract: docs/features/pipeline-mode-spec.md §5.5 +
    # CONTRACTS.md §3.1.
    df["Market Cap"] = pd.array(
        [convert_market_cap_to_numeric(v) for v in df["Market Cap"]],
        dtype="Float64",
    )
    df['Symbol'] = df['Ticker']
    df['Ticker'] = '=HYPERLINK("' + df['Link'] + '", "' + df['Ticker'] + '")'
    df.drop(columns=['Link'], axis=1, inplace=True)
    return df


def run_stock_screener(
    history: bool = False,
    debug: bool = False,
    scrape_link: str = "",
    filters: str = "",
    output_path: str = "",
):
    logger.set_level(logging.DEBUG if debug else logging.INFO)

    config = configurator.build_config(
        use_history=history,
        scrape_link=scrape_link,
        filters=filters,
        output_path=output_path,
    )
    # When `--output -` is set, the CSV stream owns stdout. Reroute the two
    # human-readable console handlers to stderr so progress / banner / typing
    # chatter doesn't corrupt the CSV bytes piped to a downstream consumer.
    # File handlers (activity.log, error.log) are unaffected. Spec §5.2 + §5.3.
    if config.output_path == STDOUT_SENTINEL:
        logger.set_console_stream(sys.stderr)
    logger.debug(f"Config: {config}", "Config created successfully:")

    # Direct-URL bypass: when a scrape link is supplied, skip the interactive filter
    # picker + query builder entirely and use the URL verbatim as the screener query.
    quarry = config.scrape_link or select_filters_and_values(config)
    logger.debug(f"Quarry: {quarry}", 'Quarry created successfully:')

    logger.info(
        f"Fetching HTML content from {quarry}", 'Fetching HTML - Started')
    html_content = fetch_page_sync(quarry)
    logger.info(
        f"HTML content fetched from {quarry} successfully", "Fetching HTML - Completed")

    stock_screener_page = StockTableScreeningContent(html_content)

    pages = fetch_urls(quarry, stock_screener_page.page_count)
    data_rows = aggregate_rows(pages)

    if len(data_rows) == 0:
        logger.error("Data Handling --->",f"No data was found for the given filters"
                     )
        return

    final_df = build_data_frame(data_rows)
    logger.info(f"Data frame created successfully", "Data Handling --->")
    logger.info(f"Saving data frame to csv file", "Data Handling --->")
    # Pillar-2 destination dispatch. The `-` sentinel means "stream CSV to
    # stdout"; pandas accepts a file-like object, so handing it `sys.stdout`
    # writes the CSV bytes directly (and nothing else, since the logger has
    # already been rerouted to stderr above). Otherwise resolve the path
    # through `config.file_path` so the precedence chain
    # (--output PATH > FINCLI_OUTPUT_DIR > default) is honored at one site.
    if config.output_path == STDOUT_SENTINEL:
        final_df.to_csv(sys.stdout, index=False)
        logger.info(f"CSV streamed to stdout", "Data Handling --->")
    else:
        file_path = config.file_path("stock_screener")
        final_df.to_csv(file_path, index=False)
        logger.info(f"File saved to {file_path}", "Data Handling --->")

