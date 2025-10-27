# scrapyx-core

Shared **base spider** and **typed service configuration** utilities for Scrapy projects.

## What you get

- `BaseServiceSpider` — production-ready base class that:
  - exposes `service_config`, `captcha_needed`, `site_key`
  - collects `items`/`errors`, has `yield_empty_item()`
  - initializes from a **typed** Service registry (from settings / optional file)

- `ServiceConfig` / `ServiceRegistry` — Pydantic models for strict config.
- `load_registry_from_settings()` — merges `settings["SERVICES"]` with optional JSON file pointed by `SCRAPYX_SERVICES_FILE`.
- `validators` — functions you can call (or wire from an extension) to **fail fast** in CI/Scrapyd.

## Minimal usage

```python
# in your spiders
from scrapyx_core.base import BaseServiceSpider

class InspectionSpider(BaseServiceSpider):
    name = "inspection"
    # use self.service_config / self.captcha_needed / self.site_key
```

Optionally, set `SCRAPYX_SERVICES_FILE=/path/to/services.json` to load/merge external config.

This package is **middleware-agnostic** and pairs well with `scrapyx-mw` (add-on + middlewares).

