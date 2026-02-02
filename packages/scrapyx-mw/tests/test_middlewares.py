"""Unit tests for scrapyx-mw middlewares."""

import pytest
from unittest.mock import MagicMock, Mock, patch
from scrapy import Request
from scrapy.http import HtmlResponse

from scrapyx_mw.middlewares.session import SessionMiddleware
from scrapyx_mw.middlewares.api_request import ApiRequestMiddleware
from scrapyx_mw.middlewares.debug import DebugRequestMiddleware


class TestSessionMiddleware:
    """Test session middleware."""

    @pytest.fixture
    def middleware(self):
        """Create a session middleware instance."""
        settings = MagicMock()
        settings.getdict.return_value = {"Accept": "application/json"}
        settings.get.return_value = {}

        middleware = SessionMiddleware(settings)
        return middleware

    def test_process_request_with_headers(self, middleware):
        """Test request processing with session headers."""
        request = Request("http://example.com")
        spider = MagicMock()
        spider.service_config = {"HEADERS": {"User-Agent": "Custom Agent"}}

        result = middleware.process_request(request, spider)
        assert result is None
        assert "User-Agent" in request.headers
        assert request.headers["User-Agent"] == b"Custom Agent"

    def test_process_request_without_headers(self, middleware):
        """Test request processing without custom headers."""
        request = Request("http://example.com")
        spider = MagicMock()
        spider.service_config = {}

        result = middleware.process_request(request, spider)
        assert result is None


class TestApiRequestMiddleware:
    """Test API request middleware."""

    @pytest.fixture
    def middleware(self):
        """Create an API request middleware instance."""
        settings = MagicMock()
        settings.get.return_value = {}

        middleware = ApiRequestMiddleware(settings)
        return middleware

    def test_process_request_with_api_headers(self, middleware):
        """Test request processing with API headers."""
        request = Request("http://example.com")
        spider = MagicMock()
        spider.service_config = {"API_HEADERS": {"X-API-Key": "secret"}}

        result = middleware.process_request(request, spider)
        assert result is None
        assert "X-Api-Key" in request.headers
        assert request.headers["X-Api-Key"] == b"secret"

    def test_process_request_without_api_headers(self, middleware):
        """Test request processing without API headers."""
        request = Request("http://example.com")
        spider = MagicMock()
        spider.service_config = {}

        result = middleware.process_request(request, spider)
        assert result is None


class TestDebugRequestMiddleware:
    """Test debug request middleware."""

    @pytest.fixture
    def middleware(self):
        """Create a debug middleware instance."""
        settings = MagicMock()

        middleware = DebugRequestMiddleware(settings)
        return middleware

    def test_process_request_logging(self, middleware):
        """Test request processing with debug logging."""
        request = Request("http://example.com")
        spider = MagicMock()
        spider.logger = MagicMock()

        result = middleware.process_request(request, spider)
        assert result is None
        spider.logger.debug.assert_called_once()
