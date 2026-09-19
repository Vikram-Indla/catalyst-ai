"""Lexical similarity: normalisation, Jaccard/containment, nearest above a threshold."""

from catalyst_ai.platform.similarity import nearest, normalise, similarity


def test_normalise_folds_case_accents_and_stop_words() -> None:
    assert normalise("The Élan of a Board") == {"elan", "boar"}
    assert normalise("a to the") == frozenset()


def test_similarity_bounds() -> None:
    assert similarity("export board to csv", "export the board as CSV") >= 0.6
    assert similarity("export board to csv", "rotate signing keys") == 0.0
    assert similarity("", "anything") == 0.0
    assert similarity("invite members", "invite members by email link with an expiry") >= 0.6


def test_nearest_picks_the_best_above_the_threshold() -> None:
    siblings = ["Rotate signing keys", "Export the board to CSV", "Invite members"]
    assert nearest("export board csv", siblings, 0.6) == "Export the board to CSV"
    assert nearest("delete the organisation", siblings, 0.6) is None
