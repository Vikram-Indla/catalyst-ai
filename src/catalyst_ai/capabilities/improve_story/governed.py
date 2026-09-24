"""A governed record's rule: the rewrite keeps the facts, the glossary and Latin digits.

The facts a rewrite may state are the ones its inputs carry: the title, the description, the
criteria, the parent, the comment and the record's context. The member's focus hint and the kind's
focus are not facts: a hint asking for a target does not make one. And the facts of the text it
rewrites all survive: a shorter wording that drops a target has changed it. Digits of any script
are read as Latin before they are compared, and the output is returned in Latin digits.
"""

from catalyst_ai.capabilities.improve_story.comments import TOKEN_MENTION
from catalyst_ai.contract.improve_story import ImproveStoryMode, ImproveStoryRequest, RecordInput
from catalyst_ai.platform.language import latin, stated_facts

FACT_ADDED = "fact_added"
FACT_LOST = "fact_lost"
TERM_LOST = "glossary_term_lost"


def facts(text: str) -> set[str]:
    """Return every number, item key, link and participant token the text states.

    A token's digits name a person, not a quantity, so numbers are read with the tokens set aside.
    """
    plain = latin(text)
    return stated_facts(TOKEN_MENTION.sub(" ", plain)) | set(TOKEN_MENTION.findall(plain))


def known_text(request: ImproveStoryRequest, record: RecordInput) -> str:
    """Return every input a rewrite may take a fact from, joined; a comment's author included."""
    comment = request.comment
    parts = [
        request.title,
        request.description,
        request.acceptance_criteria or "",
        request.parent_title or "",
        request.parent_description or "",
        f"{comment.text}\n@{comment.participant}" if comment else "",
        *(line.text for line in record.context),
    ]
    return "\n".join(parts)


def problems(request: ImproveStoryRequest, output: str) -> list[tuple[str, str]]:
    """Return (code, what) for every fact the output adds or loses and every glossary term lost.

    A reply is not a rewrite of the source, so it owes the source's facts and terms nothing.
    """
    record = request.record
    if record is None:
        return []
    added = sorted(facts(output) - facts(known_text(request, record)))
    found = [(FACT_ADDED, item) for item in added]
    if request.mode is ImproveStoryMode.REPLY:
        return found
    source = request.comment.text if request.comment else request.description
    dropped = sorted(facts(source) - facts(output))
    lost = [term for term in record.glossary if term in source and term not in output]
    return found + [(FACT_LOST, item) for item in dropped] + [(TERM_LOST, term) for term in lost]
