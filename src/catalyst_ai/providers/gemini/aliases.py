"""Alias resolution: the register's row for the alias the environment selected.

A capability asks for `text-default`; the environment may say that text work here means
`text-fast` (the cheapest row) or `text-long`, per capability or for all of them. Nothing
outside the register names a model: configuration carries the alias, the register carries the
model and its price (`ARCH-005 §2`). An environment may pin an alias to another of the register's
priced ids of its class (`CATALYST_AI_MODEL_TEXT_DEFAULT` and its siblings); `check_pins` refuses
any other id when the provider is built, before the process serves (`D-064`).
"""

from types import MappingProxyType

from catalyst_ai.config import Settings
from catalyst_ai.config.settings import ENV_PREFIX
from catalyst_ai.contract.models import ModelAlias, TextAlias
from catalyst_ai.providers.gemini.models import (
    EMBEDDING_IDS,
    KNOWN_IDS,
    REGISTER,
    TEXT_IDS,
    ModelSpec,
)

SELECTABLE = frozenset({ModelAlias.TEXT_DEFAULT})
PINS = MappingProxyType(
    {
        ModelAlias.TEXT_DEFAULT: "model_text_default",
        ModelAlias.TEXT_FAST: "model_text_fast",
        ModelAlias.GRADER_DEFAULT: "model_grader_default",
        ModelAlias.EMBED_DEFAULT: "model_embed_default",
    }
)


class UnpricedModelError(ValueError):
    """A pin names an id the register does not price for its alias's class."""


def check_pins(settings: Settings) -> None:
    """Refuse a pinned id the register does not price for that alias, naming the variable."""
    for alias, field in PINS.items():
        value = getattr(settings, field)
        allowed = EMBEDDING_IDS if alias is ModelAlias.EMBED_DEFAULT else TEXT_IDS
        if value is not None and value not in allowed:
            message = (
                f"{ENV_PREFIX}{field.upper()}: {value!r} is not a priced model for {alias.value}; "
                f"the register prices {sorted(allowed)}, and another id takes a register row "
                "with its price and an eval run (ARCH-008 §1)"
            )
            raise UnpricedModelError(message)


def selected(settings: Settings, capability: str | None = None) -> TextAlias:
    """Return the alias text work resolves to: the capability's, else the environment's."""
    chosen = settings.capability(capability).model_alias if capability else None
    return chosen or settings.model_text_alias


def resolve(alias: ModelAlias, settings: Settings, capability: str | None = None) -> ModelSpec:
    """Resolve an alias to its concrete model; text work follows the environment's selection."""
    row = ModelAlias(selected(settings, capability).value) if alias in SELECTABLE else alias
    pinned = getattr(settings, PINS[row]) if row in PINS else None
    return KNOWN_IDS[pinned] if pinned else REGISTER[row]
