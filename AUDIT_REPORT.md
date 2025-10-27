# Scrapy/Scrapyd Ecosystem MVP Audit Report

## Overview

This repository contains three Python packages for a Scrapy/Scrapyd ecosystem MVP:

1. **scrapyx** (packages/scrapyx) — Empty namespace package providing `scrapyx` namespace
2. **scrapyx-core** (packages/scrapyx-core) — Base spider class with service configuration registry, Pydantic models, and completion event publishing (webhook & FastStream/RabbitMQ/Redis)
3. **scrapyx-mw** (packages/scrapyx-mw) — Composable middlewares for session management, API headers, captcha solving (2captcha/CapSolver polling & webhook), proxy rotation, smart retry, plus production hardening extensions (telemetry, guardrails, log redaction, config validation)

The codebase is in active development with basic tests present but incomplete coverage.

## Packages & Entry Points

### Python Packages
- **scrapyx** (packages/scrapyx/src/scrapyx/__init__.py) — Namespace package, version 0.1.0
- **scrapyx_core** (packages/scrapyx-core/src/scrapyx_core/) — Core utilities
- **scrapyx_mw** (packages/scrapyx-mw/src/scrapyx_mw/) — Middlewares and add-on

### Console Scripts
None defined. No `[project.scripts]` or `[project.entry-points]` in any pyproject.toml.

### Integration Points

**DOWNLOADER_MIDDLEWARES** (via scrapyx-mw):
- `scrapyx_mw.middlewares.session.SessionMiddleware` (priority 705)
- `scrapyx_mw.middlewares.api_request.ApiRequestMiddleware` (priority 710)
- `scrapyx_mw.middlewares.debug.DebugRequestMiddleware` (priority 740)
- `scrapyx_mw.middlewares.proxy_rotation.ProxyRotationMiddleware` (priority 750)
- `scrapyx_mw.middlewares.smart_retry.SmartRetryMiddleware` (priority 755)
- `scrapyx_mw.middlewares.captcha_polling.AsyncCaptchaMiddleware` (priority 760)
- `scrapyx_mw.middlewares.captcha_webhook.WebhookCaptchaMiddleware` (priority 761)

**SPIDER_MIDDLEWARES**: None provided.

**EXTENSIONS**:
- `scrapyx_mw.extensions.config_validator.ConfigValidator` (priority 10)
- `scrapyx_mw.extensions.telemetry.TelemetryExtension` (priority 20)
- `scrapyx_mw.extensions.guardrails.GuardrailsExtension` (priority 30)
- `scrapyx_mw.extensions.log_redactor.LogRedactorExtension` (priority 40)
- `scrapyx_core.extensions.webhook.WebhookExtension`
- `scrapyx_core.extensions.completion_publisher.CompletionPublisherExtension`

**Scrapy Add-on**:
- `scrapyx_mw.addon.ScrapyxAddon` — Composable add-on that programmatically enables middlewares/extensions via settings flags

### Scrapyd Sidecar Service
- **scrapyx_mw.scrapyd.webhook_service** — HTTP server listening on port 6801 (default)
  - POST `/webhook` accepts `id=<captcha_id>&code=<solution>` from 2captcha
  - GET `/health` returns status
  - Stores solutions in `/var/lib/scrapyd/webhook_solutions.db` (SQLite)
  - Auto-cleanup of solutions older than 1 hour
  - Run: `python -m scrapyx_mw.scrapyd.webhook_service`

## Public API

### scrapyx_core

```python
# packages/scrapyx-core/src/scrapyx_core/__init__.py
from scrapyx_core import (
    BaseServiceSpider,       # Base spider class
    ServiceConfig,           # Pydantic model for per-spider config
    ServiceRegistry,         # Pydantic model holding dict[str, ServiceConfig]
    load_registry_from_settings,  # Function to load from settings + optional JSON file
    validators               # Module with validate_captcha_settings, validate_services_registry
)
```

**BaseServiceSpider** (`packages/scrapyx-core/src/scrapyx_core/base.py:13-104`):
```python
class BaseServiceSpider(scrapy.Spider):
    def __init__(self, name: Optional[str] = None, _job: Optional[str] = None, **kwargs)
    @property def service_config(self) -> dict[str, Any]
    @property def captcha_needed(self) -> bool
    @property def site_key(self) -> Optional[str]
    def yield_empty_item(self, item_cls: type[Any]) -> Any
    def get_results(self) -> dict[str, Any]
    def log_error(self, message: str, url: Optional[str] = None) -> None
```

**ServiceRegistry** (`packages/scrapyx-core/src/scrapyx_core/config.py:32-40`):
```python
def for_spider(self, spider_name: str) -> ServiceConfig  # Uppercases spider name, raises MissingServiceError if not found
```

**ServiceConfig** (`packages/scrapyx-core/src/scrapyx_core/config.py:7-29`):
```python
class ServiceConfig(BaseModel):
    BASE_URL: Optional[str] = None
    PAGE_URL: Optional[str] = None
    API_URL: Optional[str] = None
    TOKEN_URL: Optional[str] = None
    SITE_KEY: Optional[str] = None
    CAPTCHA_REQUIRED: bool = False
    HEADERS: Optional[Dict[str, str]] = None
    HTML_HEADERS: Optional[Dict[str, str]] = None
    API_HEADERS: Optional[Dict[str, str]] = None
    RECAPTCHA_INVISIBLE: Optional[bool] = None
    RECAPTCHA_ENTERPRISE: Optional[bool] = None
    def to_runtime_dict(self) -> Dict[str, object]
```

**Events** (`packages/scrapyx-core/src/scrapyx_core/models/events.py:3-19`):
```python
class SpiderCompletionEvent(BaseModel):
    job_id: str
    spider_name: str
    status: str  # "success" or "failed"
    reason: str
    items_count: int = 0
    errors_count: int = 0
    project: str

class WebhookCallbackEvent(BaseModel):
    task_id: str
    callback_url: str
    status: str
    data: dict
```

### scrapyx_mw

```python
# packages/scrapyx-mw/src/scrapyx_mw/__init__.py
from scrapyx_mw import (
    ScrapyxAddon,                      # Composable add-on
    apply_downloader_middlewares,     # Function to build middleware dict
    apply_spider_middlewares,         # Function (returns empty dict)
    default_config                     # Function returning ScrapyXConfig dataclass
)
```

**ScrapyxAddon** (`packages/scrapyx-mw/src/scrapyx_mw/addon.py:32-191`):
```python
class ScrapyxAddon:
    @classmethod
    def update_pre_crawler_settings(cls, settings: Any) -> None  # Composes middleware/extensions based on settings flags
```

**Providers** (`packages/scrapyx-mw/src/scrapyx_mw/providers/__init__.py`):
```python
from scrapyx_mw.providers import (
    CaptchaError,
    CaptchaProvider,
    CapSolverProvider,
    PermanentCaptchaError,
    TransientCaptchaError,
    TwoCaptchaProvider,
    create_provider  # Factory function
)
```

**Middlewares** (`packages/scrapyx-mw/src/scrapyx_mw/middlewares/__init__.py`):
```python
from scrapyx_mw.middlewares import (
    ApiRequestMiddleware,
    AsyncCaptchaMiddleware,
    WebhookCaptchaMiddleware,
    DebugRequestMiddleware,
    ProxyRotationMiddleware,
    SessionMiddleware,
    SmartRetryMiddleware
)
```

**Extensions** (`packages/scrapyx-mw/src/scrapyx_mw/extensions/__init__.py`):
```python
from scrapyx_mw.extensions import (
    ConfigValidator,
    TelemetryExtension,
    GuardrailsExtension,
    LogRedactorExtension
)
```

## Settings & Environment

| Key | Type | Default | Where Used (file:line) | Notes/Precedence/Alias |
| --- | ---- | ------- | ---------------------- | ---------------------- |
| **SERVICES** | dict | `{}` | scrapyx_core/loaders.py:26, scrapyx_core/config.py:33, scrapyx_mw/extensions/config_validator.py:55 | Dict[str, ServiceConfig] — per-spider config; uppercased spider names |
| **SCRAPYX_SERVICES_FILE** | str | None | scrapyx_core/loaders.py:28 | Env var; JSON file path; merged before settings["SERVICES"] |
| **SCRAPYX_SESSION_ENABLED** | bool | `True` | scrapyx_mw/addon.py:50 | Controls SessionMiddleware (priority 705) |
| **SCRAPYX_API_REQUEST_ENABLED** | bool | `True` | scrapyx_mw/addon.py:51 | Controls ApiRequestMiddleware (priority 710) |
| **SCRAPYX_DEBUG_ENABLED** | bool | `False` | scrapyx_mw/addon.py:52 | Controls DebugRequestMiddleware (priority 740) |
| **SCRAPYX_PROXY_ROTATION_ENABLED** | bool | `False` | scrapyx_mw/addon.py:53 | Controls ProxyRotationMiddleware (priority 750) |
| **SCRAPYX_SMART_RETRY_ENABLED** | bool | `False` | scrapyx_mw/addon.py:54 | Controls SmartRetryMiddleware (priority 755) |
| **SCRAPYX_CAPTCHA_MODE** | str | `"none"` | scrapyx_mw/addon.py:56 | `"none"` \| `"polling"` \| `"webhook"` |
| **SCRAPYX_CAPTCHA_ENABLED** | bool | `False` | scrapyx_mw/addon.py:58 | Honored; also checks CAPTCHA_ENABLED (alias) |
| **CAPTCHA_ENABLED** | bool | `False` | scrapyx_mw/addon.py:58, scrapyx_mw/middlewares/captcha_polling.py:25 | Alias for SCRAPYX_CAPTCHA_ENABLED |
| **CAPTCHA_API_KEY** | str | `""` | scrapyx_mw/middlewares/captcha_polling.py:28, scrapyx_mw/addon.py:99 | Required if CAPTCHA_ENABLED=True |
| **CAPTCHA_PROVIDER** | str | `"2captcha"` | scrapyx_mw/middlewares/captcha_polling.py:45 | `"2captcha"` or `"capsolver"` |
| **CAPTCHA_TOKEN_TTL_SECONDS** | int | `110` | scrapyx_mw/middlewares/captcha_polling.py:32 | Token cache TTL |
| **CAPTCHA_POLL_INITIAL_S** | float | `4.0` | scrapyx_mw/middlewares/captcha_polling.py:33 | Initial poll delay (seconds) |
| **CAPTCHA_POLL_MAX_S** | float | `45.0` | scrapyx_mw/middlewares/captcha_polling.py:34 | Max poll delay (seconds) |
| **CAPTCHA_POLL_MAX_TIME_S** | float | `180.0` | scrapyx_mw/middlewares/captcha_polling.py:35 | Total polling timeout |
| **CAPTCHA_HTTP_TIMEOUT_S** | float | `15.0` | scrapyx_mw/middlewares/captcha_polling.py:36 | HTTP request timeout |
| **CAPTCHA_HTTP_RETRIES** | int | `2` | scrapyx_mw/middlewares/captcha_polling.py:37 | HTTP retry count |
| **CAPTCHA_WEBHOOK_URL** | str | `"http://127.0.0.1:6801/webhook"` | scrapyx_mw/middlewares/captcha_webhook.py:30 | Webhook receiver URL |
| **CAPTCHA_2CAPTCHA_BASE** | str | `"https://2captcha.com"` | scrapyx_mw/middlewares/captcha_polling.py:47 | Base URL for 2captcha API |
| **CAPTCHA_2CAPTCHA_METHOD** | str | `"userrecaptcha"` | scrapyx_mw/middlewares/captcha_polling.py:48 | 2captcha method |
| **CAPTCHA_CAPSOLVER_BASE** | str | `"https://api.capsolver.com"` | scrapyx_mw/middlewares/captcha_polling.py:49 | Base URL for CapSolver API |
| **CAPTCHA_CAPSOLVER_TASK_TYPE** | str | `"ReCaptchaV2TaskProxyLess"` | scrapyx_mw/middlewares/captcha_polling.py:50 | CapSolver task type |
| **SESSION_HEADERS** | dict | `{}` | scrapyx_mw/middlewares/session.py:7, scrapyx_mw/addon.py:116 | Global default headers (overridden by SERVICE["HEADERS"]) |
| **SCRAPYX_TELEMETRY_ENABLED** | bool | `False` | scrapyx_mw/addon.py:61 | Controls TelemetryExtension (priority 20) |
| **SCRAPYX_GUARDRAILS_ENABLED** | bool | `False` | scrapyx_mw/addon.py:62 | Controls GuardrailsExtension (priority 30) |
| **SCRAPYX_LOG_REDACTION_ENABLED** | bool | `False` | scrapyx_mw/addon.py:63 | Controls LogRedactorExtension (priority 40) |
| **SCRAPYX_RATE_LIMIT_PER_HOUR** | int | `0` | scrapyx_mw/extensions/guardrails.py:33 | 0 = disabled |
| **SCRAPYX_RATE_LIMIT_PER_DAY** | int | `0` | scrapyx_mw/extensions/guardrails.py:34 | 0 = disabled |
| **SCRAPYX_MAX_SPEND_PER_DAY** | float | `0.0` | scrapyx_mw/extensions/guardrails.py:37 | Budget limit (USD); 0 = disabled |
| **SCRAPYX_CAPTCHA_COST_PER_SOLVE** | float | `0.002` | scrapyx_mw/extensions/guardrails.py:38 | Cost per solve (USD) |
| **SCRAPYX_CIRCUIT_BREAKER_THRESHOLD** | int | `5` | scrapyx_mw/extensions/guardrails.py:41 | Circuit breaker failure threshold |
| **SCRAPYX_REDACTION_TEXT** | str | `"[REDACTED]"` | scrapyx_mw/extensions/log_redactor.py:54 | Redaction placeholder |
| **SCRAPYX_REDACTION_PATTERNS** | list | `[]` | scrapyx_mw/extensions/log_redactor.py:46 | Custom regex patterns |
| **SCRAPYX_PROXY_ROTATION_STRATEGY** | str | `"round_robin"` | scrapyx_mw/middlewares/proxy_rotation.py:33 | `"round_robin"` \| `"random"` \| `"weighted"` |
| **SCRAPYX_PROXY_HEALTH_CHECK** | bool | `True` | scrapyx_mw/middlewares/proxy_rotation.py:34 | Enable proxy health checks |
| **SCRAPYX_PROXY_HEALTH_CHECK_INTERVAL** | int | `300` | scrapyx_mw/middlewares/proxy_rotation.py:35 | Health check interval (seconds) |
| **SCRAPYX_PROXY_MAX_FAILURES** | int | `3` | scrapyx_mw/middlewares/proxy_rotation.py:36 | Max failures before proxy removal |
| **SCRAPYX_PROXY_SESSION_PERSISTENCE** | bool | `True` | scrapyx_mw/middlewares/proxy_rotation.py:37 | Enable session-aware proxy selection |
| **SCRAPYX_PROXY_LIST** | list | `[]` | scrapyx_mw/middlewares/proxy_rotation.py:48 | List of proxy URLs |
| **SCRAPYX_PROXY_ENV_VAR** | str | `"SCRAPYX_PROXY_LIST"` | scrapyx_mw/middlewares/proxy_rotation.py:52 | Env var name for proxy list |
| **SCRAPYX_PROXY_FILE** | str | None | scrapyx_mw/middlewares/proxy_rotation.py:59 | File path for proxy list |
| **SCRAPYX_RETRY_MAX_TIMES** | int | `3` | scrapyx_mw/middlewares/smart_retry.py:29 | Max retry attempts |
| **SCRAPYX_RETRY_HTTP_CODES** | list | `[500, 502, 503, 504, 408, 429]` | scrapyx_mw/middlewares/smart_retry.py:30 | HTTP status codes to retry |
| **SCRAPYX_RETRY_BASE_BACKOFF** | float | `1.0` | scrapyx_mw/middlewares/smart_retry.py:43 | Base backoff delay (seconds) |
| **SCRAPYX_RETRY_MAX_BACKOFF** | float | `60.0` | scrapyx_mw/middlewares/smart_retry.py:44 | Max backoff delay (seconds) |
| **SCRAPYX_RETRY_BACKOFF_MULTIPLIER** | float | `2.0` | scrapyx_mw/middlewares/smart_retry.py:45 | Backoff multiplier |
| **SCRAPYX_RETRY_JITTER_ENABLED** | bool | `True` | scrapyx_mw/middlewares/smart_retry.py:46 | Enable jitter |
| **SCRAPYX_RETRY_JITTER_RANGE** | float | `0.1` | scrapyx_mw/middlewares/smart_retry.py:47 | Jitter range (0.0-1.0) |
| **SCRAPYX_RETRY_CIRCUIT_BREAKER_ENABLED** | bool | `True` | scrapyx_mw/middlewares/smart_retry.py:50 | Enable circuit breaker |
| **SCRAPYX_RETRY_CIRCUIT_BREAKER_THRESHOLD** | int | `5` | scrapyx_mw/middlewares/smart_retry.py:51 | Circuit breaker threshold |
| **SCRAPYX_RETRY_CIRCUIT_BREAKER_TIMEOUT** | int | `60` | scrapyx_mw/middlewares/smart_retry.py:52 | Circuit breaker timeout (seconds) |
| **SCRAPYX_RETRY_PRIORITY_ENABLED** | bool | `True` | scrapyx_mw/middlewares/smart_retry.py:60 | Enable priority-based retry |
| **SCRAPYX_RETRY_PRIORITY_MULTIPLIER** | float | `1.5` | scrapyx_mw/middlewares/smart_retry.py:61 | Priority multiplier |
| **WEBHOOK_ENABLED** | bool | `False` | scrapyx_core/extensions/webhook.py:42 | Enable webhook extension |
| **GLOBAL_WEBHOOK_URL** | str | None | scrapyx_core/extensions/webhook.py:43 | Global webhook URL |
| **WEBHOOK_URLS** | dict | `{}` | scrapyx_core/extensions/webhook.py:46 | Per-spider webhook URLs |
| **WEBHOOK_TIMEOUT** | int | `30` | scrapyx_core/extensions/webhook.py:44 | Webhook timeout (seconds) |
| **WEBHOOK_RETRIES** | int | `3` | scrapyx_core/extensions/webhook.py:45 | Webhook retry count |
| **BROKER_TYPE** | str | `"rabbitmq"` | scrapyx_core/extensions/completion_publisher.py:24 | `"rabbitmq"` or `"redis"` |
| **RABBITMQ_URL** | str | `"amqp://admin:admin@localhost:5672/"` | scrapyx_core/extensions/completion_publisher.py:27-28 | RabbitMQ broker URL |
| **REDIS_URL** | str | `"redis://localhost:6379/0"` | scrapyx_core/extensions/completion_publisher.py:29-30 | Redis broker URL |
| **ADDONS** | dict | `{}` | scrapyx_mw/addon.py | Scrapy add-ons registry |

### Settings Precedence & Merging

1. **Service registry** (`load_registry_from_settings` in scrapyx-core/loaders.py:18-39):
   - JSON file from env `SCRAPYX_SERVICES_FILE` (optional)
   - Then `settings["SERVICES"]` (overrides file)
   - `SPIDER_NAME` uppercased for lookup

2. **ScrapyxAddon** (`scrapyx_mw/addon.py:37-173`):
   - Composes middleware dicts with `setdefault()` to avoid overriding user values
   - Sets defaults at "addon" priority
   - Middleware priorities:
     - Session: 705, API Request: 710, Debug: 740, Proxy: 750, Smart Retry: 755
     - Captcha polling: 760, Captcha webhook: 761

## Lifecycle & Signals

| Component | Signal | Purpose | File:Line |
| --------- | ------ | ------- | --------- |
| **BaseServiceSpider** | `item_scraped` | Collects scraped items into `spider.items` | scrapyx_core/base.py:52 |
| **WebhookExtension** | `spider_closed` | Sends webhook POST with job results | scrapyx_core/extensions/webhook.py:58 |
| **CompletionPublisherExtension** | `spider_closed` | Publishes SpiderCompletionEvent to broker queue | scrapyx_core/extensions/completion_publisher.py:37 |
| **ConfigValidator** | `engine_started` | Validates CAPTCHA_ENABLED + SERVICES config | scrapyx_mw/extensions/config_validator.py:39 |
| **TelemetryExtension** | `spider_opened`, `spider_closed` | Tracks captcha metrics, logs summary | scrapyx_mw/extensions/telemetry.py:39-40 |
| **GuardrailsExtension** | `spider_opened`, `engine_stopped` | Checks rate limits, budget at start/stop | scrapyx_mw/extensions/guardrails.py:53-54 |
| **LogRedactorExtension** | `spider_opened` | Installs log filters for sensitive data | scrapyx_mw/extensions/log_redactor.py:63 |
| **SessionMiddleware** | `spider_opened` | Logs activation | scrapyx_mw/middlewares/session.py:12 |
| **ApiRequestMiddleware** | `spider_opened` | Logs activation | scrapyx_mw/middlewares/api_request.py:9 |
| **AsyncCaptchaMiddleware** | `spider_opened` | Logs provider | scrapyx_mw/middlewares/captcha_polling.py:59 |
| **WebhookCaptchaMiddleware** | `spider_opened` | Logs activation | scrapyx_mw/middlewares/captcha_webhook.py:50 |

## Service Registry & Base Spider

### ServiceRegistry Schema
- **File**: `packages/scrapyx-core/src/scrapyx_core/config.py:32-40`
- `for_spider(spider_name: str) -> ServiceConfig`
  - Uppercases `spider_name`
  - Raises `MissingServiceError` (KeyError) if not found

### ServiceConfig Schema
- **File**: `packages/scrapyx-core/src/scrapyx_core/config.py:7-29`
- Fields: `BASE_URL`, `PAGE_URL`, `API_URL`, `TOKEN_URL`, `SITE_KEY`, `CAPTCHA_REQUIRED`, `HEADERS`, `HTML_HEADERS`, `API_HEADERS`, `RECAPTCHA_INVISIBLE`, `RECAPTCHA_ENTERPRISE`
- All optional except `CAPTCHA_REQUIRED: bool = False`

### Loader Precedence
- **File**: `packages/scrapyx-core/src/scrapyx_core/loaders.py:18-39`
1. Read env `SCRAPYX_SERVICES_FILE` → JSON file (if exists)
2. Read `settings["SERVICES"]`
3. Merge: `dict(file_services)` updated with `settings_services`
4. Coerce to `Dict[str, ServiceConfig]`

### BaseServiceSpider
- **File**: `packages/scrapyx-core/src/scrapyx_core/base.py:13-104`
- `job_id` from `__init__(_job=...)` parameter (scrapyx_core/base.py:28,30)
- `captcha_needed` from `registry.for_spider(spider.name).CAPTCHA_REQUIRED` (scrapyx_core/base.py:48)
- `site_key` from `registry.for_spider(spider.name).SITE_KEY` (scrapyx_core/base.py:49)
- `items` list populated by `item_scraped` signal handler (scrapyx_core/base.py:73-75)
- `errors` list via `log_error(message, url)` method (scrapyx_core/base.py:89-92)
- `yield_empty_item(item_cls)` uses ItemLoader + adds `job_id` (scrapyx_core/base.py:84-87)
- **Unbounded lists**: `items` and `errors` have no bounds (memory risk)

## Push/Transports

### Webhook Extension
- **File**: `packages/scrapyx-core/src/scrapyx_core/extensions/webhook.py:23-155`
- **Settings**: `WEBHOOK_ENABLED`, `GLOBAL_WEBHOOK_URL`, `WEBHOOK_URLS` (dict), `WEBHOOK_TIMEOUT` (30s), `WEBHOOK_RETRIES` (3)
- **Retries**: Uses `tenacity` decorator (stop_after_attempt=3, wait_exponential, retry_if_exception_type)
- **Timeout**: `WEBHOOK_TIMEOUT` (httpx.AsyncClient timeout)
- **Payload**: `dict` with `job_id`, `spider_name`, `status`, `reason`, `items_count`, `errors_count`, `project`, `items`, `errors`, `timestamp`
- **Event loop**: `asyncio.get_event_loop()` / `asyncio.new_event_loop()` + `run_until_complete()` (scrapyx_core/extensions/webhook.py:138-143)

### FastStream Completion Publisher
- **File**: `packages/scrapyx-core/src/scrapyx_core/extensions/completion_publisher.py:17-84`
- **Brokers**: RabbitMQ (`RabbitBroker`) or Redis (`RedisBroker`)
- **Settings**: `BROKER_TYPE`, `RABBITMQ_URL`, `REDIS_URL`
- **Queue**: `"spider.completion"` (hardcoded)
- **Payload**: `SpiderCompletionEvent` (Pydantic) → `model_dump()`
- **Event loop**: `asyncio.get_event_loop()` / `asyncio.new_event_loop()` + `run_until_complete()` (scrapyx_core/extensions/completion_publisher.py:69-76)

### Event Models
- **File**: `packages/scrapyx-core/src/scrapyx_core/models/events.py:3-12`
- **SpiderCompletionEvent**: `job_id`, `spider_name`, `status`, `reason`, `items_count`, `errors_count`, `project`
- **WebhookCallbackEvent**: `task_id`, `callback_url`, `status`, `data` (defines but not used in codebase)

### Signature/HMAC
**Not found** — No signing/HMAC in webhook payloads or event models.

## Data Flow

### Spider Completion Push Flow

```mermaid
sequenceDiagram
    participant Scrapy as Scrapy Engine
    participant BaseSpider as BaseServiceSpider
    participant Ext as Extension
    participant Broker as Broker/Webhook
    participant Sidecar as Sidecar (webhook mode only)

    Scrapy->>BaseSpider: spider_closed(reason)
    BaseSpider->>BaseSpider: Collect items/errors
    Scrapy->>Ext: spider_closed(reason)
    
    alt Webhook Mode
        Ext->>Ext: Build event_data (job_id, status, items/errors)
        Ext->>Broker: POST webhook (json=event_data)
        Broker-->>Ext: 200 OK
    else FastStream Mode
        Ext->>Ext: Build SpiderCompletionEvent
        Ext->>Broker: Publish to "spider.completion"
        Broker-->>Ext: Ack
    end
    
    Note over Scrapy,Broker: Event loop: asyncio.new_event_loop() + run_until_complete()
```

## How to Enable

### 1. Ops Only (Addon + Validator + Guardrails)

```python
# settings.py
ADDONS = {
    "scrapyx_mw.addon.ScrapyxAddon": 0,
}

SCRAPYX_SESSION_ENABLED = True
SCRAPYX_API_REQUEST_ENABLED = True
SCRAPYX_DEBUG_ENABLED = False
SCRAPYX_CAPTCHA_MODE = "none"
SCRAPYX_CAPTCHA_ENABLED = False

# Enable production extensions
SCRAPYX_TELEMETRY_ENABLED = False
SCRAPYX_GUARDRAILS_ENABLED = True
SCRAPYX_LOG_REDACTION_ENABLED = True
SCRAPYX_GUARDRAILS_RATE_LIMIT_PER_HOUR = 0
SCRAPYX_GUARDRAILS_RATE_LIMIT_PER_DAY = 1000
SCRAPYX_MAX_SPEND_PER_DAY = 100.0

# Service registry (required by BaseServiceSpider)
SERVICES = {
    "YOUR_SPIDER": {
        "CAPTCHA_REQUIRED": False,
    }
}
```

### 2. Captcha Polling

```python
# settings.py
ADDONS = {
    "scrapyx_mw.addon.ScrapyxAddon": 0,
}

SCRAPYX_CAPTCHA_MODE = "polling"
CAPTCHA_ENABLED = True
CAPTCHA_API_KEY = "your-2captcha-key"
CAPTCHA_PROVIDER = "2captcha"  # or "capsolver"

SERVICES = {
    "INSPECTION": {
        "CAPTCHA_REQUIRED": True,
        "SITE_KEY": "6Le-wvkSAAAAAKB...",
    }
}
```

### 3. Captcha Webhook

```python
# settings.py
ADDONS = {
    "scrapyx_mw.addon.ScrapyxAddon": 0,
}

SCRAPYX_CAPTCHA_MODE = "webhook"
CAPTCHA_ENABLED = True
CAPTCHA_API_KEY = "your-2captcha-key"
CAPTCHA_WEBHOOK_URL = "http://127.0.0.1:6801/webhook"

SERVICES = {
    "INSPECTION": {
        "CAPTCHA_REQUIRED": True,
        "SITE_KEY": "6Le-wvkSAAAAAKB...",
    }
}
```

# Run sidecar (terminal):
# python -m scrapyx_mw.scrapyd.webhook_service
```

### 4. Webhook Completion Push

```python
# settings.py
EXTENSIONS = {
    "scrapyx_core.extensions.webhook.WebhookExtension": 500,
}

WEBHOOK_ENABLED = True
WEBHOOK_URLS = {
    "inspection": "https://your-callback.com/webhook",
}
WEBHOOK_TIMEOUT = 30
WEBHOOK_RETRIES = 3

# BaseServiceSpider must be used to populate job_id/items/errors
```

### 5. FastStream Completion Push

```python
# settings.py
EXTENSIONS = {
    "scrapyx_core.extensions.completion_publisher.CompletionPublisherExtension": 500,
}

BROKER_TYPE = "rabbitmq"  # or "redis"
RABBITMQ_URL = "amqp://admin:admin@localhost:5672/"
# or REDIS_URL = "redis://localhost:6379/0"

# BaseServiceSpider must be used
```

### 6. Scrapyd Job Scheduling

**Not found** — No Scrapyd integration in codebase. Jobs scheduled via Scrapyd API require `_job` parameter to BaseServiceSpider (scrapyx_core/base.py:28). No sample `curl` command provided.

## DX & Ops

### Logging
- **Debug**: `spider.logger.debug(...)` used in DebugRequestMiddleware (scrapyx_mw/middlewares/debug.py:4-5)
- **Info**: All middlewares log on `spider_opened` (e.g., scrapyx_mw/middlewares/captcha_polling.py:63)
- **Error**: Captcha errors logged via `spider.logger.error(...)` (scrapyx_mw/middlewares/captcha_polling.py:145)

### Custom Stats Keys
- **Telemetry** (`scrapyx_mw/extensions/telemetry.py:64-69`): `captcha/attempts`, `captcha/successes`, `captcha/failures`, `captcha/success_rate_pct`, `captcha/avg_solve_time_sec`, `captcha/total_time_sec`
- **Guardrails** (`scrapyx_mw/extensions/guardrails.py:131-132`): `captcha/total_spend`, `captcha/remaining_budget`

### Memory Notes
- **Unbounded lists**: `BaseServiceSpider.items` and `BaseServiceSpider.errors` accumulate without limits (scrapyx_core/base.py:33-34)
- **In-flight tracking**: Captcha polling tracks `inflight` dict without bounds (scrapyx_mw/middlewares/captcha_polling.py:40)
- **Stats**: Guardrails uses `request_counts` defaultdict without bounds (scrapyx_mw/extensions/guardrails.py:45)

### Async/Twisted Notes
- **Event loop handling**: Both webhook and completion extensions use `asyncio.get_event_loop()` / `asyncio.new_event_loop()` + `run_until_complete()` in Twisted context
  - Location: `scrapyx_core/extensions/webhook.py:138-143`, `scrapyx_core/extensions/completion_publisher.py:69-76`
- **Twisted patterns**: Captcha middleware uses `defer.inlineCallbacks` and `reactor.callLater()` (scrapyx_mw/middlewares/captcha_polling.py:65-113)

## Gaps / TODOs

### Missing Tests/Docs
- **No tests for**: scrapyx_core extensions (webhook, completion_publisher), scrapyx_mw/middlewares (proxy_rotation, smart_retry), scrapyx_mw/extensions (guardrails, log_redactor, telemetry)
- **Partial tests**: scrapyx_mw/tests/test_captcha_integration.py has stubs but not runnable (missing imports)
- **Doc gaps**: No examples for WebhookExtension, CompletionPublisherExtension usage; no Scrapyd integration guide

### Precedence Unclear
- **Alias handling**: `CAPTCHA_ENABLED` vs `SCRAPYX_CAPTCHA_ENABLED` — both honored, no conflict resolution documented
- **Setting priority**: Middlewares use "addon" priority (scrapyx_mw/addon.py:89) but behavior on user overrides unclear

### Duplicate Keys
- **CAPTCHA_*** settings duplicated in `scrapyx_mw/addon.py:97-106` (both `setdefault()` calls) and imported by middlewares
- **SESSION_HEADERS** vs `service_config["HEADERS"]` — precedence: `service_config` wins (scrapyx_mw/middlewares/session.py:17)

### Unbounded Lists
- **BaseServiceSpider.items/errors**: No limits (scrapyx_core/base.py:33-34) — memory risk on large jobs
- **Guardrails `request_counts`**: No cleanup policy (scrapyx_mw/extensions/guardrails.py:45)
- **Captcha `inflight` cache**: No bounds (scrapyx_mw/middlewares/captcha_polling.py:40)

### Unhandled Exceptions
- **WebhookExtension**: Broad `except Exception` catches all (scrapyx_core/extensions/webhook.py:83-84)
- **CompletionPublisherExtension**: Broad `except Exception` (scrapyx_core/extensions/completion_publisher.py:82-83)
- **Log redactor regex**: Catches `re.error` but logs only (scrapyx_mw/extensions/log_redactor.py:50-51)

### Security
- **No signature/HMAC**: Webhook payloads not signed (scrapyx_core/extensions/webhook.py:111-121)
- **API keys in logs**: Log redaction exists but must be explicitly enabled (scrapyx_mw/extensions/log_redactor.py:25-54)

### Recommended Fixes
- **Add bounds to BaseServiceSpider.items/errors** (scrapyx_core/base.py:33-34): Implement `max_items`, `max_errors` settings
- **Document CAPTCHA_ENABLED vs SCRAPYX_CAPTCHA_ENABLED** priority (scrapyx_mw/addon.py:58)
- **Add cleanup policy to Guardrails `request_counts`** (scrapyx_mw/extensions/guardrails.py:91-120)
- **Add integration tests for webhook/completion extensions**
- **Document Scrapyd job_id handling** — clarify how `_job` flows from Scrapyd to spider
- **Add HMAC signing to webhook payloads** (scrapyx_core/extensions/webhook.py:128)
- **Make log redaction opt-out vs opt-in** (scrapyx_mw/extensions/log_redactor.py:25)

