# ScrapyX - Composable Scrapy Framework

A comprehensive suite of packages for building robust Scrapy scrapers with production-ready middlewares, configuration management, and extensibility.

## 📦 Packages

This repository contains three packages:

- **`scrapyx-pkgs`** - Main package that installs everything (scrapyx-core + scrapyx-mw)
- **`scrapyx-core`** - Shared Scrapy base spider + typed service configuration registry
- **`scrapyx-mw`** - Composable Scrapy middlewares (API/session, debug, captcha, proxy rotation, smart retry, etc.)

## 🚀 Quick Start

### Install Everything (Recommended)

```bash
pip install scrapyx-pkgs
```

### Install Specific Components

```bash
# Just core functionality
pip install scrapyx-pkgs[core]

# Just middleware
pip install scrapyx-pkgs[mw]

# Minimal namespace only
pip install scrapyx-pkgs[minimal]
```

### Or Install Individual Packages

```bash
pip install scrapyx-core scrapyx-mw
```

## 📚 Documentation

See individual package READMEs:
- [`packages/scrapyx/README.md`](packages/scrapyx/README.md)
- [`packages/scrapyx-core/README.md`](packages/scrapyx-core/README.md)
- [`packages/scrapyx-mw/README.md`](packages/scrapyx-mw/README.md)

## 🏗️ Development

This is a monorepo managed with `uv`.

### Setup

```bash
# Install uv if not already installed
pip install uv

# Sync dependencies
cd packages/scrapyx-core && uv sync
cd ../scrapyx-mw && uv sync
```

### Building Packages

```bash
# Build individual package
cd packages/scrapyx-pkgs && uv run python -m build
cd packages/scrapyx-core && uv run python -m build
cd packages/scrapyx-mw && uv run python -m build
```

## 📝 License

[Your License Here]

