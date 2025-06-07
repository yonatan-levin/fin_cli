"""
Unit tests for shared configuration settings module.
"""
import unittest
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from shared.infrastructure.config.settings import (
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


class TestEnvironment(unittest.TestCase):
    """Test cases for the Environment enum."""

    def test_from_string_valid(self):
        """Test creating an Environment from a valid string."""
        # Test all valid environments
        self.assertEqual(Environment.from_string(
            "development"), Environment.DEVELOPMENT)
        self.assertEqual(Environment.from_string(
            "staging"), Environment.STAGING)
        self.assertEqual(Environment.from_string(
            "production"), Environment.PRODUCTION)

        # Test case insensitivity
        self.assertEqual(Environment.from_string(
            "DEVELOPMENT"), Environment.DEVELOPMENT)
        self.assertEqual(Environment.from_string(
            "Development"), Environment.DEVELOPMENT)

    def test_from_string_invalid(self):
        """Test creating an Environment from an invalid string."""
        with self.assertRaises(ValueError):
            Environment.from_string("invalid")

    @patch.dict(os.environ, {"ENVIRONMENT": "production"})
    def test_current_from_env(self):
        """Test getting current environment from environment variable."""
        self.assertEqual(Environment.current(), Environment.PRODUCTION)

    @patch.dict(os.environ, {}, clear=True)
    def test_current_default(self):
        """Test getting current environment with default value."""
        self.assertEqual(Environment.current(), Environment.DEVELOPMENT)


class TestBaseConfig(unittest.TestCase):
    """Test cases for the BaseConfig class."""

    def test_initialization(self):
        """Test BaseConfig initialization with default values."""
        config = BaseConfig()

        self.assertEqual(config.app_name, "AlgoBeta")
        self.assertEqual(config.app_version, "1.0.0")
        self.assertEqual(config.environment, Environment.DEVELOPMENT)
        self.assertEqual(config.log_level, "INFO")
        self.assertFalse(config.debug_mode)
        self.assertTrue(config.use_cache)
        self.assertFalse(config.use_history)
        self.assertEqual(config.filters, ())
        self.assertEqual(config.scrape_link, "")

    def test_initialization_with_custom_values(self):
        """Test BaseConfig initialization with custom values."""
        config = BaseConfig(
            app_name="Test App",
            debug_mode=True,
            use_history=True,
            filters=(("key", "value"),),
            scrape_link="http://example.com"
        )

        self.assertEqual(config.app_name, "Test App")
        self.assertTrue(config.debug_mode)
        self.assertTrue(config.use_history)
        self.assertEqual(config.filters, (("key", "value"),))
        self.assertEqual(config.scrape_link, "http://example.com")

    def test_to_dict(self):
        """Test converting BaseConfig to dictionary."""
        config = BaseConfig(app_name="Test App", debug_mode=True)
        config_dict = config.to_dict()

        self.assertEqual(config_dict["app_name"], "Test App")
        self.assertTrue(config_dict["debug_mode"])
        self.assertEqual(config_dict["environment"], "development")

    def test_file_path(self):
        """Test file path generation."""
        config = BaseConfig()
        file_path = config.file_path("test_file")

        # Check that the path contains the expected elements
        self.assertIn("workspace_output", file_path)
        self.assertIn("test_file", file_path)
        self.assertTrue(file_path.endswith(".csv"))


class TestEnvironmentConfigs(unittest.TestCase):
    """Test cases for environment-specific configurations."""

    def test_development_config(self):
        """Test DevelopmentConfig initialization."""
        config = DevelopmentConfig()

        self.assertEqual(config.environment, Environment.DEVELOPMENT)
        self.assertTrue(config.debug_mode)
        self.assertEqual(config.log_level, "DEBUG")

    def test_staging_config(self):
        """Test StagingConfig initialization."""
        config = StagingConfig()

        self.assertEqual(config.environment, Environment.STAGING)
        self.assertFalse(config.debug_mode)
        self.assertEqual(config.log_level, "INFO")

    def test_production_config(self):
        """Test ProductionConfig initialization."""
        config = ProductionConfig()

        self.assertEqual(config.environment, Environment.PRODUCTION)
        self.assertFalse(config.debug_mode)
        self.assertEqual(config.log_level, "WARNING")
        self.assertTrue(config.use_cache)
        self.assertEqual(config.api_timeout, 60)

    def test_financial_config(self):
        """Test FinancialConfig initialization."""
        config = FinancialConfig()

        # Test financial-specific settings
        self.assertEqual(config.yahoo_finance_rate_limit, 5)
        self.assertEqual(config.finviz_rate_limit, 2)
        self.assertEqual(config.cache_ttl, 86400)
        self.assertEqual(config.circuit_breaker_failure_threshold, 5)
        self.assertEqual(config.circuit_breaker_recovery_timeout, 60)

    def test_stock_screener_config(self):
        """Test StockScreenerConfig initialization."""
        config = StockScreenerConfig()

        # Test screener-specific settings
        self.assertEqual(config.app_name, "Stock Screener CLI")
        self.assertEqual(config.base_url, "https://finviz.com/")
        self.assertEqual(config.default_screener_version, 111)
        self.assertEqual(config.default_filter_type, 2)
        self.assertEqual(config.request_delay, 1.0)
        self.assertEqual(config.max_retries, 3)


class TestConfigurationManager(unittest.TestCase):
    """Test cases for the ConfigurationManager class."""

    def setUp(self):
        """Set up test fixtures."""
        self.manager = ConfigurationManager(BaseConfig)

        # Mock environment variables
        self.env_patcher = patch.dict(os.environ, {}, clear=True)
        self.env_patcher.start()

    def tearDown(self):
        """Clean up after tests."""
        self.env_patcher.stop()

    @patch.dict(os.environ, {"ENVIRONMENT": "development"})
    def test_load_config_development(self):
        """Test loading development configuration."""
        config = self.manager.load_config()

        # Should be development config
        self.assertEqual(config.environment, Environment.DEVELOPMENT)
        self.assertTrue(config.debug_mode)
        self.assertEqual(config.log_level, "DEBUG")

    @patch.dict(os.environ, {"ENVIRONMENT": "production"})
    def test_load_config_production(self):
        """Test loading production configuration."""
        config = self.manager.load_config()

        # Should be production config
        self.assertEqual(config.environment, Environment.PRODUCTION)
        self.assertFalse(config.debug_mode)
        self.assertEqual(config.log_level, "WARNING")

    @patch.dict(os.environ, {"ALGOBETA_DEBUG_MODE": "true", "ALGOBETA_LOG_LEVEL": "ERROR"})
    def test_update_from_env_vars(self):
        """Test updating configuration from environment variables."""
        config = self.manager.load_config()

        self.assertTrue(config.debug_mode)
        self.assertEqual(config.log_level, "ERROR")

    def test_update_from_file(self):
        """Test updating configuration from JSON file."""
        # Create a temporary config file
        config_data = {
            "app_name": "Test From File",
            "debug_mode": True,
            "api_timeout": 45
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_file_path = f.name

        try:
            with patch.dict(os.environ, {"CONFIG_FILE": config_file_path}):
                config = self.manager.load_config()

                self.assertEqual(config.app_name, "Test From File")
                self.assertTrue(config.debug_mode)
                self.assertEqual(config.api_timeout, 45)
        finally:
            os.unlink(config_file_path)

    def test_load_config_with_kwargs(self):
        """Test loading configuration with additional parameters."""
        config = self.manager.load_config(
            app_name="Custom App",
            use_history=True,
            filters=(("test", "value"),)
        )

        self.assertEqual(config.app_name, "Custom App")
        self.assertTrue(config.use_history)
        self.assertEqual(config.filters, (("test", "value"),))

    def test_config_property(self):
        """Test the config property caching."""
        # First access should load config
        config1 = self.manager.config

        # Second access should return cached config
        config2 = self.manager.config

        self.assertIs(config1, config2)


class TestGlobalConfigFunctions(unittest.TestCase):
    """Test cases for global configuration functions."""

    def test_get_config(self):
        """Test get_config function."""
        config = get_config()
        self.assertIsInstance(config, BaseConfig)

    def test_get_financial_config(self):
        """Test get_financial_config function."""
        config = get_financial_config()
        self.assertIsInstance(config, FinancialConfig)

    def test_get_stock_screener_config(self):
        """Test get_stock_screener_config function."""
        config = get_stock_screener_config()
        self.assertIsInstance(config, StockScreenerConfig)

    def test_build_config_basic(self):
        """Test build_config function with basic parameters."""
        config = build_config(use_history=True, filters='{"key": "value"}')

        self.assertTrue(config.use_history)
        # Note: The filters parsing depends on the json_to_tuples function

    def test_build_config_with_history(self):
        """Test build_config function with history enabled."""
        # Create a mock history file
        history_dir = Path("fincli/stock_screening/local_history")
        history_dir.mkdir(parents=True, exist_ok=True)
        history_file = history_dir / "filter_history.json"

        test_filters = {"filter1": "value1", "filter2": "value2"}

        try:
            with open(history_file, 'w') as f:
                json.dump(test_filters, f)

            config = build_config(use_history=True)

            self.assertTrue(config.use_history)
            self.assertEqual(config.filters, tuple(test_filters.items()))

        finally:
            # Clean up
            if history_file.exists():
                history_file.unlink()


if __name__ == '__main__':
    unittest.main()
