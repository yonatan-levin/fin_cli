from ..locators.stock_table_locators import StockTableLocators
from bs4 import BeautifulSoup

from ..parsers.stock_table import StockTableScreenerParser


class StockTableScreeningContent:
    def __init__(self, html_content):
        self.soup = BeautifulSoup(html_content, "html.parser")

    @property
    def all_table_content(self) -> list[StockTableScreenerParser]:
        return [
            StockTableScreenerParser(e)
            for e in self.soup.select(StockTableLocators.STOCKS_TABLE)
        ]
    @property
    def page_count(self):
        content = self.soup.find_all(class_=StockTableLocators.PAGE_CLASS)
        if not content:
            return 0
        # Find last numeric link safely
        anchors = content[-1].find_all('a') if content[-1] else []
        nums = []
        for a in anchors:
            try:
                nums.append(int(a.get_text(strip=True)))
            except Exception:
                continue
        return max(nums) if nums else 0
