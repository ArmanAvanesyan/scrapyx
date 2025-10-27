# Scrapyx-MW Documentation

This directory contains documentation for the scrapyx-mw package.

## 📚 Documentation Files

- **[Index](index.md)** - Complete documentation index
- **[Deployment Guide](deployment.md)** - Production deployment instructions  
- **[Migration Guide](migration.md)** - Migrate existing projects to scrapyx-mw

## 🚀 Quick Start

For the main package README with installation and usage, see: [README.md](../README.md)

## 📖 Key Documentation

### Getting Started
1. Read the [main README](../README.md) for installation and quick start
2. Check [deployment.md](deployment.md) for production setup
3. See [migration.md](migration.md) if migrating an existing project

### Middlewares
The scrapyx-mw package provides:
- **Session Management** - Automatic session handling with configurable headers
- **API Request** - Inject API-specific headers from spider configuration
- **Debug Logging** - Comprehensive request/response logging
- **Captcha Solving** - Multi-provider captcha (2captcha, CapSolver) with polling and webhook modes
- **Proxy Rotation** - Intelligent proxy management with health checking
- **Smart Retry** - Exponential backoff with jitter and circuit breaker

### Extensions
- **Telemetry** - Track captcha solve attempts and costs
- **Guardrails** - Rate limiting, budget controls, and circuit breaker
- **Log Redaction** - Automatically redact sensitive information
- **Config Validator** - Fail-fast validation of captcha settings

## 🔗 External Links

- Main package: [README.md](../README.md)
- Root project documentation: [../../docs/](../../docs/)
