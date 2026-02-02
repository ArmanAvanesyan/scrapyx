"""
CurlCffi middleware for Scrapy.

Provides browser impersonation capabilities using curl_cffi for all requests.
Uses curl_cffi by default for all requests, but can be disabled per-request via meta.

Usage:
    Enable in settings:
    DOWNLOADER_MIDDLEWARES = {
        'scrapyx_mw.middlewares.curl_cffi.CurlCffiMiddleware': 706,
    }

    To disable for a specific request:
    request.meta['use_curl_cffi'] = False

    To customize impersonation target:
    request.meta['curl_cffi_impersonate'] = 'chrome110'  # Optional, default is chrome110
"""

import logging
from typing import Any

from scrapy import Request
from scrapy.http import HtmlResponse, Response, TextResponse

try:
    from curl_cffi import requests as curl_requests

    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False

logger = logging.getLogger(__name__)


class CurlCffiMiddleware:
    """
    Middleware that uses curl_cffi for browser impersonation on all requests.

    By default, all requests use curl_cffi. To disable for a specific request,
    set request.meta['use_curl_cffi'] = False.
    """

    def __init__(self, settings: Any) -> None:
        """Initialize middleware."""
        self.settings = settings
        if not CURL_CFFI_AVAILABLE:
            logger.warning(
                "curl_cffi not available. Install with: uv pip install curl-cffi. "
                "Middleware will be disabled."
            )

    @classmethod
    def from_crawler(cls, crawler: Any) -> "CurlCffiMiddleware":
        """Create middleware instance from crawler."""
        return cls(crawler.settings)

    def process_request(self, request: Request, spider) -> Response | None:
        """
        Process request using curl_cffi (enabled by default).

        Args:
            request: Scrapy request
            spider: Spider instance

        Returns:
            Response if curl_cffi was used, None to continue with default handler
        """
        # Check if curl_cffi should be disabled for this request
        # Default is True (use curl_cffi), unless explicitly disabled
        use_curl_cffi = request.meta.get("use_curl_cffi", True)

        if not use_curl_cffi or not CURL_CFFI_AVAILABLE:
            return None  # Continue with default handler

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
        if method == "POST":
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
