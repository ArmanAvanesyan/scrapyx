"""
ConfigValidator Extension
-------------------------
Ensures CAPTCHA-related configuration is valid before the crawler starts.

Fails fast when:
- Any spider has SERVICES[SPIDER_NAME_UPPER]["CAPTCHA_REQUIRED"] = True
  but missing SITE_KEY, or
- CAPTCHA_ENABLED=True but CAPTCHA_API_KEY missing or blank.

Usage:
  Automatically enabled by scrapyx_mw.addon.ScrapyxAddon
  or manually via settings:

  EXTENSIONS = {
      "scrapyx_mw.extensions.config_validator.ConfigValidator": 10,
  }
"""

from __future__ import annotations
import logging
from scrapy import signals
from scrapy.exceptions import NotConfigured

logger = logging.getLogger(__name__)


class ConfigValidator:
    """Fail-fast validator for CAPTCHA configuration."""

    def __init__(self, crawler):
        self.crawler = crawler
        self.settings = crawler.settings

    @classmethod
    def from_crawler(cls, crawler):
        ext = cls(crawler)
        crawler.signals.connect(ext.engine_started, signal=signals.engine_started)
        return ext

    def engine_started(self):
        """Run validation once engine starts but before requests are scheduled."""
        settings = self.settings

        captcha_enabled = settings.getbool("CAPTCHA_ENABLED", False)
        captcha_api_key = settings.get("CAPTCHA_API_KEY", "").strip()

        if captcha_enabled and not captcha_api_key:
            raise NotConfigured(
                "CAPTCHA_ENABLED=True but CAPTCHA_API_KEY is missing or blank."
            )

        # Validate each spider service config if available
        services = settings.getdict("SERVICES", {})

        for spider_name, conf in services.items():
            if conf.get("CAPTCHA_REQUIRED", False):
                site_key = conf.get("SITE_KEY")
                if not site_key:
                    raise NotConfigured(
                        f"Spider '{spider_name}' requires CAPTCHA but has no SITE_KEY defined."
                    )

        logger.info("[ConfigValidator] CAPTCHA configuration validated successfully.")
