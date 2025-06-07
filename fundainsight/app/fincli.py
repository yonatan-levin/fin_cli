from shared.infrastructure.config import get_config
from fincli.app.main import aggregate_rows, build_data_frame, fetch_urls
from fincli.stock_screening.content.stock_table import StockTableScreeningContent
from fincli.utils.quary_builders import build_stock_screener_query
from fincli.utils.web_scraper import fetch_page_sync
from logger import logger


def get_recommended_stocks(filters: tuple, scrape_link: str = ""):
    logger.info(f"Filters to use {filters}", 'Filters - Started')

    if scrape_link == "":
        quarry = build_stock_screener_query(filters)
    else:
        quarry = scrape_link

    logger.info(
        f"Fetching HTML content from {quarry}", 'Fetching HTML - Started')
    html_content = fetch_page_sync(quarry)

    if html_content is None:
        logger.error("Fetching HTML --->",
                     f"Failed to fetch HTML content from {quarry}")
        return

    logger.info(
        f"HTML content fetched from {quarry} successfully", "Fetching HTML - Completed")

    stock_screener_page = StockTableScreeningContent(html_content)

    pages = fetch_urls(quarry, stock_screener_page.page_count)
    data_rows = aggregate_rows(pages)

    if len(data_rows) == 0:
        logger.error("Data Handling --->",
                     f"No data was found for the given filters")

    final_df = build_data_frame(data_rows)

    logger.info(f"Data frame created successfully", "Data Handling --->")

    file_path = get_config().file_path("funda_insight_raw_result")
    final_df.to_csv(file_path, index=False)

    logger.info(f"File saved to {file_path}", "Data Handling --->")

    return final_df
