"""
API Keys Configuration Management.

This module provides easy configuration management for financial data provider API keys
and settings. It supports environment variables, config files, and direct configuration.
"""
import os
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from pathlib import Path
import json

from shared.infrastructure.logging.log_manager import LogManager

logger = LogManager().get_logger("api_keys_config")


@dataclass
class ApiKeysConfig:
    """
    Configuration for financial data provider API keys.

    This class manages API keys and settings for various financial data providers
    with support for environment variables and config files.
    """
    # Alpha Vantage settings
    alpha_vantage_api_key: Optional[str] = None
    alpha_vantage_enabled: bool = False
    alpha_vantage_rate_limit: int = 5  # requests per minute (free tier)

    # IEX Cloud settings
    iex_cloud_api_token: Optional[str] = None
    iex_cloud_enabled: bool = False
    iex_cloud_is_sandbox: bool = True  # Use sandbox by default
    iex_cloud_rate_limit: int = 100  # requests per second

    # Polygon.io settings
    polygon_api_key: Optional[str] = None
    polygon_enabled: bool = False
    polygon_rate_limit: int = 5  # requests per minute (free tier)

    # Financial Modeling Prep settings
    fmp_api_key: Optional[str] = None
    fmp_enabled: bool = False
    fmp_rate_limit: int = 250  # requests per day (free tier)

    # Provider selection and fallback settings
    primary_provider: str = "yfinance"
    enable_fallback_providers: bool = True
    provider_timeout: int = 30  # seconds

    # Cache settings
    cache_ttl: int = 3600  # 1 hour
    enable_memory_cache: bool = True

    def __post_init__(self):
        """Automatically load configuration from environment variables."""
        self.load_from_environment()
        self._auto_enable_providers()

    def load_from_environment(self):
        """Load API keys and settings from environment variables."""
        # Alpha Vantage
        if os.getenv('ALPHA_VANTAGE_API_KEY'):
            self.alpha_vantage_api_key = os.getenv('ALPHA_VANTAGE_API_KEY')
            logger.info("Loaded Alpha Vantage API key from environment")

        if os.getenv('ALPHA_VANTAGE_RATE_LIMIT'):
            try:
                self.alpha_vantage_rate_limit = int(
                    os.getenv('ALPHA_VANTAGE_RATE_LIMIT'))
            except ValueError:
                logger.warning(
                    "Invalid ALPHA_VANTAGE_RATE_LIMIT, using default")

        # IEX Cloud
        if os.getenv('IEX_CLOUD_API_TOKEN'):
            self.iex_cloud_api_token = os.getenv('IEX_CLOUD_API_TOKEN')
            logger.info("Loaded IEX Cloud API token from environment")

        if os.getenv('IEX_CLOUD_IS_SANDBOX'):
            self.iex_cloud_is_sandbox = os.getenv(
                'IEX_CLOUD_IS_SANDBOX', 'true').lower() == 'true'

        if os.getenv('IEX_CLOUD_RATE_LIMIT'):
            try:
                self.iex_cloud_rate_limit = int(
                    os.getenv('IEX_CLOUD_RATE_LIMIT'))
            except ValueError:
                logger.warning("Invalid IEX_CLOUD_RATE_LIMIT, using default")

        # Polygon.io
        if os.getenv('POLYGON_API_KEY'):
            self.polygon_api_key = os.getenv('POLYGON_API_KEY')
            logger.info("Loaded Polygon API key from environment")

        # Financial Modeling Prep
        if os.getenv('FMP_API_KEY'):
            self.fmp_api_key = os.getenv('FMP_API_KEY')
            logger.info(
                "Loaded Financial Modeling Prep API key from environment")

        # Provider settings
        if os.getenv('PRIMARY_PROVIDER'):
            self.primary_provider = os.getenv('PRIMARY_PROVIDER')

        if os.getenv('ENABLE_FALLBACK_PROVIDERS'):
            self.enable_fallback_providers = os.getenv(
                'ENABLE_FALLBACK_PROVIDERS', 'true').lower() == 'true'

        if os.getenv('PROVIDER_TIMEOUT'):
            try:
                self.provider_timeout = int(os.getenv('PROVIDER_TIMEOUT'))
            except ValueError:
                logger.warning("Invalid PROVIDER_TIMEOUT, using default")

        # Cache settings
        if os.getenv('CACHE_TTL'):
            try:
                self.cache_ttl = int(os.getenv('CACHE_TTL'))
            except ValueError:
                logger.warning("Invalid CACHE_TTL, using default")

    def _auto_enable_providers(self):
        """Automatically enable providers that have API keys configured."""
        if self.alpha_vantage_api_key:
            self.alpha_vantage_enabled = True
            logger.info("Auto-enabled Alpha Vantage provider")

        if self.iex_cloud_api_token:
            self.iex_cloud_enabled = True
            logger.info("Auto-enabled IEX Cloud provider")

        if self.polygon_api_key:
            self.polygon_enabled = True
            logger.info("Auto-enabled Polygon provider")

        if self.fmp_api_key:
            self.fmp_enabled = True
            logger.info("Auto-enabled Financial Modeling Prep provider")

    def load_from_file(self, config_path: str):
        """
        Load configuration from a JSON file.

        Args:
            config_path: Path to the configuration file
        """
        try:
            config_file = Path(config_path)
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config_data = json.load(f)

                    # Update attributes from config data
                    for key, value in config_data.items():
                        if hasattr(self, key):
                            setattr(self, key, value)

                    logger.info(f"Loaded configuration from {config_path}")
                    self._auto_enable_providers()
            else:
                logger.warning(f"Configuration file not found: {config_path}")
        except Exception as e:
            logger.error(f"Error loading configuration from file: {e}")

    def save_to_file(self, config_path: str):
        """
        Save current configuration to a JSON file.

        Args:
            config_path: Path where to save the configuration
        """
        try:
            config_data = {
                'alpha_vantage_api_key': self.alpha_vantage_api_key,
                'alpha_vantage_enabled': self.alpha_vantage_enabled,
                'alpha_vantage_rate_limit': self.alpha_vantage_rate_limit,
                'iex_cloud_api_token': self.iex_cloud_api_token,
                'iex_cloud_enabled': self.iex_cloud_enabled,
                'iex_cloud_is_sandbox': self.iex_cloud_is_sandbox,
                'iex_cloud_rate_limit': self.iex_cloud_rate_limit,
                'polygon_api_key': self.polygon_api_key,
                'polygon_enabled': self.polygon_enabled,
                'polygon_rate_limit': self.polygon_rate_limit,
                'fmp_api_key': self.fmp_api_key,
                'fmp_enabled': self.fmp_enabled,
                'fmp_rate_limit': self.fmp_rate_limit,
                'primary_provider': self.primary_provider,
                'enable_fallback_providers': self.enable_fallback_providers,
                'provider_timeout': self.provider_timeout,
                'cache_ttl': self.cache_ttl,
                'enable_memory_cache': self.enable_memory_cache,
            }

            config_file = Path(config_path)
            config_file.parent.mkdir(parents=True, exist_ok=True)

            with open(config_file, 'w') as f:
                json.dump(config_data, f, indent=2)

            logger.info(f"Saved configuration to {config_path}")
        except Exception as e:
            logger.error(f"Error saving configuration to file: {e}")

    def get_enabled_providers(self) -> list:
        """
        Get a list of enabled providers.

        Returns:
            List of enabled provider names
        """
        enabled = ['yfinance']  # yfinance is always available

        if self.alpha_vantage_enabled:
            enabled.append('alpha_vantage')
        if self.iex_cloud_enabled:
            enabled.append('iex_cloud')
        if self.polygon_enabled:
            enabled.append('polygon')
        if self.fmp_enabled:
            enabled.append('fmp')

        return enabled

    def validate_configuration(self) -> Dict[str, Any]:
        """
        Validate the current configuration.

        Returns:
            Dictionary with validation results
        """
        validation = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'enabled_providers': self.get_enabled_providers()
        }

        # Check API keys for enabled providers
        if self.alpha_vantage_enabled and not self.alpha_vantage_api_key:
            validation['errors'].append(
                "Alpha Vantage enabled but no API key provided")
            validation['valid'] = False

        if self.iex_cloud_enabled and not self.iex_cloud_api_token:
            validation['errors'].append(
                "IEX Cloud enabled but no API token provided")
            validation['valid'] = False

        if self.polygon_enabled and not self.polygon_api_key:
            validation['errors'].append(
                "Polygon enabled but no API key provided")
            validation['valid'] = False

        if self.fmp_enabled and not self.fmp_api_key:
            validation['errors'].append(
                "Financial Modeling Prep enabled but no API key provided")
            validation['valid'] = False

        # Check primary provider
        if self.primary_provider not in ['yfinance', 'alpha_vantage', 'iex_cloud', 'polygon', 'fmp', 'composite']:
            validation['warnings'].append(
                f"Unknown primary provider: {self.primary_provider}")

        # Check if only yfinance is available
        if len(validation['enabled_providers']) == 1:
            validation['warnings'].append(
                "Only yfinance provider is available. Consider adding API keys for additional providers.")

        return validation

    def __str__(self) -> str:
        """String representation of the configuration."""
        enabled_providers = self.get_enabled_providers()
        return f"ApiKeysConfig(primary={self.primary_provider}, enabled_providers={enabled_providers})"


# Global configuration instance
_global_config: Optional[ApiKeysConfig] = None


def get_api_keys_config() -> ApiKeysConfig:
    """
    Get the global API keys configuration instance.

    Returns:
        Global ApiKeysConfig instance
    """
    global _global_config
    if _global_config is None:
        _global_config = ApiKeysConfig()
        logger.info("Created global API keys configuration")
    return _global_config


def load_config_from_file(config_path: str) -> ApiKeysConfig:
    """
    Load configuration from a file and set it as global config.

    Args:
        config_path: Path to the configuration file

    Returns:
        Loaded ApiKeysConfig instance
    """
    global _global_config
    _global_config = ApiKeysConfig()
    _global_config.load_from_file(config_path)
    return _global_config


def create_sample_config_file(config_path: str = "config/api_keys.json"):
    """
    Create a sample configuration file with explanations.

    Args:
        config_path: Path where to create the sample file
    """
    sample_config = {
        "_comment": "Sample API keys configuration file",
        "_instructions": {
            "alpha_vantage": "Get your free API key from: https://www.alphavantage.co/support/#api-key",
            "iex_cloud": "Get your API token from: https://iexcloud.io/console/",
            "polygon": "Get your API key from: https://polygon.io/dashboard",
            "fmp": "Get your API key from: https://financialmodelingprep.com/developer/docs"
        },
        "alpha_vantage_api_key": "YOUR_ALPHA_VANTAGE_API_KEY_HERE",
        "alpha_vantage_enabled": False,
        "alpha_vantage_rate_limit": 5,
        "iex_cloud_api_token": "YOUR_IEX_CLOUD_API_TOKEN_HERE",
        "iex_cloud_enabled": False,
        "iex_cloud_is_sandbox": True,
        "iex_cloud_rate_limit": 100,
        "polygon_api_key": "YOUR_POLYGON_API_KEY_HERE",
        "polygon_enabled": False,
        "polygon_rate_limit": 5,
        "fmp_api_key": "YOUR_FMP_API_KEY_HERE",
        "fmp_enabled": False,
        "fmp_rate_limit": 250,
        "primary_provider": "composite",
        "enable_fallback_providers": True,
        "provider_timeout": 30,
        "cache_ttl": 3600,
        "enable_memory_cache": True
    }

    try:
        config_file = Path(config_path)
        config_file.parent.mkdir(parents=True, exist_ok=True)

        with open(config_file, 'w') as f:
            json.dump(sample_config, f, indent=2)

        logger.info(f"Created sample configuration file: {config_path}")
        print(f"📝 Sample configuration file created: {config_path}")
        print("📖 Edit this file with your API keys and settings")
    except Exception as e:
        logger.error(f"Error creating sample config file: {e}")
        print(f"❌ Error creating sample config file: {e}")


if __name__ == "__main__":
    # Create sample config when run directly
    create_sample_config_file()

    # Demonstrate configuration usage
    config = get_api_keys_config()
    print(f"\n🔧 Current configuration: {config}")

    validation = config.validate_configuration()
    print(f"\n✅ Configuration validation: {validation}")
