"""
Factory for creating captcha providers.
"""

from typing import Any
from twisted.web.client import Agent

from .base import CaptchaProvider
from .twocaptcha import TwoCaptchaProvider
from .capsolver import CapSolverProvider


def create_provider(provider_name: str, api_key: str, agent: Agent, settings: dict) -> CaptchaProvider:
    """
    Factory function to create captcha providers.
    
    Args:
        provider_name: Name of the provider ("2captcha" or "capsolver")
        api_key: API key for the provider
        agent: Twisted Agent instance for HTTP requests
        settings: Provider-specific settings dictionary
        
    Returns:
        An instance of the appropriate CaptchaProvider subclass
        
    Supported providers:
        - "capsolver": CapSolver API implementation
        - "2captcha" or default: 2captcha.com implementation
    """
    provider_name = provider_name.lower()
    
    if provider_name == "capsolver":
        return CapSolverProvider(
            api_key=api_key,
            agent=agent,
            base_url=settings.get("CAPTCHA_CAPSOLVER_BASE", "https://api.capsolver.com"),
            task_type=settings.get("CAPTCHA_CAPSOLVER_TASK_TYPE", "ReCaptchaV2TaskProxyLess"),
            request_timeout_s=settings.get("CAPTCHA_HTTP_TIMEOUT_S", 15.0),
            http_retries=settings.get("CAPTCHA_HTTP_RETRIES", 2),
        )
    else:
        # Default to 2captcha
        return TwoCaptchaProvider(
            api_key=api_key,
            agent=agent,
            base_url=settings.get("CAPTCHA_2CAPTCHA_BASE", "https://2captcha.com"),
            method=settings.get("CAPTCHA_2CAPTCHA_METHOD", "userrecaptcha"),
            request_timeout_s=settings.get("CAPTCHA_HTTP_TIMEOUT_S", 15.0),
            http_retries=settings.get("CAPTCHA_HTTP_RETRIES", 2),
        )
