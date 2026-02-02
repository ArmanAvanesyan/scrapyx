from __future__ import annotations

import uuid
from typing import Any, Optional

import scrapy
from itemloaders import ItemLoader
from scrapy import signals

from .loaders import load_registry_from_settings


class BaseServiceSpider(scrapy.Spider):
    """
    Reusable base spider that exposes:
    - service_config (dict)  — typed source from ServiceRegistry
    - captcha_needed (bool)  — per-service flag surfaced for middlewares
    - site_key (str|None)    — service-level recaptcha site key
    - items/errors lists     — handy collection for summary returns
    - yield_empty_item()     — builds an item with job_id attached
    """

    reset_captcha_flag: bool = True  # middlewares can flip this
    _service_config: dict[str, Any] | None = None
    _captcha_needed: bool = False
    _site_key: Optional[str] = None

    def __init__(
        self, name: Optional[str] = None, _job: Optional[str] = None, **kwargs: Any
    ) -> None:
        super().__init__(name=name, **kwargs)
        self.job_id: Optional[str] = _job
        self.cookiejar_key: str = str(uuid.uuid4())

        self.items: list[Any] = []
        self.errors: list[str] = []

    # ---- lifecycle wiring

    @classmethod
    def from_crawler(cls, crawler: Any, *args: Any, **kwargs: Any) -> "BaseServiceSpider":
        spider = super().from_crawler(crawler, *args, **kwargs)

        # Load typed registry and apply to spider state
        registry = load_registry_from_settings(crawler.settings)
        cfg = registry.for_spider(spider.name)
        cfg_dict = cfg.to_runtime_dict()

        spider._service_config = cfg_dict
        spider._captcha_needed = bool(cfg.CAPTCHA_REQUIRED)
        spider._site_key = cfg.SITE_KEY

        # connect item collection
        crawler.signals.connect(spider.item_scraped, signal=signals.item_scraped)
        return spider

    # ---- properties / helpers

    @property
    def service_config(self) -> dict[str, Any]:
        return self._service_config or {}

    @property
    def captcha_needed(self) -> bool:
        return bool(self._captcha_needed)

    @captcha_needed.setter
    def captcha_needed(self, value: bool) -> None:
        self._captcha_needed = bool(value)

    @property
    def site_key(self) -> Optional[str]:
        return self._site_key

    def item_scraped(self, item: Any, response: Any, spider: Any) -> None:
        if spider == self:
            self.items.append(item)

    async def validate_required_args(self, **required: Any) -> bool:
        missing = [k for k, v in required.items() if not v]
        if missing:
            self.logger.error(f"Missing required arguments: {', '.join(missing)}")
            return False
        return True

    async def yield_empty_item(self, item_cls: type[Any]) -> Any:
        loader = ItemLoader(item=item_cls())
        loader.add_value("job_id", self.job_id)
        return loader.load_item()

    def log_error(self, message: str, url: Optional[str] = None) -> None:
        msg = f"{message} - URL: {url}" if url else message
        self.errors.append(msg)
        self.logger.error(msg)

    def get_results(self) -> dict[str, Any]:
        return {
            "spider_name": self.name,
            "status": "completed",
            "items_count": len(self.items),
            "errors_count": len(self.errors),
            "items": self.items,
            "errors": self.errors,
        }
