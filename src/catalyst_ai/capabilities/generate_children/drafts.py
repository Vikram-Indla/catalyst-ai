"""Draft-only children: wording, and no number, date or link the parent does not already state.

A target, a weight or a measure belongs to the member who adopts the draft. A candidate that states
one the parent's text and the sources lack is withheld and counted; the rest lose their criteria
and come back in Latin digits.
"""

from catalyst_ai.capabilities.generate_children.schema import ModelCandidate
from catalyst_ai.contract.generate_children import GenerateChildrenRequest
from catalyst_ai.platform.language import latin, stated_facts


def known_facts(request: GenerateChildrenRequest) -> set[str]:
    """Return every fact the parent's title, its description and the sources state."""
    parts = [request.parent_title, request.parent_description, *request.source_texts]
    return stated_facts("\n".join(parts))


def as_drafts(
    candidates: list[ModelCandidate], request: GenerateChildrenRequest
) -> tuple[list[ModelCandidate], int]:
    """Return the candidates as drafts, and how many were withheld for stating a new fact."""
    if not request.draft_only:
        return candidates, 0
    known = known_facts(request)
    kept: list[ModelCandidate] = []
    for candidate in candidates:
        title, description = latin(candidate.title), latin(candidate.description)
        if stated_facts(title + "\n" + description) <= known:
            update = {"title": title, "description": description, "acceptance_criteria": []}
            kept.append(candidate.model_copy(update=update))
    return kept, len(candidates) - len(kept)
