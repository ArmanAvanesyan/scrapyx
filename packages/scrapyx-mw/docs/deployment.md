# Scrapyx-MW Deployment Guide

## Overview

This guide covers deploying projects that use the `scrapyx-mw` package for enhanced Scrapy middleware functionality. The `scrapyx-mw` package provides production-ready middleware for session management, API requests, debugging, captcha solving, and more.

## 🚀 Quick Setup

### 1. Install scrapyx-mw

```bash
# Add to your project's pyproject.toml
[tool.poetry.dependencies]
scrapyx-mw = { path = "../../libs/scrapyx-mw", develop = true }

# Or with uv
uv add "scrapyx-mw @ file://path/to/libs/scrapyx-mw"
```

### 2. Enable the Add-on

```python
# In your Scrapy settings.py
ADDONS = {
    "scrapyx_mw.addon.ScrapyxAddon": 0,
}

# Configure middleware flags
SCRAPYX_SESSION_ENABLED = True
SCRAPYX_API_REQUEST_ENABLED = True
SCRAPYX_DEBUG_ENABLED = os.getenv("SCRAPY_ENV", "development") == "development"
```

### 3. Configure Captcha (Optional)

```python
# For 2captcha
CAPTCHA_ENABLED = True
CAPTCHA_PROVIDER = "2captcha"
CAPTCHA_API_KEY = os.getenv("CAPTCHA_API_KEY", "")

# For CapSolver
CAPTCHA_ENABLED = True
CAPTCHA_PROVIDER = "capsolver"
CAPTCHA_API_KEY = os.getenv("CAPTCHA_API_KEY", "")
CAPTCHA_CAPSOLVER_BASE = os.getenv("CAPTCHA_CAPSOLVER_BASE", "https://api.capsolver.com")
CAPTCHA_CAPSOLVER_TASK_TYPE = os.getenv("CAPTCHA_CAPSOLVER_TASK_TYPE", "ReCaptchaV2TaskProxyLess")
```

## 🏗️ Production Configuration

### Environment Variables

```bash
# Required for captcha solving
CAPTCHA_API_KEY=your-api-key-here

# Optional: CapSolver specific
CAPTCHA_CAPSOLVER_BASE=https://api.capsolver.com
CAPTCHA_CAPSOLVER_TASK_TYPE=ReCaptchaV2TaskProxyLess

# Optional: Production hardening
SCRAPYX_TELEMETRY_ENABLED=true
SCRAPYX_GUARDRAILS_ENABLED=true
SCRAPYX_LOG_REDACTION_ENABLED=true

# Optional: Guardrails configuration
SCRAPYX_GUARDRAILS_RATE_LIMIT=10
SCRAPYX_GUARDRAILS_BUDGET_LIMIT=100.0
SCRAPYX_GUARDRAILS_CIRCUIT_BREAKER_THRESHOLD=5
```

### Docker Configuration

```dockerfile
# Dockerfile for Scrapy project with scrapyx-mw
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml ./
COPY libs/scrapyx-mw ./libs/scrapyx-mw/

# Install dependencies
RUN pip install uv && uv sync

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 scrapyuser && chown -R scrapyuser:scrapyuser /app
USER scrapyuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:6800/ || exit 1

# Start Scrapyd
CMD ["uv", "run", "scrapyd"]
```

### Docker Compose Integration

```yaml
# docker-compose.yml
version: '3.8'

services:
  scrapyd:
    build:
      context: ./services/scrapyd
      dockerfile: Dockerfile
    container_name: vehicle-compliance-scrapyd
    ports:
      - "6800:6800"  # Scrapyd web interface
      - "6801:6801"  # Webhook callback port
    networks:
      - carrio_test_net
    volumes:
      - scrapyd_logs:/var/log/scrapyd
      - scrapyd_data:/var/lib/scrapyd
    environment:
      - SCRAPY_ENV=${SCRAPY_ENV:-production}
      - CAPTCHA_API_KEY=${CAPTCHA_API_KEY}
      - CAPTCHA_CAPSOLVER_BASE=${CAPTCHA_CAPSOLVER_BASE:-https://api.capsolver.com}
      - SCRAPYX_TELEMETRY_ENABLED=${SCRAPYX_TELEMETRY_ENABLED:-true}
      - SCRAPYX_GUARDRAILS_ENABLED=${SCRAPYX_GUARDRAILS_ENABLED:-true}
      - SCRAPYX_LOG_REDACTION_ENABLED=${SCRAPYX_LOG_REDACTION_ENABLED:-true}
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6800/"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

volumes:
  scrapyd_logs:
    driver: local
  scrapyd_data:
    driver: local

networks:
  carrio_test_net:
    external: true
```

## 🔧 Scrapyd Deployment

### 1. Deploy Project to Scrapyd

```bash
# From your Scrapy project directory
cd services/scrapyd/projects/compliance_scraper

# Deploy to local Scrapyd
scrapyd-deploy local

# Deploy to remote Scrapyd
scrapyd-deploy production
```

### 2. Verify Deployment

```bash
# Check deployed projects
curl http://localhost:6800/listprojects.json

# Check project spiders
curl http://localhost:6800/listspiders.json?project=compliance_scraper

# Check project settings
curl http://localhost:6800/settings.json?project=compliance_scraper
```

### 3. Run Spiders

```bash
# Schedule a spider job
curl http://localhost:6800/schedule.json \
  -d project=compliance_scraper \
  -d spider=inspection \
  -d arg_plate_number=34AB123 \
  -d arg_cert_number=AB123456

# Check job status
curl http://localhost:6800/jobs.json?project=compliance_scraper
```

## 🛡️ Production Hardening

### Telemetry Extension

The telemetry extension tracks captcha solving metrics:

```python
# Automatically enabled with SCRAPYX_TELEMETRY_ENABLED=true
SCRAPYX_TELEMETRY_ENABLED = True

# Optional: Custom telemetry settings
SCRAPYX_TELEMETRY_METRICS_ENABLED = True
SCRAPYX_TELEMETRY_COST_TRACKING = True
```

### Guardrails Extension

Rate limiting and budget controls:

```python
# Automatically enabled with SCRAPYX_GUARDRAILS_ENABLED=true
SCRAPYX_GUARDRAILS_ENABLED = True

# Optional: Custom guardrails settings
SCRAPYX_GUARDRAILS_RATE_LIMIT = 10  # requests per minute
SCRAPYX_GUARDRAILS_BUDGET_LIMIT = 100.0  # USD per day
SCRAPYX_GUARDRAILS_CIRCUIT_BREAKER_THRESHOLD = 5  # failures before circuit opens
```

### Log Redaction Extension

Automatically redacts sensitive information:

```python
# Automatically enabled with SCRAPYX_LOG_REDACTION_ENABLED=true
SCRAPYX_LOG_REDACTION_ENABLED = True

# Optional: Custom redaction patterns
SCRAPYX_LOG_REDACTION_PATTERNS = [
    r"api[_-]?key['\"]?\s*[:=]\s*['\"]?([a-zA-Z0-9_-]+)",
    r"token['\"]?\s*[:=]\s*['\"]?([a-zA-Z0-9_.-]+)",
]
```

## 🔄 Webhook Configuration

### 1. Start Webhook Service

```bash
# Start webhook service for 2captcha callbacks
uv run python -m compliance_scraper.scrapyd.webhook_service
```

### 2. Configure Webhook URL

```python
# In your spider settings
CAPTCHA_WEBHOOK_URL = "http://your-scrapyd-host:6801/webhook"
CAPTCHA_WEBHOOK_ENABLED = True
```

### 3. Verify Webhook Health

```bash
# Check webhook service health
curl http://localhost:6801/health

# Test webhook endpoint
curl -X POST http://localhost:6801/webhook \
  -H "Content-Type: application/json" \
  -d '{"taskId": "test", "solution": "test-solution"}'
```

## 🧪 Testing & Validation

### 1. Test Middleware Integration

```bash
# Verify addon is loaded
uv run scrapy settings --get ADDONS

# Check enabled extensions
uv run scrapy settings --get EXTENSIONS

# List spiders
uv run scrapy list
```

### 2. Test Captcha Solving

```bash
# Run a spider with captcha requirements
uv run scrapy crawl inspection \
  -a arg_plate_number=34AB123 \
  -a arg_cert_number=AB123456 \
  -L INFO
```

### 3. Test Production Features

```bash
# Test with production hardening enabled
SCRAPYX_TELEMETRY_ENABLED=true \
SCRAPYX_GUARDRAILS_ENABLED=true \
SCRAPYX_LOG_REDACTION_ENABLED=true \
uv run scrapy crawl inspection \
  -a arg_plate_number=34AB123 \
  -a arg_cert_number=AB123456
```

## 🚨 Troubleshooting

### Common Issues

#### 1. Addon Not Loading

```bash
# Check if scrapyx-mw is installed
uv run python -c "import scrapyx_mw; print('scrapyx-mw installed')"

# Verify addon configuration
uv run scrapy settings --get ADDONS
```

#### 2. Captcha Solving Fails

```bash
# Check API key configuration
echo $CAPTCHA_API_KEY

# Verify provider settings
uv run scrapy settings --get CAPTCHA_PROVIDER
uv run scrapy settings --get CAPTCHA_ENABLED
```

#### 3. Middleware Not Applied

```bash
# Check middleware configuration
uv run scrapy settings --get DOWNLOADER_MIDDLEWARES
uv run scrapy settings --get SPIDER_MIDDLEWARES

# Verify addon flags
uv run scrapy settings --get SCRAPYX_SESSION_ENABLED
```

### Debug Commands

```bash
# Enable debug logging
uv run scrapy crawl inspection \
  -a arg_plate_number=34AB123 \
  -a arg_cert_number=AB123456 \
  -L DEBUG

# Check specific settings
uv run scrapy settings --get SCRAPYX_DEBUG_ENABLED
uv run scrapy settings --get SCRAPYX_TELEMETRY_ENABLED
```

## 📊 Monitoring

### Health Checks

```bash
# Scrapyd health
curl http://localhost:6800/

# Webhook service health
curl http://localhost:6801/health

# Spider job status
curl http://localhost:6800/jobs.json?project=compliance_scraper
```

### Metrics Collection

The telemetry extension provides metrics for:
- Captcha solve attempts and success rate
- Average solve time
- Cost tracking
- Error rates

Access metrics via Scrapyd's built-in monitoring or integrate with external monitoring systems.

## 🔄 Updates & Maintenance

### Updating scrapyx-mw

```bash
# Update the package
cd libs/scrapyx-mw
git pull origin main

# Rebuild and redeploy
uv sync
scrapyd-deploy local
```

### Configuration Changes

1. Update environment variables
2. Restart Scrapyd service
3. Redeploy project if needed
4. Verify configuration with test runs

---

**Last Updated**: January 2025  
**Version**: 1.0  
**Maintainer**: Development Team
