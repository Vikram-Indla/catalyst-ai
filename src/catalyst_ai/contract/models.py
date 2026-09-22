"""The alias vocabulary: what a capability asks for, and what configuration may select.

An alias is the only model word anything but the register may say. It lives here, in the leaf,
because both the settings (which select one) and the port (which resolves one) need it, and a
vocabulary shared by two layers belongs under both (`ARCH-005 §2`, `ARCH-012 §1`).
"""

from enum import StrEnum


class ModelAlias(StrEnum):
    """What a capability names; the register resolves it to a provider and a model id."""

    TEXT_DEFAULT = "text-default"
    TEXT_FAST = "text-fast"
    TEXT_LONG = "text-long"
    EMBED_DEFAULT = "embed-default"
    GRADER_DEFAULT = "grader-default"


class TextAlias(StrEnum):
    """The aliases an environment may select for text work; the others are not a choice.

    `embed-default` is the index's own model — changing it invalidates every stored vector —
    and `grader-default` is the measuring instrument, never the product (`RULE-008 §3`).
    """

    TEXT_DEFAULT = "text-default"
    TEXT_FAST = "text-fast"
    TEXT_LONG = "text-long"
