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

    def test_fetch_passes_http_version_and_curl_options_to_curl_cffi(self):
        """When meta contains curl_cffi_http_version and curl_cffi_curl_options, pass to curl_cffi."""
        from scrapy.core.downloader.handlers.http11 import HTTP11DownloadHandler
        from scrapyx_mw.downloadhandlers import curl_cffi as curl_cffi_mod

        if not curl_cffi_mod.CURL_CFFI_AVAILABLE:
            pytest.skip("curl_cffi is required for this test")

        mock_response = MagicMock()
        mock_response.url = "http://example.com"
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.content = b"<html></html>"
        mock_response.encoding = "utf-8"

        with patch.object(
            HTTP11DownloadHandler, "__init__", lambda self, s, c=None: None
        ), patch.object(
            curl_cffi_mod.curl_requests,
            "request",
            return_value=mock_response,
        ) as mock_request:
            settings = MagicMock()
            settings.getbool.return_value = True
            handler = CurlCffiDownloadHandler(settings)
            curl_options = {"some_option": 1}
            request = Request(
                "http://example.com",
                meta={
                    "use_curl_cffi": True,
                    "curl_cffi_http_version": "v1",
                    "curl_cffi_curl_options": curl_options,
                },
            )
            spider = MagicMock()
            response = handler._fetch_with_curl_cffi(request, spider)
            mock_request.assert_called_once()
            call_kwargs = mock_request.call_args[1]
            assert call_kwargs["http_version"] == "v1"
            assert call_kwargs["curl_options"] == curl_options
            assert response.status == 200


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

    def test_process_request_passes_http_version_and_curl_options_to_curl_cffi(self):
        """When meta contains curl_cffi_http_version and curl_cffi_curl_options, pass to curl_cffi."""
        from scrapyx_mw.middlewares import curl_cffi as curl_cffi_mod

        if not curl_cffi_mod.CURL_CFFI_AVAILABLE:
            pytest.skip("curl_cffi is required for this test")

        mock_response = MagicMock()
        mock_response.url = "http://example.com"
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.content = b"<html></html>"
        mock_response.encoding = "utf-8"

        with patch.object(
            curl_cffi_mod.curl_requests,
            "request",
            return_value=mock_response,
        ) as mock_request:
            settings = MagicMock()
            middleware = CurlCffiMiddleware(settings)
            curl_options = {"some_option": 1}
            request = Request(
                "http://example.com",
                meta={
                    "curl_cffi_http_version": "v1",
                    "curl_cffi_curl_options": curl_options,
                },
            )
            spider = MagicMock()
            middleware.process_request(request, spider)
            mock_request.assert_called_once()
            call_kwargs = mock_request.call_args[1]
            assert call_kwargs["http_version"] == "v1"
            assert call_kwargs["curl_options"] == curl_options
