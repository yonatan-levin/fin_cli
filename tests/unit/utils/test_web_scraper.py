"""Unit tests for web scraping utilities."""

from __future__ import annotations

import pytest
from unittest.mock import Mock, patch

from finpack.utils.web_scraper import fetch_page_sync


def test_fetch_page_sync_success():
    """Verify fetch_page_sync returns content on success."""
    mock_response = Mock()
    mock_response.content = b"<html>Test content</html>"
    
    with patch("finpack.utils.web_scraper._session.get", return_value=mock_response):
        result = fetch_page_sync("https://example.com")
        assert result == b"<html>Test content</html>"


def test_fetch_page_sync_raises_on_http_error():
    """Verify fetch_page_sync raises HTTPError on bad status."""
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = Exception("HTTP 404")
    
    with patch("finpack.utils.web_scraper._session.get", return_value=mock_response):
        with pytest.raises(Exception, match="HTTP 404"):
            fetch_page_sync("https://example.com/404")


def test_fetch_page_sync_uses_random_user_agent():
    """Verify fetch_page_sync sends user-agent header."""
    mock_response = Mock()
    mock_response.content = b"content"
    
    with patch("finpack.utils.web_scraper._session.get", return_value=mock_response) as mock_get:
        fetch_page_sync("https://example.com")
        
        # Verify user-agent header was set
        call_kwargs = mock_get.call_args[1]
        assert "headers" in call_kwargs
        assert "user-agent" in call_kwargs["headers"]


def test_fetch_page_sync_timeout():
    """Verify fetch_page_sync uses timeout."""
    mock_response = Mock()
    mock_response.content = b"content"
    
    with patch("finpack.utils.web_scraper._session.get", return_value=mock_response) as mock_get:
        fetch_page_sync("https://example.com")
        
        # Verify timeout was set
        call_kwargs = mock_get.call_args[1]
        assert "timeout" in call_kwargs
        assert call_kwargs["timeout"] == 15

