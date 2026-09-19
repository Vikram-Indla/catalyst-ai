"""One JSON formatter, one redacting filter, one configure call."""

import json
import logging
from datetime import UTC, datetime

CONTENT_KEYS = frozenset(
    {
        "text",
        "prompt",
        "completion",
        "content",
        "description",
        "comment",
        "body",
        "input",
        "output",
        "question",
        "answer",
        "document",
        "email",
        "name",
        "token",
        "secret",
        "password",
        "api_key",
        "authorization",
    }
)
REDACTED = "[redacted]"
STANDARD_ATTRIBUTES = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}


class RedactingFilter(logging.Filter):
    """Drop the value of any record attribute whose name is a content or secret key."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact in place and keep the record."""
        for key in list(record.__dict__):
            if key not in STANDARD_ATTRIBUTES and key.lower() in CONTENT_KEYS:
                setattr(record, key, REDACTED)
        return True


class JsonFormatter(logging.Formatter):
    """Render a record as one JSON line with its extra attributes."""

    def format(self, record: logging.LogRecord) -> str:
        """Return the JSON line."""
        line: dict[str, object] = {
            "at": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in STANDARD_ATTRIBUTES and not key.startswith("_"):
                line[key] = value
        if record.exc_info:
            line["exception"] = self.formatException(record.exc_info)
        return json.dumps(line, default=str)


def configure_logging(level: str) -> None:
    """Install the JSON handler with the redacting filter on the root logger."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactingFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
