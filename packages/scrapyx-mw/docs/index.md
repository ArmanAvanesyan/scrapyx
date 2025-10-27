# Scrapyx-MW Documentation

Welcome to the scrapyx-mw documentation! This package provides production-ready Scrapy middlewares for common use cases.

## 📚 Documentation Index

### Getting Started
- [Installation](installation.md) - How to install and set up scrapyx-mw
- [Quick Start](quick-start.md) - Get up and running quickly
- [Configuration](configuration.md) - Complete configuration guide

### Middlewares
- [Session Middleware](middlewares/session.md) - Session management and headers
- [API Request Middleware](middlewares/api-request.md) - API-specific headers
- [Debug Middleware](middlewares/debug.md) - Request/response logging
- [Captcha Middlewares](middlewares/captcha.md) - Captcha solving (polling and webhook)
- [Proxy Rotation Middleware](middlewares/proxy-rotation.md) - Intelligent proxy management
- [Smart Retry Middleware](middlewares/smart-retry.md) - Exponential backoff retry logic

### Extensions
- [Telemetry Extension](extensions/telemetry.md) - Captcha metrics tracking
- [Guardrails Extension](extensions/guardrails.md) - Rate limiting and budget controls
- [Log Redaction Extension](extensions/log-redaction.md) - Sensitive data redaction
- [Config Validator Extension](extensions/config-validator.md) - Configuration validation

### Providers
- [Captcha Providers](providers.md) - 2captcha and CapSolver integration

### Deployment
- [Production Deployment](deployment.md) - Deploy scrapyx-mw in production
- [Migration Guide](migration.md) - Migrate existing projects

### Advanced
- [Scrapy Add-on](addon.md) - Using the scrapyx-mw addon system
- [Presets](presets.md) - Programmatic middleware composition
- [Testing](testing.md) - Testing with scrapyx-mw

## 🚀 Quick Links

- **Main README**: [README.md](../README.md) - Package overview and quick reference
- **Deployment**: [deployment.md](deployment.md) - Production deployment guide
- **Migration**: [migration.md](migration.md) - Migration guide for existing projects

## 📖 Features

scrapyx-mw provides:
- ✅ Session management with configurable headers
- ✅ API request handling with per-spider configuration
- ✅ Debug logging for development
- ✅ Multi-provider captcha solving (2captcha, CapSolver)
- ✅ Proxy rotation with health checking
- ✅ Smart retry with exponential backoff
- ✅ Production hardening (telemetry, guardrails, log redaction)
- ✅ Easy integration via Scrapy Add-on
