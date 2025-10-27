from __future__ import annotations
from typing import Dict, Any
from .config import ScrapyXConfig

def default_config(**overrides: Any) -> ScrapyXConfig:
    cfg = ScrapyXConfig()
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg

def apply_downloader_middlewares(settings: Dict[str, Any], cfg: ScrapyXConfig) -> Dict[str, int]:
    """
    Build the DOWNLOADER_MIDDLEWARES dict at settings import time.
    Also mirrors cfg values into Scrapy settings names for compatibility.
    """
    mw: Dict[str, int] = {}

    if cfg.session:
        mw["scrapyx_mw.middlewares.session.SessionMiddleware"] = cfg.prio_session
    if cfg.api_request:
        mw["scrapyx_mw.middlewares.api_request.ApiRequestMiddleware"] = cfg.prio_api
    if cfg.debug:
        mw["scrapyx_mw.middlewares.debug.DebugRequestMiddleware"] = cfg.prio_debug

    if cfg.captcha == "polling" and cfg.captcha_enabled:
        mw["scrapyx_mw.middlewares.captcha_polling.AsyncCaptchaMiddleware"] = cfg.prio_captcha_poll
    elif cfg.captcha == "webhook" and cfg.captcha_enabled:
        mw["scrapyx_mw.middlewares.captcha_webhook.WebhookCaptchaMiddleware"] = cfg.prio_captcha_webhook

    # Surface cfg into settings for middlewares to read
    settings.setdefault("SCRAPYX", {})
    settings["SCRAPYX"].update(vars(cfg))

    settings.setdefault("CAPTCHA_ENABLED", cfg.captcha_enabled)
    settings.setdefault("CAPTCHA_API_KEY", cfg.captcha_api_key)
    settings.setdefault("CAPTCHA_PROVIDER", cfg.captcha_provider)
    settings.setdefault("CAPTCHA_TOKEN_TTL_SECONDS", cfg.captcha_token_ttl_s)
    settings.setdefault("CAPTCHA_POLL_INITIAL_S", cfg.captcha_poll_initial_s)
    settings.setdefault("CAPTCHA_POLL_MAX_S", cfg.captcha_poll_max_s)
    settings.setdefault("CAPTCHA_POLL_MAX_TIME_S", cfg.captcha_poll_max_time_s)
    settings.setdefault("CAPTCHA_HTTP_TIMEOUT_S", cfg.captcha_http_timeout_s)
    settings.setdefault("CAPTCHA_HTTP_RETRIES", cfg.captcha_http_retries)
    settings.setdefault("CAPTCHA_WEBHOOK_URL", cfg.captcha_webhook_url)
    settings.setdefault("SESSION_HEADERS", cfg.session_headers or {})

    return mw

def apply_spider_middlewares(settings: Dict[str, Any], cfg: ScrapyXConfig) -> Dict[str, int]:
    mw: Dict[str, int] = {}
    # No spider middlewares currently
    return mw
