from __future__ import annotations

import json
import os
from typing import Any, Dict

from .config import ServiceRegistry, ServiceConfig


def _coerce_raw_services(raw: Dict[str, Any]) -> Dict[str, ServiceConfig]:
    result: Dict[str, ServiceConfig] = {}
    for k, v in (raw or {}).items():
        # Accept plain dicts or already-shaped dicts
        result[k] = ServiceConfig(**v) if isinstance(v, dict) else ServiceConfig()
    return result


def load_registry_from_settings(settings: Any) -> ServiceRegistry:
    """
    Build a ServiceRegistry from Scrapy settings, with optional JSON override/merge.

    Order of precedence (last wins):
    1) JSON file pointed by env `SCRAPYX_SERVICES_FILE` (optional)
    2) settings["SERVICES"]
    """
    settings_services = settings.get("SERVICES", {}) or {}

    file_path = os.getenv("SCRAPYX_SERVICES_FILE")
    file_services: Dict[str, Any] = {}
    if file_path and os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            file_raw = json.load(f)
        # allow both {"INSPECTION": {...}} and {"services": {...}}
        file_services = file_raw.get("services", file_raw)

    merged: Dict[str, Any] = dict(file_services)
    merged.update(settings_services)  # settings override file

    return ServiceRegistry(services=_coerce_raw_services(merged))

