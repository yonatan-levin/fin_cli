from bs4 import BeautifulSoup

from fincli.stock_screening.locators.stock_table_locators import StockTableLocators
from fincli.stock_screening.parsers.stock_table import StockTableScreenerParser


class StockTableScreeningContent:
    def __init__(self, html_content):
        self.soup = BeautifulSoup(html_content, "html.parser")

    @property
    def all_table_content(self) -> list[StockTableScreenerParser]:
        return [
            StockTableScreenerParser(e) for e in self.soup.select(StockTableLocators.STOCKS_TABLE)
        ]

    @property
    def page_count(self):
        content = self.soup.find_all(class_=StockTableLocators.PAGE_CLASS)
        num_of_pages = int(content[-2].string) if len(content) != 0 else 0

        return num_of_pages
