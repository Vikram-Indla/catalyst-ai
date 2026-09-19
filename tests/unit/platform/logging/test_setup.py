"""Logging: content keys are redacted; lines are JSON; configure installs one handler."""

import json
import logging
import sys

from catalyst_ai.platform.logging import RedactingFilter, configure_logging
from catalyst_ai.platform.logging.setup import REDACTED, JsonFormatter


def _record(**extra: object) -> logging.LogRecord:
    record = logging.LogRecord("t", logging.INFO, "f", 1, "hello %s", ("world",), None)
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_filter_redacts_content_keys() -> None:
    record = _record(prompt="secret text", organization_id="org")
    assert RedactingFilter().filter(record) is True
    assert record.__dict__["prompt"] == REDACTED
    assert record.__dict__["organization_id"] == "org"
    assert record.name == "t"


def test_formatter_emits_json_with_extras() -> None:
    line = json.loads(JsonFormatter().format(_record(capability="x")))
    assert line["message"] == "hello world"
    assert line["capability"] == "x"
    assert line["level"] == "INFO"


def _boom() -> None:
    raise ValueError("boom")


def test_formatter_includes_exception() -> None:
    try:
        _boom()
    except ValueError:
        record = logging.LogRecord("t", logging.ERROR, "f", 1, "x", None, sys.exc_info())
    assert "boom" in json.loads(JsonFormatter().format(record))["exception"]


def test_configure_installs_one_handler() -> None:
    configure_logging("WARNING")
    root = logging.getLogger()
    assert len(root.handlers) == 1
    assert root.level == logging.WARNING
    assert isinstance(root.handlers[0].formatter, JsonFormatter)
