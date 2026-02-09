from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Optional, Dict

CaptchaStrategy = Literal["none", "polling", "webhook"]


@dataclass
class ScrapyXConfig:
    api_request: bool = True
    session: bool = True
    debug: bool = False
    captcha: CaptchaStrategy = "none"

    # Captcha base knobs
    captcha_enabled: bool = False
    captcha_api_key: str = ""
    captcha_provider: str = "2captcha"

    # Polling tuning
    captcha_token_ttl_s: int = 110
    captcha_poll_initial_s: float = 4.0
    captcha_poll_max_s: float = 45.0
    captcha_poll_max_time_s: float = 180.0
    captcha_http_timeout_s: float = 15.0
    captcha_http_retries: int = 2

    # Webhook
    captcha_webhook_url: str = "http://127.0.0.1:6801/webhook"

    # Session defaults
    session_headers: Optional[Dict[str, str]] = None

    # Where per-spider configs live
    services_key: str = "SERVICES"

    # Priorities (Session/ApiRequest before CurlCffi so headers apply to curl_cffi requests)
    prio_session: int = 705
    prio_api: int = 706
    prio_debug: int = 740
    prio_captcha_poll: int = 760
    prio_captcha_webhook: int = 761
    prio_curl_cffi: int = 708

    # CurlCffi middleware (browser impersonation)
    curl_cffi: bool = False
