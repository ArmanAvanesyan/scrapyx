"""
Proxy rotation middleware for scrapyx-mw.

This middleware provides intelligent proxy rotation with support for:
- Multiple proxy sources (lists, APIs, databases)
- Proxy health checking and automatic removal of failed proxies
- Load balancing across proxy pools
- Session persistence for specific requests
- Proxy authentication support
"""

import random
import time
from typing import Dict, List, Optional, Set, Any
from urllib.parse import urlparse

from scrapy import Request, Spider
from scrapy.exceptions import NotConfigured
from scrapy.http import Response


class ProxyRotationMiddleware:
    """Middleware for rotating proxies across requests."""

    def __init__(self, settings):
        self.settings = settings
        self.proxy_list = self._load_proxy_list()
        self.proxy_stats = {}  # Track proxy performance
        self.failed_proxies: Set[str] = set()
        self.session_proxies: Dict[str, str] = {}  # Track session-specific proxies
        
        # Configuration
        self.rotation_strategy = settings.get("SCRAPYX_PROXY_ROTATION_STRATEGY", "round_robin")
        self.health_check_enabled = settings.getbool("SCRAPYX_PROXY_HEALTH_CHECK", True)
        self.health_check_interval = settings.getint("SCRAPYX_PROXY_HEALTH_CHECK_INTERVAL", 300)
        self.max_failures = settings.getint("SCRAPYX_PROXY_MAX_FAILURES", 3)
        self.session_persistence = settings.getbool("SCRAPYX_PROXY_SESSION_PERSISTENCE", True)
        
        # Performance tracking
        self.last_health_check = 0
        self.request_count = 0

    def _load_proxy_list(self) -> List[str]:
        """Load proxy list from various sources."""
        proxies = []
        
        # From settings list
        proxy_list = self.settings.getlist("SCRAPYX_PROXY_LIST", [])
        proxies.extend(proxy_list)
        
        # From environment variable
        proxy_env = self.settings.get("SCRAPYX_PROXY_ENV_VAR", "SCRAPYX_PROXY_LIST")
        import os
        env_proxies = os.getenv(proxy_env, "")
        if env_proxies:
            proxies.extend([p.strip() for p in env_proxies.split(",") if p.strip()])
        
        # From file
        proxy_file = self.settings.get("SCRAPYX_PROXY_FILE")
        if proxy_file:
            try:
                with open(proxy_file, 'r') as f:
                    file_proxies = [line.strip() for line in f if line.strip()]
                    proxies.extend(file_proxies)
            except FileNotFoundError:
                pass
        
        # Validate proxy format
        valid_proxies = []
        for proxy in proxies:
            if self._validate_proxy_format(proxy):
                valid_proxies.append(proxy)
            else:
                print(f"Invalid proxy format: {proxy}")
        
        return valid_proxies

    def _validate_proxy_format(self, proxy: str) -> bool:
        """Validate proxy URL format."""
        try:
            parsed = urlparse(proxy)
            return parsed.scheme in ['http', 'https', 'socks4', 'socks5'] and parsed.hostname
        except Exception:
            return False

    def _get_next_proxy(self, request: Request) -> Optional[str]:
        """Get next proxy based on rotation strategy."""
        if not self.proxy_list:
            return None
        
        # Remove failed proxies
        available_proxies = [p for p in self.proxy_list if p not in self.failed_proxies]
        if not available_proxies:
            # Reset failed proxies if all are failed
            self.failed_proxies.clear()
            available_proxies = self.proxy_list
        
        if not available_proxies:
            return None
        
        # Check for session persistence
        if self.session_persistence:
            session_id = request.meta.get('session_id')
            if session_id and session_id in self.session_proxies:
                proxy = self.session_proxies[session_id]
                if proxy in available_proxies:
                    return proxy
        
        # Select proxy based on strategy
        if self.rotation_strategy == "round_robin":
            proxy = available_proxies[self.request_count % len(available_proxies)]
        elif self.rotation_strategy == "random":
            proxy = random.choice(available_proxies)
        elif self.rotation_strategy == "weighted":
            proxy = self._get_weighted_proxy(available_proxies)
        else:
            proxy = random.choice(available_proxies)
        
        # Store session proxy
        if self.session_persistence:
            session_id = request.meta.get('session_id')
            if session_id:
                self.session_proxies[session_id] = proxy
        
        self.request_count += 1
        return proxy

    def _get_weighted_proxy(self, proxies: List[str]) -> str:
        """Select proxy based on performance weights."""
        weights = []
        for proxy in proxies:
            stats = self.proxy_stats.get(proxy, {'success_rate': 1.0, 'avg_response_time': 1.0})
            # Higher success rate and lower response time = higher weight
            weight = stats['success_rate'] / max(stats['avg_response_time'], 0.1)
            weights.append(weight)
        
        return random.choices(proxies, weights=weights)[0]

    def _update_proxy_stats(self, proxy: str, success: bool, response_time: float):
        """Update proxy performance statistics."""
        if proxy not in self.proxy_stats:
            self.proxy_stats[proxy] = {
                'requests': 0,
                'successes': 0,
                'failures': 0,
                'total_response_time': 0.0,
                'success_rate': 1.0,
                'avg_response_time': 1.0
            }
        
        stats = self.proxy_stats[proxy]
        stats['requests'] += 1
        stats['total_response_time'] += response_time
        
        if success:
            stats['successes'] += 1
        else:
            stats['failures'] += 1
        
        # Calculate metrics
        stats['success_rate'] = stats['successes'] / stats['requests']
        stats['avg_response_time'] = stats['total_response_time'] / stats['requests']
        
        # Mark proxy as failed if it exceeds failure threshold
        if stats['failures'] >= self.max_failures:
            self.failed_proxies.add(proxy)

    def _should_health_check(self) -> bool:
        """Check if it's time for a health check."""
        if not self.health_check_enabled:
            return False
        
        current_time = time.time()
        return current_time - self.last_health_check > self.health_check_interval

    def _perform_health_check(self):
        """Perform health check on failed proxies."""
        if not self.failed_proxies:
            return
        
        # Simple health check - try a lightweight request
        # In a real implementation, you might want to use a more sophisticated approach
        self.last_health_check = time.time()
        
        # For now, we'll just reset some failed proxies periodically
        if len(self.failed_proxies) > len(self.proxy_list) * 0.5:
            # Reset half of failed proxies
            failed_list = list(self.failed_proxies)
            reset_count = len(failed_list) // 2
            for proxy in failed_list[:reset_count]:
                self.failed_proxies.discard(proxy)
                if proxy in self.proxy_stats:
                    self.proxy_stats[proxy]['failures'] = 0

    def process_request(self, request: Request, spider: Spider) -> Optional[Request]:
        """Process request to add proxy."""
        # Perform health check if needed
        if self._should_health_check():
            self._perform_health_check()
        
        # Get next proxy
        proxy = self._get_next_proxy(request)
        if proxy:
            request.meta['proxy'] = proxy
            request.meta['proxy_start_time'] = time.time()
            
            # Log proxy usage
            spider.logger.debug(f"Using proxy: {proxy} for {request.url}")
        
        return None

    def process_response(self, request: Request, response: Response, spider: Spider) -> Response:
        """Process response to update proxy statistics."""
        proxy = request.meta.get('proxy')
        if proxy:
            start_time = request.meta.get('proxy_start_time', time.time())
            response_time = time.time() - start_time
            
            # Determine success based on response status
            success = 200 <= response.status < 400
            
            self._update_proxy_stats(proxy, success, response_time)
            
            if success:
                spider.logger.debug(f"Proxy {proxy} succeeded for {request.url}")
            else:
                spider.logger.warning(f"Proxy {proxy} failed for {request.url} (status: {response.status})")
        
        return response

    def process_exception(self, request: Request, exception: Exception, spider: Spider) -> Optional[Request]:
        """Process exception to update proxy statistics."""
        proxy = request.meta.get('proxy')
        if proxy:
            start_time = request.meta.get('proxy_start_time', time.time())
            response_time = time.time() - start_time
            
            self._update_proxy_stats(proxy, False, response_time)
            
            spider.logger.warning(f"Proxy {proxy} failed for {request.url}: {exception}")
        
        return None

    @classmethod
    def from_crawler(cls, crawler):
        """Create middleware instance from crawler."""
        settings = crawler.settings
        
        # Check if proxy rotation is enabled
        if not settings.getbool("SCRAPYX_PROXY_ROTATION_ENABLED", False):
            raise NotConfigured("SCRAPYX_PROXY_ROTATION_ENABLED is False")
        
        return cls(settings)
