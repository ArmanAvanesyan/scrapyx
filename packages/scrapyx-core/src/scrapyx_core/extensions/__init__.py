"""Scrapyx extension modules.

Extension classes are imported lazily so that optional extras (webhook, completion)
are only required when the corresponding extension is used.
"""

__all__: list[str] = []

try:
    from .webhook import WebhookExtension
    __all__.append("WebhookExtension")
except ImportError:
    WebhookExtension = None  # type: ignore[misc, assignment]

try:
    from .completion_publisher import CompletionPublisherExtension
    __all__.append("CompletionPublisherExtension")
except ImportError:
    CompletionPublisherExtension = None  # type: ignore[misc, assignment]
