"""Unit tests for captcha providers."""

import pytest
from unittest.mock import MagicMock, patch
from twisted.web.client import Agent
import pytest_twisted

from scrapyx_mw.providers import (
    TwoCaptchaProvider,
    CapSolverProvider,
    create_provider,
    PermanentCaptchaError,
)


class TestTwoCaptchaProvider:
    """Test 2captcha provider implementation."""

    @pytest.fixture
    def provider(self):
        """Create a 2captcha provider instance."""
        agent = MagicMock(spec=Agent)
        return TwoCaptchaProvider(
            api_key="test_key",
            agent=agent,
            base_url="https://2captcha.com",
            method="userrecaptcha",
        )

    @pytest_twisted.inlineCallbacks
    def test_submit_success(self, provider):
        """Test successful captcha submission."""
        expected_captcha_id = "123456"

        # Mock the _get_json method
        with patch.object(
            provider,
            "_get_json",
            return_value={"status": 1, "request": expected_captcha_id},
        ):
            result = yield provider.submit("site_key", "http://example.com")
            assert result == expected_captcha_id

    @pytest_twisted.inlineCallbacks
    def test_submit_permanent_error(self, provider):
        """Test submission with permanent error."""
        with patch.object(
            provider,
            "_get_json",
            return_value={"status": 0, "request": "ERROR_WRONG_USER_KEY"},
        ):
            with pytest.raises(PermanentCaptchaError):
                yield provider.submit("site_key", "http://example.com")

    @pytest_twisted.inlineCallbacks
    def test_poll_success(self, provider):
        """Test successful polling."""
        expected_solution = "token_12345"

        with patch.object(
            provider,
            "_get_json",
            return_value={"status": 1, "request": expected_solution},
        ):
            result = yield provider.poll("123456")
            assert result == expected_solution

    @pytest_twisted.inlineCallbacks
    def test_poll_not_ready(self, provider):
        """Test polling when captcha is not ready."""
        with patch.object(
            provider,
            "_get_json",
            return_value={"status": 0, "request": "CAPCHA_NOT_READY"},
        ):
            result = yield provider.poll("123456")
            assert result is None


class TestCapSolverProvider:
    """Test CapSolver provider implementation."""

    @pytest.fixture
    def provider(self):
        """Create a CapSolver provider instance."""
        agent = MagicMock(spec=Agent)
        return CapSolverProvider(
            api_key="test_key",
            agent=agent,
            base_url="https://api.capsolver.com",
            task_type="ReCaptchaV2TaskProxyLess",
        )

    @pytest_twisted.inlineCallbacks
    def test_submit_success(self, provider):
        """Test successful task creation."""
        expected_task_id = "task_123456"

        with patch.object(
            provider,
            "_post_json",
            return_value={"errorId": 0, "taskId": expected_task_id},
        ):
            result = yield provider.submit("site_key", "http://example.com")
            assert result == expected_task_id

    @pytest_twisted.inlineCallbacks
    def test_submit_permanent_error(self, provider):
        """Test submission with permanent error."""
        with patch.object(
            provider,
            "_post_json",
            return_value={
                "errorId": 1,
                "errorCode": "ERROR_ZERO_BALANCE",
                "errorDescription": "No balance",
            },
        ):
            with pytest.raises(PermanentCaptchaError):
                yield provider.submit("site_key", "http://example.com")

    @pytest_twisted.inlineCallbacks
    def test_poll_ready(self, provider):
        """Test polling when solution is ready."""
        expected_solution = "token_12345"

        with patch.object(
            provider,
            "_post_json",
            return_value={
                "errorId": 0,
                "status": "ready",
                "solution": {"gRecaptchaResponse": expected_solution},
            },
        ):
            result = yield provider.poll("task_123456")
            assert result == expected_solution

    @pytest_twisted.inlineCallbacks
    def test_poll_processing(self, provider):
        """Test polling when task is still processing."""
        with patch.object(
            provider, "_post_json", return_value={"errorId": 0, "status": "processing"}
        ):
            result = yield provider.poll("task_123456")
            assert result is None


class TestProviderFactory:
    """Test provider factory function."""

    def test_create_2captcha_provider(self):
        """Test creating a 2captcha provider."""
        agent = MagicMock(spec=Agent)
        settings = {
            "CAPTCHA_2CAPTCHA_BASE": "https://2captcha.com",
            "CAPTCHA_2CAPTCHA_METHOD": "userrecaptcha",
        }

        provider = create_provider("2captcha", "test_key", agent, settings)
        assert isinstance(provider, TwoCaptchaProvider)
        assert provider.api_key == "test_key"

    def test_create_capsolver_provider(self):
        """Test creating a CapSolver provider."""
        agent = MagicMock(spec=Agent)
        settings = {
            "CAPTCHA_CAPSOLVER_BASE": "https://api.capsolver.com",
            "CAPTCHA_CAPSOLVER_TASK_TYPE": "ReCaptchaV2TaskProxyLess",
        }

        provider = create_provider("capsolver", "test_key", agent, settings)
        assert isinstance(provider, CapSolverProvider)
        assert provider.api_key == "test_key"

    def test_create_default_2captcha(self):
        """Test default to 2captcha when provider unknown."""
        agent = MagicMock(spec=Agent)
        settings = {}

        provider = create_provider("unknown", "test_key", agent, settings)
        assert isinstance(provider, TwoCaptchaProvider)
