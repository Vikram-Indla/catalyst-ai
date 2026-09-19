"""User text enters a prompt as data: fenced by markers the text itself cannot contain."""

import re

OPEN = "<<<{name}>>>"
CLOSE = "<<<end {name}>>>"
MARKER_PATTERN = re.compile(r"<<<[^<>]{0,64}>>>")
MARKER_REPLACEMENT = "<< >>"


def strip_markers(text: str) -> str:
    """Remove anything that looks like a fence so a user cannot close or open one."""
    return MARKER_PATTERN.sub(MARKER_REPLACEMENT, text)


def fence(name: str, text: str) -> str:
    """Wrap a user segment in its named fence after stripping any marker it carries."""
    body = strip_markers(text)
    return f"{OPEN.format(name=name)}\n{body}\n{CLOSE.format(name=name)}"
