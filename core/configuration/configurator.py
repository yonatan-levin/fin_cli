"""
Configuration builder module.

This module provides backward compatibility while delegating to the new shared configuration system.
"""
import json
import os
from shared.infrastructure.config import build_config as shared_build_config, BaseConfig
from ..converters.json import json_to_tuples


def build_config(
    use_history: bool = False,
    filters: str = ""
) -> BaseConfig:
    """
    Create the configuration using the new shared configuration system.

    This function maintains backward compatibility while using the enhanced configuration system.

    Args:
        use_history: Whether to use filter history
        filters: Filter string to parse

    Returns:
        BaseConfig instance with the requested configuration
    """
    return shared_build_config(use_history=use_history, filters=filters)
