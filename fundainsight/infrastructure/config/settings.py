"""
Configuration settings module.

This module provides a flexible configuration system with support for different
environments (development, staging, production) and configuration sources
(environment variables, configuration files).
"""
import os
import json
import datetime
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, TypeVar, Generic, cast

# Type variable for configuration classes
T = TypeVar('T', bound='BaseConfig')


class Environment(Enum):
    """Enumeration of supported environments."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    
    @classmethod
    def from_string(cls, value: str) -> 'Environment':
        """
        Create an Environment from a string.
        
        Args:
            value: String representation of environment
            
        Returns:
            Environment enum value
            
        Raises:
            ValueError: If the string is not a valid environment
        """
        try:
            return cls(value.lower())
        except ValueError:
            valid_values = ", ".join([e.value for e in cls])
            raise ValueError(
                f"Invalid environment: {value}. Must be one of: {valid_values}"
            )
    
    @classmethod
    def current(cls) -> 'Environment':
        """
        Get the current environment.
        
        Returns:
            Current environment based on the ENVIRONMENT environment variable
        """
        env_str = os.getenv("ENVIRONMENT", "development").lower()
        return cls.from_string(env_str)


@dataclass
class BaseConfig:
    """Base configuration class with common settings."""
    # Application metadata
    app_name: str = "Fundainsight"
    app_version: str = "1.0.0"
    description: str = "Financial analysis application"
    
    # Environment
    environment: Environment = Environment.DEVELOPMENT
    
    # Logging configuration
    log_level: str = "INFO"
    log_format: str = "text"  # or "json"
    log_dir: Optional[str] = None
    
    # File paths
    output_dir: str = field(default_factory=lambda: os.path.join(os.getcwd(), "workspace_output"))
    
    # Feature flags
    debug_mode: bool = False
    use_cache: bool = True
    
    # API configuration
    api_timeout: int = 30  # seconds
    
    def __post_init__(self):
        """Post-initialization validation and setup."""
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary.
        
        Returns:
            Dictionary representation of configuration
        """
        config_dict = asdict(self)
        
        # Convert Environment enum to string
        if isinstance(config_dict.get("environment"), Environment):
            config_dict["environment"] = config_dict["environment"].value
            
        return config_dict
    
    def file_path(self, file_name: str, extension: str = "csv") -> str:
        """
        Get a path for an output file with timestamp.
        
        Args:
            file_name: Base file name
            extension: File extension without dot
            
        Returns:
            Full path with timestamp
        """
        date = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M')
        return os.path.join(self.output_dir, f"{file_name}_{date}.{extension}")


@dataclass
class DevelopmentConfig(BaseConfig):
    """Development environment configuration."""
    environment: Environment = Environment.DEVELOPMENT
    debug_mode: bool = True
    log_level: str = "DEBUG"


@dataclass
class StagingConfig(BaseConfig):
    """Staging environment configuration."""
    environment: Environment = Environment.STAGING
    debug_mode: bool = False
    log_level: str = "INFO"


@dataclass
class ProductionConfig(BaseConfig):
    """Production environment configuration."""
    environment: Environment = Environment.PRODUCTION
    debug_mode: bool = False
    log_level: str = "WARNING"
    use_cache: bool = True
    api_timeout: int = 60  # seconds


@dataclass
class FinancialConfig(BaseConfig):
    """Financial data specific configuration."""
    # Yahoo Finance settings
    yahoo_finance_rate_limit: int = 5  # requests per second
    yahoo_finance_timeout: int = 30  # seconds
    
    # Finviz settings
    finviz_rate_limit: int = 2  # requests per second
    finviz_timeout: int = 30  # seconds
    
    # Caching
    cache_ttl: int = 86400  # seconds (24 hours)
    
    # Stock filtering
    default_filters: List[str] = field(default_factory=list)
    
    # Circuit breaker settings
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: int = 60  # seconds


class ConfigurationManager(Generic[T]):
    """
    Configuration manager for handling application settings.
    
    This class provides methods for loading configuration from different sources
    and accessing the current configuration.
    """
    
    def __init__(self, config_class: Type[T]):
        """
        Initialize the configuration manager.
        
        Args:
            config_class: The configuration class to use
        """
        self.config_class = config_class
        self._config: Optional[T] = None
    
    @property
    def config(self) -> T:
        """
        Get the current configuration.
        
        Returns:
            Current configuration
            
        Raises:
            RuntimeError: If configuration has not been loaded
        """
        if self._config is None:
            self._config = self.load_config()
        return self._config
    
    def load_config(self) -> T:
        """
        Load configuration based on current environment.
        
        Returns:
            Loaded configuration
        """
        # Get current environment
        environment = Environment.current()
        
        # Load environment-specific configuration
        if environment == Environment.DEVELOPMENT:
            config = self._load_development_config()
        elif environment == Environment.STAGING:
            config = self._load_staging_config()
        else:  # PRODUCTION
            config = self._load_production_config()
        
        # Update with environment variables
        config = self._update_from_env_vars(config)
        
        # Update with configuration file if available
        config_file = os.getenv("CONFIG_FILE")
        if config_file and os.path.exists(config_file):
            config = self._update_from_file(config, config_file)
        
        return config
    
    def _load_development_config(self) -> T:
        """
        Load development configuration.
        
        Returns:
            Development configuration
        """
        if self.config_class == BaseConfig:
            return cast(T, DevelopmentConfig())
        
        # Create default configuration for the specific class
        config = self.config_class()
        
        # Update with development settings
        dev_config = DevelopmentConfig()
        for key, value in dev_config.to_dict().items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        return config
    
    def _load_staging_config(self) -> T:
        """
        Load staging configuration.
        
        Returns:
            Staging configuration
        """
        if self.config_class == BaseConfig:
            return cast(T, StagingConfig())
        
        # Create default configuration for the specific class
        config = self.config_class()
        
        # Update with staging settings
        staging_config = StagingConfig()
        for key, value in staging_config.to_dict().items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        return config
    
    def _load_production_config(self) -> T:
        """
        Load production configuration.
        
        Returns:
            Production configuration
        """
        if self.config_class == BaseConfig:
            return cast(T, ProductionConfig())
        
        # Create default configuration for the specific class
        config = self.config_class()
        
        # Update with production settings
        prod_config = ProductionConfig()
        for key, value in prod_config.to_dict().items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        return config
    
    def _update_from_env_vars(self, config: T) -> T:
        """
        Update configuration from environment variables.
        
        Args:
            config: Configuration to update
            
        Returns:
            Updated configuration
        """
        for key in dir(config):
            # Skip private attributes and methods
            if key.startswith('_') or callable(getattr(config, key)):
                continue
            
            # Environment variable name: FUNDAINSIGHT_<UPPER_KEY>
            env_var_name = f"FUNDAINSIGHT_{key.upper()}"
            env_value = os.getenv(env_var_name)
            
            if env_value is not None:
                attr_value = getattr(config, key)
                
                # Convert to the appropriate type
                if isinstance(attr_value, bool):
                    setattr(config, key, env_value.lower() in ('true', 'yes', '1'))
                elif isinstance(attr_value, int):
                    setattr(config, key, int(env_value))
                elif isinstance(attr_value, float):
                    setattr(config, key, float(env_value))
                elif isinstance(attr_value, list):
                    setattr(config, key, env_value.split(','))
                elif isinstance(attr_value, Environment):
                    setattr(config, key, Environment.from_string(env_value))
                else:
                    setattr(config, key, env_value)
        
        return config
    
    def _update_from_file(self, config: T, file_path: str) -> T:
        """
        Update configuration from a JSON file.
        
        Args:
            config: Configuration to update
            file_path: Path to the JSON configuration file
            
        Returns:
            Updated configuration
        """
        try:
            with open(file_path, 'r') as f:
                config_data = json.load(f)
            
            for key, value in config_data.items():
                if hasattr(config, key):
                    attr_value = getattr(config, key)
                    
                    # Convert to the appropriate type
                    if isinstance(attr_value, Environment):
                        setattr(config, key, Environment.from_string(value))
                    else:
                        setattr(config, key, value)
            
            return config
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading configuration from file {file_path}: {e}")
            return config


# Singleton instances
base_config_manager = ConfigurationManager(BaseConfig)
financial_config_manager = ConfigurationManager(FinancialConfig)


def get_config() -> BaseConfig:
    """
    Get the current base configuration.
    
    Returns:
        Current base configuration
    """
    return base_config_manager.config


def get_financial_config() -> FinancialConfig:
    """
    Get the current financial configuration.
    
    Returns:
        Current financial configuration
    """
    return financial_config_manager.config 