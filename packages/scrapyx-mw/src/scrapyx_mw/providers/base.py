"""
Base provider abstraction for scrapyx-mw captcha solving.
"""

from __future__ import annotations
import json
from io import BytesIO
from typing import Optional
from twisted.internet import defer, reactor
from twisted.web.client import Agent, readBody, FileBodyProducer
from twisted.web.http_headers import Headers


class CaptchaError(Exception):
    """Base captcha error."""

    permanent: bool = False


class PermanentCaptchaError(CaptchaError):
    permanent = True


class TransientCaptchaError(CaptchaError):
    permanent = False


class CaptchaProvider:
    """Abstract provider interface."""

    def __init__(self, api_key: str, agent: Agent, **kwargs):
        self.api_key = api_key
        self.agent = agent
        self.request_timeout_s = kwargs.get("request_timeout_s", 15.0)
        self.http_retries = max(0, int(kwargs.get("http_retries", 2)))

    @defer.inlineCallbacks
    def _get_json(self, url: str) -> dict:
        """GET JSON with timeout + simple retries."""
        attempt = 0
        last_err: Exception | None = None
        while attempt <= self.http_retries:
            try:
                d = self.agent.request(b"GET", url.encode("utf-8"))
                d.addTimeout(self.request_timeout_s, reactor)
                resp = yield d
                if resp.code != 200:
                    raise TransientCaptchaError(f"HTTP {resp.code} for {url}")
                body = yield readBody(resp)
                try:
                    data = json.loads(body.decode("utf-8"))
                except Exception as e:
                    raise TransientCaptchaError(f"Invalid JSON: {e}")
                defer.returnValue(data)
            except TransientCaptchaError as e:
                last_err = e
                attempt += 1
                if attempt > self.http_retries:
                    raise
                yield self._sleep(0.75 * attempt)
            except Exception as e:
                last_err = e
                attempt += 1
                if attempt > self.http_retries:
                    raise TransientCaptchaError(f"Transport failure: {e}")
                yield self._sleep(0.75 * attempt)
        raise TransientCaptchaError(
            str(last_err) if last_err else "Unknown transport error"
        )

    @defer.inlineCallbacks
    def _post_json(self, url: str, payload: dict) -> dict:
        """POST JSON with timeout + simple retries."""
        attempt = 0
        last_err: Exception | None = None
        while attempt <= self.http_retries:
            try:
                json_data = json.dumps(payload).encode("utf-8")
                body_producer = FileBodyProducer(BytesIO(json_data))
                headers = Headers({b"Content-Type": [b"application/json"]})
                d = self.agent.request(
                    b"POST",
                    url.encode("utf-8"),
                    headers=headers,
                    bodyProducer=body_producer,
                )
                d.addTimeout(self.request_timeout_s, reactor)
                resp = yield d
                if resp.code != 200:
                    raise TransientCaptchaError(f"HTTP {resp.code} for {url}")
                response_body = yield readBody(resp)
                try:
                    data = json.loads(response_body.decode("utf-8"))
                except Exception as e:
                    raise TransientCaptchaError(f"Invalid JSON: {e}")
                defer.returnValue(data)
            except TransientCaptchaError as e:
                last_err = e
                attempt += 1
                if attempt > self.http_retries:
                    raise
                yield self._sleep(0.75 * attempt)
            except Exception as e:
                last_err = e
                attempt += 1
                if attempt > self.http_retries:
                    raise TransientCaptchaError(f"Transport failure: {e}")
                yield self._sleep(0.75 * attempt)
        raise TransientCaptchaError(
            str(last_err) if last_err else "Unknown transport error"
        )

    def _sleep(self, s: float):
        d = defer.Deferred()
        reactor.callLater(s, d.callback, None)
        return d

    @defer.inlineCallbacks
    def submit(self, site_key: str, page_url: str, is_invisible: bool = False) -> str:
        """Submit captcha for solving. Returns captcha_id."""
        raise NotImplementedError

    @defer.inlineCallbacks
    def poll(self, captcha_id: str) -> Optional[str]:
        """Poll for solution. Returns solution or None if not ready."""
        raise NotImplementedError
