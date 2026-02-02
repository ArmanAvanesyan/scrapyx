"""
Scrapy extension to publish spider completion events via FastStream.
Supports RabbitMQ and Redis brokers via configuration.
"""

import logging
import asyncio
import threading
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
            "amqp://admin:admin@localhost:5672/"
            if self.broker_type == "rabbitmq"
            else "redis://localhost:6379/0",
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
                job_id=getattr(spider, "job_id", None),
                spider_name=spider.name,
                status="success" if reason == "finished" else "failed",
                reason=reason,
                items_count=len(getattr(spider, "items", [])),
                errors_count=len(getattr(spider, "errors", [])),
                project=self.crawler.settings.get("BOT_NAME", "unknown"),
            )

            # Use a thread to avoid blocking and event loop conflicts
            def publish_in_thread():
                """Publish event in a separate thread with its own event loop."""
                # Create a new event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                async def publish_async():
                    """Publish event asynchronously."""
                    broker = self._get_broker()
                    await broker.start()
                    try:
                        await broker.publish(event.model_dump(), queue="spider.completion")
                        logger.info(
                            f"Published completion event for job {event.job_id}: {event.status}"
                        )
                    finally:
                        await broker.close()

                try:
                    loop.run_until_complete(publish_async())
                except Exception as e:
                    logger.error(f"Error publishing completion event: {e}", exc_info=True)
                finally:
                    loop.close()

            # Run in a daemon thread to not block
            thread = threading.Thread(target=publish_in_thread, daemon=True)
            thread.start()
            # Give it a moment to publish
            thread.join(timeout=10)

        except Exception as e:
            logger.error(f"Error in spider_closed: {e}", exc_info=True)
