"""Alias resolution: the register row unless configuration overrides it with a register id."""

from catalyst_ai.config import Settings
from catalyst_ai.providers.gemini.models import KNOWN_IDS, REGISTER, ModelSpec
from catalyst_ai.providers.port import ModelAlias


class UnknownModelError(Exception):
    """Configuration named a model id the register does not know."""


def resolve(alias: ModelAlias, settings: Settings) -> ModelSpec:
    """Resolve an alias to its concrete model; `MODEL_TEXT_DEFAULT` may override `text-default`."""
    override = settings.model_text_default if alias is ModelAlias.TEXT_DEFAULT else None
    if override is None:
        return REGISTER[alias]
    spec = KNOWN_IDS.get(override.removeprefix("gemini/"))
    if spec is None:
        message = f"{override!r} is not a register id"
        raise UnknownModelError(message)
    return spec
