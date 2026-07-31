from typing import cast

from bs4 import Tag

from ...resource.params.const import BASE_URL


class StockTableScreenerParser:
    """
    A class to take in an HTML page or content, and find properties of an item
    in it.
    """

    def __init__(self, html_content: Tag) -> None:
        self.html_content = html_content

    def __repr__(self) -> str:
        return f"StockScreenerParser({self.html_content})"

    @property
    def table_rows(self) -> list[Tag]:
        """
        Returns the table rows with the class "table-light is-new".
        """
        data_rows = self.html_content.find_all("tr", valign="top")

        return data_rows

    @property
    def table_data(self) -> list[list[str]]:
        """
        Returns the table data.
        """
        data = []
        for row in self.table_rows:
            cells = row.find_all("td")
            row_data = [cell.get_text(strip=True) for cell in cells]
            row_data.insert(len(row_data), self.ticker_link(cells))
            data.append(row_data)
        return data

    @classmethod
    def ticker_link(cls, cells: list[Tag]) -> str:
        """
        Returns the ticker link.
        """
        link = cast(str, cast(Tag, cells[1].find("a")).get("href"))
        return BASE_URL + link
