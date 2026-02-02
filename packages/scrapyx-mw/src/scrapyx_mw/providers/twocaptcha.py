"""
2Captcha provider implementation for scrapyx-mw.
"""

from __future__ import annotations
from typing import Optional
from urllib.parse import urlencode
from twisted.internet import defer
from twisted.web.client import Agent

from .base import CaptchaProvider, PermanentCaptchaError, TransientCaptchaError


HTTP_OK = 200


class TwoCaptchaProvider(CaptchaProvider):
    """2captcha.com provider implementation."""

    def __init__(
        self,
        api_key: str,
        agent: Agent,
        base_url: str = "https://2captcha.com",
        method: str = "userrecaptcha",
        **kwargs,
    ):
        super().__init__(api_key, agent, **kwargs)
        self.base_url = base_url
        self.method = method

    @defer.inlineCallbacks
    def submit(self, site_key: str, page_url: str, is_invisible: bool = False) -> str:
        # 2captcha auto-detects invisible, parameter included for interface consistency
        params = {
            "key": self.api_key,
            "method": self.method,
            "googlekey": site_key,
            "pageurl": page_url,
            "json": 1,
        }
        url = f"{self.base_url}/in.php?{urlencode(params)}"
        data = yield self._get_json(url)

        if data.get("status") == 1:
            return data["request"]

        req = data.get("request")
        permanent = {
            "ERROR_WRONG_USER_KEY",
            "ERROR_ZERO_BALANCE",
            "ERROR_PAGEURL",
            "ERROR_GOOGLEKEY",
            "ERROR_IP_NOT_ALLOWED",
            "ERROR_BAD_PARAMETERS",
            "ERROR_DUPLICATE",
            "ERROR_DOMAIN_NOT_ALLOWED",
        }
        if req in permanent:
            raise PermanentCaptchaError(f"2Captcha submit error: {req}")
        raise TransientCaptchaError(f"2Captcha submit error: {req or 'Unknown'}")

    @defer.inlineCallbacks
    def poll(self, captcha_id: str) -> Optional[str]:
        params = {"key": self.api_key, "action": "get", "id": captcha_id, "json": 1}
        url = f"{self.base_url}/res.php?{urlencode(params)}"
        data = yield self._get_json(url)

        if data.get("status") == 1:
            return data["request"]

        req = data.get("request")
        if req == "CAPCHA_NOT_READY":
            return None

        permanent = {
            "ERROR_WRONG_USER_KEY",
            "ERROR_WRONG_CAPTCHA_ID",
            "ERROR_CAPTCHA_UNSOLVABLE",
            "ERROR_ZERO_BALANCE",
            "ERROR_IP_NOT_ALLOWED",
        }
        if req in permanent:
            raise PermanentCaptchaError(f"2Captcha poll error: {req}")
        raise TransientCaptchaError(f"2Captcha poll error: {req or 'Unknown error'}")
