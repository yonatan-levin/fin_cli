# TESTING.md

This document defines the testing strategy, conventions, and guidelines for Fin CLI.

## Current State

**Test files are currently missing.** The `tests/` directory contains only `__pycache__/` compiled bytecode from previously existing tests. The original `.py` test files have been deleted. The compiled cache reveals the following tests *existed* at some point:

### Previously Existing Tests (from __pycache__)

**Root-level tests:**
- `test_finpack_structure` - Package structure validation
- `test_finpack_dependencies` - Dependency checks
- `test_finpack_public_api` - Public API surface tests
- `test_library_config` - Configuration tests
- `test_backward_compatibility` - Backward compat checks
- `test_fincli_app` - Fincli application tests
- `test_finpack_main` - Main module tests
- `test_stock_picker_simple` / `test_stock_picker` - Picker logic
- `test_financial_data_provider` / `test_financial_data_provider_fixed` - Yahoo data
- `test_circuit_breaker_public_flow` - Circuit breaker pattern
- `test_composite_data_provider_integration` - Provider integration
- `test_composite_market_data_flow` - Market data flow
- `test_composite_provider_cache_and_cb` - Caching + circuit breaker
- `test_composite_provider_fallbacks` - Provider fallback logic
- `test_config_env_staging_production` - Environment configs
- `test_config_settings_env_types` / `test_config_settings_public_flow` - Config
- `test_financial_calculation_service` - Calculation logic
- `test_fincli_content_page_parsing` - HTML parsing
- `test_fincli_quary_builders_public_flow` - Query building
- `test_fincli_stock_table_parsers` - Stock table parsing
- `test_finpack_cli_commands` - CLI command tests
- `test_fundainsight_picker_original_smoke` / `test_fundainsight_picker_comprehensive` - Picker
- `test_json_utils` - JSON conversion
- `test_log_manager_basic` - Logger tests
- `test_user_agent_rotator` - UA rotation
- `test_yfinance_batch` - Yahoo Finance batch

**Unit tests (`tests/unit/`):**
- `tests/unit/api/test_api_facade` - API facade
- `tests/unit/api/test_api_edge_cases` - API edge cases
- `tests/unit/core/test_screener_facade` - Screener facade
- `tests/unit/core/test_screener_edge_cases` - Screener edges
- `tests/unit/core/test_analyzer_facade` - Analyzer facade
- `tests/unit/core/test_analyzer_extras` - Analyzer extras
- `tests/unit/core/test_analyzer_with_descriptors` - Descriptors
- `tests/unit/providers/test_yahoo_provider` - Yahoo provider
- `tests/unit/providers/test_yfinance_provider_edge` - Provider edges
- `tests/unit/utils/test_logging` - Logging utils
- `tests/unit/utils/test_quary_builders_facade` / `test_quary_builders_edge` - Query builders
- `tests/unit/utils/test_web_scraper` - Web scraper

**E2E tests (`tests/e2e/`):**
- `tests/e2e/test_pipeline_unfiltered` - Unfiltered pipeline
- `tests/e2e/test_pipeline_detailed` - Detailed pipeline
- `tests/e2e/test_api_two_step` - Two-step API flow

---

## Testing Strategy

### Test Categories

#### 1. Unit Tests

Test individual functions and classes in isolation. Mock external dependencies.

**Priority targets for recreation:**

| Component | File | What to Test |
|-----------|------|-------------|
| Market cap conversion | `fincli/app/main.py` | `convert_market_cap_to_numeric()` - B/M/T/edge cases |
| Query builder | `fincli/utils/quary_builders.py` | URL construction from filter tuples |
| Financial calculations | `fundainsight/calculators/equity_calc.py` | `calculate_price_to_data()`, `ratio_between_two_values()`, `adjust_assets()` |
| Filters | `fundainsight/calculators/filters.py` | Country, sector, price filtering + chaining |
| JSON converter | `core/converters/json.py` | `json_to_tuples()` with various inputs |
| Config builder | `core/configuration/configurator.py` | `build_config()` with history/filters |
| HTML parsing | `fincli/stock_screening/` | Table content extraction, row parsing |

#### 2. Integration Tests

Test module interactions with mocked external services.

**Priority targets:**
- fincli pipeline: config -> query builder -> (mocked HTTP) -> parser -> DataFrame
- fundainsight pipeline: (mocked fincli) -> (mocked yahooquery) -> calculations -> filtering
- Configuration loading from filter_history.json

#### 3. E2E Tests

Test full pipeline with real or recorded external responses.

**Considerations:**
- Finviz and Yahoo Finance are live services - tests should use recorded/cached responses
- Use `pytest-recording` or fixture files for HTTP response snapshots
- Mark E2E tests with `@pytest.mark.e2e` so they can be skipped in CI

---

## Test Conventions

### Directory Structure

```
tests/
  conftest.py              # Shared fixtures
  unit/
    test_market_cap.py     # convert_market_cap_to_numeric
    test_query_builder.py  # build_stock_screener_query
    test_equity_calc.py    # Financial calculations
    test_filters.py        # DataFrame filters
    test_json_converter.py # json_to_tuples
    test_config.py         # Configuration building
    test_html_parser.py    # Stock table parsing
    test_logger.py         # Logger singleton
  integration/
    test_screening_pipeline.py   # fincli pipeline with mocked HTTP
    test_analysis_pipeline.py    # fundainsight pipeline with mocked data
  e2e/
    test_full_pipeline.py        # Full pipeline with fixtures
    fixtures/
      finviz_response.html       # Recorded Finviz HTML
      yahoo_balance_sheet.json   # Recorded Yahoo data
```

### Naming Conventions

- Test files: `test_{module_name}.py`
- Test classes: `TestClassName` (group related tests)
- Test functions: `test_{function_name}_{scenario}` or `test_{behavior_description}`
- Fixtures: descriptive names in `conftest.py`

```python
# Good examples:
def test_convert_market_cap_billions():
def test_convert_market_cap_missing_value_returns_na():
def test_filter_countries_excludes_all_specified():
def test_ratio_division_by_zero_returns_zero():
def test_picker_with_empty_dataframe_returns_none():
```

### Mocking Strategy

**What to mock:**
- `cfscrape.create_scraper()` - No real HTTP calls in unit tests
- `yahooquery.Ticker()` - No real Yahoo API calls in unit tests
- File I/O for CSV saving (or use `tmp_path` fixture)

**What NOT to mock:**
- pandas DataFrame operations
- Financial calculations (test with real math)
- Filter chain logic
- Configuration building from known inputs

```python
# Example: mocking yahooquery
from unittest.mock import patch, MagicMock

@patch('fundainsight.calculators.equity_calc.yq.Ticker')
def test_get_financial_data_success(mock_ticker_class):
    mock_ticker = MagicMock()
    mock_ticker_class.return_value = mock_ticker
    mock_ticker.balance_sheet.return_value = sample_balance_sheet_df
    mock_ticker.summary_detail = {'AAPL': {'marketCap': 2890000000000}}
    mock_ticker.key_stats = {'AAPL': {'sharesOutstanding': 15800000000}}
    mock_ticker.history.return_value = sample_history_df

    result = get_financial_data('AAPL')
    assert result['Symbol'] == 'AAPL'
    assert result['Market Cap'] == 2890000000000
```

### Fixtures

**Common fixtures to define in `conftest.py`:**

```python
@pytest.fixture
def sample_screening_df():
    """DataFrame mimicking fincli stock screening output."""
    return pd.DataFrame({
        'Symbol': ['AAPL', 'MSFT', 'GOOGL'],
        'Ticker': ['AAPL', 'MSFT', 'GOOGL'],
        'Sector': ['Technology', 'Technology', 'Technology'],
        'Country': ['USA', 'USA', 'USA'],
        'Market Cap': [2890000000000, 2800000000000, 1700000000000],
    })

@pytest.fixture
def sample_financial_data():
    """Dict matching get_financial_data() return schema."""
    return {
        'Symbol': 'AAPL',
        'Market Cap': 2890000000000,
        'Shares Outstanding': 15800000000,
        'Total Assets': 352583000000,
        'Adjusted Total Assets': 300000000000,
        'Adjusted Total Current Assets': 100000000000,
        'Total Equity': 62146000000,
        'Average Price in Last 30 Days': 182.50,
    }

@pytest.fixture
def sample_finviz_html():
    """Recorded Finviz HTML response for parsing tests."""
    return Path('tests/e2e/fixtures/finviz_response.html').read_bytes()
```

---

## Running Tests

```bash
# Run all tests
pytest tests/

# Run unit tests only
pytest tests/unit/

# Run with coverage
pytest --cov=fincli --cov=fundainsight --cov-report=html tests/

# Run specific test file
pytest tests/unit/test_equity_calc.py

# Run with verbose output
pytest -v tests/

# Skip E2E tests (requires network)
pytest tests/ -m "not e2e"

# Run only E2E tests
pytest tests/ -m "e2e"
```

### pytest Configuration

Add to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "e2e: end-to-end tests that may require network access",
    "slow: tests that take more than 5 seconds",
]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
```

---

## Coverage Goals

| Module | Target Coverage | Priority |
|--------|----------------|----------|
| `fundainsight/calculators/equity_calc.py` | 90%+ | HIGH - Core financial logic |
| `fundainsight/calculators/filters.py` | 95%+ | HIGH - Data filtering |
| `fincli/app/main.py` | 80%+ | HIGH - Market cap conversion, DataFrame building |
| `fincli/utils/quary_builders.py` | 95%+ | MEDIUM - URL construction |
| `core/converters/json.py` | 90%+ | MEDIUM - Config parsing |
| `fincli/stock_screening/` | 70%+ | MEDIUM - HTML parsing (depends on fixtures) |
| `config/` | 80%+ | LOW - Pydantic handles validation |
| `logger/` | 50%+ | LOW - Logging infrastructure |

---

## Known Test Gaps and Risks

1. **No test files currently exist** - All tests need to be recreated from scratch
2. **`adjust_assets()` has a bug** - `not int` is always `True` (int is a truthy type object), meaning the `if not int` branches never execute. Tests should document expected vs actual behavior.
3. **Hardcoded filters in picker.py** - Country/sector exclusions are not configurable, making them difficult to test in isolation
4. **External service dependency** - Both Finviz and Yahoo Finance can change their HTML/API structure without notice
5. **No CI pipeline** - Tests need to be integrated into a CI/CD workflow
6. **Singleton Logger** - May cause test pollution; reset or mock between tests
