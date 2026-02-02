"""Guardrails extension for rate limiting and budget controls."""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Any
from scrapy import signals
from scrapy.crawler import Crawler
from scrapy.exceptions import NotConfigured, CloseSpider

logger = logging.getLogger(__name__)


class GuardrailsExtension:
    """
    Extension for enforcing rate limits and budget controls.

    Features:
    - Rate limiting (max requests per hour/day)
    - Budget controls (max spend per spider/day)
    - Circuit breaker for repeated failures
    - Configurable thresholds
    """

    def __init__(self, crawler: Crawler) -> None:
        if not crawler.settings.getbool("SCRAPYX_GUARDRAILS_ENABLED", False):
            raise NotConfigured("Guardrails extension not enabled")

        self.settings = crawler.settings
        self.stats = crawler.stats

        # Rate limiting config
        self.max_per_hour = crawler.settings.getint("SCRAPYX_RATE_LIMIT_PER_HOUR", 0)
        self.max_per_day = crawler.settings.getint("SCRAPYX_RATE_LIMIT_PER_DAY", 0)

        # Budget config
        self.max_spend_per_day = crawler.settings.getfloat(
            "SCRAPYX_MAX_SPEND_PER_DAY", 0.0
        )
        self.captcha_cost_per_solve = crawler.settings.getfloat(
            "SCRAPYX_CAPTCHA_COST_PER_SOLVE", 0.002
        )

        # Circuit breaker config
        self.circuit_breaker_threshold = crawler.settings.getint(
            "SCRAPYX_CIRCUIT_BREAKER_THRESHOLD", 5
        )
        self.circuit_breaker_failures = 0

        # Tracking
        self.request_counts = defaultdict(lambda: {"hour": [], "day": []})
        self.total_spend = 0.0
        self.start_time = datetime.now()

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> "GuardrailsExtension":
        """Create extension instance from crawler."""
        ext = cls(crawler)
        crawler.signals.connect(ext.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(ext.engine_stopped, signal=signals.engine_stopped)
        return ext

    def spider_opened(self, spider: Any) -> None:
        """Initialize tracking on spider open."""
        if self.max_per_hour > 0 or self.max_per_day > 0:
            logger.info(
                f"Rate limiting enabled: {self.max_per_hour}/hour, {self.max_per_day}/day"
            )
        if self.max_spend_per_day > 0:
            logger.info(
                f"Budget control enabled: ${self.max_spend_per_day:.2f}/day (${self.captcha_cost_per_solve:.3f}/solve)"
            )

    def engine_stopped(self, reason: str) -> None:
        """Check guardrails on engine stop."""
        now = datetime.now()

        # Check rate limits
        if self.max_per_hour > 0:
            hour_requests = sum(
                len(times) for times in self.request_counts.values() if times["hour"]
            )
            if hour_requests >= self.max_per_hour:
                logger.warning(
                    f"Rate limit reached: {hour_requests} requests in last hour (limit: {self.max_per_hour})"
                )

        if self.max_per_day > 0:
            day_requests = sum(
                len(times) for times in self.request_counts.values() if times["day"]
            )
            if day_requests >= self.max_per_day:
                logger.warning(
                    f"Daily rate limit reached: {day_requests} requests (limit: {self.max_per_day})"
                )

        # Check budget
        if self.max_spend_per_day > 0 and self.total_spend >= self.max_spend_per_day:
            logger.warning(
                f"Budget limit reached: ${self.total_spend:.2f} (limit: ${self.max_spend_per_day:.2f})"
            )

    def check_rate_limit(self, spider_name: str) -> bool:
        """Check if rate limit is exceeded."""
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)

        # Clean old entries
        self.request_counts[spider_name]["hour"] = [
            t for t in self.request_counts[spider_name]["hour"] if t > hour_ago
        ]
        self.request_counts[spider_name]["day"] = [
            t for t in self.request_counts[spider_name]["day"] if t > day_ago
        ]

        # Check limits
        if (
            self.max_per_hour > 0
            and len(self.request_counts[spider_name]["hour"]) >= self.max_per_hour
        ):
            logger.error(
                f"Rate limit exceeded for {spider_name}: {len(self.request_counts[spider_name]['hour'])} requests in last hour"
            )
            return False

        if (
            self.max_per_day > 0
            and len(self.request_counts[spider_name]["day"]) >= self.max_per_day
        ):
            logger.error(
                f"Daily rate limit exceeded for {spider_name}: {len(self.request_counts[spider_name]['day'])} requests"
            )
            return False

        # Record request
        self.request_counts[spider_name]["hour"].append(now)
        self.request_counts[spider_name]["day"].append(now)

        return True

    def record_solve_cost(self) -> None:
        """Record captcha solve cost."""
        self.total_spend += self.captcha_cost_per_solve

        # Check budget
        if self.max_spend_per_day > 0 and self.total_spend >= self.max_spend_per_day:
            logger.error(
                f"Budget exceeded: ${self.total_spend:.2f} (limit: ${self.max_spend_per_day:.2f})"
            )
            raise CloseSpider("Budget limit exceeded")

        self.stats.set_value("captcha/total_spend", self.total_spend)
        self.stats.set_value(
            "captcha/remaining_budget",
            max(0, self.max_spend_per_day - self.total_spend),
        )

    def record_failure(self) -> None:
        """Record a failure for circuit breaker."""
        self.circuit_breaker_failures += 1

        if self.circuit_breaker_failures >= self.circuit_breaker_threshold:
            logger.error(
                f"Circuit breaker triggered: {self.circuit_breaker_failures} consecutive failures"
            )
            raise CloseSpider("Circuit breaker: too many consecutive failures")

    def reset_circuit_breaker(self) -> None:
        """Reset circuit breaker on success."""
        if self.circuit_breaker_failures > 0:
            logger.info(
                f"Circuit breaker reset after {self.circuit_breaker_failures} failures"
            )
            self.circuit_breaker_failures = 0
