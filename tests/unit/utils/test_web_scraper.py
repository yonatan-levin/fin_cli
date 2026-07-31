from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests

from fincli.utils import web_scraper


def test_scrape_returns_response_bytes_with_timeout_and_user_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get = Mock(return_value=SimpleNamespace(content=b"page"))
    monkeypatch.setattr(web_scraper.session, "get", get)
    monkeypatch.setattr(web_scraper, "choice", lambda values: values[0])

    result = web_scraper.scrape("https://example.test/screen")

    assert result == b"page"
    get.assert_called_once_with(
        "https://example.test/screen",
        headers={"user-agent": web_scraper.user_agents[0]},
        timeout=10,
    )


def test_scrape_preserves_http_error_failure_family(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        web_scraper.session,
        "get",
        Mock(side_effect=requests.exceptions.HTTPError("upstream failed")),
    )

    with pytest.raises(Exception, match="Http Error"):
        web_scraper.scrape("https://example.test/screen")


def test_fetch_page_sync_returns_bytes_and_records_elapsed_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get = Mock(return_value=SimpleNamespace(content=b"screen"))
    monkeypatch.setattr(
        web_scraper.cfscrape,
        "create_scraper",
        Mock(return_value=SimpleNamespace(get=get)),
    )
    times = iter((10.0, 10.25))
    monkeypatch.setattr(web_scraper.time, "time", lambda: next(times))
    info = Mock()
    monkeypatch.setattr(web_scraper.logger, "info", info)

    result = web_scraper.fetch_page_sync("https://example.test/screen")

    assert result == b"screen"
    get.assert_called_once_with("https://example.test/screen")
    info.assert_called_once_with(
        "https://example.test/screen took 0.25",
        "Page fetched successfully",
    )
