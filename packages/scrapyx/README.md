# scrapyx-pkgs (ScrapyX Package Suite)

This is the **main package** that provides the full ScrapyX ecosystem:

- **`scrapyx-core`** - Shared Scrapy base spider + typed service configuration registry
- **`scrapyx-mw`** - Composable Scrapy middlewares (API/session, debug, captcha, proxy rotation, etc.)

## Installation

```bash
# Install everything (recommended)
pip install scrapyx-pkgs

# Or install specific components
pip install scrapyx-pkgs[core]  # Just scrapyx-core
pip install scrapyx-pkgs[mw]     # Just scrapyx-mw
pip install scrapyx-pkgs[minimal]  # Just the namespace
```

## Why a Separate Namespace Package?

This pattern allows:
1. Independent versioning of each sub-package
2. Installing only the packages you need
3. Adding future packages under `scrapyx.*` namespace without conflicts
4. Clear separation between the umbrella (this) and actual functionality

## Structure

```
packages/scrapyx/
├── pyproject.toml          # Minimal config for namespace
├── README.md               # This file
└── src/
    └── scrapyx/
        └── __init__.py     # Empty namespace + __version__
```

