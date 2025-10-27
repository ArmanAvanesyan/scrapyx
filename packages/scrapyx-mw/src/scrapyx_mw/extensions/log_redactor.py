"""Log redaction extension for sensitive data."""

import logging
import re
from typing import List, Pattern, Any
from scrapy import signals
from scrapy.crawler import Crawler
from scrapy.exceptions import NotConfigured

logger = logging.getLogger(__name__)


class LogRedactorExtension:
    """
    Extension for redacting sensitive data from logs.
    
    Redacts:
    - API keys
    - Authentication tokens
    - Passwords
    - Custom patterns via settings
    """

    def __init__(self, crawler: Crawler) -> None:
        if not crawler.settings.getbool("SCRAPYX_LOG_REDACTION_ENABLED", False):
            raise NotConfigured("Log redaction extension not enabled")
        
        self.settings = crawler.settings
        
        # Default patterns for common secrets
        self.patterns: List[Pattern] = []
        
        # API keys
        api_key_pattern = r'(?i)(api[_-]?key|apikey)\s*[:=]\s*([a-zA-Z0-9_-]{16,})'
        self.patterns.append(re.compile(api_key_pattern))
        
        # Tokens
        token_pattern = r'(?i)(token|bearer)\s*[:=]\s*([a-zA-Z0-9_-]{20,})'
        self.patterns.append(re.compile(token_pattern))
        
        # Passwords
        password_pattern = r'(?i)(password|pwd|pass)\s*[:=]\s*([^\s\n]{8,})'
        self.patterns.append(re.compile(password_pattern))
        
        # Custom patterns from settings
        custom_patterns = self.settings.getlist("SCRAPYX_REDACTION_PATTERNS", [])
        for pattern_str in custom_patterns:
            try:
                self.patterns.append(re.compile(pattern_str))
            except re.error as e:
                logger.warning(f"Invalid redaction pattern: {pattern_str} - {e}")
        
        # Redaction placeholder
        self.redaction_text = self.settings.get("SCRAPYX_REDACTION_TEXT", "[REDACTED]")
        
        # Install filter
        self._install_filter()

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> "LogRedactorExtension":
        """Create extension instance from crawler."""
        ext = cls(crawler)
        crawler.signals.connect(ext.spider_opened, signal=signals.spider_opened)
        return ext

    def spider_opened(self, spider: Any) -> None:
        """Initialize log redaction on spider open."""
        logger.info("Log redaction enabled - sensitive data will be redacted")

    def _install_filter(self) -> None:
        """Install log filter to redact sensitive data."""
        for handler in logging.root.handlers:
            if hasattr(handler, 'addFilter') and not any(
                isinstance(f, _RedactionFilter)
                for f in handler.filters
            ):
                handler.addFilter(_RedactionFilter(self.patterns, self.redaction_text))

        # Also install on all existing loggers
        for name in logging.Logger.manager.loggerDict:
            logger_obj = logging.getLogger(name)
            for handler in logger_obj.handlers:
                if hasattr(handler, 'addFilter') and not any(
                    isinstance(f, _RedactionFilter)
                    for f in handler.filters
                ):
                    handler.addFilter(_RedactionFilter(self.patterns, self.redaction_text))

    def redact(self, text: str) -> str:
        """Redact sensitive data from text."""
        result = text
        for pattern in self.patterns:
            result = pattern.sub(f'\\1=[{self.redaction_text}]', result)
        return result


class _RedactionFilter(logging.Filter):
    """Log filter for redacting sensitive data."""
    
    def __init__(self, patterns: List[Pattern], redaction_text: str) -> None:
        super().__init__()
        self.patterns = patterns
        self.redaction_text = redaction_text

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter log records by redacting sensitive data."""
        # Redact in the message
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            record.msg = self._redact_text(record.msg)
        
        # Redact in args
        if hasattr(record, 'args') and record.args:
            new_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    new_args.append(self._redact_text(arg))
                else:
                    new_args.append(arg)
            record.args = tuple(new_args)
        
        return True

    def _redact_text(self, text: str) -> str:
        """Redact sensitive data from text."""
        result = text
        for pattern in self.patterns:
            result = pattern.sub(f'\\1=[{self.redaction_text}]', result)
        return result

