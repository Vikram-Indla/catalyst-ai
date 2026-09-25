"""A variable with the service's prefix that no setting declares refuses the start.

The settings would otherwise ignore it and keep the default: a misspelt switch
(`CATALYST_AI_CAPABILITIES_ENABLD=false`) would leave every capability on and say nothing. So at
start every environment variable carrying the prefix must name a setting — a top-level one, or a
nested one spelt with the nesting's two underscores (`CAPABILITY_SUMMARIZE__ENABLED`) — or be one
of the tooling's variables below, which the service never reads. The refusal names the variables,
never their values. There is no flag that skips it.
"""

from collections.abc import Mapping
from types import MappingProxyType

from pydantic import BaseModel

TOOLING = MappingProxyType(
    {
        "CATALYST_AI_RECORD_PROVIDER_TOKEN": "read by `make record LIVE=1`, never by the service",
        "CATALYST_AI_EVAL_DATABASE_URL": "read by the storage tests and the retrieval eval",
        "CATALYST_AI_CI_APT_MIRROR": "read by `make ci-image` (its apt mirror), not the service",
    }
)


class UnknownSettingsError(ValueError):
    """Variables with the prefix that no setting declares, by name only."""


def declared(settings: type[BaseModel], prefix: str, delimiter: str) -> frozenset[str]:
    """Return every variable name the settings read: each field, each nested field."""
    names: set[str] = set()
    for field, info in settings.model_fields.items():
        top = f"{prefix}{field}".upper()
        names.add(top)
        nested = info.annotation
        if isinstance(nested, type) and issubclass(nested, BaseModel):
            names |= {f"{top}{delimiter}{sub}".upper() for sub in nested.model_fields}
    return frozenset(names)


def unknown(environ: Mapping[str, str | None], known: frozenset[str], prefix: str) -> list[str]:
    """Return the prefixed variables that are neither settings nor the tooling's, sorted."""
    upper = prefix.upper()
    return sorted(
        name.upper()
        for name in environ
        if name.upper().startswith(upper) and name.upper() not in known | TOOLING.keys()
    )


def refuse_unknown(
    environ: Mapping[str, str | None], settings: type[BaseModel], prefix: str, delimiter: str
) -> None:
    """Refuse the start when a prefixed variable names no setting; name them, never the values."""
    found = unknown(environ, declared(settings, prefix, delimiter), prefix)
    if found:
        message = (
            f"unknown settings: {', '.join(found)}; no setting has these names "
            f"(a nested one is spelt with {delimiter!r}: CAPABILITY_<NAME>{delimiter}ENABLED)"
        )
        raise UnknownSettingsError(message)
