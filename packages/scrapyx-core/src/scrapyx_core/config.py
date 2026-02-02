from __future__ import annotations

from typing import Dict, Optional
from pydantic import BaseModel, Field


class ServiceConfig(BaseModel):
    # Core endpoints (strings on purpose; we don't enforce URL type here)
    BASE_URL: Optional[str] = None
    PAGE_URL: Optional[str] = None
    API_URL: Optional[str] = None
    TOKEN_URL: Optional[str] = None

    # Captcha
    SITE_KEY: Optional[str] = None
    CAPTCHA_REQUIRED: bool = False

    # Header profiles (plain dicts)
    HEADERS: Optional[Dict[str, str]] = None
    HTML_HEADERS: Optional[Dict[str, str]] = None
    API_HEADERS: Optional[Dict[str, str]] = None

    # Feature flags for advanced setups
    RECAPTCHA_INVISIBLE: Optional[bool] = None
    RECAPTCHA_ENTERPRISE: Optional[bool] = None

    def to_runtime_dict(self) -> Dict[str, object]:
        """Return a plain dict for runtime use in spiders/middlewares."""
        return self.model_dump()


class ServiceRegistry(BaseModel):
    services: Dict[str, ServiceConfig] = Field(default_factory=dict)

    def for_spider(self, spider_name: str) -> ServiceConfig:
        key = (spider_name or "").upper()
        if key not in self.services:
            from .errors import MissingServiceError

            raise MissingServiceError(
                f"No service configuration for spider '{spider_name}' (key '{key}')."
            )
        return self.services[key]
