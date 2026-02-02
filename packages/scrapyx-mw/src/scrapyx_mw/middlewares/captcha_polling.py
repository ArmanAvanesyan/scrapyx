from __future__ import annotations
import random
import time
from typing import Any, Optional
from twisted.internet import defer, reactor
from twisted.web.client import Agent, HTTPConnectionPool
from scrapy import signals
from scrapy.exceptions import NotConfigured

from ..providers import (
    create_provider,
    CaptchaError,
    PermanentCaptchaError,
    TransientCaptchaError,
)

HTTP_OK = 200


class AsyncCaptchaMiddleware:
    """
    Multi-provider captcha polling with:
    - Request timeouts
    - De-duplication per (spider, site_key, origin)
    - TTL cache of tokens
    - Exponential backoff with jitter
    - Support for 2captcha and CapSolver providers
    Compatible with your compliance_scraper settings & spider flags.
    """

    def __init__(self, settings: Any) -> None:
        if not settings.getbool("CAPTCHA_ENABLED", False):
            raise NotConfigured("CAPTCHA not enabled")

        self.api_key = settings.get("CAPTCHA_API_KEY")
        if not self.api_key:
            raise NotConfigured("CAPTCHA_API_KEY missing")

        self.token_ttl_s = int(settings.getint("CAPTCHA_TOKEN_TTL_SECONDS", 110))
        self.poll_initial = float(settings.getfloat("CAPTCHA_POLL_INITIAL_S", 4.0))
        self.poll_max = float(settings.getfloat("CAPTCHA_POLL_MAX_S", 45.0))
        self.poll_total = float(settings.getfloat("CAPTCHA_POLL_MAX_TIME_S", 180.0))
        self.http_timeout = float(settings.getfloat("CAPTCHA_HTTP_TIMEOUT_S", 15.0))
        self.http_retries = int(settings.getint("CAPTCHA_HTTP_RETRIES", 2))

        self.cache = {}  # key -> (token, expires)
        self.inflight = {}
        pool = HTTPConnectionPool(reactor, persistent=True)
        self.agent = Agent(reactor, pool=pool)

        # Create provider based on settings
        provider_name = settings.get("CAPTCHA_PROVIDER", "2captcha")
        provider_settings = {
            "CAPTCHA_2CAPTCHA_BASE": settings.get(
                "CAPTCHA_2CAPTCHA_BASE", "https://2captcha.com"
            ),
            "CAPTCHA_2CAPTCHA_METHOD": settings.get(
                "CAPTCHA_2CAPTCHA_METHOD", "userrecaptcha"
            ),
            "CAPTCHA_CAPSOLVER_BASE": settings.get(
                "CAPTCHA_CAPSOLVER_BASE", "https://api.capsolver.com"
            ),
            "CAPTCHA_CAPSOLVER_TASK_TYPE": settings.get(
                "CAPTCHA_CAPSOLVER_TASK_TYPE", "ReCaptchaV2TaskProxyLess"
            ),
            "CAPTCHA_HTTP_TIMEOUT_S": self.http_timeout,
            "CAPTCHA_HTTP_RETRIES": self.http_retries,
        }
        self.provider = create_provider(
            provider_name, self.api_key, self.agent, provider_settings
        )

    @classmethod
    def from_crawler(cls, crawler: Any):
        m = cls(crawler.settings)
        crawler.signals.connect(m.spider_opened, signal=signals.spider_opened)
        return m

    def spider_opened(self, spider):
        spider.logger.info(
            f"AsyncCaptchaMiddleware (polling) active with provider: {self.provider.__class__.__name__}"
        )

    def _sleep(self, s: float):
        d = defer.Deferred()
        reactor.callLater(s, d.callback, None)
        return d

    def _origin(self, url: str):
        from urllib.parse import urlparse

        p = urlparse(url)
        return f"{p.scheme}://{p.netloc}"

    def _key(self, spider, site_key, url):
        return f"{spider.name}:{site_key}:{self._origin(url)}"

    @defer.inlineCallbacks
    def process_request(self, request, spider):
        if not getattr(spider, "captcha_needed", False):
            return None
        site_key = getattr(spider, "site_key", None)
        if not site_key:
            return None

        k = self._key(spider, site_key, request.url)
        now = time.time()
        hit = self.cache.get(k)
        if hit and hit[1] > now:
            request.meta["recaptcha_solution"] = hit[0]
            return None
        elif hit:
            self.cache.pop(k, None)

        if k in self.inflight:
            try:
                sol = yield self.inflight[k]
            except Exception:
                yield self._sleep(1.0)
                defer.returnValue(request.replace(dont_filter=True))
            else:
                request.meta["recaptcha_solution"] = sol
                defer.returnValue(None)

        d = self._solve(site_key, request.url, spider)
        self.inflight[k] = d
        try:
            sol = yield d
        finally:
            self.inflight.pop(k, None)
        self.cache[k] = (sol, time.time() + self.token_ttl_s)
        request.meta["recaptcha_solution"] = sol
        if getattr(spider, "reset_captcha_flag", True):
            spider.captcha_needed = False
        defer.returnValue(None)

    @defer.inlineCallbacks
    def _solve(self, site_key, url, spider):
        try:
            # Check if this is invisible reCAPTCHA from service config
            is_invisible = False
            service_config = getattr(spider, "service_config", {})
            if service_config and service_config.get("RECAPTCHA_INVISIBLE"):
                is_invisible = True
                spider.logger.debug(f"Using invisible reCAPTCHA mode for {spider.name}")

            cid = yield self.provider.submit(site_key, url, is_invisible=is_invisible)
            start = time.time()
            delay = self.poll_initial
            sol: Optional[str] = None
            while True:
                if time.time() - start > self.poll_total:
                    raise TransientCaptchaError("Captcha polling timeout")
                try:
                    sol = yield self.provider.poll(cid)
                except PermanentCaptchaError:
                    raise
                except TransientCaptchaError:
                    pass
                if sol:
                    defer.returnValue(sol)
                jitter = random.uniform(-0.5, 0.5)
                delay = min(self.poll_max, max(1.0, delay * 1.6 + jitter))
                yield self._sleep(delay)
        except CaptchaError as e:
            spider.logger.error(f"Captcha solving failed: {e}")
            raise
