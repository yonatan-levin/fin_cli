"""
Test suite for the consolidated logging system.

This module tests the integration between the legacy logger and the new shared logging system.
"""
import unittest
import tempfile
import os
from pathlib import Path

from logger import logger
from shared.infrastructure.logging import get_logger, log_manager


class TestConsolidatedLogging(unittest.TestCase):
    """Test the consolidated logging system."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test environment."""
        # Clean up temp files
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_legacy_logger_backward_compatibility(self):
        """Test that the legacy logger maintains backward compatibility."""
        # Test basic logging methods
        logger.info("Test info message")
        logger.debug("Test debug message")
        logger.warn("Test warning message")
        logger.error("Test error", "Error message")

        # Test with title and color
        logger.info("Test message", "Test Title", "red")

        # Should not raise any exceptions
        self.assertTrue(True)

    def test_enhanced_logging_with_context(self):
        """Test enhanced logging with context support."""
        # Test context logging
        logger.info("Test with context", context={
                    "key": "value", "number": 42})
        logger.error("Error with context", "Error occurred",
                     context={"error_code": 500})

        # Should not raise any exceptions
        self.assertTrue(True)

    def test_shared_logger_functionality(self):
        """Test the shared logger functionality."""
        shared_logger = get_logger("test_logger")

        # Test basic logging
        shared_logger.info("Shared logger test")
        shared_logger.debug("Debug message")
        shared_logger.warning("Warning message")
        shared_logger.error("Error message")

        # Test with context
        shared_logger.info("Message with context", context={"test": True})

        # Should not raise any exceptions
        self.assertTrue(True)

    def test_log_manager_configuration(self):
        """Test log manager configuration."""
        # Test configuration
        log_manager.configure(
            level=20,  # INFO level
            log_format="text",
            console=True
        )

        # Test logging after configuration
        test_logger = get_logger("configured_test")
        test_logger.info("Test after configuration")

        # Should not raise any exceptions
        self.assertTrue(True)

    def test_legacy_json_logging(self):
        """Test legacy JSON logging functionality."""
        test_data = {"test": "data", "number": 123}
        test_file = Path(self.temp_dir) / "test.json"

        # Test JSON logging
        logger.log_json(test_data, test_file)

        # Verify file was created
        self.assertTrue(test_file.exists())

    def test_log_event_functionality(self):
        """Test structured event logging."""
        # Test event logging through legacy logger
        logger.log_event("test_event", user_id=123, action="test")

        # Test event logging through shared logger
        shared_logger = get_logger("event_test")
        from shared.infrastructure.logging import log_event
        log_event(shared_logger, "shared_event", data="test_data")

        # Should not raise any exceptions
        self.assertTrue(True)

    def test_level_setting(self):
        """Test log level setting."""
        import logging

        # Test setting level on legacy logger
        logger.set_level(logging.DEBUG)
        logger.debug("Debug message after level set")

        # Test setting level on shared logger
        shared_logger = get_logger("level_test")
        shared_logger.setLevel(logging.WARNING)
        shared_logger.warning("Warning after level set")

        # Should not raise any exceptions
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
