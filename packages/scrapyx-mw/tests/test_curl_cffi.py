"""Tests for CurlCffi download handler and middleware."""

import pytest
from unittest.mock import MagicMock, patch

from scrapy import Request

from scrapyx_mw.downloadhandlers.curl_cffi import CurlCffiDownloadHandler
from scrapyx_mw.middlewares.curl_cffi import CurlCffiMiddleware


class TestCurlCffiDownloadHandler:
    """Test CurlCffiDownloadHandler."""

    def test_import(self):
        """Handler is importable."""
        assert CurlCffiDownloadHandler is not None

    def test_init_reads_settings(self):
        """Handler reads CURL_CFFI_ENABLED from settings."""
        from scrapy.core.downloader.handlers.http11 import HTTP11DownloadHandler

        settings = MagicMock()
        settings.getbool.return_value = True
        with patch.object(
            HTTP11DownloadHandler, "__init__", lambda self, s, c=None: None
        ):
            handler = CurlCffiDownloadHandler(settings)
        assert handler.curl_cffi_enabled is True
        settings.getbool.assert_called_with("CURL_CFFI_ENABLED", False)

    def test_init_default_disabled(self):
        """Handler defaults to curl_cffi disabled."""
        from scrapy.core.downloader.handlers.http11 import HTTP11DownloadHandler

        settings = MagicMock()
        settings.getbool.return_value = False
        with patch.object(
            HTTP11DownloadHandler, "__init__", lambda self, s, c=None: None
        ):
            handler = CurlCffiDownloadHandler(settings)
        assert handler.curl_cffi_enabled is False


class TestCurlCffiMiddleware:
    """Test CurlCffiMiddleware."""

    def test_import(self):
        """Middleware is importable."""
        assert CurlCffiMiddleware is not None

    def test_from_crawler(self):
        """from_crawler returns middleware instance with settings."""
        crawler = MagicMock()
        crawler.settings = MagicMock()
        mw = CurlCffiMiddleware.from_crawler(crawler)
        assert mw is not None
        assert mw.settings is crawler.settings

    def test_process_request_returns_none_when_disabled_in_meta(self):
        """When request.meta['use_curl_cffi'] is False, middleware returns None."""
        settings = MagicMock()
        middleware = CurlCffiMiddleware(settings)
        request = Request("http://example.com", meta={"use_curl_cffi": False})
        spider = MagicMock()
        result = middleware.process_request(request, spider)
        assert result is None

    def test_process_request_returns_none_when_curl_cffi_unavailable(self):
        """When curl_cffi is not installed, process_request returns None for use_curl_cffi=True."""
        from scrapyx_mw.middlewares import curl_cffi as curl_cffi_mod

        if curl_cffi_mod.CURL_CFFI_AVAILABLE:
            pytest.skip("curl_cffi is installed; cannot test fallback")

        settings = MagicMock()
        middleware = CurlCffiMiddleware(settings)
        request = Request("http://example.com")  # default use_curl_cffi=True
        spider = MagicMock()
        result = middleware.process_request(request, spider)
        assert result is None
