import yfinance as yf
# import yahooquery as yq
from logger import logger
import time
import random
import datetime

# List of user agents to rotate through
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 11.5; rv:90.0) Gecko/20100101 Firefox/90.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 11_5_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Safari/605.1.15',
]

# In-memory cache for financial data
# Structure: {ticker_name: {'data': {...}, 'timestamp': datetime}}
MEMORY_CACHE = {}
CACHE_EXPIRY = 86400  # 24 hours in seconds

def get_from_cache(ticker_name):
    """Get financial data from in-memory cache if available and not expired"""
    if ticker_name not in MEMORY_CACHE:
        return None
    
    cache_entry = MEMORY_CACHE[ticker_name]
    cache_time = cache_entry.get('timestamp')
    
    # Check if cache is expired (older than 24 hours)
    if (datetime.datetime.now() - cache_time).total_seconds() > CACHE_EXPIRY:
        # Remove expired entry
        del MEMORY_CACHE[ticker_name]
        return None
    
    return cache_entry.get('data')

def save_to_cache(ticker_name, data):
    """Save financial data to in-memory cache"""
    if data is None:
        return
    
    MEMORY_CACHE[ticker_name] = {
        'data': data,
        'timestamp': datetime.datetime.now()
    }

def calculate_price_to_data(financial_data, column_name):
    return financial_data[column_name]/financial_data['Shares Outstanding']

def ratio_between_two_values(value1, value2):
    if value2 == 0:
        return 0
    return value1/value2

def adjust_assets(balance_sheet, asset_type, adjustment_factor, additional_subtracts):
    try:
        # asset_value = balance_sheet.iloc[-1][asset_type] if not int else balance_sheet.iloc[-2][asset_type]
        asset_value = balance_sheet.loc[asset_type].iloc[1] if asset_type in balance_sheet.index else 0
    except KeyError:
        return None

    for subtract in additional_subtracts:
        try:
            # asset_value  -= balance_sheet.loc[subtract].iloc[0] if subtract in balance_sheet.index else  0
            # if not int else balance_sheet.iloc[-2][subtract]
            sub = balance_sheet.loc[subtract].iloc[1]
        except KeyError:
            sub = None
        if sub is not None and sub > 0:
            asset_value -= sub
    if adjustment_factor == 0:
        return asset_value
    # Make the adjustment
    try:
        # inventory = balance_sheet.iloc[-1]['Inventory'] if not int else balance_sheet.iloc[-2]['Inventory']
        inventory = balance_sheet['Inventory'].iloc[1]  # if not int else balance_sheet.iloc[-2]['Inventory']
    except KeyError:
        inventory = None
    asset_value += (adjustment_factor * inventory) if not int else 0
    return asset_value

def get_financial_data(ticker_name: str):
    # Check cache first
    cached_data = get_from_cache(ticker_name)
    if cached_data:
        logger.info(f"Using cached data for {ticker_name}")
        return cached_data
    
    # Get the ticker object
    max_retries = 3
    for retry_count in range(max_retries):
        try:
            # Add a delay before each API call to avoid rate limiting
            # Increase delay with each retry
            delay = (2 + retry_count * 2) + random.uniform(0, 1)
            if retry_count > 0:
                logger.error(f"Retry attempt {retry_count} for {ticker_name} with {delay:.2f}s delay")
            time.sleep(delay)
            
            ticker = yf.Ticker(ticker_name)

            # Get the financial data
            balance_sheet = ticker.quarterly_balance_sheet
            if balance_sheet is None:
                logger.error(f"Error getting balance sheet for ticker {ticker_name}")
                return None
            if ticker.info is None:
                logger.error( f"Error getting summary_detail for ticker {ticker_name}")
                return None
                
            # If we got here, we successfully retrieved the data
            shares_outstanding = ticker.info['sharesOutstanding']
            market_cap = ticker.info['marketCap']

            # .iloc[1] will get you the last year / quarter
            total_assets = balance_sheet.loc['Total Assets'].iloc[1]
            total_equity = balance_sheet.loc['Stockholders Equity'].iloc[1]

            # Get the average price in the last 30 days
            history_30d = ticker.history()
            average_price_30d = history_30d['Close'].quantile(0.5)

            # Adjust the current and total assets
            adjusted_current_assets = adjust_assets(
                balance_sheet,  'Current Assets', 0.3, ['Other Current Assets'])
            adjusted_total_assets = adjust_assets(balance_sheet, "Total Assets", 0, [
                "Goodwill",  'Other Non Current Assets'])

            result = {
                'Symbol': ticker_name,
                'Market Cap': market_cap,
                'Shares Outstanding': shares_outstanding,
                'Total Assets': total_assets,
                'Adjusted Total Assets': adjusted_total_assets,
                'Adjusted Total Current Assets': adjusted_current_assets,
                'Total Equity': total_equity,
                'Average Price in Last 30 Days': average_price_30d,
            }
            
            # Save to cache
            save_to_cache(ticker_name, result)
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            # Check if it's a rate limiting error
            if "429" in error_msg or "Too Many Requests" in error_msg:
                if retry_count < max_retries - 1:
                    # Will retry in the next iteration
                    continue
                else:
                    logger.error(f"Rate limit exceeded for {ticker_name} after {max_retries} retries")
            else:
                logger.error(f"Error getting ticker {ticker_name} - {e}")
            
    # If we get here, all retries failed
    return None

def clear_cache():
    """Clear the in-memory cache"""
    global MEMORY_CACHE
    cache_size = len(MEMORY_CACHE)
    MEMORY_CACHE = {}
    logger.info(f"Cleared in-memory cache ({cache_size} entries)")
    return cache_size
