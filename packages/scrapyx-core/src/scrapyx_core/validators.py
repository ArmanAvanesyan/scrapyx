from __future__ import annotations

from typing import Any, Iterable, Tuple

from .config import ServiceRegistry


def _is_blank(s: str | None) -> bool:
    return not s or not str(s).strip()


def validate_captcha_settings(settings: Any) -> Iterable[Tuple[str, str]]:
    """
    Yield (level, message) tuples describing issues with global captcha settings.
    Does not raise — callers can aggregate/raise in extensions.
    """
    enabled = bool(settings.getbool("CAPTCHA_ENABLED", False))
    if not enabled:
        return []

    provider = (settings.get("CAPTCHA_PROVIDER", "") or "").lower()
    api_key = settings.get("CAPTCHA_API_KEY", "") or ""

    if _is_blank(provider):
        yield ("error", "CAPTCHA_ENABLED=True but CAPTCHA_PROVIDER is not set")

    if _is_blank(api_key):
        yield ("error", "CAPTCHA_ENABLED=True but CAPTCHA_API_KEY is missing/blank")

    # Optional: basic provider set
    if provider not in {"2captcha", "capsolver"}:
        yield ("warn", f"Unknown CAPTCHA_PROVIDER='{provider}'. Expected one of: 2captcha, capsolver")


def validate_services_registry(registry: ServiceRegistry) -> Iterable[Tuple[str, str]]:
    """
    Yield (level, message) tuples describing issues in per-spider service configs.
    """
    for name, cfg in (registry.services or {}).items():
        if bool(cfg.CAPTCHA_REQUIRED) and _is_blank(cfg.SITE_KEY):
            yield ("error", f"SERVICES[{name}]: CAPTCHA_REQUIRED=True but SITE_KEY is missing/blank")

