from typing import Any
from scrapy import signals

class SessionMiddleware:
    """Applies default session headers from settings.SESSION_HEADERS or service_config['HEADERS']."""
    def __init__(self, settings: Any) -> None:
        self.session_headers = settings.get("SESSION_HEADERS", {})

    @classmethod
    def from_crawler(cls, crawler: Any) -> "SessionMiddleware":
        m = cls(crawler.settings)
        crawler.signals.connect(m.spider_opened, signal=signals.spider_opened)
        return m

    def process_request(self, request, spider):
        cfg = getattr(spider, "service_config", None) or {}
        headers = cfg.get("HEADERS") or self.session_headers
        if headers:
            request.headers.update(headers)

    def spider_opened(self, spider):
        spider.logger.info("SessionMiddleware active.")
