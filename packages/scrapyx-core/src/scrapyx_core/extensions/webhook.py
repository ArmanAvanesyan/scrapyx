"""
Scrapy extension to send webhook callbacks alongside or instead of broker publishing.
Supports project-wide and per-spider configuration via settings only.
Does NOT interfere with callback_url from requests.
"""

import logging
import asyncio
import threading
from typing import Any, Optional
from scrapy import signals
from scrapy.crawler import Crawler
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

logger = logging.getLogger(__name__)


class WebhookExtension:
    """
    Sends webhook callbacks when spider completes.
    
    Configuration:
    - WEBHOOK_ENABLED: Enable/disable webhook extension (default: False)
    - GLOBAL_WEBHOOK_URL: URL to send all webhooks to (optional)
    - WEBHOOK_URLS: Dict of spider_name -> URL for per-spider overrides (optional)
    - WEBHOOK_TIMEOUT: Timeout in seconds (default: 30)
    - WEBHOOK_RETRIES: Number of retry attempts (default: 3)
    
    Note: This extension is separate from the callback_url in requests.
    It uses only configuration from Scrapy settings.
    """

    def __init__(self, crawler: Crawler) -> None:
        self.crawler = crawler
        
        # Global configuration from settings
        self.enabled = crawler.settings.getbool("WEBHOOK_ENABLED", False)
        self.global_webhook_url = crawler.settings.get("GLOBAL_WEBHOOK_URL", None)
        self.webhook_timeout = crawler.settings.getint("WEBHOOK_TIMEOUT", 30)
        self.webhook_retries = crawler.settings.getint("WEBHOOK_RETRIES", 3)
        self.webhook_urls = crawler.settings.getdict("WEBHOOK_URLS", default={})
        
        logger.info(
            f"WebhookExtension initialized: enabled={self.enabled}, "
            f"global_webhook={bool(self.global_webhook_url)}, "
            f"spider_urls={len(self.webhook_urls)}"
        )

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> "WebhookExtension":
        ext = cls(crawler)
        if ext.enabled:
            crawler.signals.connect(ext.spider_closed, signal=signals.spider_closed)
            logger.info("WebhookExtension enabled")
        return ext

    def spider_closed(self, spider: Any, reason: str) -> None:
        """Handle spider_closed signal and send webhook."""
        if not self.enabled:
            return
            
        try:
            # Determine webhook URL (per-spider or global)
            webhook_url = self._get_webhook_url(spider)
            
            if not webhook_url:
                logger.debug(f"No webhook URL configured for spider {spider.name}")
                return
            
            # Build event data with full results
            event_data = self._build_event_data(spider, reason)
            
            # Send webhook synchronously within Scrapy context
            self._send_webhook(webhook_url, event_data)
            
            logger.info(f"Sent webhook for job {event_data.get('job_id')}")
                
        except Exception as e:
            logger.error(f"Error sending webhook: {e}", exc_info=True)

    def _get_webhook_url(self, spider: Any) -> Optional[str]:
        """
        Get webhook URL from settings only.
        
        Priority:
        1. Per-spider URL from WEBHOOK_URLS dict
        2. Global webhook URL from settings
        """
        # Check for per-spider webhook URL
        spider_url = self.webhook_urls.get(spider.name, None)
        if spider_url:
            logger.debug(f"Using per-spider webhook URL for spider {spider.name}")
            return spider_url
        
        # Fall back to global webhook
        if self.global_webhook_url:
            logger.debug(f"Using global webhook URL for spider {spider.name}")
        
        return self.global_webhook_url

    def _build_event_data(self, spider: Any, reason: str) -> dict:
        """Build event data dictionary with full results."""
        from datetime import datetime
        
        return {
            "job_id": getattr(spider, 'job_id', 'unknown'),
            "spider_name": spider.name,
            "status": 'success' if reason == 'finished' else 'failed',
            "reason": reason,
            "items_count": len(getattr(spider, 'items', [])),
            "errors_count": len(getattr(spider, 'errors', [])),
            "project": self.crawler.settings.get("BOT_NAME", "unknown"),
            "items": getattr(spider, 'items', []),
            "errors": getattr(spider, 'errors', []),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError)),
    )
    def _send_webhook(self, webhook_url: str, event_data: dict) -> None:
        """Send webhook with retry logic."""
        async def _async_send():
            async with httpx.AsyncClient(timeout=self.webhook_timeout) as client:
                response = await client.post(webhook_url, json=event_data)
                response.raise_for_status()
                logger.debug(f"Webhook sent successfully: {response.status_code}")
        
        def run_in_thread():
            """Run async code in a new thread with its own event loop."""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(_async_send())
            finally:
                loop.close()
        
        # Always run in a thread to avoid event loop conflicts
        thread = threading.Thread(target=run_in_thread, daemon=True)
        thread.start()
        thread.join(timeout=10)

