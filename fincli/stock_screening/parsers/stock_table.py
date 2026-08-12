from typing import cast
from urllib.parse import parse_qs, urlparse

from bs4 import Tag

from ...resource.params.const import BASE_URL
from ..errors import ScreenerLayoutError


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
            row_data[1] = self.ticker_symbol(cells)
            row_data.insert(len(row_data), self.ticker_link(cells))
            data.append(row_data)
        return data

    @classmethod
    def ticker_symbol(cls, cells: list[Tag]) -> str:
        """Extract and validate the ticker symbol from the ticker cell.

        Finviz's redesigned layout nests two anchors in the ticker cell: a
        logo-fallback anchor (whose text is only the first letter of the
        ticker) followed by a tab-link anchor carrying the full ticker
        text. Plain `cell.get_text()` over the whole cell concatenates
        both, duplicating the first letter (e.g. "KTOS" -> "KKTOS" —
        GitHub issue #14). Reading only the LAST anchor's text avoids that;
        cross-checking it against the same anchor's href `t` query param
        catches any other corruption/drift instead of returning it
        silently.

        Args:
            cells: The row's `<td>` cells, matching `ticker_link`'s
                indexing (`cells[1]` is the ticker cell on both the legacy
                single-anchor layout and the redesigned dual-anchor one).

        Returns:
            The validated ticker symbol text.

        Raises:
            ScreenerLayoutError: The last anchor's visible text disagrees
                with its href's `t` query parameter, or the href carries
                no `t` parameter.
        """
        anchors = cells[1].find_all("a")
        if not anchors:
            # No anchor at all: let `ticker_link` raise the existing
            # AttributeError contract instead of masking it here.
            return cells[1].get_text(strip=True)

        last_anchor = anchors[-1]
        text = last_anchor.get_text(strip=True)
        href = cast(str, last_anchor.get("href", ""))
        href_ticker = parse_qs(urlparse(href).query).get("t", [""])[0]

        if not href_ticker or text != href_ticker:
            raise ScreenerLayoutError(
                f"Ticker cell text {text!r} does not match href ticker "
                f"{href_ticker!r} (href={href!r}) — Finviz layout drift or "
                "corrupted ticker data"
            )
        # Not a dead cast: `anchors[-1]` is `Any` under the bs4 stubs, so
        # `get_text()` returns `Any` and strict mypy needs the narrowing.
        return cast(str, text)

    @classmethod
    def ticker_link(cls, cells: list[Tag]) -> str:
        """Return the canonical Finviz URL for the row's ticker cell.

        Derived from the LAST anchor in the ticker cell — the same anchor
        ``ticker_symbol`` validates text-vs-href agreement on — so the
        emitted ``Link`` column can never come from a different element
        than the validated symbol. (Both live-layout anchors share one
        href today; this guards future drift.)
        """
        # `None.get` preserves the pinned no-anchor failure contract:
        # AttributeError, classified DATA=4 (same as the legacy `.find("a")`).
        last_anchor = cells[1].find_all("a")[-1] if cells[1].find_all("a") else None
        link = cast(str, cast(Tag, last_anchor).get("href"))
        return BASE_URL + link
