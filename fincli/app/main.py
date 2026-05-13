import logging
import pandas as pd
from core.configuration import configurator
from fincli.stock_screening.content.stock_table import StockTableScreeningContent
from fincli.cli.cli_stock_screener import select_filters_and_values
from logger.logger import logger
from fincli.stock_screening.locators.stock_table_locators import StockTableLocators
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
    df["Market Cap"] = df["Market Cap"].apply(lambda x: convert_market_cap_to_numeric(x))
    df['Symbol'] = df['Ticker']
    df['Ticker'] = '=HYPERLINK("' + df['Link'] + '", "' + df['Ticker'] + '")'
    df.drop(columns=['Link'], axis=1, inplace=True)
    return df

def convert_market_cap_to_numeric(market_cap):
    market_cap.replace("'","")
    if market_cap.__contains__('B'):
        return float(market_cap.replace("B","")) * 1000000000
    elif market_cap.__contains__('M'):
        return float(market_cap.replace("M","")) * 1000000
    elif market_cap.__contains__('T'):
        return float(market_cap.replace("T","")) * 1000000000000
    elif market_cap.__contains__('_'):
        return market_cap.replace("_","N/A")
    elif market_cap.__contains__('-'):
        return market_cap.replace("-","N/A")
    else:
        return float(market_cap)


def run_stock_screener(history: bool = False, debug: bool = False, scrape_link: str = ""):
    logger.set_level(logging.DEBUG if debug else logging.INFO)

    config = configurator.build_config(use_history=history, scrape_link=scrape_link)
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
    file_path = config.file_path("stock_screener")
    final_df.to_csv(file_path, index=False)
    logger.info(f"File saved to {file_path}", "Data Handling --->")

