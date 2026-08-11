class StockTableLocators:
    STOCKS_TABLE = "table.styled-table-new"
    PAGE_CLASS = "screener-pages"
    # id of the table Finviz renders instead of STOCKS_TABLE when a screen
    # legitimately matches zero tickers (carries a "0 Total" count-text
    # cell). Distinguishes a genuine empty result from a missing/malformed
    # screener table — see `StockTableScreeningContent.has_empty_marker`.
    EMPTY_BODY_ID = "js-screener-body-empty"
    PD_TABLE_COLUMNS = [
        "No.",
        "Ticker",
        "Company",
        "Sector",
        "Industry",
        "Country",
        "Market Cap",
        "P/E",
        "Price",
        "Change",
        "Volume",
        "Link",
    ]
