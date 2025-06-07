"""
Shared infrastructure configuration module.

This module provides the unified configuration system for the AlgoBeta project.
"""

from .settings import (
    Environment,
    BaseConfig,
    DevelopmentConfig,
    StagingConfig,
    ProductionConfig,
    FinancialConfig,
    StockScreenerConfig,
    ConfigurationManager,
    get_config,
    get_financial_config,
    get_stock_screener_config,
    build_config,
)

__all__ = [
    "Environment",
    "BaseConfig",
    "DevelopmentConfig",
    "StagingConfig",
    "ProductionConfig",
    "FinancialConfig",
    "StockScreenerConfig",
    "ConfigurationManager",
    "get_config",
    "get_financial_config",
    "get_stock_screener_config",
    "build_config",
]
