"""Structured JSON logging with the redacting filter; content never reaches a line."""

from catalyst_ai.platform.logging.setup import CONTENT_KEYS, RedactingFilter, configure_logging

__all__ = ["CONTENT_KEYS", "RedactingFilter", "configure_logging"]
