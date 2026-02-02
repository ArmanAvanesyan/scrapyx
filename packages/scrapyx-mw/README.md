# scrapyx-mw

Composable Scrapy middlewares packaged for reuse across projects:
- API / Session headers injection
- Debug logging
- Captcha (polling via 2captcha or CapSolver) **or** Captcha (webhook + sidecar SQLite store)
- Proxy rotation with health checking
- Smart retry with exponential backoff

This package is **compatible** with projects that store per-spider config under
`SERVICES[SPIDER_NAME_UPPER]` (e.g., `CAPTCHA_REQUIRED`, `SITE_KEY`, `HEADERS`),
as used in your `compliance_scraper` project.

## 📚 Documentation

- **[Full Documentation](docs/index.md)** - Complete documentation index
- **[Deployment Guide](docs/deployment.md)** - Production deployment instructions
- **[Migration Guide](docs/migration.md)** - Migrate existing projects

## Install (with uv)

From a project that consumes this plugin:

```bash
uv add -e ./libs/scrapyx-mw
# or publish and: uv add scrapyx-mw
```

Only **Scrapy** and **Twisted** are required; the resolver will reuse already-installed versions. For browser impersonation (curl_cffi), use: `uv add scrapyx-mw[curl-cffi]`.

## 🚀 Features

### Core Middlewares
- **Session Management**: Automatic session handling with configurable headers
- **API Request**: Inject API-specific headers from spider configuration
- **Debug Logging**: Comprehensive request/response logging for development

### Captcha Solving
- **Multi-Provider Support**: 2captcha and CapSolver providers
- **Polling Mode**: Traditional polling-based captcha solving
- **Webhook Mode**: Webhook-based captcha solving with fallback to polling
- **Configurable Timeouts**: Customizable polling intervals and timeouts

### Production Hardening
- **Telemetry**: Track captcha solve attempts, success rates, and costs
- **Guardrails**: Rate limiting, budget controls, and circuit breaker
- **Log Redaction**: Automatically redact sensitive information from logs
- **Configuration Validation**: Fail-fast validation of captcha settings

### Advanced Features
- **Proxy Rotation**: Intelligent proxy rotation with health checking
- **Smart Retry**: Exponential backoff with jitter and circuit breaker
- **Scrapy Add-on**: One-switch enablement of all features

## Enable in your Scrapy project

In your project `settings.py`:

```python
from scrapyx_mw import default_config, apply_downloader_middlewares, apply_spider_middlewares

# Toggle features here
SCRAPYX = default_config(
    api_request=True,
    session=True,
    debug=False,
    captcha="none",         # "none" | "polling" | "webhook"
    captcha_enabled=False,  # also controlled by env var CAPTCHA_ENABLED
    captcha_api_key="",     # required if captcha_enabled
    captcha_webhook_url="http://127.0.0.1:6801/webhook",
    session_headers={"Accept": "application/json"},
)

DOWNLOADER_MIDDLEWARES.update(apply_downloader_middlewares(globals(), SCRAPYX))
SPIDER_MIDDLEWARES.update(apply_spider_middlewares(globals(), SCRAPYX))

# Per-spider service configs, same shape as in your compliance_scraper:
SERVICES = {
    "EXAMPLE_SERVICE": {
        "CAPTCHA_REQUIRED": True,
        "SITE_KEY": "6Lxxxxxx...your-site-key...",
        "HEADERS": {"Accept": "text/html,application/xhtml+xml"}
    }
}
```

> **Note:** Your spiders can keep using `spider.service_config`, `spider.captcha_needed`, and `spider.site_key`
> (as in your `BaseComplianceSpider`); this plugin is designed to read those fields.

## Captcha options

* **Polling** (`captcha="polling"`): middleware submits & polls 2captcha or CapSolver.
* **Webhook** (`captcha="webhook"`): middleware submits with a `callbackUrl` and waits for the **sidecar**
  webhook receiver to store codes in SQLite for pickup.

### Supported Providers

- **2captcha**: Traditional polling-based captcha solving
- **CapSolver**: Modern API-based captcha solving with JSON endpoints

### Provider Configuration

```python
# For 2captcha
CAPTCHA_PROVIDER = "2captcha"
CAPTCHA_API_KEY = "your-2captcha-key"
CAPTCHA_2CAPTCHA_BASE = "https://2captcha.com"  # optional
CAPTCHA_2CAPTCHA_METHOD = "userrecaptcha"       # optional

# For CapSolver
CAPTCHA_PROVIDER = "capsolver"
CAPTCHA_API_KEY = "your-capsolver-key"
CAPTCHA_CAPSOLVER_BASE = "https://api.capsolver.com"           # optional
CAPTCHA_CAPSOLVER_TASK_TYPE = "ReCaptchaV2TaskProxyLess"       # optional
```

### Webhook sidecar

Run the included receiver next to Scrapyd (bind to `127.0.0.1` by default):

```bash
uv run python -m scrapyx_mw.scrapyd.webhook_service
# Health: GET http://127.0.0.1:6801/health
# Webhook: POST from 2captcha to /webhook (id, code)
```

> DB file path: `/var/lib/scrapyd/webhook_solutions.db` (same as your original project for drop-in compatibility).
> 
> **Note**: CapSolver webhook support is limited - it falls back to polling behavior in webhook mode.

## Environment variables

```dotenv
CAPTCHA_ENABLED=false
CAPTCHA_API_KEY=
CAPTCHA_PROVIDER=2captcha
CAPTCHA_WEBHOOK_URL=http://127.0.0.1:6801/webhook
CAPTCHA_TOKEN_TTL_SECONDS=110
CAPTCHA_POLL_INITIAL_S=4.0
CAPTCHA_POLL_MAX_S=45.0
CAPTCHA_POLL_MAX_TIME_S=180.0
CAPTCHA_HTTP_TIMEOUT_S=15.0
CAPTCHA_HTTP_RETRIES=2

# 2captcha specific
CAPTCHA_2CAPTCHA_BASE=https://2captcha.com
CAPTCHA_2CAPTCHA_METHOD=userrecaptcha

# CapSolver specific
CAPTCHA_CAPSOLVER_BASE=https://api.capsolver.com
CAPTCHA_CAPSOLVER_TASK_TYPE=ReCaptchaV2TaskProxyLess
```

## Enable via Scrapy **Add-on** (recommended)

Instead of editing middleware dicts manually, turn on the package with **one line**:

```python
# settings.py
ADDONS = {
  "scrapyx_mw.addon.ScrapyxAddon": 0,
}
```

Then tweak behavior using flags:

| Setting                       | Type  |                         Default | Notes                                                                         |
| ----------------------------- | ----- | ------------------------------: | ----------------------------------------------------------------------------- |
| `SCRAPYX_SESSION_ENABLED`     | bool  |                          `True` | Enable default session headers middleware                                     |
| `SCRAPYX_API_REQUEST_ENABLED` | bool  |                          `True` | Enable API header injector middleware                                         |
| `SCRAPYX_DEBUG_ENABLED`       | bool  |                         `False` | Log outgoing requests at DEBUG                                                |
| `SCRAPYX_CAPTCHA_MODE`        | str   |                        `"none"` | `"none" \| "polling" \| "webhook"`                                            |
| `SCRAPYX_CAPTCHA_ENABLED`     | bool  |                         `False` | Master switch; `CAPTCHA_ENABLED` is also honored                              |
| `CAPTCHA_API_KEY`             | str   |                            `""` | Required if captcha is enabled                                                |
| `CAPTCHA_WEBHOOK_URL`         | str   | `http://127.0.0.1:6801/webhook` | Webhook receiver URL                                                          |
| `CAPTCHA_*` knobs             | mixed |                    see defaults | TTL, polling delays, HTTP timeouts/retries                                    |
| `SESSION_HEADERS`             | dict  |                            `{}` | Global default headers (overridden by per-spider `service_config["HEADERS"]`) |
| `SCRAPYX_CURL_CFFI_ENABLED`   | bool  |                         `False` | Enable CurlCffi **download handler** (opt-in: per request or global)        |
| `SCRAPYX_CURL_CFFI_MIDDLEWARE_ENABLED` | bool | `False` | Enable CurlCffi **middleware** (opt-out: all requests use curl_cffi unless disabled in meta) |

The Add-on composes `DOWNLOADER_MIDDLEWARES` / `SPIDER_MIDDLEWARES` / `DOWNLOAD_HANDLERS` with **"addon"** priority and avoids overwriting user-set values.

### CurlCffi (browser impersonation)

Optional support for [curl_cffi](https://github.com/yifeikong/curl_cffi) for browser impersonation on anti-bot sites. Install the extra when using the handler or middleware: `uv pip install scrapyx-mw[curl-cffi]` or `uv pip install curl-cffi`.

- **Handler** (`SCRAPYX_CURL_CFFI_ENABLED=True`): opt-in per request via `request.meta['use_curl_cffi'] = True` or globally; keeps the full download pipeline.
- **Middleware** (`SCRAPYX_CURL_CFFI_MIDDLEWARE_ENABLED=True`): opt-out—all requests use curl_cffi unless `request.meta['use_curl_cffi'] = False`. Choose one approach per project (handler or middleware).

### Compatibility notes

* Reads per-spider config from `SERVICES[SPIDER_NAME_UPPER]` (same as your `compliance_scraper`).
* Honors `spider.captcha_needed`, `spider.site_key`, and injects `request.meta["recaptcha_solution"]`.
* Webhook DB path remains `/var/lib/scrapyd/webhook_solutions.db` for drop-in compatibility.

> Prefer Add-on mode for fleet-wide consistency. The original `presets.py` helpers still work if you want to compose stacks manually.

---

## Notes on compatibility

* Reads `SERVICES[SPIDER_NAME_UPPER]` for `CAPTCHA_REQUIRED`, `SITE_KEY`, `HEADERS`.
* Honors `spider.captcha_needed` and `spider.site_key`, and sets `request.meta["recaptcha_solution"]`.
* Webhook SQLite schema and path matches the original (`/var/lib/scrapyd/webhook_solutions.db`).
* Session/API middlewares merge with `service_config["HEADERS"]` (exactly like your project).

---

### How to use the new Add-on

In your Scrapy project (that consumes `libs/scrapyx-mw`):

```python
# settings.py
ADDONS = {
    "scrapyx_mw.addon.ScrapyxAddon": 0,
}

# Optional toggles
SCRAPYX_SESSION_ENABLED = True
SCRAPYX_API_REQUEST_ENABLED = True
SCRAPYX_DEBUG_ENABLED = False

# Captcha
SCRAPYX_CAPTCHA_MODE = "polling"   # or "webhook" or "none"
SCRAPYX_CAPTCHA_ENABLED = True     # or set CAPTCHA_ENABLED=True
CAPTCHA_API_KEY = "your-2captcha-key"
# CAPTCHA_WEBHOOK_URL = "http://127.0.0.1:6801/webhook"

# (keep your existing SERVICES mapping)
SERVICES = {
    "EXAMPLE_SERVICE": {
        "CAPTCHA_REQUIRED": True,
        "SITE_KEY": "6Lxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "HEADERS": {"Accept": "text/html,application/xhtml+xml"}
    }
}
```

If you choose **webhook** mode, run the sidecar on the Scrapyd host:

```bash
uv run python -m scrapyx_mw.scrapyd.webhook_service
# Health: curl http://127.0.0.1:6801/health
```

---

## ConfigValidator Extension

This extension validates CAPTCHA-related configuration on startup and aborts misconfigured crawls early.

Enabled automatically by the Add-on. To use independently:

```python
EXTENSIONS = {
    "scrapyx_mw.extensions.config_validator.ConfigValidator": 10,
}
```

### Checks performed

* If `CAPTCHA_ENABLED=True` but `CAPTCHA_API_KEY` is missing → fail.
* For each spider where `SERVICES[SPIDER_NAME_UPPER]["CAPTCHA_REQUIRED"]=True`:
  * Ensure `SITE_KEY` is set.

Useful in CI and Scrapyd to prevent broken deployments.

## 🔄 Proxy Rotation Middleware

The proxy rotation middleware provides intelligent proxy management:

### Configuration

```python
# Enable proxy rotation
SCRAPYX_PROXY_ROTATION_ENABLED = True

# Proxy sources
SCRAPYX_PROXY_LIST = [
    "http://proxy1:8080",
    "http://proxy2:8080",
    "socks5://proxy3:1080"
]

# Or from environment variable
SCRAPYX_PROXY_ENV_VAR = "SCRAPYX_PROXY_LIST"  # Default
# export SCRAPYX_PROXY_LIST="http://proxy1:8080,http://proxy2:8080"

# Or from file
SCRAPYX_PROXY_FILE = "proxies.txt"

# Rotation strategy
SCRAPYX_PROXY_ROTATION_STRATEGY = "round_robin"  # "round_robin" | "random" | "weighted"

# Health checking
SCRAPYX_PROXY_HEALTH_CHECK = True
SCRAPYX_PROXY_HEALTH_CHECK_INTERVAL = 300  # seconds
SCRAPYX_PROXY_MAX_FAILURES = 3

# Session persistence
SCRAPYX_PROXY_SESSION_PERSISTENCE = True
```

### Features

- **Multiple Sources**: Load proxies from settings, environment variables, or files
- **Health Checking**: Automatically remove failed proxies
- **Load Balancing**: Round-robin, random, or weighted selection
- **Session Persistence**: Use same proxy for requests with same session_id
- **Performance Tracking**: Monitor proxy success rates and response times

## 🔁 Smart Retry Middleware

The smart retry middleware provides intelligent retry logic with exponential backoff:

### Configuration

```python
# Enable smart retry
SCRAPYX_SMART_RETRY_ENABLED = True

# Retry configuration
SCRAPYX_RETRY_MAX_TIMES = 3
SCRAPYX_RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

# Backoff configuration
SCRAPYX_RETRY_BASE_BACKOFF = 1.0  # seconds
SCRAPYX_RETRY_MAX_BACKOFF = 60.0  # seconds
SCRAPYX_RETRY_BACKOFF_MULTIPLIER = 2.0
SCRAPYX_RETRY_JITTER_ENABLED = True
SCRAPYX_RETRY_JITTER_RANGE = 0.1

# Circuit breaker
SCRAPYX_RETRY_CIRCUIT_BREAKER_ENABLED = True
SCRAPYX_RETRY_CIRCUIT_BREAKER_THRESHOLD = 5  # failures before circuit opens
SCRAPYX_RETRY_CIRCUIT_BREAKER_TIMEOUT = 60  # seconds before circuit resets

# Priority handling
SCRAPYX_RETRY_PRIORITY_ENABLED = True
SCRAPYX_RETRY_PRIORITY_MULTIPLIER = 1.5  # reduce delay for high-priority requests
```

### Features

- **Exponential Backoff**: Increasing delays between retries
- **Jitter**: Random variation to prevent thundering herd
- **Circuit Breaker**: Stop retrying failed domains temporarily
- **Priority Support**: Faster retries for high-priority requests
- **Statistics**: Track retry success rates and delays per domain
