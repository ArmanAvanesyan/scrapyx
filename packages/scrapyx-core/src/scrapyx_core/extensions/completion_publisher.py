"""
Scrapy extension to publish spider completion events via FastStream.
Supports RabbitMQ and Redis brokers via configuration.
"""

import logging
from typing import Any, Optional, Literal
from scrapy import signals
from scrapy.crawler import Crawler
from faststream.rabbit import RabbitBroker
from faststream.redis import RedisBroker
from scrapyx_core.models.events import SpiderCompletionEvent

logger = logging.getLogger(__name__)


class CompletionPublisherExtension:
    """Publishes spider completion events via FastStream."""

    def __init__(self, crawler: Crawler) -> None:
        self.crawler = crawler
        
        # Get broker configuration
        self.broker_type: Literal["rabbitmq", "redis"] = crawler.settings.get(
            "BROKER_TYPE", "rabbitmq"
        )
        self.broker_url: str = crawler.settings.get(
            "RABBITMQ_URL" if self.broker_type == "rabbitmq" else "REDIS_URL",
            "amqp://admin:admin@localhost:5672/" if self.broker_type == "rabbitmq" 
            else "redis://localhost:6379/0"
        )
        self._broker: Optional[RabbitBroker | RedisBroker] = None

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> "CompletionPublisherExtension":
        ext = cls(crawler)
        crawler.signals.connect(ext.spider_closed, signal=signals.spider_closed)
        logger.info(f"CompletionPublisherExtension initialized with {ext.broker_type}")
        return ext

    def _get_broker(self) -> RabbitBroker | RedisBroker:
        """Get or create broker instance."""
        if self._broker is None:
            if self.broker_type == "rabbitmq":
                self._broker = RabbitBroker(self.broker_url)
            else:
                self._broker = RedisBroker(self.broker_url)
            logger.info(f"Connected to {self.broker_type} at {self.broker_url}")
        return self._broker

    def spider_closed(self, spider: Any, reason: str) -> None:
        """Handle spider_closed signal and publish event."""
        try:
            # Build event
            event = SpiderCompletionEvent(
                job_id=getattr(spider, 'job_id', None),
                spider_name=spider.name,
                status='success' if reason == 'finished' else 'failed',
                reason=reason,
                items_count=len(getattr(spider, 'items', [])),
                errors_count=len(getattr(spider, 'errors', [])),
                project=self.crawler.settings.get("BOT_NAME", "unknown"),
            )
            
            # Publish via FastStream (synchronous context)
            broker = self._get_broker()
            
            # Use broker's sync publish method
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            loop.run_until_complete(
                broker.publish(event.model_dump(), queue="spider.completion")
            )
            
            logger.info(f"Published completion event for job {event.job_id}: {event.status}")
                
        except Exception as e:
            logger.error(f"Error publishing completion event: {e}", exc_info=True)
