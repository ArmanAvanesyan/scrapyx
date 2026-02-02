"""
Captcha providers for scrapyx-mw package.

Supports multiple captcha solving services:
- 2captcha (polling-based)
- CapSolver (polling-based)
- Future: webhook-based providers
"""

from .base import (
    CaptchaError,
    CaptchaProvider,
    PermanentCaptchaError,
    TransientCaptchaError,
)
from .capsolver import CapSolverProvider
from .factory import create_provider
from .twocaptcha import TwoCaptchaProvider

__all__ = [
    "CaptchaError",
    "CaptchaProvider",
    "CapSolverProvider",
    "PermanentCaptchaError",
    "TransientCaptchaError",
    "TwoCaptchaProvider",
    "create_provider",
]
