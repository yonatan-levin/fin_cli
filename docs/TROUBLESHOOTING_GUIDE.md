# FinPack Troubleshooting Guide

**Version**: 1.0.0  
**Last Updated**: September 10, 2025  
**Target Audience**: Users, Developers, Support Team

---

## 📋 Overview

This guide provides solutions to common issues encountered when installing, configuring, and using FinPack. Issues are organized by category with step-by-step resolution instructions.

---

## 🗂️ Quick Index

- [Installation Issues](#-installation-issues)
- [Import and Configuration Problems](#-import-and-configuration-problems)
- [Data Provider Issues](#-data-provider-issues)
- [Performance Problems](#-performance-problems)
- [API and Rate Limiting](#-api-and-rate-limiting)
- [CLI Tool Issues](#-cli-tool-issues)
- [Testing and Development](#-testing-and-development)
- [Environment and Dependencies](#-environment-and-dependencies)
- [Getting Help](#-getting-help)

---

## 💾 Installation Issues

### Issue: `pip install finpack` fails
**Symptoms**: Package installation errors, dependency conflicts

**Common Causes & Solutions**:

1. **Outdated pip**
   ```bash
   # Update pip first
   python -m pip install --upgrade pip
   pip install finpack
   ```

2. **Python version incompatibility**
   ```bash
   # Check Python version (requires 3.8+)
   python --version
   
   # If < 3.8, upgrade Python or use pyenv/conda
   ```

3. **Virtual environment conflicts**
   ```bash
   # Create clean virtual environment
   python -m venv venv_clean
   source venv_clean/bin/activate  # Linux/Mac
   # or venv_clean\Scripts\activate  # Windows
   pip install finpack
   ```

4. **Network/proxy issues**
   ```bash
   # Use different index
   pip install --index-url https://pypi.org/simple/ finpack
   
   # Behind corporate proxy
   pip install --proxy http://proxy.company.com:8080 finpack
   ```

### Issue: Import errors after installation
**Symptoms**: `ModuleNotFoundError: No module named 'finpack'`

**Solutions**:
1. **Verify installation**
   ```bash
   pip list | grep finpack
   pip show finpack
   ```

2. **Check Python path**
   ```python
   import sys
   print(sys.path)
   # Ensure pip install location is in path
   ```

3. **Reinstall in correct environment**
   ```bash
   pip uninstall finpack
   pip install finpack
   ```

---

## 🔄 Import and Configuration Problems

### Issue: Deprecation warnings on import
**Symptoms**: Warning messages about deprecated import paths

**Expected Behavior**: This is normal during transition period

**Solutions**:
1. **Update import statements** (recommended)
   ```python
   # Old (deprecated)
   from fincli.app.main import run_stock_screener
   from fundainsight.app.main import get_opportunities
   
   # New (preferred)
   from finpack.fincli.app.main import run_stock_screener
   from finpack.fundainsight.app.main import get_opportunities
   ```

2. **Suppress warnings temporarily**
   ```python
   import warnings
   warnings.filterwarnings("ignore", category=DeprecationWarning)
   import finpack
   ```

### Issue: Configuration errors
**Symptoms**: `ConfigurationError`, API key issues

**Solutions**:
1. **Reset configuration**
   ```python
   from finpack.shared.infrastructure.config import reset_library_config
   reset_library_config()
   finpack.configure_library()
   ```

2. **Check environment variables**
   ```bash
   # List FinPack environment variables
   env | grep FINPACK
   
   # Set missing variables
   export FINPACK_LOG_LEVEL=INFO
   export FINPACK_MAX_WORKERS=5
   ```

3. **Verify API keys**
   ```python
   from finpack.shared.infrastructure.config import get_library_config
   config = get_library_config()
   print(f"API keys enabled: {config.enable_api_keys}")
   ```

---

## 🔌 Data Provider Issues

### Issue: No data returned from providers
**Symptoms**: Empty DataFrames, `None` results, timeout errors

**Diagnosis Steps**:
1. **Check provider status**
   ```python
   from finpack.shared.domain.services import FinancialDataProviderFactory
   factory = FinancialDataProviderFactory()
   provider = factory.create_default_provider()
   
   # Test basic connectivity
   data = provider.get_market_data(['AAPL'])
   print(f"Data received: {data is not None}")
   ```

2. **Test individual providers**
   ```python
   # Test yfinance directly
   import yfinance as yf
   stock = yf.Ticker('AAPL')
   info = stock.info
   print(f"yfinance working: {len(info) > 0}")
   ```

**Solutions**:
1. **Check network connectivity**
   ```bash
   ping finance.yahoo.com
   curl -I https://query1.finance.yahoo.com/v8/finance/chart/AAPL
   ```

2. **Verify API keys** (for premium providers)
   ```bash
   # Alpha Vantage
   export ALPHA_VANTAGE_API_KEY=your_key_here
   
   # IEX Cloud
   export IEX_CLOUD_API_KEY=your_key_here
   ```

3. **Increase timeout settings**
   ```python
   from finpack.shared.infrastructure.config import LibraryConfig
   config = LibraryConfig(request_timeout=60)  # 60 seconds
   finpack.configure_library(config)
   ```

### Issue: Rate limiting errors
**Symptoms**: HTTP 429 errors, "too many requests" messages

**Solutions**:
1. **Reduce request frequency**
   ```python
   import time
   
   # Add delays between requests
   for symbol in symbols:
       data = provider.get_financial_data(symbol)
       time.sleep(1)  # 1 second delay
   ```

2. **Use batch requests**
   ```python
   # Instead of individual requests
   results = provider.get_multiple_financial_data(['AAPL', 'MSFT', 'GOOGL'])
   ```

3. **Configure rate limiting**
   ```python
   from finpack.shared.infrastructure.config import LibraryConfig
   config = LibraryConfig(
       max_concurrent_requests=1,  # Reduce concurrency
       request_delay=2.0  # 2 second delay between requests
   )
   ```

---

## ⚡ Performance Problems

### Issue: Slow import times
**Symptoms**: Long delays when importing finpack

**Solutions**:
1. **Use specific imports**
   ```python
   # Instead of importing everything
   import finpack
   
   # Import only what you need
   from finpack.fincli.app.main import run_stock_screener
   ```

2. **Lazy loading**
   ```python
   # Import inside functions when needed
   def analyze_stocks():
       from finpack.fundainsight.app.stock_picker import StockPicker
       return StockPicker()
   ```

### Issue: High memory usage
**Symptoms**: Python process consuming excessive RAM

**Diagnosis**:
```python
import psutil
import os

process = psutil.Process(os.getpid())
print(f"Memory usage: {process.memory_info().rss / 1024 / 1024:.1f} MB")
```

**Solutions**:
1. **Clear data caches periodically**
   ```python
   # Clear internal caches (if available)
   from finpack.shared.infrastructure.utils import clear_caches
   clear_caches()
   ```

2. **Process data in chunks**
   ```python
   # Instead of loading all data at once
   symbols = ['AAPL', 'MSFT', ...]  # Large list
   
   # Process in smaller batches
   batch_size = 10
   for i in range(0, len(symbols), batch_size):
       batch = symbols[i:i + batch_size]
       results = process_batch(batch)
       # Process results immediately
   ```

### Issue: Slow data retrieval
**Symptoms**: Long wait times for financial data

**Solutions**:
1. **Enable concurrent requests**
   ```python
   from finpack.shared.infrastructure.config import LibraryConfig
   config = LibraryConfig(max_concurrent_requests=5)
   finpack.configure_library(config)
   ```

2. **Use caching**
   ```python
   config = LibraryConfig(cache_enabled=True, cache_ttl=3600)  # 1 hour cache
   ```

---

## 🔑 API and Rate Limiting

### Issue: API key not recognized
**Symptoms**: Authentication failures, "invalid API key" errors

**Solutions**:
1. **Verify key format**
   ```bash
   # Alpha Vantage keys are typically 16 characters
   echo $ALPHA_VANTAGE_API_KEY | wc -c
   
   # Check for extra spaces or characters
   echo "$ALPHA_VANTAGE_API_KEY" | od -c
   ```

2. **Test API key directly**
   ```bash
   # Test Alpha Vantage key
   curl "https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=MSFT&apikey=$ALPHA_VANTAGE_API_KEY"
   ```

3. **Check key permissions**
   - Ensure API key has required permissions
   - Verify key hasn't expired
   - Check usage quotas

### Issue: Quota exceeded
**Symptoms**: "quota exceeded", "limit reached" errors

**Solutions**:
1. **Check usage limits**
   ```python
   # Some providers offer usage statistics
   from finpack.shared.domain.services import AlphaVantageDataProvider
   provider = AlphaVantageDataProvider(api_key="your_key")
   # Check if provider has usage statistics method
   ```

2. **Implement exponential backoff**
   ```python
   import time
   import random
   
   def request_with_backoff(func, max_retries=3):
       for attempt in range(max_retries):
           try:
               return func()
           except QuotaExceeded:
               if attempt < max_retries - 1:
                   delay = (2 ** attempt) + random.random()
                   time.sleep(delay)
               else:
                   raise
   ```

---

## 🖥️ CLI Tool Issues

### Issue: CLI commands not found
**Symptoms**: `command not found: finpack`, entry point errors

**Solutions**:
1. **Verify installation includes entry points**
   ```bash
   pip show finpack | grep entry-points
   ```

2. **Use module syntax**
   ```bash
   # Instead of 'finpack fincli'
   python -m finpack fincli
   
   # Or directly
   python -m finpack.fincli
   ```

3. **Check PATH**
   ```bash
   which finpack
   echo $PATH
   # Ensure pip's bin directory is in PATH
   ```

### Issue: CLI hangs or freezes
**Symptoms**: Command starts but doesn't respond

**Solutions**:
1. **Check for blocking operations**
   ```bash
   # Run with verbose output
   python -m finpack fincli --verbose
   ```

2. **Interrupt and debug**
   ```bash
   # Ctrl+C to interrupt, then check logs
   tail -f ~/.finpack/logs/finpack.log
   ```

3. **Use timeout**
   ```bash
   timeout 30s python -m finpack fincli
   ```

---

## 🧪 Testing and Development

### Issue: Tests failing locally
**Symptoms**: Test suite errors, import failures in tests

**Solutions**:
1. **Install development dependencies**
   ```bash
   pip install -e .[dev]
   pip install pytest pytest-cov pytest-mock
   ```

2. **Check test environment**
   ```bash
   # Run tests with verbose output
   python -m pytest -v tests/
   
   # Run specific test file
   python -m pytest tests/test_finpack_public_api.py -v
   ```

3. **Clear test caches**
   ```bash
   # Remove pytest cache
   rm -rf .pytest_cache
   
   # Remove Python cache
   find . -name "__pycache__" -type d -exec rm -rf {} +
   ```

### Issue: Mock/patch errors in tests
**Symptoms**: Mock assertions failing, patch not working

**Solutions**:
1. **Check import paths**
   ```python
   # Ensure patch targets the actual import location
   @patch('finpack.shared.domain.services.yfinance')  # Not just 'yfinance'
   def test_function(self, mock_yf):
       pass
   ```

2. **Verify patch scope**
   ```python
   # Use where the name is used, not where it's defined
   with patch('module_under_test.dependency') as mock_dep:
       result = module_under_test.function()
   ```

---

## 🌍 Environment and Dependencies

### Issue: Dependency conflicts
**Symptoms**: Version conflicts, unable to install alongside other packages

**Solutions**:
1. **Check dependency tree**
   ```bash
   pip install pipdeptree
   pipdeptree --packages finpack
   ```

2. **Create isolated environment**
   ```bash
   # Use conda for complex dependency resolution
   conda create -n finpack_env python=3.9
   conda activate finpack_env
   pip install finpack
   ```

3. **Manual resolution**
   ```bash
   # Identify conflicting packages
   pip check
   
   # Install compatible versions manually
   pip install "pandas>=1.3.0,<2.0.0"
   pip install finpack
   ```

### Issue: Platform-specific errors
**Symptoms**: Works on one OS but fails on another

**Solutions**:
1. **Check platform requirements**
   ```python
   import platform
   print(f"Platform: {platform.platform()}")
   print(f"Python: {platform.python_version()}")
   ```

2. **Install platform-specific dependencies**
   ```bash
   # On Windows, may need Visual C++ Build Tools
   # On Linux, may need development headers
   sudo apt-get install python3-dev build-essential  # Ubuntu/Debian
   ```

---

## 🔍 Diagnostic Tools

### System Information
```python
def finpack_system_info():
    """Print comprehensive system information for debugging."""
    import sys
    import platform
    import finpack
    
    print("=== FinPack System Information ===")
    print(f"FinPack version: {finpack.__version__}")
    print(f"Python version: {sys.version}")
    print(f"Platform: {platform.platform()}")
    print(f"Architecture: {platform.architecture()}")
    
    # Check imports
    try:
        import pandas as pd
        print(f"Pandas version: {pd.__version__}")
    except ImportError as e:
        print(f"Pandas import error: {e}")
    
    try:
        import yfinance as yf
        print(f"yfinance version: {yf.__version__}")
    except ImportError as e:
        print(f"yfinance import error: {e}")
    
    # Check configuration
    try:
        from finpack.shared.infrastructure.config import get_library_config
        config = get_library_config()
        print(f"Log level: {config.log_level}")
        print(f"API keys enabled: {config.enable_api_keys}")
    except Exception as e:
        print(f"Configuration error: {e}")

# Run the diagnostic
finpack_system_info()
```

### Network Connectivity Test
```python
def test_connectivity():
    """Test network connectivity to financial data sources."""
    import requests
    
    sources = {
        'Yahoo Finance': 'https://query1.finance.yahoo.com/v8/finance/chart/AAPL',
        'Alpha Vantage': 'https://www.alphavantage.co',
        'IEX Cloud': 'https://cloud.iexapis.com',
    }
    
    for name, url in sources.items():
        try:
            response = requests.get(url, timeout=10)
            status = "✅ OK" if response.status_code < 400 else f"❌ {response.status_code}"
            print(f"{name}: {status}")
        except Exception as e:
            print(f"{name}: ❌ Error - {e}")

test_connectivity()
```

---

## 🆘 Getting Help

### Before Asking for Help
1. **Check this troubleshooting guide**
2. **Search existing GitHub issues**
3. **Try the diagnostic tools above**
4. **Prepare a minimal reproduction case**

### Where to Get Help

1. **GitHub Issues**: https://github.com/YourOrg/finpack/issues
   - Bug reports
   - Feature requests
   - General questions

2. **GitHub Discussions**: https://github.com/YourOrg/finpack/discussions
   - Community Q&A
   - Usage examples
   - Best practices

3. **Email Support**: support@algobeta.com
   - Security issues (private)
   - Enterprise support
   - Urgent problems

### How to Report Issues

**Include the following information**:
1. **Environment**: OS, Python version, FinPack version
2. **Steps to reproduce**: Exact commands/code that cause the issue
3. **Expected behavior**: What should happen
4. **Actual behavior**: What actually happens
5. **Error messages**: Full error text and stack traces
6. **System info**: Output from `finpack_system_info()` function above

**Example Issue Template**:
```markdown
## Bug Description
Brief description of the issue.

## Environment
- OS: Windows 10 / macOS 12 / Ubuntu 20.04
- Python: 3.9.7
- FinPack: 1.0.0
- Installation method: pip

## Steps to Reproduce
1. Run this command: `...`
2. Execute this code: `...`
3. Observe the error

## Expected Behavior
What you expected to happen.

## Actual Behavior
What actually happened.

## Error Messages
```
Paste full error messages and stack traces here
```

## Additional Context
Any other relevant information.
```

---

## 🔄 Update History

| Date | Changes | Version |
|------|---------|---------|
| 2025-09-10 | Initial troubleshooting guide | 1.0.0 |

---

**For additional help, contact the development team through the channels listed above.**
