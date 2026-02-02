from typing import Any
from scrapy import signals


class ApiRequestMiddleware:
    """Injects API-specific headers from spider.service_config['HEADERS']."""

    @classmethod
    def from_crawler(cls, crawler: Any) -> "ApiRequestMiddleware":
        m = cls()
        crawler.signals.connect(m.spider_opened, signal=signals.spider_opened)
        return m

    def process_request(self, request, spider):
        cfg = getattr(spider, "service_config", None) or {}
        headers = cfg.get("HEADERS", {})
        if headers:
            request.headers.update(headers)

    def spider_opened(self, spider):
        spider.logger.info("ApiRequestMiddleware active.")
