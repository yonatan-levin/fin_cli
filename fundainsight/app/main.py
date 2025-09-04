import logging
from pandas import DataFrame
from shared.infrastructure.config import get_financial_config, build_config
from logger.logger import logger
from .stock_picker import picker
from .fincli import get_recommended_stocks


def get_opportunities(history: bool = False, debug: bool = False, set_filters: str = "", scrape_link: str = "") -> DataFrame | None:
    logger.set_level(logging.DEBUG if debug else logging.INFO)

    # Enhanced logging with context
    logger.info("Starting fundainsight opportunity analysis", context={
        "use_history": history,
        "debug_mode": debug,
        "has_filters": bool(set_filters),
        "has_scrape_link": bool(scrape_link)
    })

    config = build_config(use_history=history, filters=set_filters)

    if (config.filters is None or config.filters == () and scrape_link == ""):
        logger.error("No filters were provided or could not be parsed.", context={
            "config_filters": config.filters,
            "scrape_link": scrape_link,
            "use_history": history
        })
        return

    df_stocks = get_recommended_stocks(
        filters=config.filters, scrape_link=scrape_link)

    data = picker(df_stocks)

    if data is None:
        logger.warn("Picker returned no data", context={
            "stocks_input_count": len(df_stocks) if df_stocks is not None else 0
        })
        return

    logger.info("Saving results to csv..", context={
        "result_count": len(data),
        "file_path": config.file_path("funda_insight_result")
    })
    data.to_csv(config.file_path("funda_insight_result"), index=False)
    logger.info("Results saved to csv successfully", context={
        "result_count": len(data)
    })

    return data
