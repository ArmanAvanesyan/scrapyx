class ConfigError(RuntimeError):
    """Raised when service configuration is invalid."""


class MissingServiceError(KeyError):
    """Raised when a spider has no matching SERVICE entry."""

