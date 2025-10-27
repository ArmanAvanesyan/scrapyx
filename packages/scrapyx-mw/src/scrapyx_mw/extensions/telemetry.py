"""Telemetry extension for tracking captcha solving metrics."""

import logging
import time
from typing import Dict, Any
from scrapy import signals
from scrapy.crawler import Crawler
from scrapy.exceptions import NotConfigured

logger = logging.getLogger(__name__)


class TelemetryExtension:
    """
    Extension for tracking captcha solving metrics.
    
    Tracks:
    - Solve attempts, successes, failures
    - Solve times
    - Estimated costs
    - Success rates
    """

    def __init__(self, crawler: Crawler) -> None:
        if not crawler.settings.getbool("SCRAPYX_TELEMETRY_ENABLED", False):
            raise NotConfigured("Telemetry extension not enabled")
        
        self.stats = crawler.stats
        self.solve_attempts = 0
        self.solve_successes = 0
        self.solve_failures = 0
        self.total_solve_time = 0.0
        self.solve_start_times: Dict[str, float] = {}

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> "TelemetryExtension":
        """Create extension instance from crawler."""
        ext = cls(crawler)
        crawler.signals.connect(ext.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(ext.spider_closed, signal=signals.spider_closed)
        return ext

    def spider_opened(self, spider: Any) -> None:
        """Initialize tracking on spider open."""
        logger.info("Telemetry extension enabled - tracking captcha metrics")

    def spider_closed(self, spider: Any, reason: str) -> None:
        """Log summary on spider close."""
        total = self.solve_attempts
        if total > 0:
            success_rate = (self.solve_successes / total) * 100
            avg_time = self.total_solve_time / total if total > 0 else 0
            
            logger.info(
                f"Captcha Telemetry Summary:\n"
                f"  Attempts: {total}\n"
                f"  Successes: {self.solve_successes} ({success_rate:.1f}%)\n"
                f"  Failures: {self.solve_failures}\n"
                f"  Avg Solve Time: {avg_time:.2f}s\n"
                f"  Total Time: {self.total_solve_time:.2f}s"
            )
            
            # Emit to stats
            self.stats.set_value("captcha/attempts", total)
            self.stats.set_value("captcha/successes", self.solve_successes)
            self.stats.set_value("captcha/failures", self.solve_failures)
            self.stats.set_value("captcha/success_rate_pct", success_rate)
            self.stats.set_value("captcha/avg_solve_time_sec", avg_time)
            self.stats.set_value("captcha/total_time_sec", self.total_solve_time)

    def record_solve_start(self, captcha_id: str) -> None:
        """Record the start of a captcha solve attempt."""
        self.solve_attempts += 1
        self.solve_start_times[captcha_id] = time.time()
        self.stats.inc_value("captcha/attempts")

    def record_solve_success(self, captcha_id: str) -> None:
        """Record a successful captcha solve."""
        self.solve_successes += 1
        if captcha_id in self.solve_start_times:
            solve_time = time.time() - self.solve_start_times.pop(captcha_id)
            self.total_solve_time += solve_time
            self.stats.inc_value("captcha/successes")
            self.stats.set_value("captcha/last_solve_time_sec", solve_time)

    def record_solve_failure(self, captcha_id: str, error: str) -> None:
        """Record a failed captcha solve attempt."""
        self.solve_failures += 1
        if captcha_id in self.solve_start_times:
            self.solve_start_times.pop(captcha_id)
        self.stats.inc_value("captcha/failures")
        self.stats.inc_value(f"captcha/failures/{error}", 1)

