"""
CurlCffi download handler for Scrapy.

Provides browser impersonation capabilities using curl_cffi for sites
with anti-bot protection (e.g., jobs.am).

Usage:
    Enable globally in settings:
    DOWNLOAD_HANDLERS = {
        'https': 'scrapyx_mw.downloadhandlers.curl_cffi.CurlCffiDownloadHandler',
        'http': 'scrapyx_mw.downloadhandlers.curl_cffi.CurlCffiDownloadHandler',
    }

    Or enable per-request via meta:
    request.meta['use_curl_cffi'] = True
    request.meta['curl_cffi_impersonate'] = 'chrome110'  # Optional
"""

import logging

from scrapy import Request
from scrapy.core.downloader.handlers.http11 import HTTP11DownloadHandler
from scrapy.http import Response
from twisted.internet.defer import Deferred
from twisted.internet.threads import deferToThread

try:
    from curl_cffi import requests as curl_requests

    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False
    curl_requests = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class CurlCffiDownloadHandler(HTTP11DownloadHandler):
    """
    Download handler that uses curl_cffi for browser impersonation.

    Falls back to standard HTTP11DownloadHandler if curl_cffi is not available
    or if request doesn't specify use_curl_cffi in meta.
    """

    def __init__(self, settings, crawler=None):
        """Initialize handler."""
        super().__init__(settings, crawler)
        self.curl_cffi_enabled = settings.getbool("CURL_CFFI_ENABLED", False)

        if not CURL_CFFI_AVAILABLE:
            logger.warning(
                "curl_cffi not available. Install with: uv pip install curl-cffi. "
                "Falling back to standard HTTP handler."
            )

    def download_request(self, request: Request, spider) -> Deferred:
        """
        Download a request using curl_cffi if enabled, otherwise use standard handler.

        Args:
            request: Scrapy request
            spider: Spider instance

        Returns:
            Deferred that fires with Response
        """
        # Check if curl_cffi should be used for this request
        use_curl_cffi = self.curl_cffi_enabled or request.meta.get(
            "use_curl_cffi", False
        )

        if use_curl_cffi and CURL_CFFI_AVAILABLE:
            return self._download_with_curl_cffi(request, spider)
        else:
            # Use standard handler
            return super().download_request(request, spider)

    def _download_with_curl_cffi(self, request: Request, spider) -> Deferred:
        """
        Download request using curl_cffi.

        Args:
            request: Scrapy request
            spider: Spider instance

        Returns:
            Deferred that fires with Response
        """
        # Run curl_cffi request in thread pool (it's synchronous)
        return deferToThread(self._fetch_with_curl_cffi, request, spider)

    def _fetch_with_curl_cffi(self, request: Request, spider) -> Response:
        """
        Fetch request using curl_cffi (runs in thread).

        Args:
            request: Scrapy request
            spider: Spider instance

        Returns:
            Scrapy Response object
        """
        # Get impersonation target from meta or default
        impersonate = request.meta.get("curl_cffi_impersonate", "chrome110")

        # Prepare request kwargs
        kwargs = {
            "timeout": request.meta.get("download_timeout", 180),
            "allow_redirects": True,
        }

        # Set headers
        headers = {}
        if request.headers:
            # Convert Scrapy headers to dict
            if hasattr(request.headers, "to_unicode_dict"):
                headers = request.headers.to_unicode_dict()
            else:
                headers = dict(request.headers)
        kwargs["headers"] = headers

        # Set cookies
        if request.cookies:
            kwargs["cookies"] = dict(request.cookies)

        # Set method and data
        method = request.method.upper()
        if method == "GET":
            # GET requests - params are in URL already
            pass
        elif method == "POST":
            from scrapy import FormRequest

            if isinstance(request, FormRequest):
                kwargs["data"] = request.formdata
            else:
                kwargs["data"] = request.body

        try:
            # Make request with curl_cffi
            curl_response = curl_requests.request(
                method, request.url, impersonate=impersonate, **kwargs
            )

            # Convert curl_cffi response to Scrapy Response
            return self._curl_response_to_scrapy_response(
                curl_response,
                request,
            )
        except Exception as e:
            logger.error(f"curl_cffi request failed for {request.url}: {e}")
            # Return error response
            from scrapy.http import TextResponse

            return TextResponse(
                url=request.url,
                status=500,
                body=str(e).encode("utf-8"),
                request=request,
            )

    def _curl_response_to_scrapy_response(
        self,
        curl_response,
        request: Request,
    ) -> Response:
        """
        Convert curl_cffi response to Scrapy Response.

        Args:
            curl_response: curl_cffi Response object
            request: Original Scrapy request

        Returns:
            Scrapy Response object
        """
        from scrapy.http import TextResponse, HtmlResponse

        # Determine response class based on content type
        content_type = curl_response.headers.get("content-type", "").lower()

        if "text/html" in content_type:
            response_class = HtmlResponse
        else:
            response_class = TextResponse

        # Convert headers
        headers = {}
        for key, value in curl_response.headers.items():
            headers[key.encode("utf-8")] = value.encode("utf-8")

        return response_class(
            url=str(curl_response.url),
            status=curl_response.status_code,
            headers=headers,
            body=curl_response.content,
            encoding=curl_response.encoding or "utf-8",
            request=request,
        )
