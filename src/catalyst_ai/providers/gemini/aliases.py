"""Alias resolution: the register's row for the alias the environment selected.

A capability asks for `text-default`; the environment may say that text work here means
`text-fast` (the cheapest row) or `text-long`, per capability or for all of them. Nothing
outside the register names a model: configuration carries the alias, the register carries the
model and its price (`ARCH-005 §2`).
"""

from catalyst_ai.config import Settings
from catalyst_ai.contract.models import ModelAlias, TextAlias
from catalyst_ai.providers.gemini.models import REGISTER, ModelSpec

SELECTABLE = frozenset({ModelAlias.TEXT_DEFAULT})


def selected(settings: Settings, capability: str | None = None) -> TextAlias:
    """Return the alias text work resolves to: the capability's, else the environment's."""
    chosen = settings.capability(capability).model_alias if capability else None
    return chosen or settings.model_text_alias


def resolve(alias: ModelAlias, settings: Settings, capability: str | None = None) -> ModelSpec:
    """Resolve an alias to its concrete model; text work follows the environment's selection."""
    if alias in SELECTABLE:
        return REGISTER[ModelAlias(selected(settings, capability).value)]
    return REGISTER[alias]
