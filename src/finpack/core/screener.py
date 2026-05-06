from __future__ import annotations

from typing import Iterable, Tuple, List

import pandas as pd

from ..models.stock_screening.content import stock_table as stock_content_mod
from ..models.stock_screening.locators.stock_table_locators import StockTableLocators
from ..utils.quary_builders import build_stock_screener_query
from ..utils.web_scraper import fetch_page_sync


class StockScreener:
    """Unified facade for Finviz-based stock screening."""

    def __init__(self) -> None:
        pass

    def screen(self, filters: Iterable[Tuple[str, str]] | None = None, scrape_link: str | None = None) -> pd.DataFrame:
        if scrape_link:
            quarry = scrape_link
        elif filters is not None:
            quarry = build_stock_screener_query(filters)
        else:
            raise ValueError("Either filters or scrape_link must be provided")

        html_content = fetch_page_sync(quarry)
        stock_screener_page = stock_content_mod.StockTableScreeningContent(html_content)

        pages = self._fetch_pages(quarry, stock_screener_page.page_count)
        data_rows = self._aggregate_rows(pages)
        if len(data_rows) == 0:
            return pd.DataFrame()

        df = pd.concat([pd.DataFrame(row) for row in data_rows])
        df.columns = StockTableLocators.PD_TABLE_COLUMNS
        df["Symbol"] = df["Ticker"]
        df["Ticker"] = '=HYPERLINK("' + df['Link'] + '", "' + df['Ticker'] + '")'
        df.drop(columns=['Link'], axis=1, inplace=True)
        return df

    def _fetch_pages(self, quarry: str, page_count: int) -> List[bytes]:
        urls = [f"{quarry}&r={abs(20*(i) + 1)}" for i in range(page_count + 1)]
        return [fetch_page_sync(url) for url in urls]

    def _aggregate_rows(self, pages: List[bytes]) -> List[List[List[str]]]:
        parsers = []
        for page_content in pages:
            tab = stock_content_mod.StockTableScreeningContent(page_content)
            parsers.extend(tab.all_table_content)
        return [parser.table_data for parser in parsers]
