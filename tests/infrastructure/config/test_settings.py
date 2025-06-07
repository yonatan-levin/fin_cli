"""
Unit tests for settings configuration module.
"""
import unittest
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from fundainsight.infrastructure.config.settings import (
    BaseConfig,
    DevelopmentConfig,
    Environment,
    FinancialConfig,
    ProductionConfig,
    StagingConfig,
    ConfigurationManager,
    get_config,
    get_financial_config
)


class TestEnvironment(unittest.TestCase):
    """Test cases for the Environment enum."""

    def test_from_string_valid(self):
        """Test creating an Environment from a valid string."""
        # Test all valid environments
        self.assertEqual(Environment.from_string("development"), Environment.DEVELOPMENT)
        self.assertEqual(Environment.from_string("staging"), Environment.STAGING)
        self.assertEqual(Environment.from_string("production"), Environment.PRODUCTION)
        
        # Test case insensitivity
        self.assertEqual(Environment.from_string("DEVELOPMENT"), Environment.DEVELOPMENT)
        self.assertEqual(Environment.from_string("Staging"), Environment.STAGING)
        self.assertEqual(Environment.from_string("Production"), Environment.PRODUCTION)
    
    def test_from_string_invalid(self):
        """Test creating an Environment from an invalid string."""
        with self.assertRaises(ValueError):
            Environment.from_string("invalid_environment")
    
    @patch.dict(os.environ, {"ENVIRONMENT": "production"})
    def test_current_from_env(self):
        """Test getting the current environment from environment variable."""
        self.assertEqual(Environment.current(), Environment.PRODUCTION)
    
    @patch.dict(os.environ, {}, clear=True)
    def test_current_default(self):
        """Test getting the default environment when not set."""
        self.assertEqual(Environment.current(), Environment.DEVELOPMENT)


class TestBaseConfig(unittest.TestCase):
    """Test cases for the BaseConfig class."""

    def test_initialization(self):
        """Test initializing a BaseConfig with default values."""
        config = BaseConfig()
        
        # Test default values
        self.assertEqual(config.app_name, "Fundainsight")
        self.assertEqual(config.app_version, "1.0.0")
        self.assertEqual(config.environment, Environment.DEVELOPMENT)
        self.assertEqual(config.log_level, "INFO")
        self.assertEqual(config.debug_mode, False)
        self.assertEqual(config.use_cache, True)
    
    def test_initialization_with_custom_values(self):
        """Test initializing a BaseConfig with custom values."""
        config = BaseConfig(
            app_name="TestApp",
            app_version="2.0.0",
            environment=Environment.PRODUCTION,
            log_level="WARNING",
            debug_mode=True,
            use_cache=False
        )
        
        # Test custom values
        self.assertEqual(config.app_name, "TestApp")
        self.assertEqual(config.app_version, "2.0.0")
        self.assertEqual(config.environment, Environment.PRODUCTION)
        self.assertEqual(config.log_level, "WARNING")
        self.assertEqual(config.debug_mode, True)
        self.assertEqual(config.use_cache, False)
    
    def test_to_dict(self):
        """Test converting BaseConfig to a dictionary."""
        config = BaseConfig(
            app_name="TestApp",
            environment=Environment.PRODUCTION
        )
        
        config_dict = config.to_dict()
        
        # Test dictionary values
        self.assertEqual(config_dict["app_name"], "TestApp")
        self.assertEqual(config_dict["environment"], "production")  # Should be string, not enum
    
    def test_file_path(self):
        """Test generating a file path with timestamp."""
        config = BaseConfig(output_dir="/tmp")
        
        # Test file path generation
        file_path = config.file_path("test_file", "csv")
        
        # Validate path components
        self.assertTrue(file_path.startswith("/tmp/test_file_"))
        self.assertTrue(file_path.endswith(".csv"))
        
        # Check for timestamp format
        timestamp_part = file_path.replace("/tmp/test_file_", "").replace(".csv", "")
        self.assertRegex(timestamp_part, r"\d{4}-\d{2}-\d{2}_\d{2}-\d{2}")


class TestEnvironmentConfigs(unittest.TestCase):
    """Test cases for environment-specific configuration classes."""

    def test_development_config(self):
        """Test DevelopmentConfig values."""
        config = DevelopmentConfig()
        
        self.assertEqual(config.environment, Environment.DEVELOPMENT)
        self.assertEqual(config.debug_mode, True)
        self.assertEqual(config.log_level, "DEBUG")
    
    def test_staging_config(self):
        """Test StagingConfig values."""
        config = StagingConfig()
        
        self.assertEqual(config.environment, Environment.STAGING)
        self.assertEqual(config.debug_mode, False)
        self.assertEqual(config.log_level, "INFO")
    
    def test_production_config(self):
        """Test ProductionConfig values."""
        config = ProductionConfig()
        
        self.assertEqual(config.environment, Environment.PRODUCTION)
        self.assertEqual(config.debug_mode, False)
        self.assertEqual(config.log_level, "WARNING")
        self.assertEqual(config.use_cache, True)
        self.assertEqual(config.api_timeout, 60)  # Higher timeout in production
    
    def test_financial_config(self):
        """Test FinancialConfig values."""
        config = FinancialConfig()
        
        # Verify financial-specific settings
        self.assertEqual(config.yahoo_finance_rate_limit, 5)
        self.assertEqual(config.yahoo_finance_timeout, 30)
        self.assertEqual(config.finviz_rate_limit, 2)
        self.assertEqual(config.cache_ttl, 86400)  # 24 hours
        self.assertEqual(config.circuit_breaker_failure_threshold, 5)
        self.assertEqual(config.circuit_breaker_recovery_timeout, 60)
        
        # Verify BaseConfig values are inherited
        self.assertEqual(config.app_name, "Fundainsight")
        self.assertEqual(config.environment, Environment.DEVELOPMENT)


class TestConfigurationManager(unittest.TestCase):
    """Test cases for the ConfigurationManager class."""

    def setUp(self):
        """Set up tests with temporary files and environment variables."""
        # Create a temporary config file for testing
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_file = Path(self.temp_dir.name) / "config.json"
        
        # Sample config JSON
        config_data = {
            "app_name": "TestFromFile",
            "log_level": "ERROR",
            "debug_mode": True
        }
        
        # Write to the file
        with open(self.config_file, "w") as f:
            json.dump(config_data, f)
        
        # Clear environment for test isolation
        self.env_patcher = patch.dict(os.environ, {}, clear=True)
        self.env_patcher.start()
    
    def tearDown(self):
        """Clean up after tests."""
        self.temp_dir.cleanup()
        self.env_patcher.stop()
    
    def test_load_config_development(self):
        """Test loading development configuration."""
        # Set up development environment
        os.environ["ENVIRONMENT"] = "development"
        
        # Create manager and load config
        manager = ConfigurationManager(BaseConfig)
        config = manager.load_config()
        
        # Verify development config is loaded
        self.assertEqual(config.environment, Environment.DEVELOPMENT)
        self.assertEqual(config.log_level, "INFO")  # Default from BaseConfig
    
    def test_load_config_production(self):
        """Test loading production configuration."""
        # Set up production environment
        os.environ["ENVIRONMENT"] = "production"
        
        # Create manager and load config
        manager = ConfigurationManager(BaseConfig)
        config = manager.load_config()
        
        # Verify production config is loaded
        self.assertEqual(config.environment, Environment.PRODUCTION)
        self.assertEqual(config.log_level, "WARNING")  # From ProductionConfig
    
    def test_update_from_env_vars(self):
        """Test updating configuration from environment variables."""
        # Set environment variables
        os.environ["FUNDAINSIGHT_APP_NAME"] = "EnvApp"
        os.environ["FUNDAINSIGHT_LOG_LEVEL"] = "CRITICAL"
        os.environ["FUNDAINSIGHT_DEBUG_MODE"] = "true"
        
        # Create manager and load config
        manager = ConfigurationManager(BaseConfig)
        config = manager.load_config()
        
        # Verify environment variables override defaults
        self.assertEqual(config.app_name, "EnvApp")
        self.assertEqual(config.log_level, "CRITICAL")
        self.assertEqual(config.debug_mode, True)
    
    def test_update_from_file(self):
        """Test updating configuration from a file."""
        # Set environment to point to config file
        os.environ["FUNDAINSIGHT_CONFIG_FILE"] = str(self.config_file)
        
        # Create manager and load config
        manager = ConfigurationManager(BaseConfig)
        config = manager.load_config()
        
        # Verify file values override defaults
        self.assertEqual(config.app_name, "TestFromFile")
        self.assertEqual(config.log_level, "ERROR")
        self.assertEqual(config.debug_mode, True)
    
    def test_config_precedence(self):
        """Test configuration source precedence (env vars > file > defaults)."""
        # Set environment to point to config file
        os.environ["FUNDAINSIGHT_CONFIG_FILE"] = str(self.config_file)
        
        # Also set conflicting environment variables (should take precedence)
        os.environ["FUNDAINSIGHT_APP_NAME"] = "EnvOverride"
        
        # Create manager and load config
        manager = ConfigurationManager(BaseConfig)
        config = manager.load_config()
        
        # Verify precedence: env var > file > default
        self.assertEqual(config.app_name, "EnvOverride")  # From env var
        self.assertEqual(config.log_level, "ERROR")       # From file
        self.assertEqual(config.debug_mode, True)         # From file
        self.assertEqual(config.use_cache, True)          # Default value
    
    def test_config_property(self):
        """Test the config property that initializes configuration on first access."""
        # Create manager
        manager = ConfigurationManager(BaseConfig)
        
        # Access config property
        config = manager.config
        
        # Verify config is loaded and cached
        self.assertIsNotNone(config)
        self.assertIsInstance(config, BaseConfig)
        
        # Verify it's the same instance on second access
        second_access = manager.config
        self.assertIs(second_access, config)


class TestGlobalConfigFunctions(unittest.TestCase):
    """Test cases for global configuration functions."""

    @patch('fundainsight.infrastructure.config.settings.ConfigurationManager')
    def test_get_config(self, mock_manager_class):
        """Test get_config global function."""
        # Setup mock
        mock_manager = mock_manager_class.return_value
        mock_config = BaseConfig(app_name="MockApp")
        mock_manager.config = mock_config
        
        # Call function
        config = get_config()
        
        # Verify manager was created with correct class
        mock_manager_class.assert_called_once_with(BaseConfig)
        
        # Verify result is the mock config
        self.assertEqual(config, mock_config)
    
    @patch('fundainsight.infrastructure.config.settings.ConfigurationManager')
    def test_get_financial_config(self, mock_manager_class):
        """Test get_financial_config global function."""
        # Setup mock
        mock_manager = mock_manager_class.return_value
        mock_config = FinancialConfig(app_name="MockFinApp")
        mock_manager.config = mock_config
        
        # Call function
        config = get_financial_config()
        
        # Verify manager was created with correct class
        mock_manager_class.assert_called_once_with(FinancialConfig)
        
        # Verify result is the mock config
        self.assertEqual(config, mock_config)


if __name__ == "__main__":
    unittest.main() 