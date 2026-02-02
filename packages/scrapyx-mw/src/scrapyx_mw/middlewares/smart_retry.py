"""
Smart retry middleware with exponential backoff for scrapyx-mw.

This middleware provides intelligent retry logic with:
- Exponential backoff with jitter
- Configurable retry conditions
- Request-specific retry policies
- Circuit breaker pattern
- Retry statistics and monitoring
"""

import random
import time
from typing import Optional
from urllib.parse import urlparse

from scrapy import Request, Spider
from scrapy.exceptions import NotConfigured
from scrapy.http import Response


class SmartRetryMiddleware:
    """Smart retry middleware with exponential backoff and circuit breaker."""

    def __init__(self, settings):
        self.settings = settings

        # Retry configuration
        self.max_retry_times = settings.getint("SCRAPYX_RETRY_MAX_TIMES", 3)
        self.retry_http_codes = settings.getlist(
            "SCRAPYX_RETRY_HTTP_CODES", [500, 502, 503, 504, 408, 429]
        )
        self.retry_exceptions = settings.getlist(
            "SCRAPYX_RETRY_EXCEPTIONS",
            [
                "twisted.internet.defer.TimeoutError",
                "twisted.internet.error.TimeoutError",
                "twisted.internet.error.ConnectionRefusedError",
                "twisted.internet.error.ConnectionDone",
                "twisted.internet.error.ConnectionLost",
                "twisted.internet.error.DNSLookupError",
                "twisted.internet.error.ConnectionError",
                "scrapy.exceptions.TimeoutError",
            ],
        )

        # Backoff configuration
        self.base_backoff = settings.getfloat("SCRAPYX_RETRY_BASE_BACKOFF", 1.0)
        self.max_backoff = settings.getfloat("SCRAPYX_RETRY_MAX_BACKOFF", 60.0)
        self.backoff_multiplier = settings.getfloat(
            "SCRAPYX_RETRY_BACKOFF_MULTIPLIER", 2.0
        )
        self.jitter_enabled = settings.getbool("SCRAPYX_RETRY_JITTER_ENABLED", True)
        self.jitter_range = settings.getfloat("SCRAPYX_RETRY_JITTER_RANGE", 0.1)

        # Circuit breaker configuration
        self.circuit_breaker_enabled = settings.getbool(
            "SCRAPYX_RETRY_CIRCUIT_BREAKER_ENABLED", True
        )
        self.circuit_breaker_threshold = settings.getint(
            "SCRAPYX_RETRY_CIRCUIT_BREAKER_THRESHOLD", 5
        )
        self.circuit_breaker_timeout = settings.getint(
            "SCRAPYX_RETRY_CIRCUIT_BREAKER_TIMEOUT", 60
        )

        # Statistics and monitoring
        self.retry_stats = {}
        self.circuit_breakers = {}  # Track circuit breaker state per domain
        self.request_retry_count = {}  # Track retry count per request

        # Priority configuration
        self.priority_retry_enabled = settings.getbool(
            "SCRAPYX_RETRY_PRIORITY_ENABLED", True
        )
        self.priority_multiplier = settings.getfloat(
            "SCRAPYX_RETRY_PRIORITY_MULTIPLIER", 1.5
        )

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except Exception:
            return "unknown"

    def _should_retry(
        self,
        request: Request,
        response: Optional[Response],
        exception: Optional[Exception],
    ) -> bool:
        """Determine if request should be retried."""
        # Check if retry is disabled for this request
        if request.meta.get("dont_retry", False):
            return False

        # Check circuit breaker
        if self.circuit_breaker_enabled:
            domain = self._get_domain(request.url)
            if self._is_circuit_open(domain):
                return False

        # Check retry count
        retry_count = self._get_retry_count(request)
        if retry_count >= self.max_retry_times:
            return False

        # Check response status
        if response:
            if response.status in self.retry_http_codes:
                return True

        # Check exceptions
        if exception:
            exception_name = (
                f"{exception.__class__.__module__}.{exception.__class__.__name__}"
            )
            if exception_name in self.retry_exceptions:
                return True

        return False

    def _get_retry_count(self, request: Request) -> int:
        """Get current retry count for request."""
        request_id = id(request)
        return self.request_retry_count.get(request_id, 0)

    def _increment_retry_count(self, request: Request):
        """Increment retry count for request."""
        request_id = id(request)
        self.request_retry_count[request_id] = self._get_retry_count(request) + 1

    def _calculate_backoff_delay(self, request: Request) -> float:
        """Calculate backoff delay with exponential backoff and jitter."""
        retry_count = self._get_retry_count(request)

        # Base exponential backoff
        delay = self.base_backoff * (self.backoff_multiplier**retry_count)

        # Apply maximum backoff limit
        delay = min(delay, self.max_backoff)

        # Apply jitter to prevent thundering herd
        if self.jitter_enabled:
            jitter = random.uniform(-self.jitter_range, self.jitter_range)
            delay = delay * (1 + jitter)

        # Apply priority multiplier for high-priority requests
        if self.priority_retry_enabled and request.meta.get("priority", 0) > 0:
            delay = delay / self.priority_multiplier

        return max(0, delay)

    def _is_circuit_open(self, domain: str) -> bool:
        """Check if circuit breaker is open for domain."""
        if domain not in self.circuit_breakers:
            return False

        circuit = self.circuit_breakers[domain]
        current_time = time.time()

        # Check if circuit should be reset
        if current_time - circuit["last_failure"] > self.circuit_breaker_timeout:
            circuit["state"] = "closed"
            circuit["failure_count"] = 0

        return circuit["state"] == "open"

    def _update_circuit_breaker(self, domain: str, success: bool):
        """Update circuit breaker state for domain."""
        if not self.circuit_breaker_enabled:
            return

        if domain not in self.circuit_breakers:
            self.circuit_breakers[domain] = {
                "state": "closed",
                "failure_count": 0,
                "last_failure": 0,
            }

        circuit = self.circuit_breakers[domain]
        current_time = time.time()

        if success:
            # Reset circuit breaker on success
            circuit["state"] = "closed"
            circuit["failure_count"] = 0
        else:
            # Increment failure count
            circuit["failure_count"] += 1
            circuit["last_failure"] = current_time

            # Open circuit if threshold exceeded
            if circuit["failure_count"] >= self.circuit_breaker_threshold:
                circuit["state"] = "open"

    def _update_retry_stats(self, request: Request, success: bool, delay: float):
        """Update retry statistics."""
        domain = self._get_domain(request.url)

        if domain not in self.retry_stats:
            self.retry_stats[domain] = {
                "total_requests": 0,
                "retried_requests": 0,
                "successful_retries": 0,
                "failed_retries": 0,
                "total_delay": 0.0,
                "avg_delay": 0.0,
            }

        stats = self.retry_stats[domain]
        stats["total_requests"] += 1

        retry_count = self._get_retry_count(request)
        if retry_count > 0:
            stats["retried_requests"] += 1
            stats["total_delay"] += delay

            if success:
                stats["successful_retries"] += 1
            else:
                stats["failed_retries"] += 1

            stats["avg_delay"] = stats["total_delay"] / stats["retried_requests"]

    def _create_retry_request(self, request: Request, spider: Spider) -> Request:
        """Create retry request with updated meta."""
        retry_count = self._get_retry_count(request)
        delay = self._calculate_backoff_delay(request)

        # Create new request with retry information
        retry_request = request.replace(
            meta={
                **request.meta,
                "retry_count": retry_count,
                "retry_delay": delay,
                "retry_timestamp": time.time(),
            }
        )

        # Add delay to request
        retry_request.meta["download_delay"] = delay

        return retry_request

    def process_response(
        self, request: Request, response: Response, spider: Spider
    ) -> Optional[Request]:
        """Process response and determine if retry is needed."""
        domain = self._get_domain(request.url)

        # Update circuit breaker
        success = 200 <= response.status < 400
        self._update_circuit_breaker(domain, success)

        # Check if retry is needed
        if self._should_retry(request, response, None):
            self._increment_retry_count(request)
            retry_request = self._create_retry_request(request, spider)

            # Update statistics
            delay = retry_request.meta.get("retry_delay", 0)
            self._update_retry_stats(request, False, delay)

            # Log retry
            spider.logger.warning(
                f"Retrying {request.url} (attempt {self._get_retry_count(request)}) "
                f"after {delay:.2f}s delay (status: {response.status})"
            )

            return retry_request

        # Update statistics for successful request
        if success:
            self._update_retry_stats(request, True, 0)

        return None

    def process_exception(
        self, request: Request, exception: Exception, spider: Spider
    ) -> Optional[Request]:
        """Process exception and determine if retry is needed."""
        domain = self._get_domain(request.url)

        # Update circuit breaker
        self._update_circuit_breaker(domain, False)

        # Check if retry is needed
        if self._should_retry(request, None, exception):
            self._increment_retry_count(request)
            retry_request = self._create_retry_request(request, spider)

            # Update statistics
            delay = retry_request.meta.get("retry_delay", 0)
            self._update_retry_stats(request, False, delay)

            # Log retry
            spider.logger.warning(
                f"Retrying {request.url} (attempt {self._get_retry_count(request)}) "
                f"after {delay:.2f}s delay (exception: {exception})"
            )

            return retry_request

        # Log final failure
        spider.logger.error(f"Failed to process {request.url}: {exception}")

        return None

    def spider_opened(self, spider: Spider):
        """Called when spider is opened."""
        spider.logger.info(
            f"SmartRetryMiddleware initialized with max_retry_times={self.max_retry_times}"
        )

    def spider_closed(self, spider: Spider):
        """Called when spider is closed."""
        # Log retry statistics
        if self.retry_stats:
            spider.logger.info("Retry statistics:")
            for domain, stats in self.retry_stats.items():
                spider.logger.info(
                    f"  {domain}: {stats['retried_requests']}/{stats['total_requests']} "
                    f"retried, {stats['successful_retries']} successful, "
                    f"avg delay: {stats['avg_delay']:.2f}s"
                )

    @classmethod
    def from_crawler(cls, crawler):
        """Create middleware instance from crawler."""
        settings = crawler.settings

        # Check if smart retry is enabled
        if not settings.getbool("SCRAPYX_SMART_RETRY_ENABLED", False):
            raise NotConfigured("SCRAPYX_SMART_RETRY_ENABLED is False")

        return cls(settings)
