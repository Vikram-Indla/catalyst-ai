"""The list contract's rule: only declared parameters, values and sorts, in the list's formats.

The model's answer is normalised before it is judged — digits become Latin whatever script they
were written in, and an enum value takes its declared spelling — and then every parameter must be
declared, every value must be of its parameter's type (a date `YYYY-MM-DD`, a date-time RFC 3339
with its offset, a number, a declared enum value), `q` only where the list has search, and the sort
one the list accepts. What fails is a problem, never a correction: the capability repairs once and
then refuses.
"""

import re
from collections.abc import Callable, Mapping
from datetime import date, datetime
from types import MappingProxyType

from catalyst_ai.contract.interpret_query import Listing, ListingFilter

DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
NUMBER = re.compile(r"^-?\d+(\.\d+)?$")
SEARCH = "q"
NOT_DECLARED = "param_not_declared"
BAD_VALUE = "value_not_allowed"
BAD_SORT = "sort_not_declared"


def listing_lines(listing: Listing) -> str:
    """Write the declaration for the prompt: one line per parameter, then the sorts and search."""
    lines = []
    for spec in listing.filters:
        values = f": {' | '.join(spec.values)}" if spec.values else ""
        lines.append(f"- {spec.param} ({spec.type}){values}")
    lines.append(f"Sorts: {', '.join(listing.sorts)} (the first is the default)")
    lines.append(f"Free-text search (q): {'yes' if listing.q else 'no'}")
    return "\n".join(lines)


def _date(value: str) -> bool:
    if not DATE.match(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _datetime(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False
    return parsed.tzinfo is not None


READERS: Mapping[str, Callable[[str], bool]] = MappingProxyType(
    {
        "date": _date,
        "datetime": _datetime,
        "number": lambda value: NUMBER.match(value) is not None,
        "text": lambda value: bool(value.strip()),
    }
)


def _typed(value: str, spec: ListingFilter) -> str | None:
    """Return the value in the parameter's format, or None when it is not of its type."""
    if spec.type == "enum":
        return {v.casefold(): v for v in spec.values or []}.get(value.casefold())
    return value if READERS[spec.type](value) else None


def normalise(
    parameters: dict[str, str], sort: str | None, listing: Listing
) -> tuple[dict[str, str], str | None, list[str]]:
    """Return the parameters in the list's formats, the sort, and every problem found."""
    declared = {spec.param: spec for spec in listing.filters}
    kept: dict[str, str] = {}
    problems: list[str] = []
    for name, raw in parameters.items():
        value = raw.translate(DIGITS).strip()
        if name == SEARCH and listing.q and value:
            kept[name] = value
            continue
        spec = declared.get(name)
        if spec is None:
            problems.append(f"{NOT_DECLARED}: {name}")
            continue
        typed = _typed(value, spec)
        if typed is None:
            problems.append(f"{BAD_VALUE}: {name}")
        else:
            kept[name] = typed
    if sort is not None and sort not in listing.sorts:
        problems.append(f"{BAD_SORT}: {sort}")
    return kept, sort, problems
