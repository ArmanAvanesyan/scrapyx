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
    
    def _start_broker(self) -> None:
        """Start the broker connection."""
        async def start_async():
            broker = self._get_broker()
            await broker.start()
            return broker
        
        def run_in_thread():
            """Run async code in a new thread with its own event loop."""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(start_async())
                logger.info(f"Broker {self.broker_type} started")
            except Exception as e:
                logger.error(f"Error starting broker: {e}", exc_info=True)
            finally:
                loop.close()
        
        # Check if there's a running event loop
        try:
            _ = asyncio.get_running_loop()  # Detect if we're in a running loop
            # If we're here, there's a running loop, so run in a thread
            thread = threading.Thread(target=run_in_thread, daemon=True)
            thread.start()
            thread.join(timeout=10)  # Wait up to 10 seconds
        except RuntimeError:
            # No running loop, we can run directly
            run_in_thread()

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
            
            def run_in_thread():
                """Run async code in a new thread with its own event loop."""
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(
                        broker.publish(event.model_dump(), queue="spider.completion")
                    )
                    logger.info(f"Published completion event for job {event.job_id}: {event.status}")
                except Exception as e:
                    logger.error(f"Error in thread publishing completion event: {e}", exc_info=True)
                finally:
                    loop.close()
            
            # Check if there's a running event loop
            try:
                _ = asyncio.get_running_loop()  # Detect if we're in a running loop
                # If we're here, there's a running loop, so run in a thread
                thread = threading.Thread(target=run_in_thread, daemon=True)
                thread.start()
                thread.join(timeout=10)  # Wait up to 10 seconds
            except RuntimeError:
                # No running loop, we can run directly
                run_in_thread()
                
        except Exception as e:
            logger.error(f"Error publishing completion event: {e}", exc_info=True)
        finally:
            # Close broker connection
            if self._broker is not None:
                async def close_async():
                    await self._broker.close()
                
                def close_in_thread():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(close_async())
                        logger.info(f"Broker {self.broker_type} closed")
                    except Exception as e:
                        logger.error(f"Error closing broker: {e}", exc_info=True)
                    finally:
                        loop.close()
                
                try:
                    _ = asyncio.get_running_loop()  # Detect if we're in a running loop
                    thread = threading.Thread(target=close_in_thread, daemon=True)
                    thread.start()
                    thread.join(timeout=10)
                except RuntimeError:
                    close_in_thread()
