"""
Config file for the stock screener app.

DEPRECATED: This module is maintained for backward compatibility.
Use shared.infrastructure.config instead for new code.
"""
import datetime
import os
from typing import Any
from shared.infrastructure.config import BaseConfig, get_stock_screener_config


# ---- Legacy stubs to remove dependency on deprecated *core* package ----
# These minimal classes preserve the previous public API surface without
# importing `core.configuration.config_base`.

class SystemSettings:
    """Very thin placeholder that mimics the old pydantic-based SystemSettings."""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class Configurable:
    """Placeholder generic base – kept only for backward compatibility."""

    default_settings = None

    @classmethod
    def get_user_config(cls):
        return cls.default_settings


class Config(SystemSettings):
    """
    Legacy configuration class for backward compatibility.

    DEPRECATED: Use shared.infrastructure.config.StockScreenerConfig instead.
    """
    name: str = "Stock Screener CLI config"
    description: str = "Configuration for the Stock Screener CLI app."
    ########################
    # Application Settings #
    ########################
    use_history: bool = False
    filters: tuple = ()
    scrape_link: str = ""

    def __init__(self, **kwargs):
        """Initialize config, delegating to the new shared config system when possible."""
        super().__init__(**kwargs)

        # Try to get values from the new config system
        try:
            shared_config = get_stock_screener_config()
            self.use_history = getattr(
                shared_config, 'use_history', self.use_history)
            self.filters = getattr(shared_config, 'filters', self.filters)
            self.scrape_link = getattr(
                shared_config, 'scrape_link', self.scrape_link)
        except Exception:
            # Fall back to default values if shared config fails
            pass

    @staticmethod
    def file_path(file_name: str) -> str:
        """
        Return the path to the file.

        DEPRECATED: Use BaseConfig.file_path() instead.
        """
        date = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M')
        return os.path.join(os.getcwd(), f'workspace_output/{file_name}_{date}.csv')


# For late use if needed to define a strongly typed config builder.
class ConfigBuilder(Configurable):
    """
    Configuration builder class.

    DEPRECATED: Use shared.infrastructure.config.ConfigurationManager instead.
    """
    default_settings = Config()

    @classmethod
    def build_config_from_env(cls) -> Config:
        """
        Build the configuration.

        DEPRECATED: Use shared.infrastructure.config.build_config() instead.
        """
        config_dict = {
            "use_history": os.getenv("USE_HISTORY", default=cls.default_settings.use_history),
        }

        return Config(**config_dict)
