"""
scrapyx-mw Add-on

A Scrapy Add-on that programmatically enables the scrapyx-mw middlewares
according to simple settings flags. This lets users turn on the full stack
via the official `ADDONS` setting, without manually editing middleware dicts.

Usage in project settings.py:

ADDONS = {
    "scrapyx_mw.addon.ScrapyxAddon": 0,
}

# Optional flags (all have sensible defaults):
#   SCRAPYX_SESSION_ENABLED=True
#   SCRAPYX_API_REQUEST_ENABLED=True
#   SCRAPYX_DEBUG_ENABLED=False
#   SCRAPYX_CAPTCHA_MODE="none"        # "none" | "polling" | "webhook"
#   SCRAPYX_CAPTCHA_ENABLED=False
#   SCRAPYX_CURL_CFFI_ENABLED=False   # CurlCffi download handler (opt-in)
#   SCRAPYX_CURL_CFFI_MIDDLEWARE_ENABLED=False  # CurlCffi middleware (opt-out)
#   CAPTCHA_ENABLED (alias), CAPTCHA_API_KEY, CAPTCHA_WEBHOOK_URL, etc.

Notes:
- We *only* set/merge values at "addon" priority and try not to override user-specified values.
- We preserve existing DOWNLOADER_MIDDLEWARES/SPIDER_MIDDLEWARES entries if present.
"""

from __future__ import annotations
from typing import Any, Dict
from scrapy.exceptions import NotConfigured


class ScrapyxAddon:
    """Composable Add-on for scrapyx-mw components."""

    # ---- Add-on lifecycle: runs before crawler is built ----
    @classmethod
    def update_pre_crawler_settings(cls, settings: Any) -> None:
        """
        Compose middleware stacks and defaults *before* the crawler builds its components.
        This is the right timing per Scrapy's add-on lifecycle.
        """

        # Helper getters with defaults
        getbool = lambda k, d: settings.getbool(k, d)
        getstr = lambda k, d: settings.get(k, d)
        getint = lambda k, d: int(settings.getint(k, d))
        getflt = lambda k, d: float(settings.getfloat(k, d))

        # Feature flags (users can override in their project settings)
        session_on = getbool("SCRAPYX_SESSION_ENABLED", True)
        api_req_on = getbool("SCRAPYX_API_REQUEST_ENABLED", True)
        debug_on = getbool("SCRAPYX_DEBUG_ENABLED", False)
        proxy_rotation_on = getbool("SCRAPYX_PROXY_ROTATION_ENABLED", False)
        smart_retry_on = getbool("SCRAPYX_SMART_RETRY_ENABLED", False)
        curl_cffi_handler_on = getbool("SCRAPYX_CURL_CFFI_ENABLED", False)
        curl_cffi_mw_on = getbool("SCRAPYX_CURL_CFFI_MIDDLEWARE_ENABLED", False)

        captcha_mode = getstr(
            "SCRAPYX_CAPTCHA_MODE", "none"
        )  # "none" | "polling" | "webhook"
        # Respect both our namespaced flag and the canonical one
        captcha_enabled = getbool(
            "SCRAPYX_CAPTCHA_ENABLED", settings.getbool("CAPTCHA_ENABLED", False)
        )

        # Production hardening extensions
        telemetry_on = getbool("SCRAPYX_TELEMETRY_ENABLED", False)
        guardrails_on = getbool("SCRAPYX_GUARDRAILS_ENABLED", False)
        log_redaction_on = getbool("SCRAPYX_LOG_REDACTION_ENABLED", False)

        # Pull existing dicts (if any)
        dmw: Dict[str, int] = dict(settings.getdict("DOWNLOADER_MIDDLEWARES") or {})
        smw: Dict[str, int] = dict(settings.getdict("SPIDER_MIDDLEWARES") or {})

        # ---- Compose downloader middlewares (only set if missing) ----
        if session_on:
            dmw.setdefault("scrapyx_mw.middlewares.session.SessionMiddleware", 705)
        if api_req_on:
            dmw.setdefault(
                "scrapyx_mw.middlewares.api_request.ApiRequestMiddleware", 710
            )
        if debug_on:
            dmw.setdefault("scrapyx_mw.middlewares.debug.DebugRequestMiddleware", 740)
        if proxy_rotation_on:
            dmw.setdefault(
                "scrapyx_mw.middlewares.proxy_rotation.ProxyRotationMiddleware", 750
            )
        if smart_retry_on:
            dmw.setdefault(
                "scrapyx_mw.middlewares.smart_retry.SmartRetryMiddleware", 755
            )

        # Captcha strategy: pick one based on mode + enabled
        if captcha_enabled:
            if captcha_mode == "polling":
                dmw.setdefault(
                    "scrapyx_mw.middlewares.captcha_polling.AsyncCaptchaMiddleware", 760
                )
            elif captcha_mode == "webhook":
                dmw.setdefault(
                    "scrapyx_mw.middlewares.captcha_webhook.WebhookCaptchaMiddleware",
                    761,
                )

        if curl_cffi_mw_on:
            dmw.setdefault("scrapyx_mw.middlewares.curl_cffi.CurlCffiMiddleware", 706)

        # Save stacks back with "addon" priority, so user values still win
        settings.set("DOWNLOADER_MIDDLEWARES", dmw, priority="addon")
        settings.set("SPIDER_MIDDLEWARES", smw, priority="addon")

        # ---- Propagate defaults for captcha/session knobs (only if not set by the project) ----
        def setdefault(name: str, value: Any) -> None:
            if settings.get(name, None) is None:
                settings.set(name, value, priority="addon")

        # ---- Download handlers (curl_cffi for browser impersonation) ----
        if curl_cffi_handler_on:
            handlers: Dict[str, str] = dict(settings.getdict("DOWNLOAD_HANDLERS") or {})
            handler_path = (
                "scrapyx_mw.downloadhandlers.curl_cffi.CurlCffiDownloadHandler"
            )
            handlers.setdefault("https", handler_path)
            handlers.setdefault("http", handler_path)
            settings.set("DOWNLOAD_HANDLERS", handlers, priority="addon")
            setdefault("CURL_CFFI_ENABLED", True)

        setdefault("CAPTCHA_ENABLED", captcha_enabled)
        # Support both SCRAPYX_* and CAPTCHA_* prefixed settings for consistency
        setdefault(
            "CAPTCHA_API_KEY",
            getstr("SCRAPYX_CAPTCHA_API_KEY", getstr("CAPTCHA_API_KEY", "")),
        )
        setdefault(
            "CAPTCHA_PROVIDER",
            getstr("SCRAPYX_CAPTCHA_PROVIDER", getstr("CAPTCHA_PROVIDER", "2captcha")),
        )
        setdefault(
            "CAPTCHA_TOKEN_TTL_SECONDS", getint("CAPTCHA_TOKEN_TTL_SECONDS", 110)
        )
        setdefault("CAPTCHA_POLL_INITIAL_S", getflt("CAPTCHA_POLL_INITIAL_S", 4.0))
        setdefault("CAPTCHA_POLL_MAX_S", getflt("CAPTCHA_POLL_MAX_S", 45.0))
        setdefault("CAPTCHA_POLL_MAX_TIME_S", getflt("CAPTCHA_POLL_MAX_TIME_S", 180.0))
        setdefault("CAPTCHA_HTTP_TIMEOUT_S", getflt("CAPTCHA_HTTP_TIMEOUT_S", 15.0))
        setdefault("CAPTCHA_HTTP_RETRIES", getint("CAPTCHA_HTTP_RETRIES", 2))
        setdefault(
            "CAPTCHA_WEBHOOK_URL",
            getstr("CAPTCHA_WEBHOOK_URL", "http://127.0.0.1:6801/webhook"),
        )

        # Provider-specific settings
        setdefault(
            "CAPTCHA_2CAPTCHA_BASE",
            getstr("CAPTCHA_2CAPTCHA_BASE", "https://2captcha.com"),
        )
        setdefault(
            "CAPTCHA_2CAPTCHA_METHOD",
            getstr("CAPTCHA_2CAPTCHA_METHOD", "userrecaptcha"),
        )
        setdefault(
            "CAPTCHA_CAPSOLVER_BASE",
            getstr("CAPTCHA_CAPSOLVER_BASE", "https://api.capsolver.com"),
        )
        setdefault(
            "CAPTCHA_CAPSOLVER_TASK_TYPE",
            getstr("CAPTCHA_CAPSOLVER_TASK_TYPE", "ReCaptchaV2TaskProxyLess"),
        )

        # Default session headers map (can be overridden per-spider via service_config["HEADERS"])
        setdefault("SESSION_HEADERS", settings.get("SESSION_HEADERS", {}))

        # Proxy rotation defaults
        setdefault(
            "SCRAPYX_PROXY_ROTATION_STRATEGY",
            getstr("SCRAPYX_PROXY_ROTATION_STRATEGY", "round_robin"),
        )
        setdefault(
            "SCRAPYX_PROXY_HEALTH_CHECK", getbool("SCRAPYX_PROXY_HEALTH_CHECK", True)
        )
        setdefault(
            "SCRAPYX_PROXY_HEALTH_CHECK_INTERVAL",
            getint("SCRAPYX_PROXY_HEALTH_CHECK_INTERVAL", 300),
        )
        setdefault(
            "SCRAPYX_PROXY_MAX_FAILURES", getint("SCRAPYX_PROXY_MAX_FAILURES", 3)
        )
        setdefault(
            "SCRAPYX_PROXY_SESSION_PERSISTENCE",
            getbool("SCRAPYX_PROXY_SESSION_PERSISTENCE", True),
        )

        # Smart retry defaults
        setdefault("SCRAPYX_RETRY_MAX_TIMES", getint("SCRAPYX_RETRY_MAX_TIMES", 3))
        setdefault(
            "SCRAPYX_RETRY_HTTP_CODES",
            settings.getlist(
                "SCRAPYX_RETRY_HTTP_CODES", [500, 502, 503, 504, 408, 429]
            ),
        )
        setdefault(
            "SCRAPYX_RETRY_BASE_BACKOFF", getflt("SCRAPYX_RETRY_BASE_BACKOFF", 1.0)
        )
        setdefault(
            "SCRAPYX_RETRY_MAX_BACKOFF", getflt("SCRAPYX_RETRY_MAX_BACKOFF", 60.0)
        )
        setdefault(
            "SCRAPYX_RETRY_BACKOFF_MULTIPLIER",
            getflt("SCRAPYX_RETRY_BACKOFF_MULTIPLIER", 2.0),
        )
        setdefault(
            "SCRAPYX_RETRY_JITTER_ENABLED",
            getbool("SCRAPYX_RETRY_JITTER_ENABLED", True),
        )
        setdefault(
            "SCRAPYX_RETRY_JITTER_RANGE", getflt("SCRAPYX_RETRY_JITTER_RANGE", 0.1)
        )
        setdefault(
            "SCRAPYX_RETRY_CIRCUIT_BREAKER_ENABLED",
            getbool("SCRAPYX_RETRY_CIRCUIT_BREAKER_ENABLED", True),
        )
        setdefault(
            "SCRAPYX_RETRY_CIRCUIT_BREAKER_THRESHOLD",
            getint("SCRAPYX_RETRY_CIRCUIT_BREAKER_THRESHOLD", 5),
        )
        setdefault(
            "SCRAPYX_RETRY_CIRCUIT_BREAKER_TIMEOUT",
            getint("SCRAPYX_RETRY_CIRCUIT_BREAKER_TIMEOUT", 60),
        )
        setdefault(
            "SCRAPYX_RETRY_PRIORITY_ENABLED",
            getbool("SCRAPYX_RETRY_PRIORITY_ENABLED", True),
        )
        setdefault(
            "SCRAPYX_RETRY_PRIORITY_MULTIPLIER",
            getflt("SCRAPYX_RETRY_PRIORITY_MULTIPLIER", 1.5),
        )

        # Optional: bail out if nothing is enabled (not required; we still leave gentle defaults)
        # if not any([session_on, api_req_on, debug_on, captcha_enabled]):
        #     raise NotConfigured("scrapyx-mw: all features disabled")

        # ---- Enable extensions (config validator always enabled) ----
        ext_map = dict(settings.getdict("EXTENSIONS") or {})
        ext_map.setdefault("scrapyx_mw.extensions.config_validator.ConfigValidator", 10)

        # Enable production hardening extensions if configured
        if telemetry_on:
            ext_map.setdefault("scrapyx_mw.extensions.telemetry.TelemetryExtension", 20)

        if guardrails_on:
            ext_map.setdefault(
                "scrapyx_mw.extensions.guardrails.GuardrailsExtension", 30
            )
            # Set defaults for guardrails settings
            setdefault(
                "SCRAPYX_RATE_LIMIT_PER_HOUR", getint("SCRAPYX_RATE_LIMIT_PER_HOUR", 0)
            )
            setdefault(
                "SCRAPYX_RATE_LIMIT_PER_DAY", getint("SCRAPYX_RATE_LIMIT_PER_DAY", 0)
            )
            setdefault(
                "SCRAPYX_MAX_SPEND_PER_DAY", getflt("SCRAPYX_MAX_SPEND_PER_DAY", 0.0)
            )
            setdefault(
                "SCRAPYX_CAPTCHA_COST_PER_SOLVE",
                getflt("SCRAPYX_CAPTCHA_COST_PER_SOLVE", 0.002),
            )
            setdefault(
                "SCRAPYX_CIRCUIT_BREAKER_THRESHOLD",
                getint("SCRAPYX_CIRCUIT_BREAKER_THRESHOLD", 5),
            )

        if log_redaction_on:
            ext_map.setdefault(
                "scrapyx_mw.extensions.log_redactor.LogRedactorExtension", 40
            )
            setdefault(
                "SCRAPYX_REDACTION_TEXT", getstr("SCRAPYX_REDACTION_TEXT", "[REDACTED]")
            )
            setdefault(
                "SCRAPYX_REDACTION_PATTERNS",
                settings.getlist("SCRAPYX_REDACTION_PATTERNS", []),
            )

        settings.set("EXTENSIONS", ext_map, priority="addon")

    # ---- Optional runtime hook (not required here) ----
    def __init__(self, *args, **kwargs) -> None:
        # Handle both direct instantiation and from_crawler calls
        if args and hasattr(args[0], "settings"):
            # Called from from_crawler
            self.crawler = args[0]
        else:
            # Called directly by Scrapy
            self.crawler = None
        # You could connect to signals here if you want runtime behavior/stats.

    @classmethod
    def from_crawler(cls, crawler: Any) -> "ScrapyxAddon":
        """Required by Scrapy for add-on instantiation."""
        return cls(crawler)
