"""The comment modes' markup rule: what a polished comment keeps, what a reply may name.

A polished comment keeps every mention, link and code span of the comment exactly. A reply may
mention only the participants the comment already names (its author and its mentions), and may
link only what the comment, the item's title or its description already link: a reply that names
someone new or points somewhere new has invented a fact.
"""

import re

from catalyst_ai.contract.improve_story import CommentInput, ImproveStoryMode
from catalyst_ai.platform.language import links

TOKEN_MENTION = re.compile(r"(?<![\w.])@p[0-9]{1,4}\b")
CODE_SPAN = re.compile(r"`[^`\n]+`")
DROPPED = "markup_dropped"
INVENTED = "reference_invented"


def mentions(text: str) -> set[str]:
    """Return every participant mention in the text."""
    return set(TOKEN_MENTION.findall(text))


def markup(text: str) -> set[str]:
    """Return every mention, link and code span in the text."""
    return mentions(text) | links(text) | set(CODE_SPAN.findall(text))


def allowed_references(comment: CommentInput, context: str) -> set[str]:
    """Return what a reply may mention or link: the comment's people and the known links."""
    return (
        mentions(comment.text) | {f"@{comment.participant}"} | links(comment.text + "\n" + context)
    )


def markup_problem(
    mode: ImproveStoryMode, comment: CommentInput, context: str, output: str
) -> str | None:
    """Return the detail code when the output breaks the comment modes' markup rule, or None."""
    if mode is ImproveStoryMode.POLISH_COMMENT:
        return DROPPED if not markup(comment.text) <= markup(output) else None
    referenced = mentions(output) | links(output)
    return INVENTED if not referenced <= allowed_references(comment, context) else None
