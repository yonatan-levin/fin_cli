"""Tests for the finpack logging utilities.

These tests validate that logging configuration is explicit and that helper
functions behave predictably for both console and file output.
"""

from __future__ import annotations

import importlib
import logging
import sys
from pathlib import Path


def reload_logging_module():
    """Reload the logging module to reset module-level state for each test."""

    sys.modules.pop("finpack.utils.logging", None)
    return importlib.import_module("finpack.utils.logging")


def test_logging_is_not_configured_on_import():
    """Importing the module must not configure handlers automatically."""

    module = reload_logging_module()

    assert module.is_logging_configured() is False


def test_configure_logging_with_console_handler(tmp_path: Path):
    """Console handler should be available when requested explicitly."""

    module = reload_logging_module()

    config = module.FinPackConfig(
        log_level="DEBUG",
        log_to_console=True,
        log_to_file=False,
    )

    logger = module.configure_logging(config)

    assert module.is_logging_configured() is True
    assert any(isinstance(handler, logging.StreamHandler) for handler in logger.handlers)


def test_configure_logging_with_file_handler(tmp_path: Path):
    """File handler should write logs to the provided directory."""

    module = reload_logging_module()

    config = module.FinPackConfig(
        log_level="INFO",
        log_to_console=False,
        log_to_file=True,
        log_file_name="finpack-test.log",
        log_directory=tmp_path,
    )

    logger = module.configure_logging(config)

    assert any(isinstance(handler, logging.FileHandler) for handler in logger.handlers)
    log_file = tmp_path / "finpack-test.log"
    assert log_file.exists()


def test_reset_logging_allows_reconfiguration(tmp_path: Path):
    """reset_logging should clear handlers for deterministic reconfiguration."""

    module = reload_logging_module()

    config = module.FinPackConfig(
        log_level="WARNING",
        log_to_console=True,
        log_to_file=True,
        log_file_name="finpack-test.log",
        log_directory=tmp_path,
    )

    module.configure_logging(config)
    assert module.is_logging_configured() is True

    module.reset_logging()
    assert module.is_logging_configured() is False

    module.configure_logging(config)
    assert module.is_logging_configured() is True
 
