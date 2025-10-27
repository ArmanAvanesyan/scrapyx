"""
CapSolver provider implementation for scrapyx-mw.
"""

from __future__ import annotations
from typing import Optional
from twisted.internet import defer
from twisted.web.client import Agent

from .base import CaptchaProvider, PermanentCaptchaError, TransientCaptchaError


class CapSolverProvider(CaptchaProvider):
    """
    CapSolver implementation using JSON POST:
    - createTask:  POST https://api.capsolver.com/createTask
    - getTaskResult: POST https://api.capsolver.com/getTaskResult

    Expected fields (success):
      createTask -> {"errorId":0,"taskId":"..."}
      getTaskResult -> {"errorId":0,"status":"ready","solution":{"gRecaptchaResponse":"..."}}
                        or {"errorId":0,"status":"processing"}

    Failures have errorId != 0 with errorCode/errorDescription.
    """

    def __init__(self, api_key: str, agent: Agent, base_url: str = "https://api.capsolver.com",
                 task_type: str = "ReCaptchaV2TaskProxyLess", **kwargs):
        super().__init__(api_key, agent, **kwargs)
        self.base_url = base_url
        self.task_type = task_type

    @defer.inlineCallbacks
    def submit(self, site_key: str, page_url: str, is_invisible: bool = False) -> str:
        payload = {
            "clientKey": self.api_key,
            "task": {
                "type": self.task_type,
                "websiteURL": page_url,
                "websiteKey": site_key,
            }
        }
        
        # Add isInvisible parameter for invisible reCAPTCHA
        if is_invisible:
            payload["task"]["isInvisible"] = True
        
        url = f"{self.base_url}/createTask"
        data = yield self._post_json(url, payload)

        error_id = data.get("errorId", 1)
        if error_id == 0 and data.get("taskId"):
            return data["taskId"]

        # Decode error
        code = data.get("errorCode", "")
        desc = data.get("errorDescription", "")
        # Common permanent-ish errors
        permanent_codes = {
            "ERROR_TOKEN_EXPIRED", "ERROR_UNSUPPORTED_TASK_TYPE", "ERROR_KEY_DENIED",
            "ERROR_INCORRECT_SESSION_DATA", "ERROR_BAD_PARAMETERS", "ERROR_ZERO_BALANCE",
            "ERROR_TOO_MANY_BAD_REQUESTS",
        }
        if code in permanent_codes:
            raise PermanentCaptchaError(f"CapSolver createTask error: {code} {desc}".strip())

        raise TransientCaptchaError(f"CapSolver createTask error: {code or desc or 'Unknown error'}")

    @defer.inlineCallbacks
    def poll(self, captcha_id: str) -> Optional[str]:
        payload = {"clientKey": self.api_key, "taskId": captcha_id}
        url = f"{self.base_url}/getTaskResult"
        data = yield self._post_json(url, payload)

        error_id = data.get("errorId", 0)
        if error_id != 0:
            code = data.get("errorCode", "")
            desc = data.get("errorDescription", "")
            permanent_codes = {
                "ERROR_TOKEN_EXPIRED", "ERROR_KEY_DENIED", "ERROR_INCORRECT_SESSION_DATA",
                "ERROR_BAD_PARAMETERS", "ERROR_ZERO_BALANCE",
            }
            if code in permanent_codes:
                raise PermanentCaptchaError(f"CapSolver getTaskResult error: {code} {desc}".strip())
            raise TransientCaptchaError(f"CapSolver getTaskResult error: {code or desc or 'Unknown error'}")

        status = data.get("status")
        if status == "processing":
            return None

        if status == "ready":
            solution = (data.get("solution") or {}).get("gRecaptchaResponse")
            if solution:
                return solution
            # If ready but missing field, treat as transient data hiccup
            raise TransientCaptchaError("CapSolver ready but missing gRecaptchaResponse")

        # Unknown status → transient
        raise TransientCaptchaError(f"CapSolver unexpected status: {status}")
