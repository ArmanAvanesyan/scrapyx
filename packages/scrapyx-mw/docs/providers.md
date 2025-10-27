# Captcha Providers

The `scrapyx-mw` package supports multiple captcha solving providers through an extensible abstraction layer.

## Supported Providers

### 2Captcha

2Captcha is a traditional polling-based captcha solving service.

#### Features
- Well-established service with wide support
- Simple HTTP GET/POST API
- JSON-based responses
- High success rate

#### Configuration

```python
CAPTCHA_PROVIDER = "2captcha"
CAPTCHA_API_KEY = "your-2captcha-api-key"

# Optional settings
CAPTCHA_2CAPTCHA_BASE = "https://2captcha.com"  # default
CAPTCHA_2CAPTCHA_METHOD = "userrecaptcha"        # default
```

#### API Endpoints

- **Submit**: `GET https://2captcha.com/in.php?key={api_key}&method={method}&googlekey={site_key}&pageurl={page_url}&json=1`
- **Poll**: `GET https://2captcha.com/res.php?key={api_key}&action=get&id={captcha_id}&json=1`

#### Error Handling

- **Permanent errors**: `ERROR_WRONG_USER_KEY`, `ERROR_ZERO_BALANCE`, `ERROR_PAGEURL`, `ERROR_GOOGLEKEY`, `ERROR_IP_NOT_ALLOWED`, `ERROR_BAD_PARAMETERS`, `ERROR_DUPLICATE`, `ERROR_DOMAIN_NOT_ALLOWED`
- **Transient errors**: `CAPCHA_NOT_READY`, network issues

---

### CapSolver

CapSolver is a modern API-based captcha solving service with JSON endpoints.

#### Features
- Modern JSON-based API
- Fast response times
- Advanced task types
- Proxy support (when configured)

#### Configuration

```python
CAPTCHA_PROVIDER = "capsolver"
CAPTCHA_API_KEY = "your-capsolver-api-key"

# Optional settings
CAPTCHA_CAPSOLVER_BASE = "https://api.capsolver.com"              # default
CAPTCHA_CAPSOLVER_TASK_TYPE = "ReCaptchaV2TaskProxyLess"          # default
```

#### API Endpoints

- **Submit**: `POST https://api.capsolver.com/createTask`
- **Poll**: `POST https://api.capsolver.com/getTaskResult`

#### Task Types

- `ReCaptchaV2TaskProxyLess`: Standard reCAPTCHA v2 without proxy
- `ReCaptchaV2Task`: Standard reCAPTCHA v2 with proxy (requires proxy configuration)
- `ReCaptchaV3TaskProxyLess`: reCAPTCHA v3 without proxy
- `ReCaptchaV3Task`: reCAPTCHA v3 with proxy

#### Error Handling

- **Permanent errors**: `ERROR_TOKEN_EXPIRED`, `ERROR_UNSUPPORTED_TASK_TYPE`, `ERROR_KEY_DENIED`, `ERROR_INCORRECT_SESSION_DATA`, `ERROR_BAD_PARAMETERS`, `ERROR_ZERO_BALANCE`, `ERROR_TOO_MANY_BAD_REQUESTS`
- **Transient errors**: Network issues, rate limiting

---

## Provider Abstraction

The providers module implements a clean abstraction layer that allows easy addition of new providers.

### Architecture

```
scrapyx_mw/
└── providers/
    ├── __init__.py      # Public API exports
    ├── base.py          # CaptchaProvider base class
    ├── twocaptcha.py    # TwoCaptchaProvider implementation
    ├── capsolver.py     # CapSolverProvider implementation
    └── factory.py       # create_provider() factory function
```

### Base Provider Interface

All providers must implement the `CaptchaProvider` base class:

```python
class CaptchaProvider:
    """Abstract provider interface."""
    
    def __init__(self, api_key: str, agent: Agent, **kwargs):
        """Initialize provider with API key and Twisted agent."""
        pass
    
    @defer.inlineCallbacks
    def submit(self, site_key: str, page_url: str) -> str:
        """Submit captcha for solving. Returns captcha_id."""
        raise NotImplementedError
    
    @defer.inlineCallbacks
    def poll(self, captcha_id: str) -> Optional[str]:
        """Poll for solution. Returns solution or None if not ready."""
        raise NotImplementedError
```

### Error Handling

The base provider defines three error types:

- `CaptchaError`: Base captcha error
- `PermanentCaptchaError`: Non-retryable errors (invalid API key, zero balance, etc.)
- `TransientCaptchaError`: Retryable errors (network issues, rate limiting, etc.)

### Factory Function

The `create_provider()` factory function creates the appropriate provider instance based on configuration:

```python
provider = create_provider(
    provider_name="capsolver",
    api_key="your-api-key",
    agent=agent,  # Twisted Agent instance
    settings={
        "CAPTCHA_CAPSOLVER_BASE": "https://api.capsolver.com",
        "CAPTCHA_CAPSOLVER_TASK_TYPE": "ReCaptchaV2TaskProxyLess",
    }
)
```

## Adding a New Provider

To add a new captcha provider:

1. **Create provider file**: Create `libs/scrapyx-mw/src/scrapyx_mw/providers/yourprovider.py`
2. **Implement base class**: Inherit from `CaptchaProvider` and implement `submit()` and `poll()` methods
3. **Add error handling**: Use `PermanentCaptchaError` and `TransientCaptchaError` appropriately
4. **Update factory**: Add provider creation logic to `factory.py`
5. **Update exports**: Add the new provider to `__init__.py`
6. **Write tests**: Add tests to `tests/test_providers.py`

### Example Provider

```python
"""YourProvider implementation for scrapyx-mw."""

from __future__ import annotations
from typing import Optional
from twisted.internet import defer
from twisted.web.client import Agent

from .base import CaptchaProvider, PermanentCaptchaError, TransientCaptchaError


class YourProvider(CaptchaProvider):
    """YourProvider implementation."""
    
    def __init__(self, api_key: str, agent: Agent, base_url: str = "https://api.yourprovider.com", **kwargs):
        super().__init__(api_key, agent, **kwargs)
        self.base_url = base_url
    
    @defer.inlineCallbacks
    def submit(self, site_key: str, page_url: str) -> str:
        """Submit captcha for solving."""
        # Implement your submission logic
        # Return the captcha_id
        raise NotImplementedError
    
    @defer.inlineCallbacks
    def poll(self, captcha_id: str) -> Optional[str]:
        """Poll for solution."""
        # Implement your polling logic
        # Return solution or None if not ready
        raise NotImplementedError
```

## Testing

The provider tests use pytest with pytest-twisted for async support:

```bash
# Run provider tests
cd libs/scrapyx-mw
PYTHONPATH=src uv run pytest tests/test_providers.py -v
```

## Resources

- [2Captcha API Documentation](https://2captcha.com/2captcha-api)
- [CapSolver API Documentation](https://docs.capsolver.com/)
