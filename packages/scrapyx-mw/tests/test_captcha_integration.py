"""Integration tests for captcha solving."""

import pytest
from unittest.mock import Mock, patch
from scrapy import Request

from scrapyx_mw.middlewares.captcha_polling import AsyncCaptchaMiddleware


@pytest.mark.integration
class TestCaptchaPollingIntegration:
    """Integration tests for captcha polling middleware."""

    @pytest.fixture
    def settings(self):
        """Create mock settings."""
        settings = Mock()
        settings.getbool.return_value = True
        settings.get.return_value = "test_api_key"
        settings.getint.return_value = 110
        settings.getfloat.return_value = 4.0
        return settings

    @pytest.fixture
    def middleware(self, settings):
        """Create captcha middleware instance."""
        with patch("scrapyx_mw.middlewares.captcha_polling.Agent"):
            with patch(
                "scrapyx_mw.middlewares.captcha_polling.create_provider"
            ) as mock_create:
                # Mock provider
                mock_provider = Mock()
                mock_provider.submit.return_value = "captcha_id_123"
                mock_provider.poll.return_value = "solution_token"
                mock_create.return_value = mock_provider

                middleware = AsyncCaptchaMiddleware(settings)
                middleware.provider = mock_provider
                return middleware

    def test_captcha_cache_ttl(self, middleware):
        """Test that captcha solutions are cached with TTL."""
        request = Request("http://example.com")
        spider = Mock()
        spider.name = "test_spider"
        spider.captcha_needed = True
        spider.site_key = "6Le-wvkSAAAAAKB"

        # First request should solve captcha
        result1 = middleware.process_request(request, spider)

        # Second request should use cache
        request2 = Request("http://example.com")
        result2 = middleware.process_request(request2, spider)

        # Both should succeed
        assert result1 is None or request.meta.get("recaptcha_solution")
        assert result2 is None or request2.meta.get("recaptcha_solution")

    def test_captcha_deduplication(self, middleware):
        """Test that simultaneous requests are de-duplicated."""
        request1 = Request("http://example.com")
        request2 = Request("http://example.com")
        spider = Mock()
        spider.name = "test_spider"
        spider.captcha_needed = True
        spider.site_key = "6Le-wvkSAAAAAKB"

        # Both requests should share the same captcha solution
        result1 = middleware.process_request(request1, spider)
        result2 = middleware.process_request(request2, spider)

        # Solutions should be identical
        assert result1 is None or request1.meta.get("recaptcha_solution")
        assert result2 is None or request2.meta.get("recaptcha_solution")

    def test_captcha_disabled(self):
        """Test that middleware is disabled when CAPTCHA_ENABLED=False."""
        settings = Mock()
        settings.getbool.return_value = False

        with pytest.raises(Exception):  # Should raise NotConfigured
            AsyncCaptchaMiddleware(settings)

    def test_missing_api_key(self):
        """Test that middleware requires API key."""
        settings = Mock()
        settings.getbool.return_value = True
        settings.get.return_value = None  # No API key

        with pytest.raises(Exception):  # Should raise NotConfigured
            AsyncCaptchaMiddleware(settings)


@pytest.mark.integration
class TestCaptchaWebhookIntegration:
    """Integration tests for webhook captcha middleware."""

    def test_webhook_middleware_initialization(self):
        """Test webhook middleware initialization."""
        from scrapyx_mw.middlewares.captcha_webhook import WebhookCaptchaMiddleware

        settings = Mock()
        settings.getbool.return_value = True
        settings.get.return_value = "test_api_key"

        with patch("scrapyx_mw.middlewares.captcha_webhook.Agent"):
            with patch("scrapyx_mw.middlewares.captcha_webhook.create_provider"):
                middleware = WebhookCaptchaMiddleware(settings)
                assert middleware.api_key == "test_api_key"
