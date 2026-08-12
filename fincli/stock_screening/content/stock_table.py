from bs4 import BeautifulSoup

from fincli.stock_screening.locators.stock_table_locators import StockTableLocators
from fincli.stock_screening.parsers.stock_table import StockTableScreenerParser


class StockTableScreeningContent:
    def __init__(self, html_content: str | bytes) -> None:
        self.soup = BeautifulSoup(html_content, "html.parser")

    @property
    def all_table_content(self) -> list[StockTableScreenerParser]:
        return [
            StockTableScreenerParser(e) for e in self.soup.select(StockTableLocators.STOCKS_TABLE)
        ]

    @property
    def page_count(self) -> int:
        content = self.soup.find_all(class_=StockTableLocators.PAGE_CLASS)
        if len(content) == 0:
            return 0
        # Single match = exactly 1 page (selected, no next-arrow); >1 = numeric
        # links + trailing is-next arrow at [-1], so last numeric is at [-2].
        if len(content) == 1:
            return int(content[0].get_text(strip=True))
        return int(content[-2].get_text(strip=True))

    @property
    def has_empty_marker(self) -> bool:
        """Whether this page carries Finviz's legitimate zero-result marker.

        Finviz renders a `table#js-screener-body-empty` element (with a
        "0 Total" `count-text` cell) instead of `STOCKS_TABLE` when a screen
        genuinely matches zero tickers. Callers use this to tell a legit
        empty result apart from a missing/malformed screener table — see
        `fincli.app.main.aggregate_rows`.

        Returns:
            True when the empty-result marker element is present on the
            page, False otherwise.
        """
        return self.soup.find("table", id=StockTableLocators.EMPTY_BODY_ID) is not None
