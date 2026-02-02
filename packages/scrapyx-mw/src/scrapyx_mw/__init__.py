from .presets import (
    apply_downloader_middlewares,
    apply_spider_middlewares,
    default_config,
)
from .addon import ScrapyxAddon

__all__ = [
    "apply_downloader_middlewares",
    "apply_spider_middlewares",
    "default_config",
    "ScrapyxAddon",
]
