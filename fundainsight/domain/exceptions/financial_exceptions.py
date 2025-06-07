"""
Financial exceptions module.

This module defines custom exceptions related to financial data retrieval and processing.
"""


class FinancialDataError(Exception):
    """Base exception for all financial data errors."""
    pass


class FinancialDataRetrievalError(FinancialDataError):
    """Exception raised when financial data cannot be retrieved."""
    
    def __init__(self, message="Failed to retrieve financial data", *args, **kwargs):
        self.message = message
        super().__init__(self.message, *args, **kwargs)


class RateLimitError(FinancialDataRetrievalError):
    """Exception raised when rate limits are exceeded."""
    
    def __init__(self, message="Rate limit exceeded", retry_after=None, *args, **kwargs):
        self.retry_after = retry_after
        message = f"{message}. Retry after: {retry_after}" if retry_after else message
        super().__init__(message, *args, **kwargs)


class DataValidationError(FinancialDataError):
    """Exception raised when financial data validation fails."""
    
    def __init__(self, message="Financial data validation failed", field=None, *args, **kwargs):
        self.field = field
        message = f"{message} for field: {field}" if field else message
        super().__init__(message, *args, **kwargs)


class CalculationError(FinancialDataError):
    """Exception raised when a financial calculation fails."""
    
    def __init__(self, message="Financial calculation failed", calculation=None, *args, **kwargs):
        self.calculation = calculation
        message = f"{message}: {calculation}" if calculation else message
        super().__init__(message, *args, **kwargs)


class StockNotFoundError(FinancialDataRetrievalError):
    """Exception raised when a stock symbol is not found."""
    
    def __init__(self, symbol=None, *args, **kwargs):
        message = f"Stock symbol not found: {symbol}" if symbol else "Stock symbol not found"
        self.symbol = symbol
        super().__init__(message, *args, **kwargs)


class FinancialStatementError(FinancialDataRetrievalError):
    """Exception raised when financial statements cannot be retrieved."""
    
    def __init__(self, symbol=None, statement_type=None, *args, **kwargs):
        self.symbol = symbol
        self.statement_type = statement_type
        message = f"Could not retrieve {statement_type} for {symbol}" if statement_type and symbol else "Could not retrieve financial statement"
        super().__init__(message, *args, **kwargs)


class InsufficientDataError(FinancialDataError):
    """Exception raised when there is insufficient data for analysis."""
    
    def __init__(self, message="Insufficient data for analysis", missing_data=None, *args, **kwargs):
        self.missing_data = missing_data
        if missing_data:
            message = f"{message}. Missing data: {', '.join(missing_data)}"
        super().__init__(message, *args, **kwargs)


class ApiKeyError(FinancialDataRetrievalError):
    """Exception raised when there are issues with API keys."""
    
    def __init__(self, message="API key error", provider=None, *args, **kwargs):
        self.provider = provider
        message = f"{message} for provider: {provider}" if provider else message
        super().__init__(message, *args, **kwargs)


class CircuitBreakerOpenError(FinancialDataRetrievalError):
    """Exception raised when the circuit breaker is open."""
    
    def __init__(self, message="Circuit breaker is open", service=None, open_until=None, *args, **kwargs):
        self.service = service
        self.open_until = open_until
        
        if service and open_until:
            message = f"{message} for service {service} until {open_until}"
        elif service:
            message = f"{message} for service {service}"
            
        super().__init__(message, *args, **kwargs) 