"""
Scrapyx-MW middlewares package.

This package provides production-ready Scrapy middlewares for common use cases.
"""

from .api_request import ApiRequestMiddleware
from .captcha_polling import AsyncCaptchaMiddleware
from .captcha_webhook import WebhookCaptchaMiddleware
from .curl_cffi import CurlCffiMiddleware
from .debug import DebugRequestMiddleware
from .proxy_rotation import ProxyRotationMiddleware
from .session import SessionMiddleware
from .smart_retry import SmartRetryMiddleware

__all__ = [
    "ApiRequestMiddleware",
    "AsyncCaptchaMiddleware",
    "CurlCffiMiddleware",
    "WebhookCaptchaMiddleware",
    "DebugRequestMiddleware",
    "ProxyRotationMiddleware",
    "SessionMiddleware",
    "SmartRetryMiddleware",
]
