<!-- a24d54ce-23fd-4bf4-a65a-cc07f5673ee4 ff32c43b-8cd3-4266-b8a5-b0c43709cf1a -->
# FinPack Two‑Step User Library Migration Plan (yfinance, no CLI)

### Scope and goals

- **Unify** Finviz screening (from `fincli/`) and fundamentals/ratios (from `fundainsight/`) into the **finpack** library.
- **Provider**: yfinance only (no yahooquery).
- **Public API**: simple two-step functions; no CLI or pipeline object.
  - screen(filters|link) → DataFrame of candidates
  - analyze(symbols) → DataFrame with ratios and key descriptors
- **Keep KISS, Clean Architecture, TDD** with integration/E2E focus and ≥90% coverage.

### Key observations (current state)

- Finviz screening builds a query and scrapes results table, shaping columns and hyperlinking `Ticker`:
```19:40:src/finpack/core/screener.py
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
```

- Fundaments/ratios logic uses 30‑day average price and per‑share asset metrics:
```8:16:fundainsight/calculators/equity_calc.py
def calculate_price_to_data(financial_data, column_name):
    return financial_data[column_name]/financial_data['Shares Outstanding']

def ratio_between_two_values(value1, value2):
    if value2 == 0:
        return 0
    return value1/value2
```




`````70:89:fundainsight/calculators/equity_calc.py

history_30d = ticker.history(period="1mo")

average_price_30d = history_30d['close'].quantile(0.5)

adjusted_current_assets = adjust_assets(

balance_sheet, 'CurrentAssets', 0.3, ['OtherCurrentAssets'])

adjusted_total_assets = adjust_assets(balance_sheet, 'TotalAssets', 0, [

'Goodwill', 'OtherNonCurrentAssets'])

return {

'Symbol': ticker_name,

'Market Cap': market_cap,

'Shares Outstanding': shares_outstanding,

'Total Assets': total_assets,

'Adjusted Total Assets': adjusted_total_assets,

'Adjusted Total Current Assets': adjusted_current_assets,

'Total Equity': total_equity,

'Average Price in Last 30 Days': average_price_30d,

}

````
- Current finpack analyzer uses yfinance but ratios use current price; sector/country not surfaced:
```16:45:src/finpack/core/analyzer.py
    def ratios(self, symbol: str) -> Dict[str, float]:
        balance = self.provider.get_balance_sheet(symbol)
        if balance.empty:
            return {}
        latest = balance.iloc[-1]
        total_assets = float(latest.get("TotalAssets") or latest.get("Total Assets") or 0)
        current_assets = float(latest.get("CurrentAssets") or latest.get("Current Assets") or 0)
        info = self.provider.get_info(symbol)
        price = float(info.get("currentPrice") or info.get("regularMarketPrice") or 0)
        shares_outstanding = float(info.get("sharesOutstanding", 0) or 0)
        market_cap = info.get("marketCap")
        # Compute 30-day median close when history is available
        avg_price_30d = None
        try:
            hist = self.provider.get_history(symbol, period="1mo", interval="1d")
            if isinstance(hist, pd.DataFrame) and "close" in hist.columns and not hist.empty:
                avg_price_30d = float(hist["close"].quantile(0.5))
        except Exception:
            avg_price_30d = None
        price_by_assets = 0.0 if shares_outstanding == 0 else total_assets / shares_outstanding
        price_by_current_assets = 0.0 if shares_outstanding == 0 else current_assets / shares_outstanding
        ratio_current = 0.0 if price_by_current_assets == 0 else price / price_by_current_assets
        ratio_assets = 0.0 if price_by_assets == 0 else price / price_by_assets
````

- Example uses a pipeline helper we will remove in favor of explicit two-step calls:
```13:18:example/advanced_usage.py
    try:
        df = build_unfiltered_results(symbols, analyzer=analyzer)
        print("Unfiltered results:")
        print(df.head())
    except Exception as e:
        print("Pipeline skipped due to data fetch error:", e)
`````

### Target public API (no CLI)

- **finpack.screen(filters|link)**: Build Finviz URL and scrape results into a DataFrame with columns from `StockTableLocators.PD_TABLE_COLUMNS`, plus `Symbol`.
- **finpack.analyze(symbols)**: Return DataFrame with unified columns:
  - `Ticker`, `Sector`, `Industry`, `Country`, `Market Cap`, `Average Price in Last 30 Days`,

`price_by_assets`, `price_by_current_assets`, `price/price_to_current_assets_ratio`, `price/price_to_assets_ratio`.

  - Ratios computed using 30‑day median price (to match historical fundainsight behavior).
- **finpack.build_screener_query(filters)**: Re‑export existing builder for non-scrape usage.
- Optional convenience: **finpack.enrich(screen_df)** merges `screen_df['Symbol']` with `analyze` output on symbol.

### Clean Architecture alignment

- **Providers**: keep `YFinanceProvider` as the only fundamentals provider.
- **Core**: 
  - `StockScreener` (unchanged, library only)
  - `FundamentalAnalyzer` (updated ratios + descriptors)
- **API façade**: new lightweight `finpack.api` exposing the two functions; re-export in `finpack.__init__`.
- **No import-time side effects**; keep logging optional/configurable.

### Implementation plan (TDD-first)

1) Analyzer parity with fundainsight ratios (yfinance)

- Add sector/industry/country from `Ticker.info` when present; continue `market_cap` usage.
- Switch ratio numerators to 30‑day median price; keep current price unused in ratios to match history.
- Ensure `Ticker` field equals the input symbol; do not hyperlink here.
- Tests first:
  - Unit: `test_analyzer_ratios_formula` with a FakeProvider to validate per‑share math and 30‑day median numerator.
  - Integration: `test_analyze_yfinance_vcr` with 1–2 symbols using VCR cassettes.

2) Public API façade

- Create `src/finpack/api.py` with:
  - `def screen(filters=None, scrape_link=None) -> DataFrame`
  - `def analyze(symbols: Sequence[str]) -> DataFrame`
  - `def enrich(screen_df: DataFrame) -> DataFrame` (optional helper)
- Re‑export in `src/finpack/__init__.py`.
- Tests first:
  - Integration: `test_screen_then_analyze_e2e_vcr` (filters → screen → analyze → non-empty DF, expected columns).

3) Example updates (no CLI, no pipeline)

- Replace `example/advanced_usage.py` and `simple_usage.py` to demonstrate two-step flow and safe error handling.
- Tests: smoke example via import/run in CI with network recorded via VCR.

4) Docs

- Update `docs/api_reference.md` and `README.md` with two-step usage and minimal examples.

5) Deprecations and cleanup

- Mark `build_unfiltered_results` as deprecated (kept temporarily as thin wrapper to `analyze`) or remove from examples entirely.

### Test strategy and coverage (≥90%)

- **Integration/E2E focus** per project rules, backed by `pytest-vcr` cassettes to avoid flakiness.
- Deterministic unit tests with FakeProvider ensure math correctness and edge cases (missing fields, empty history, shares=0).
- Existing utils/screener unit tests retained; add locators parsing regression tests with small HTML fixtures.

### Risks and mitigations

- **External HTML changes (Finviz)**: selector unit tests + minimal parser; fail gracefully to empty DF.
- **Network flakiness/rate limits**: VCR cassettes; retries minimal in provider; keep symbol list small in tests.
- **yfinance field variance**: robust key access with fallbacks; tests covering missing keys.
- **Column drift**: enforce canonical column order in analyzer output; tests assert schema.

### Acceptance criteria (Definition of Done)

- `finpack.screen` and `finpack.analyze` available from `finpack` top-level.
- `analyze` returns DataFrame with columns exactly:
  - `Ticker, Sector, Industry, Country, Market Cap, Average Price in Last 30 Days, price_by_assets, price_by_current_assets, price/price_to_current_assets_ratio, price/price_to_assets_ratio`.
- Example scripts use the new two-step API and run without CLI.
- All tests green; coverage ≥90%.

### Deliverables

- Updated analyzer and new API façade (`src/finpack/api.py`, re-exports).
- Revised examples and docs.
- New tests (unit, integration, E2E with VCR) and recorded cassettes.

### Timeline (lean)

- Day 1: Analyzer parity + API façade + unit/integration tests + examples.
- Day 2: E2E with VCR, docs, cleanup, deprecations, coverage hardening.

### Next steps

- Approve plan. Then implement TDD-first in small steps, starting with analyzer unit tests and FakeProvider.

### To-dos

- [ ] Update analyzer to 30-day median price ratios; add sector/industry/country.
- [ ] Create finpack.api with screen, analyze, enrich; re-export in __init__.
- [ ] Add unit + integration tests (FakeProvider, yfinance VCR) for analyzer/API.
- [ ] Add E2E test: screen→analyze with VCR cassettes; assert schema.
- [ ] Update examples and docs to two-step API; remove pipeline usage.
- [ ] Deprecate or remove build_unfiltered_results from examples; keep wrapper if needed.