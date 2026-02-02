"""
Webhook-based Captcha Middleware
- Submits to 2captcha or CapSolver with `callbackUrl`
- Waits for sidecar to store solution in SQLite
- Compatible with settings & flow from your compliance_scraper project
"""

import json
import sqlite3
import time
import logging
from typing import Any, Optional
from urllib.parse import urlencode
from twisted.internet import defer, reactor
from twisted.web.client import Agent, readBody
from scrapy import signals
from scrapy.exceptions import IgnoreRequest, NotConfigured

from ..providers import (
    create_provider,
    CaptchaError,
)

logger = logging.getLogger(__name__)
HTTP_OK = 200
DB_PATH = "/var/lib/scrapyd/webhook_solutions.db"  # same path for compatibility


class WebhookCaptchaMiddleware:
    def __init__(self, settings: Any) -> None:
        self.api_key: Optional[str] = settings.get("CAPTCHA_API_KEY")
        if not settings.getbool("CAPTCHA_ENABLED", False) or not self.api_key:
            raise NotConfigured("Captcha webhook not enabled or API key missing")

        self.webhook_url: str = settings.get(
            "CAPTCHA_WEBHOOK_URL", "http://127.0.0.1:6801/webhook"
        )
        self.agent = Agent(reactor)

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
            "CAPTCHA_HTTP_TIMEOUT_S": settings.getfloat("CAPTCHA_HTTP_TIMEOUT_S", 15.0),
            "CAPTCHA_HTTP_RETRIES": settings.getint("CAPTCHA_HTTP_RETRIES", 2),
        }
        self.provider = create_provider(
            provider_name, self.api_key, self.agent, provider_settings
        )

        self._init_database()

    @classmethod
    def from_crawler(cls, crawler: Any) -> "WebhookCaptchaMiddleware":
        m = cls(crawler.settings)
        crawler.signals.connect(m.spider_opened, signal=signals.spider_opened)
        return m

    def spider_opened(self, spider: Any) -> None:
        spider.logger.info(
            f"WebhookCaptchaMiddleware active with provider: {self.provider.__class__.__name__}"
        )

    def _init_database(self) -> None:
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("""
            CREATE TABLE IF NOT EXISTS captcha_solutions (
                captcha_id TEXT PRIMARY KEY,
                solution   TEXT NOT NULL,
                received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                used BOOLEAN DEFAULT FALSE
            )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to init DB: {e}")

    @defer.inlineCallbacks
    def process_request(self, request: Any, spider: Any) -> Optional[Any]:
        if not getattr(spider, "captcha_needed", False):
            return None
        if request.meta.get("recaptcha_solution"):
            return None

        site_key = getattr(spider, "site_key", None)
        if not site_key:
            spider.logger.error("Missing site_key on spider for captcha webhook.")
            raise IgnoreRequest("Missing site_key")

        try:
            captcha_id = yield self._submit(site_key, request.url, spider)
            solution = yield self._wait_solution(captcha_id, spider, timeout_s=300)
            if solution:
                request.meta["recaptcha_solution"] = solution
                if getattr(spider, "reset_captcha_flag", True):
                    spider.captcha_needed = False
                return None
            spider.logger.warning("Captcha webhook timeout.")
            raise IgnoreRequest("Captcha solution timeout.")
        except Exception as e:
            spider.logger.error(f"Webhook captcha error: {e}")
            raise IgnoreRequest(str(e)) from e

    @defer.inlineCallbacks
    def _submit(self, site_key: str, page_url: str, spider: Any) -> str:
        """Submit captcha with webhook callback."""
        # Check if this is invisible reCAPTCHA
        is_invisible = False
        service_config = getattr(spider, "service_config", {})
        if service_config and service_config.get("RECAPTCHA_INVISIBLE"):
            is_invisible = True

        # For 2captcha, add callbackUrl to the submission
        if hasattr(self.provider, "base_url") and "2captcha" in str(
            type(self.provider)
        ):
            params = {
                "key": self.api_key,
                "method": "userrecaptcha",
                "googlekey": site_key,
                "pageurl": page_url,
                "json": 1,
                "callbackUrl": self.webhook_url,
            }
            url = f"https://2captcha.com/in.php?{urlencode(params)}"
            resp = yield self.agent.request(b"GET", url.encode())
            if resp.code != HTTP_OK:
                raise Exception(f"Invalid status code: {resp.code}")
            data = json.loads((yield readBody(resp)).decode("utf-8"))
            if data.get("status") != 1:
                raise Exception(f"Submit error: {data.get('request')}")
            return data["request"]
        else:
            # For CapSolver, use the provider's submit method
            # Note: CapSolver doesn't support webhook callbacks in the same way
            # This will fall back to polling behavior
            try:
                captcha_id = yield self.provider.submit(
                    site_key, page_url, is_invisible=is_invisible
                )
                return captcha_id
            except CaptchaError as e:
                raise Exception(f"CapSolver submit error: {e}")

    @defer.inlineCallbacks
    def _wait_solution(
        self, captcha_id: str, spider: Any, timeout_s: int = 300
    ) -> Optional[str]:
        start = time.time()
        while time.time() - start < timeout_s:
            sol = self._get_solution(captcha_id)
            if sol:
                spider.logger.info("Captcha webhook solution received.")
                defer.returnValue(sol)
            yield self._sleep(1.0)
        defer.returnValue(None)

    def _get_solution(self, captcha_id: str) -> Optional[str]:
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute(
                "SELECT solution FROM captcha_solutions WHERE captcha_id=? AND used=FALSE",
                (captcha_id,),
            )
            row = c.fetchone()
            if row:
                c.execute(
                    "UPDATE captcha_solutions SET used=TRUE WHERE captcha_id=?",
                    (captcha_id,),
                )
                conn.commit()
                conn.close()
                return row[0]
            conn.close()
            return None
        except Exception as e:
            logger.error(f"DB read error: {e}")
            return None

    def _sleep(self, s: float) -> defer.Deferred:
        d = defer.Deferred()
        reactor.callLater(s, d.callback, None)
        return d
